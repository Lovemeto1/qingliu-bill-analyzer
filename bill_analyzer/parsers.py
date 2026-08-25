from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath

import pandas as pd


CANONICAL_COLUMNS = [
    "source",
    "transaction_id",
    "occurred_at",
    "flow_type",
    "amount",
    "net_amount",
    "cash_in_amount",
    "cash_out_amount",
    "consumption_amount",
    "refund_amount",
    "cashflow_class",
    "category",
    "category_raw",
    "transaction_type",
    "counterparty",
    "item_description",
    "payment_method",
    "status_raw",
    "status_normalized",
    "note",
    "merchant_order_id",
    "included",
]


class BillParseError(ValueError):
    """账单无法被安全识别或解析。"""


@dataclass
class ParseResult:
    data: pd.DataFrame
    platform: str
    source_name: str
    encoding: str | None
    raw_rows: int
    duplicate_rows: int
    invalid_rows: int
    excluded_rows: int
    unknown_status_rows: int
    warnings: list[str] = field(default_factory=list)


def parse_bill(content: bytes, filename: str, selected_platform: str = "自动识别") -> ParseResult:
    """解析上传的账单字节，并返回统一交易模型。"""
    if not content:
        raise BillParseError("上传的文件为空。")
    if len(content) > 30 * 1024 * 1024:
        raise BillParseError("文件超过 30 MB，请分时间段导出后再上传。")

    content, filename = _unwrap_zip(content, filename)
    raw_table, encoding = _read_table(content, filename)
    header_index, detected_platform = _find_header(raw_table)

    if selected_platform not in {"自动识别", "微信", "支付宝"}:
        raise BillParseError("未知的平台选择。")
    if selected_platform != "自动识别" and selected_platform != detected_platform:
        raise BillParseError(
            f"文件内容识别为{detected_platform}账单，与所选的{selected_platform}不一致。"
        )

    raw = _promote_header(raw_table, header_index)
    normalized, stats = _normalize(raw, detected_platform)
    warnings: list[str] = []
    if stats["invalid_rows"]:
        warnings.append(f"有 {stats['invalid_rows']} 条记录缺少有效日期或金额，已排除。")
    if stats["unknown_status_rows"]:
        warnings.append(
            f"有 {stats['unknown_status_rows']} 条交易状态未匹配已知规则，已保留并标记为“未知”。"
        )
    if not (normalized["flow_type"] == "income").any():
        warnings.append("账单中没有识别到资金流入，收入与结余分析仅供参考。")

    return ParseResult(
        data=normalized,
        platform=detected_platform,
        source_name=filename,
        encoding=encoding,
        raw_rows=len(raw),
        duplicate_rows=stats["duplicate_rows"],
        invalid_rows=stats["invalid_rows"],
        excluded_rows=stats["excluded_rows"],
        unknown_status_rows=stats["unknown_status_rows"],
        warnings=warnings,
    )


def _unwrap_zip(content: bytes, filename: str) -> tuple[bytes, str]:
    if not filename.lower().endswith(".zip"):
        return content, filename
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            candidates = [
                info
                for info in archive.infolist()
                if not info.is_dir()
                and PurePosixPath(info.filename).suffix.lower() in {".csv", ".xlsx"}
            ]
            if not candidates:
                raise BillParseError("压缩包中没有找到 CSV 或 Excel 账单。")
            if len(candidates) > 1:
                raise BillParseError("压缩包中包含多份账单，请解压后单独上传。")
            info = candidates[0]
            if info.flag_bits & 0x1:
                raise BillParseError("该 ZIP 账单已加密，请先使用导出密码解压，再上传其中的 CSV 文件。")
            if info.file_size > 30 * 1024 * 1024:
                raise BillParseError("压缩包内的账单超过 30 MB。")
            try:
                inner = archive.read(info)
            except RuntimeError as exc:
                raise BillParseError("ZIP 账单无法解压；如果文件带密码，请先解压后上传 CSV。") from exc
            inner_name = PurePosixPath(info.filename).name
            return inner, inner_name
    except zipfile.BadZipFile as exc:
        raise BillParseError("ZIP 文件已损坏或格式不正确。") from exc


