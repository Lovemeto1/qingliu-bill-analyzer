from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .analytics import (
    detect_recurring,
    recent_period_comparison,
    small_frequent_summary,
    spending_by,
    summary_metrics,
)


@dataclass(frozen=True)
class Advice:
    priority: str
    title: str
    evidence: str
    action: str
    confidence: str


def generate_advice(data: pd.DataFrame) -> list[Advice]:
    metrics = summary_metrics(data)
    advice: list[Advice] = []

    if metrics.active_days < 30:
        advice.append(
            Advice(
                priority="提示",
                title="数据覆盖时间较短",
                evidence=f"当前筛选范围覆盖 {metrics.active_days} 天。",
                action="建议上传至少连续三个月的账单，再判断长期消费趋势。",
                confidence="高",
            )
        )

    comparison = recent_period_comparison(data)
    if comparison and pd.notna(comparison["change"]) and comparison["change"] > 0.2:
        advice.append(
            Advice(
                priority="优先",
                title="最近 30 天消费明显上升",
                evidence=(
                    f"最近 30 天消费 ¥{comparison['recent']:,.0f}，较此前 30 天"
                    f"增加 {comparison['change']:.0%}。"
                ),
                action="查看支出排行榜和分类结构，优先核对增长金额最大的类别。",
                confidence="高",
            )
        )
    elif comparison and pd.notna(comparison["change"]) and comparison["change"] < -0.2:
        advice.append(
            Advice(
                priority="观察",
                title="最近 30 天消费有所下降",
                evidence=(
                    f"最近 30 天消费 ¥{comparison['recent']:,.0f}，较此前 30 天"
                    f"下降 {abs(comparison['change']):.0%}。"
                ),
                action="可以检查下降来自临时因素还是可持续的消费调整。",
                confidence="高",
            )
        )

    categories = spending_by(data, "category")
    if not categories.empty:
        top = categories.iloc[0]
        if float(top["占比"]) >= 0.35 and len(categories) > 1:
            advice.append(
                Advice(
                    priority="优先",
                    title=f"消费较集中于“{top['category']}”",
                    evidence=f"该类别支出 ¥{top['金额']:,.0f}，占消费支出的 {top['占比']:.0%}。",
                    action="先查看这个类别中的前几名商户，通常比平均削减所有类别更容易执行。",
                    confidence="高",
                )
            )

    counterparties = spending_by(data, "counterparty", limit=10)
    if not counterparties.empty:
        top = counterparties.iloc[0]
        if float(top["占比"]) >= 0.25:
            advice.append(
                Advice(
                    priority="观察",
                    title="单一交易对方占比较高",
                    evidence=f"“{top['counterparty']}”累计支出 ¥{top['金额']:,.0f}，占比 {top['占比']:.0%}。",
                    action="确认其中是否包含房租、学费等合理大额固定支出；若不是，可重点复核。",
                    confidence="中",
                )
            )

    small = small_frequent_summary(data)
    if small["count"] >= 10 and small["share"] >= 0.1:
        advice.append(
            Advice(
                priority="观察",
                title="小额高频消费累积值得关注",
                evidence=(
                    f"不高于 ¥{small['threshold']:,.0f} 的交易共 {small['count']} 笔，"
                    f"累计 ¥{small['amount']:,.0f}，占消费 {small['share']:.0%}。"
                ),
                action="可按商户排序，识别最容易合并、减少或改用月度预算管理的项目。",
                confidence="中",
            )
        )

    recurring = detect_recurring(data)
    if not recurring.empty:
        monthly = float(recurring["月均金额"].head(5).sum())
        advice.append(
            Advice(
                priority="观察",
                title="检测到疑似周期性支出",
                evidence=f"前 {min(len(recurring), 5)} 项疑似周期支出的月均合计约 ¥{monthly:,.0f}。",
                action="逐项确认是否为仍在使用的会员、订阅或固定服务；算法仅作提示，不代表一定是订阅。",
                confidence="中",
            )
        )

    if metrics.cash_in > 0 and metrics.cash_out > metrics.cash_in * 1.05:
        advice.append(
            Advice(
                priority="优先",
                title="账单范围内资金流出高于流入",
                evidence=(
                    f"资金流入 ¥{metrics.cash_in:,.0f}，全部资金流出 ¥{metrics.cash_out:,.0f}，"
                    f"差额为 ¥{metrics.cash_out - metrics.cash_in:,.0f}。"
                ),
                action="先确认工资是否完整包含在所上传账单中；数据完整时，再考虑压缩可调整支出。",
                confidence="中",
            )
        )
    elif metrics.cash_in == 0:
        advice.append(
            Advice(
                priority="提示",
                title="暂不评估储蓄率",
                evidence="当前筛选数据没有识别到有效资金流入。",
                action="如果主要收入进入银行卡或其他账户，可结合相应流水后再判断收支平衡。",
                confidence="高",
            )
        )

    expense_rows = data.loc[data["included"] & (data["amount"] > 0)]
    refund_share = metrics.refunds / float(expense_rows["amount"].sum()) if not expense_rows.empty else 0.0
    if refund_share >= 0.1:
        advice.append(
            Advice(
                priority="观察",
                title="退款金额占比较高",
                evidence=f"退款合计 ¥{metrics.refunds:,.0f}，约占相关交易金额的 {refund_share:.0%}。",
                action="可检查退款是否集中在少数购物平台或品类，减少不必要的反复购买。",
                confidence="中",
            )
        )

    if not advice:
        advice.append(
            Advice(
                priority="提示",
                title="当前没有发现明显异常",
                evidence="消费趋势、集中度和资金流入流出没有触发预设提醒阈值。",
                action="继续按月观察分类占比和周期性支出变化。",
                confidence="中",
            )
        )
    priority_order = {"优先": 0, "观察": 1, "提示": 2}
    return sorted(advice, key=lambda item: priority_order[item.priority])
