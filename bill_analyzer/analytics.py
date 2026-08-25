from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SummaryMetrics:
    consumption: float
    cash_in: float
    cash_out: float
    net_cashflow: float
    refunds: float
    transaction_count: int
    active_days: int
    daily_consumption: float
    median_consumption: float


def apply_category_overrides(data: pd.DataFrame, overrides: dict[str, str]) -> pd.DataFrame:
    result = data.copy()
    if overrides:
        mapped = result["counterparty"].map(overrides)
        result.loc[mapped.notna(), "category"] = mapped[mapped.notna()]
    return result


def filter_transactions(
    data: pd.DataFrame,
    start_date,
    end_date,
    categories: list[str] | None = None,
    payment_methods: list[str] | None = None,
) -> pd.DataFrame:
    if data.empty:
        return data.copy()
    dates = data["occurred_at"].dt.date
    mask = dates.between(start_date, end_date)
    if categories:
        mask &= data["category"].isin(categories)
    if payment_methods:
        mask &= data["payment_method"].isin(payment_methods)
    return data.loc[mask].copy()


def summary_metrics(data: pd.DataFrame) -> SummaryMetrics:
    valid = data.loc[data["included"]].copy()
    consumption_values = valid.loc[valid["consumption_amount"] > 0, "consumption_amount"]
    dates = valid["occurred_at"].dropna()
    active_days = 0 if dates.empty else max((dates.max().date() - dates.min().date()).days + 1, 1)
    consumption = float(valid["consumption_amount"].sum())
    cash_in = float(valid["cash_in_amount"].sum())
    cash_out = float(valid["cash_out_amount"].sum())
    return SummaryMetrics(
        consumption=consumption,
        cash_in=cash_in,
        cash_out=cash_out,
        net_cashflow=cash_in - cash_out,
        refunds=float(valid["refund_amount"].sum()),
        transaction_count=int(len(valid)),
        active_days=active_days,
        daily_consumption=consumption / active_days if active_days else 0.0,
        median_consumption=float(consumption_values.median()) if not consumption_values.empty else 0.0,
    )


def monthly_cashflow(data: pd.DataFrame) -> pd.DataFrame:
    valid = data.loc[data["included"] & data["occurred_at"].notna()].copy()
    if valid.empty:
        return pd.DataFrame(columns=["month", "资金流入", "消费支出", "全部流出", "净现金流"])
    valid["month"] = valid["occurred_at"].dt.to_period("M").dt.to_timestamp()
    grouped = (
        valid.groupby("month", as_index=False)[
            ["cash_in_amount", "consumption_amount", "cash_out_amount"]
        ]
        .sum()
        .rename(
            columns={
                "cash_in_amount": "资金流入",
                "consumption_amount": "消费支出",
                "cash_out_amount": "全部流出",
            }
        )
    )
    grouped["净现金流"] = grouped["资金流入"] - grouped["全部流出"]
    return grouped


def spending_by(data: pd.DataFrame, dimension: str, limit: int | None = None) -> pd.DataFrame:
    spend = data.loc[data["included"] & (data["consumption_amount"] > 0)].copy()
    if spend.empty:
        return pd.DataFrame(columns=[dimension, "金额", "笔数", "占比"])
    spend[dimension] = spend[dimension].replace("", "未标注").fillna("未标注")
    grouped = (
        spend.groupby(dimension, as_index=False)
        .agg(金额=("consumption_amount", "sum"), 笔数=("transaction_id", "count"))
        .sort_values("金额", ascending=False)
    )
    total = grouped["金额"].sum()
    grouped["占比"] = grouped["金额"] / total if total else 0.0
    if limit:
        grouped = grouped.head(limit)
    return grouped.reset_index(drop=True)


def inflow_by(data: pd.DataFrame, dimension: str, limit: int | None = None) -> pd.DataFrame:
    income = data.loc[data["included"] & (data["cash_in_amount"] > 0)].copy()
    if income.empty:
        return pd.DataFrame(columns=[dimension, "金额", "笔数", "占比"])
    income[dimension] = income[dimension].replace("", "未标注").fillna("未标注")
    grouped = (
        income.groupby(dimension, as_index=False)
        .agg(金额=("cash_in_amount", "sum"), 笔数=("transaction_id", "count"))
        .sort_values("金额", ascending=False)
    )
    total = grouped["金额"].sum()
    grouped["占比"] = grouped["金额"] / total if total else 0.0
    if limit:
        grouped = grouped.head(limit)
    return grouped.reset_index(drop=True)


