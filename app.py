from __future__ import annotations

import hashlib
import html
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from bill_analyzer.advice import generate_advice
from bill_analyzer.analytics import (
    apply_category_overrides,
    detect_recurring,
    filter_transactions,
    high_value_transactions,
    hourly_heatmap,
    inflow_by,
    monthly_cashflow,
    spending_by,
    summary_metrics,
    weekday_spending,
)
from bill_analyzer.parsers import BillParseError, parse_bill


st.set_page_config(
    page_title="清流账单分析助手",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)


PRIMARY = "#0f766e"
SECONDARY = "#d97706"
BLUE = "#2563eb"
MUTED = "#64748b"
CATEGORIES = [
    "餐饮",
    "交通出行",
    "购物",
    "居住",
    "通讯网络",
    "医疗健康",
    "教育",
    "休闲娱乐",
    "生活服务",
    "人情往来",
    "金融保险",
    "其他消费",
    "债务与还款",
    "转账与资金往来",
    "资金流入",
    "退款",
]


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.7rem; padding-bottom: 3rem; max-width: 1440px;}
        [data-testid="stMetric"] {
            background: color-mix(in srgb, var(--background-color) 94%, #0f766e 6%);
            border: 1px solid color-mix(in srgb, var(--text-color) 14%, transparent);
            border-radius: 14px;
            padding: 1rem 1.05rem;
        }
        [data-testid="stMetricValue"] {font-weight: 650;}
        .hero {
            padding: 1.2rem 0 1.4rem 0;
            border-bottom: 1px solid color-mix(in srgb, var(--text-color) 12%, transparent);
            margin-bottom: 1.2rem;
        }
        .hero h1 {margin: 0 0 .35rem 0; letter-spacing: -.02em;}
        .hero p {margin: 0; opacity: .72; max-width: 820px;}
        .privacy-note {
            padding: .8rem 1rem;
            border-radius: 12px;
            background: color-mix(in srgb, var(--background-color) 93%, #0f766e 7%);
            border-left: 4px solid #0f766e;
            margin: .7rem 0 1rem 0;
        }
        .advice-card {
            padding: 1rem 1.1rem;
            margin: .65rem 0;
            border: 1px solid color-mix(in srgb, var(--text-color) 14%, transparent);
            border-radius: 14px;
        }
        .advice-card h4 {margin: .1rem 0 .5rem 0;}
        .advice-card p {margin: .35rem 0;}
        .priority-high {border-left: 5px solid #dc2626;}
        .priority-watch {border-left: 5px solid #d97706;}
        .priority-note {border-left: 5px solid #0f766e;}
        div[data-testid="stDataFrame"] {border-radius: 12px; overflow: hidden;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def money(value: float) -> str:
    return f"¥{value:,.2f}"


def style_figure(fig: go.Figure, height: int = 390) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=12, r=12, t=52, b=15),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Microsoft YaHei, PingFang SC, sans-serif"),
        hoverlabel=dict(font_size=13),
        legend_title_text="",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,.15)")
    return fig


def render_empty_state() -> None:
    st.markdown(
        """
        <div class="hero">
          <h1>清流 · 本地账单分析助手</h1>
          <p>把微信或支付宝导出的原始账单转化为清晰的消费结构、现金流趋势和可执行建议。</p>
        </div>
        <div class="privacy-note"><b>隐私承诺：</b>账单只在这台电脑的本地进程中解析，不调用外部 API，不上传到第三方服务。</div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(3)
    with cols[0]:
        st.subheader("① 上传原始账单")
        st.write("支持微信 XLSX、支付宝 CSV，以及只包含一份账单的 ZIP。")
    with cols[1]:
        st.subheader("② 核对统计口径")
        st.write("自动处理退款、失败交易、转账和还款，并允许修正消费分类。")
    with cols[2]:
        st.subheader("③ 查看本地报告")
        st.write("包含排行榜、消费与收入结构、趋势、习惯分析和规则建议。")
    st.info("请在左侧选择平台并上传账单。推荐直接上传微信或支付宝官方导出的原始文件。")


def render_quality(result) -> None:
    with st.expander("数据质量与统计口径", expanded=bool(result.warnings)):
        cols = st.columns(5)
        cols[0].metric("识别平台", result.platform)
        cols[1].metric("原始记录", f"{result.raw_rows:,}")
        cols[2].metric("去重记录", f"{result.duplicate_rows:,}")
        cols[3].metric("排除记录", f"{result.excluded_rows:,}")
        cols[4].metric("有效记录", f"{int(result.data['included'].sum()):,}")
        st.caption(
            "消费支出仅统计有效的商品与服务净支出；失败或关闭交易被排除；退款从原支出中扣减；"
            "转账、红包、理财划转和信用卡还款单独归类。"
        )
        for warning in result.warnings:
            st.warning(warning)


def render_category_editor(data: pd.DataFrame, file_key: str) -> dict[str, str]:
    spend = data.loc[data["consumption_amount"] > 0]
    if spend.empty:
        return {}
    mapping = (
        spend.groupby(["counterparty", "category"], as_index=False)["consumption_amount"]
        .sum()
        .sort_values("consumption_amount", ascending=False)
        .drop_duplicates("counterparty")
        .head(120)
        .rename(columns={"counterparty": "交易对方", "category": "消费分类", "consumption_amount": "累计金额"})
    )
    edited = st.data_editor(
        mapping,
        key=f"category_editor_{file_key}",
        hide_index=True,
        use_container_width=True,
        height=260,
        disabled=["交易对方", "累计金额"],
        column_config={
            "消费分类": st.column_config.SelectboxColumn("消费分类", options=CATEGORIES, required=True),
            "累计金额": st.column_config.NumberColumn("累计金额", format="¥ %.2f"),
        },
    )
    return dict(zip(edited["交易对方"], edited["消费分类"]))


def render_overview(data: pd.DataFrame) -> None:
    metrics = summary_metrics(data)
    cols = st.columns(5)
    cols[0].metric("消费支出", money(metrics.consumption), help="商品与服务净支出，不含转账和还款")
    cols[1].metric("资金流入", money(metrics.cash_in), help="账单内识别到的资金流入，不等同于税务意义的收入")
    cols[2].metric("全部资金流出", money(metrics.cash_out), help="包括消费、转账与还款")
    cols[3].metric("净现金流", money(metrics.net_cashflow))
    cols[4].metric("日均消费", money(metrics.daily_consumption))

    monthly = monthly_cashflow(data)
    left, right = st.columns([1.55, 1])
    with left:
        fig = go.Figure()
        fig.add_bar(x=monthly["month"], y=monthly["消费支出"], name="消费支出", marker_color=SECONDARY)
        fig.add_bar(x=monthly["month"], y=monthly["资金流入"], name="资金流入", marker_color=PRIMARY)
        fig.add_scatter(
            x=monthly["month"],
            y=monthly["净现金流"],
            name="净现金流",
            mode="lines+markers",
            line=dict(color=BLUE, width=3),
        )
        fig.update_layout(title="月度现金流", barmode="group", hovermode="x unified")
        fig.update_yaxes(title="金额（元）")
        st.plotly_chart(style_figure(fig), use_container_width=True, config={"displaylogo": False})
    with right:
        categories = spending_by(data, "category")
        if categories.empty:
            st.info("当前筛选范围没有可展示的消费支出。")
        else:
            fig = px.pie(
                categories,
                names="category",
                values="金额",
                hole=0.55,
                title="消费结构",
                color_discrete_sequence=px.colors.qualitative.Safe,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label", hovertemplate="%{label}<br>¥%{value:,.2f}<extra></extra>")
            st.plotly_chart(style_figure(fig), use_container_width=True, config={"displaylogo": False})

    cols = st.columns(4)
    cols[0].metric("有效交易", f"{metrics.transaction_count:,} 笔")
    cols[1].metric("单笔消费中位数", money(metrics.median_consumption))
    cols[2].metric("退款金额", money(metrics.refunds))
    cols[3].metric("数据覆盖", f"{metrics.active_days:,} 天")


def render_expenses(data: pd.DataFrame) -> None:
    top_merchants = spending_by(data, "counterparty", 10).sort_values("金额")
    categories = spending_by(data, "category")
    left, right = st.columns(2)
    with left:
        if top_merchants.empty:
            st.info("当前筛选范围没有消费支出。")
        else:
            fig = px.bar(
                top_merchants,
                x="金额",
                y="counterparty",
                orientation="h",
                text_auto=".2s",
                title="交易对方支出排行榜前十",
                color_discrete_sequence=[PRIMARY],
            )
            fig.update_yaxes(title="")
            fig.update_xaxes(title="金额（元）")
            fig.update_traces(hovertemplate="%{y}<br>¥%{x:,.2f}<extra></extra>")
            st.plotly_chart(style_figure(fig, 430), use_container_width=True, config={"displaylogo": False})
    with right:
        if not categories.empty:
            fig = px.bar(
                categories.sort_values("金额"),
                x="金额",
                y="category",
                orientation="h",
                title="消费分类金额",
                color="占比",
                color_continuous_scale="Tealgrn",
            )
            fig.update_yaxes(title="")
            fig.update_xaxes(title="金额（元）")
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(style_figure(fig, 430), use_container_width=True, config={"displaylogo": False})

    by_payment = spending_by(data, "payment_method")
    by_item = spending_by(data, "item_description", 10)
    left, right = st.columns(2)
    with left:
        st.subheader("支付方式结构")
        st.dataframe(
            by_payment.rename(columns={"payment_method": "支付方式"}),
            use_container_width=True,
            hide_index=True,
            column_config={"金额": st.column_config.NumberColumn(format="¥ %.2f"), "占比": st.column_config.ProgressColumn(format="%.1%%", min_value=0, max_value=1)},
        )
    with right:
        st.subheader("商品说明支出前十")
        st.dataframe(
            by_item.rename(columns={"item_description": "商品说明"}),
            use_container_width=True,
            hide_index=True,
            column_config={"金额": st.column_config.NumberColumn(format="¥ %.2f"), "占比": st.column_config.ProgressColumn(format="%.1%%", min_value=0, max_value=1)},
        )


def render_income(data: pd.DataFrame) -> None:
    metrics = summary_metrics(data)
    if metrics.cash_in <= 0:
        st.info("当前筛选范围没有识别到资金流入，因此不计算储蓄率或收入稳定性。")
        return
    cols = st.columns(3)
    cols[0].metric("资金流入", money(metrics.cash_in))
    cols[1].metric("资金流出", money(metrics.cash_out))
    cols[2].metric("账单净现金流", money(metrics.net_cashflow))
    by_source = inflow_by(data, "counterparty", 10)
    by_type = inflow_by(data, "transaction_type")
    left, right = st.columns(2)
    with left:
        fig = px.bar(
            by_source.sort_values("金额"),
            x="金额",
            y="counterparty",
            orientation="h",
            title="资金流入来源前十",
            color_discrete_sequence=[PRIMARY],
        )
        fig.update_yaxes(title="")
        fig.update_xaxes(title="金额（元）")
        st.plotly_chart(style_figure(fig), use_container_width=True, config={"displaylogo": False})
    with right:
        fig = px.pie(
            by_type,
            names="transaction_type",
            values="金额",
            hole=0.55,
            title="资金流入类型",
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        st.plotly_chart(style_figure(fig), use_container_width=True, config={"displaylogo": False})
    st.caption("资金流入可能包含他人转账、收款或内部账户划转，不应自动等同于工资或可支配收入。")


def render_habits(data: pd.DataFrame) -> None:
    weekdays = weekday_spending(data)
    heatmap = hourly_heatmap(data)
    left, right = st.columns([1, 1.4])
    with left:
        fig = px.bar(
            weekdays,
            x="星期",
            y="金额",
            title="星期消费分布",
            color_discrete_sequence=[SECONDARY],
        )
        fig.update_yaxes(title="金额（元）")
        st.plotly_chart(style_figure(fig), use_container_width=True, config={"displaylogo": False})
    with right:
        fig = go.Figure(
            data=go.Heatmap(
                z=heatmap.values,
                x=[f"{hour:02d}:00" for hour in heatmap.columns],
                y=heatmap.index,
                colorscale="Tealgrn",
                hovertemplate="%{y} %{x}<br>消费 ¥%{z:,.2f}<extra></extra>",
                colorbar=dict(title="元"),
            )
        )
        fig.update_layout(title="星期 × 时段消费热力图")
        st.plotly_chart(style_figure(fig), use_container_width=True, config={"displaylogo": False})

    recurring = detect_recurring(data)
    large = high_value_transactions(data)
    left, right = st.columns(2)
    with left:
        st.subheader("疑似周期性支出")
        st.caption("同一交易对方跨月至少出现两个月，且月度金额波动较小；结果仅作复核线索。")
        st.dataframe(
            recurring.head(20),
            use_container_width=True,
            hide_index=True,
            column_config={
                "月均金额": st.column_config.NumberColumn(format="¥ %.2f"),
                "金额稳定度": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=1),
            },
        )
    with right:
        st.subheader("大额消费记录")
        display = large[["occurred_at", "counterparty", "category", "consumption_amount"]].copy()
        display.columns = ["交易时间", "交易对方", "分类", "消费金额"]
        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            column_config={"消费金额": st.column_config.NumberColumn(format="¥ %.2f")},
        )


def render_advice(data: pd.DataFrame) -> None:
    st.caption("以下建议由本地规则根据当前筛选数据生成，不调用 AI，也不构成投资或信贷建议。")
    css_class = {"优先": "priority-high", "观察": "priority-watch", "提示": "priority-note"}
    for item in generate_advice(data):
        safe_priority = html.escape(item.priority)
        safe_title = html.escape(item.title)
        safe_evidence = html.escape(item.evidence)
        safe_action = html.escape(item.action)
        safe_confidence = html.escape(item.confidence)
        st.markdown(
            f"""
            <div class="advice-card {css_class[item.priority]}">
              <h4>{safe_priority} · {safe_title}</h4>
              <p><b>数据依据：</b>{safe_evidence}</p>
              <p><b>建议行动：</b>{safe_action}</p>
              <p style="opacity:.65"><small>规则可信度：{safe_confidence}</small></p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_details(data: pd.DataFrame) -> None:
    query = st.text_input("搜索交易对方、商品说明或备注", placeholder="例如：咖啡、地铁、某个商户")
    details = data.copy()
    if query:
        mask = (
            details["counterparty"].str.contains(query, case=False, na=False, regex=False)
            | details["item_description"].str.contains(query, case=False, na=False, regex=False)
            | details["note"].str.contains(query, case=False, na=False, regex=False)
        )
        details = details.loc[mask]
    display = details[
        [
            "occurred_at",
            "source",
            "flow_type",
            "counterparty",
            "item_description",
            "category",
            "amount",
            "net_amount",
            "payment_method",
            "status_raw",
            "included",
        ]
    ].copy()
    display["flow_type"] = display["flow_type"].map(
        {"expense": "支出", "income": "收入", "neutral": "不计收支"}
    )
    display.columns = [
        "交易时间",
        "平台",
        "收/支",
        "交易对方",
        "商品说明",
        "分类",
        "原始金额",
        "净金额",
        "支付方式",
        "原始状态",
        "纳入统计",
    ]
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        height=480,
        column_config={
            "原始金额": st.column_config.NumberColumn(format="¥ %.2f"),
            "净金额": st.column_config.NumberColumn(format="¥ %.2f"),
        },
    )
    export = data.copy()
    export["occurred_at"] = export["occurred_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
    st.download_button(
        "下载清洗后的 CSV",
        data=export.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
        file_name=f"清洗账单_{date.today():%Y%m%d}.csv",
        mime="text/csv",
        use_container_width=False,
    )
    st.caption("导出文件包含交易对方和订单号等敏感字段，请妥善保存。")


def main() -> None:
    inject_styles()
    st.sidebar.title("清流账单助手")
    st.sidebar.caption("本地运行 · 无外部 API")
    selected_platform = st.sidebar.radio("账单平台", ["自动识别", "微信", "支付宝"], horizontal=True)
    uploaded = st.sidebar.file_uploader(
        "上传账单",
        type=["csv", "xlsx", "zip"],
        help="支持官方导出的微信、支付宝账单；单个文件不超过 30 MB。",
    )
    st.sidebar.markdown("账单只在当前本地会话中处理。关闭程序后不会建立历史账户或云端副本。")

    if uploaded is None:
        render_empty_state()
        return

    try:
        payload = uploaded.getvalue()
        result = parse_bill(payload, uploaded.name, selected_platform)
    except BillParseError as exc:
        st.error(str(exc))
        st.info("请确认上传的是微信或支付宝官方导出的原始账单，且没有手动修改表头。")
        return
    except Exception:
        st.error("账单解析时出现未预期错误。请尝试重新导出账单，或检查文件是否被其他软件修改。")
        return

    file_key = hashlib.sha256(payload).hexdigest()[:10]
    data = result.data.copy()
    st.sidebar.divider()
    with st.sidebar.expander("修正商户消费分类"):
        st.caption("修改后会立即用于本次分析，不会写回原账单。")
        overrides = render_category_editor(data, file_key)
    data = apply_category_overrides(data, overrides)

    valid_dates = data["occurred_at"].dropna()
    if valid_dates.empty:
        st.error("账单中没有可用的交易日期。")
        return
    min_date, max_date = valid_dates.min().date(), valid_dates.max().date()
    date_value = st.sidebar.date_input(
        "分析日期",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if isinstance(date_value, (tuple, list)) and len(date_value) == 2:
        start_date, end_date = date_value
    else:
        start_date = end_date = date_value
    category_filter = st.sidebar.multiselect(
        "限定分类（留空表示全部）", sorted(data["category"].dropna().unique().tolist())
    )
    payment_options = sorted(
        value for value in data["payment_method"].dropna().unique().tolist() if value
    )
    payment_filter = st.sidebar.multiselect("限定支付方式（留空表示全部）", payment_options)
    filtered = filter_transactions(data, start_date, end_date, category_filter, payment_filter)

    st.markdown(
        f"""
        <div class="hero">
          <h1>清流 · 账单分析报告</h1>
          <p>{result.platform}账单 · {start_date:%Y-%m-%d} 至 {end_date:%Y-%m-%d} · 当前筛选 {len(filtered):,} 条记录</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_quality(result)

    tabs = st.tabs(["财务总览", "支出分析", "资金流入", "消费习惯", "个性化建议", "交易明细"])
    with tabs[0]:
        render_overview(filtered)
    with tabs[1]:
        render_expenses(filtered)
    with tabs[2]:
        render_income(filtered)
    with tabs[3]:
        render_habits(filtered)
    with tabs[4]:
        render_advice(filtered)
    with tabs[5]:
        render_details(filtered)


if __name__ == "__main__":
    main()