def _read_table(content: bytes, filename: str) -> tuple[pd.DataFrame, str | None]:
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix == ".xlsx":
        try:
            return pd.read_excel(io.BytesIO(content), header=None, dtype=object), None
        except Exception as exc:
            raise BillParseError("Excel 文件无法读取，请确认它是微信或支付宝原始导出账单。") from exc
    if suffix != ".csv":
        raise BillParseError("仅支持 CSV、XLSX 和包含单份账单的 ZIP 文件。")

    text = None
    used_encoding = None
    for encoding in ("utf-8-sig", "gb18030", "utf-16"):
        try:
            candidate = content.decode(encoding)
        except UnicodeDecodeError:
            continue
        if "交易时间" in candidate and ("收/支" in candidate or "交易分类" in candidate):
            text, used_encoding = candidate, encoding
            break
    if text is None:
        raise BillParseError("无法识别 CSV 编码或账单表头。")

    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise BillParseError("CSV 文件中没有数据。")
    width = max(len(row) for row in rows)
    padded = [row + [None] * (width - len(row)) for row in rows]
    return pd.DataFrame(padded, dtype=object), used_encoding


def _clean_cell(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).replace("\ufeff", "").strip()


def _find_header(table: pd.DataFrame) -> tuple[int, str]:
    for index, row in table.head(80).iterrows():
        values = {_clean_cell(value) for value in row.tolist()}
        if "交易时间" not in values or "收/支" not in values:
            continue
        if {"交易分类", "交易状态", "收/付款方式"}.issubset(values):
            return int(index), "支付宝"
        if {"交易类型", "当前状态"}.issubset(values) and (
            "金额(元)" in values or "金额" in values
        ):
            return int(index), "微信"
    raise BillParseError("未找到受支持的微信或支付宝账单表头。")


def _promote_header(table: pd.DataFrame, header_index: int) -> pd.DataFrame:
    headers: list[str] = []
    seen: dict[str, int] = {}
    for position, value in enumerate(table.iloc[header_index].tolist()):
        name = _clean_cell(value) or f"_extra_{position}"
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            name = f"{name}_{seen[name]}"
        headers.append(name)
    data = table.iloc[header_index + 1 :].copy()
    data.columns = headers
    data = data.dropna(how="all")
    non_empty_mask = data.apply(lambda row: any(_clean_cell(value) for value in row), axis=1)
    return data.loc[non_empty_mask].reset_index(drop=True)


