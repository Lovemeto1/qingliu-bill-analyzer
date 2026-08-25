from __future__ import annotations

from io import BytesIO, StringIO

import openpyxl
import pandas as pd

from bill_analyzer.parsers import BillParseError, parse_bill


def make_alipay_csv() -> bytes:
    preamble = [f"说明行{i}" for i in range(1, 24)]
    header = [
        "交易时间",
        "交易分类",
        "交易对方",
        "对方账号",
        "商品说明",
        "收/支",
        "金额",
        "收/付款方式",
        "交易状态",
        "交易订单号",
        "商家订单号",
        "备注",
        "",
    ]
    rows = [
        ["2026-01-01 08:00:00", "餐饮美食", "早餐店", "", "早餐", "支出", "20.00", "余额", "交易成功", "a1", "m1", "", ""],
        ["2026-01-02 10:00:00", "转账红包", "朋友", "", "转账", "收入", "100.00", "余额", "交易成功", "a2", "m2", "", ""],
        ["2026-01-03 11:00:00", "日用百货", "商店", "", "商品", "支出", "50.00", "余额", "交易关闭", "a3", "m3", "", ""],
        ["2026-01-04 12:00:00", "餐饮美食", "餐厅", "", "午餐", "支出", "30.00", "余额", "退款成功", "a4", "m4", "", ""],
    ]
    output = StringIO()
    for line in preamble:
        output.write(line + "\n")
    import csv

    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return output.getvalue().encode("gb18030")


def make_wechat_xlsx() -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row in range(1, 18):
        sheet.cell(row=row, column=1, value=f"说明{row}")
    header = [
        "交易时间",
        "交易类型",
        "交易对方",
        "商品",
        "收/支",
        "金额(元)",
        "支付方式",
        "当前状态",
        "交易单号",
        "商户单号",
        "备注",
    ]
    sheet.append(header)
    sheet.append(["2026-02-01 08:00:00", "商户消费", "咖啡店", "咖啡", "支出", "¥30.00", "零钱", "支付成功", "w1", "wm1", ""])
    sheet.append(["2026-02-02 08:00:00", "商户消费", "餐厅", "午餐", "支出", "¥30.00", "零钱", "已退款¥12.00", "w2", "wm2", ""])
    sheet.append(["2026-02-03 08:00:00", "转账", "朋友", "转账", "支出", "¥50.00", "零钱", "已转账", "w3", "wm3", ""])
    sheet.append(["2026-02-04 08:00:00", "二维码收款", "客户", "收款", "收入", "¥200.00", "零钱", "已收钱", "w4", "wm4", ""])
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def test_parse_alipay_gb18030_and_exclusions():
    result = parse_bill(make_alipay_csv(), "支付宝交易明细.csv", "支付宝")
    assert result.platform == "支付宝"
    assert result.encoding == "gb18030"
    assert result.raw_rows == 4
    assert result.excluded_rows == 1
    assert result.data["cash_in_amount"].sum() == 100
    assert result.data["consumption_amount"].sum() == 20
    assert result.data["refund_amount"].sum() == 30


def test_parse_wechat_refund_transfer_and_income():
    result = parse_bill(make_wechat_xlsx(), "微信支付账单.xlsx", "微信")
    assert result.platform == "微信"
    assert result.data["consumption_amount"].sum() == 48
    assert result.data["cash_out_amount"].sum() == 98
    assert result.data["cash_in_amount"].sum() == 200
    assert result.data["refund_amount"].sum() == 12
    transfer = result.data.loc[result.data["transaction_id"] == "w3"].iloc[0]
    assert transfer["cashflow_class"] == "transfer"
    assert transfer["consumption_amount"] == 0


def test_platform_mismatch_is_rejected():
    try:
        parse_bill(make_alipay_csv(), "支付宝交易明细.csv", "微信")
    except BillParseError as exc:
        assert "不一致" in str(exc)
    else:
        raise AssertionError("平台不一致时应当拒绝解析")