def weekday_spending(data: pd.DataFrame) -> pd.DataFrame:
    spend = data.loc[data["included"] & (data["consumption_amount"] > 0)].copy()
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    if spend.empty:
        return pd.DataFrame({"星期": weekdays, "金额": [0.0] * 7, "笔数": [0] * 7})
    spend["weekday_num"] = spend["occurred_at"].dt.weekday
    grouped = spend.groupby("weekday_num").agg(金额=("consumption_amount", "sum"), 笔数=("transaction_id", "count"))
    grouped = grouped.reindex(range(7), fill_value=0).reset_index()
    grouped["星期"] = grouped["weekday_num"].map(dict(enumerate(weekdays)))
    return grouped[["星期", "金额", "笔数"]]


def hourly_heatmap(data: pd.DataFrame) -> pd.DataFrame:
    spend = data.loc[data["included"] & (data["consumption_amount"] > 0)].copy()
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    if spend.empty:
        return pd.DataFrame(0.0, index=weekdays, columns=list(range(24)))
    spend["weekday_num"] = spend["occurred_at"].dt.weekday
    spend["hour"] = spend["occurred_at"].dt.hour
    pivot = spend.pivot_table(
        index="weekday_num", columns="hour", values="consumption_amount", aggfunc="sum", fill_value=0
    )
    pivot = pivot.reindex(index=range(7), columns=range(24), fill_value=0.0)
    pivot.index = weekdays
    return pivot


def detect_recurring(data: pd.DataFrame) -> pd.DataFrame:
    spend = data.loc[
        data["included"]
        & (data["consumption_amount"] > 0)
        & data["counterparty"].fillna("").ne("")
    ].copy()
    columns = ["交易对方", "覆盖月份", "总笔数", "月均金额", "金额稳定度"]
    if spend.empty:
        return pd.DataFrame(columns=columns)
    spend["month"] = spend["occurred_at"].dt.to_period("M")
    monthly = spend.groupby(["counterparty", "month"], as_index=False).agg(
        month_amount=("consumption_amount", "sum"), transactions=("transaction_id", "count")
    )
    rows = []
    for counterparty, group in monthly.groupby("counterparty"):
        months = len(group)
        if months < 2:
            continue
        mean = float(group["month_amount"].mean())
        if mean <= 0:
            continue
        cv = float(group["month_amount"].std(ddof=0) / mean) if months > 1 else 1.0
        total_transactions = int(group["transactions"].sum())
        if cv <= 0.25 and total_transactions >= months:
            rows.append(
                {
                    "交易对方": counterparty,
                    "覆盖月份": months,
                    "总笔数": total_transactions,
                    "月均金额": mean,
                    "金额稳定度": max(0.0, 1.0 - cv),
                }
            )
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows).sort_values(["月均金额", "覆盖月份"], ascending=False).reset_index(drop=True)


def high_value_transactions(data: pd.DataFrame, limit: int = 15) -> pd.DataFrame:
    spend = data.loc[data["included"] & (data["consumption_amount"] > 0)].copy()
    if spend.empty:
        return spend
    threshold = max(float(spend["consumption_amount"].quantile(0.9)), 200.0)
    return spend.loc[spend["consumption_amount"] >= threshold].nlargest(
        limit, "consumption_amount"
    )


def small_frequent_summary(data: pd.DataFrame) -> dict[str, float | int]:
    spend = data.loc[data["included"] & (data["consumption_amount"] > 0)].copy()
    if spend.empty:
        return {"threshold": 0.0, "amount": 0.0, "count": 0, "share": 0.0}
    threshold = min(max(float(spend["consumption_amount"].quantile(0.25)), 10.0), 50.0)
    small = spend.loc[spend["consumption_amount"] <= threshold]
    total = float(spend["consumption_amount"].sum())
    amount = float(small["consumption_amount"].sum())
    return {
        "threshold": threshold,
        "amount": amount,
        "count": int(len(small)),
        "share": amount / total if total else 0.0,
    }


def recent_period_comparison(data: pd.DataFrame, days: int = 30) -> dict[str, float] | None:
    spend = data.loc[data["included"] & (data["consumption_amount"] > 0)].copy()
    if spend.empty:
        return None
    end = spend["occurred_at"].max().normalize()
    recent_start = end - pd.Timedelta(days=days - 1)
    previous_start = recent_start - pd.Timedelta(days=days)
    recent = float(spend.loc[spend["occurred_at"].between(recent_start, end + pd.Timedelta(days=1)), "consumption_amount"].sum())
    previous = float(
        spend.loc[
            spend["occurred_at"].between(previous_start, recent_start, inclusive="left"),
            "consumption_amount",
        ].sum()
    )
    return {
        "recent": recent,
        "previous": previous,
        "change": (recent - previous) / previous if previous else np.nan,
    }