def _normalize(raw: pd.DataFrame, platform: str) -> tuple[pd.DataFrame, dict[str, int]]:
    mapping = {
        "交易时间": "occurred_at",
        "收/支": "flow_raw",
        "金额": "amount_raw",
        "金额(元)": "amount_raw",
        "交易分类": "category_raw",
        "交易类型": "transaction_type",
        "交易对方": "counterparty",
        "商品说明": "item_description",
        "商品": "item_description",
        "收/付款方式": "payment_method",
        "支付方式": "payment_method",
        "交易状态": "status_raw",
        "当前状态": "status_raw",
        "交易订单号": "transaction_id",
        "交易单号": "transaction_id",
        "商家订单号": "merchant_order_id",
        "商户单号": "merchant_order_id",
        "备注": "note",
    }
    selected = pd.DataFrame(index=raw.index)
    for original, canonical in mapping.items():
        if original in raw.columns and canonical not in selected.columns:
            selected[canonical] = raw[original]
    for column in {
        "occurred_at",
        "flow_raw",
        "amount_raw",
        "category_raw",
        "transaction_type",
        "counterparty",
        "item_description",
        "payment_method",
        "status_raw",
        "transaction_id",
        "merchant_order_id",
        "note",
    }:
        if column not in selected:
            selected[column] = ""

    text_columns = [column for column in selected.columns if column not in {"occurred_at"}]
    for column in text_columns:
        selected[column] = selected[column].map(_clean_cell)

    selected["occurred_at"] = pd.to_datetime(selected["occurred_at"], errors="coerce")
    amount_text = selected["amount_raw"].map(_clean_cell).str.replace(",", "", regex=False)
    selected["amount"] = pd.to_numeric(
        amount_text.str.extract(r"(-?\d+(?:\.\d+)?)", expand=False), errors="coerce"
    ).abs()
    selected["source"] = platform
    selected["flow_type"] = selected["flow_raw"].map(_normalize_flow)
    selected["status_normalized"] = selected["status_raw"].map(_normalize_status)

    invalid_mask = selected["occurred_at"].isna() | selected["amount"].isna()
    failed_mask = selected["status_normalized"].isin({"failed", "closed"})
    selected["included"] = ~(invalid_mask | failed_mask)

    refund_from_status = pd.to_numeric(
        selected["status_raw"].str.extract(r"[¥￥]\s*([\d,]+(?:\.\d+)?)", expand=False).str.replace(",", "", regex=False),
        errors="coerce",
    )
    full_refund = selected["status_raw"].str.contains("全额退款|退款成功", na=False)
    selected["refund_amount"] = refund_from_status.fillna(0.0)
    selected.loc[full_refund & selected["refund_amount"].eq(0), "refund_amount"] = selected["amount"]
    selected["refund_amount"] = selected[["refund_amount", "amount"]].min(axis=1).fillna(0.0)
    # 微信会同时导出原消费和一条退款入账。退款只在原支出（或支付宝“不计收支”退款行）
    # 上计量，避免把同一笔退款重复统计两次。
    income_refund = selected["flow_type"].eq("income") & selected["status_normalized"].eq("refunded")
    selected.loc[income_refund, "refund_amount"] = 0.0
    selected["net_amount"] = selected["amount"].fillna(0.0)
    expense_refund = selected["flow_type"].eq("expense")
    selected.loc[expense_refund, "net_amount"] = (
        selected.loc[expense_refund, "amount"].fillna(0.0)
        - selected.loc[expense_refund, "refund_amount"]
    ).clip(lower=0)

    selected["cashflow_class"] = selected.apply(_cashflow_class, axis=1)
    selected["category"] = selected.apply(_classify_category, axis=1)
    selected["cash_in_amount"] = 0.0
    selected["cash_out_amount"] = 0.0
    selected["consumption_amount"] = 0.0
    income_mask = selected["included"] & selected["flow_type"].eq("income") & ~selected[
        "status_normalized"
    ].eq("refunded")
    expense_mask = selected["included"] & selected["flow_type"].eq("expense")
    consumption_mask = expense_mask & selected["cashflow_class"].eq("consumption")
    selected.loc[income_mask, "cash_in_amount"] = selected.loc[income_mask, "amount"]
    selected.loc[expense_mask, "cash_out_amount"] = selected.loc[expense_mask, "net_amount"]
    selected.loc[consumption_mask, "consumption_amount"] = selected.loc[
        consumption_mask, "net_amount"
    ]

    selected["transaction_id"] = selected.apply(_stable_transaction_id, axis=1)
    before_dedup = len(selected)
    selected = selected.drop_duplicates(subset=["source", "transaction_id"], keep="last").copy()
    duplicate_rows = before_dedup - len(selected)

    selected = selected.sort_values("occurred_at", na_position="last").reset_index(drop=True)
    for column in CANONICAL_COLUMNS:
        if column not in selected:
            selected[column] = ""
    result = selected[CANONICAL_COLUMNS].copy()
    stats = {
        "duplicate_rows": duplicate_rows,
        "invalid_rows": int(invalid_mask.sum()),
        "excluded_rows": int((invalid_mask | failed_mask).sum()),
        "unknown_status_rows": int(selected["status_normalized"].eq("unknown").sum()),
    }
    return result, stats


