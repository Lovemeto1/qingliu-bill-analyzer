from __future__ import annotations

import pandas as pd

from bill_analyzer.advice import generate_advice
from bill_analyzer.analytics import monthly_cashflow, spending_by, summary_metrics


def sample_data() -> pd.DataFrame:
    rows = []
    for index in range(6):
        rows.append(
            {
                "source": "微信",
                "transaction_id": f"t{index}",
                "occurred_at": pd.Timestamp("2026-01-01") + pd.Timedelta(days=index * 12),
                "included": True,
                "consumption_amount": 100.0 if index < 5 else 500.0,
                "cash_in_amount": 0.0,
                "cash_out_amount": 100.0 if index < 5 else 500.0,
                "refund_amount": 0.0,
                "amount": 100.0 if index < 5 else 500.0,
                "category": "餐饮" if index < 5 else "购物",
                "counterparty": "固定商户" if index < 5 else "商城",
                "payment_method": "零钱",
                "item_description": "测试商品",
            }
        )
    return pd.DataFrame(rows)


def test_summary_and_ranking_reconcile():
    data = sample_data()
    metrics = summary_metrics(data)
    assert metrics.consumption == 1000
    assert metrics.cash_out == 1000
    ranking = spending_by(data, "category")
    assert ranking["金额"].sum() == metrics.consumption
    assert set(ranking["category"]) == {"餐饮", "购物"}


def test_monthly_cashflow_has_net_column():
    monthly = monthly_cashflow(sample_data())
    assert "净现金流" in monthly.columns
    assert monthly["消费支出"].sum() == 1000


def test_advice_is_explainable():
    advice = generate_advice(sample_data())
    assert advice
    assert all(item.evidence and item.action and item.confidence for item in advice)