def _normalize_flow(value: object) -> str:
    text = _clean_cell(value)
    if text == "支出":
        return "expense"
    if text == "收入":
        return "income"
    return "neutral"


def _normalize_status(value: object) -> str:
    text = _clean_cell(value)
    if re.search(r"关闭|失败|已撤销|未支付", text):
        return "closed" if "关闭" in text else "failed"
    if re.search(r"退款|退还", text):
        return "refunded"
    if re.search(r"成功|已收钱|已转账|已到账|已存入|资金已到|对方已收", text):
        return "success"
    return "unknown"


def _cashflow_class(row: pd.Series) -> str:
    text = " ".join(
        _clean_cell(row.get(column))
        for column in ("transaction_type", "category_raw", "item_description", "counterparty")
    )
    flow = row.get("flow_type")
    if row.get("status_normalized") == "refunded" and flow != "expense":
        return "refund"
    if flow == "income":
        return "income"
    if flow == "neutral":
        return "refund" if row.get("status_normalized") == "refunded" else "neutral"
    if re.search(r"信用卡还款|贷款还款|花呗还款|白条还款", text):
        return "repayment"
    if re.search(r"转账|红包|零钱通|余额宝|理财|基金|提现", text):
        return "transfer"
    return "consumption"


CATEGORY_RULES: list[tuple[str, str]] = [
    ("餐饮", r"餐饮|美食|外卖|饭|餐厅|食堂|咖啡|奶茶|茶饮|面包|蛋糕|烧烤|火锅|超市|便利店|生鲜|水果"),
    ("交通出行", r"交通|出行|地铁|公交|铁路|火车|机票|航空|打车|滴滴|高德|停车|加油|充电桩|高速|单车"),
    ("购物", r"服饰|装扮|百货|购物|淘宝|天猫|京东|拼多多|抖音商城|家电|数码|鞋|衣|饰品"),
    ("居住", r"房租|物业|水费|电费|燃气|家居|装修|住房"),
    ("通讯网络", r"话费|流量|宽带|通信|通讯|手机充值"),
    ("医疗健康", r"医疗|医院|诊所|药房|药店|体检|健康|挂号"),
    ("教育", r"教育|培训|学校|学费|课程|书店|考试|知识"),
    ("休闲娱乐", r"娱乐|电影|影院|游戏|演出|旅游|酒店|景区|运动|健身|音乐|视频会员"),
    ("生活服务", r"生活服务|快递|物流|洗衣|维修|美容|美发|家政|打印|摄影"),
    ("人情往来", r"人情|礼物|礼品|捐赠|公益|婚礼|红包"),
    ("金融保险", r"保险|手续费|服务费|利息|银行"),
]


def _classify_category(row: pd.Series) -> str:
    cashflow_class = row.get("cashflow_class")
    if cashflow_class == "income":
        return "资金流入"
    if cashflow_class == "repayment":
        return "债务与还款"
    if cashflow_class in {"transfer", "neutral"}:
        return "转账与资金往来"
    if cashflow_class == "refund":
        return "退款"
    text = " ".join(
        _clean_cell(row.get(column))
        for column in ("category_raw", "transaction_type", "counterparty", "item_description")
    )
    for category, pattern in CATEGORY_RULES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return category
    return "其他消费"


def _stable_transaction_id(row: pd.Series) -> str:
    raw = _clean_cell(row.get("transaction_id"))
    if raw:
        return raw
    parts = [
        _clean_cell(row.get("occurred_at")),
        _clean_cell(row.get("amount")),
        _clean_cell(row.get("counterparty")),
        _clean_cell(row.get("item_description")),
        _clean_cell(row.get("flow_raw")),
    ]
    return "generated-" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]
