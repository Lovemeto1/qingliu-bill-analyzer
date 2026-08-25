# 参与贡献

感谢你愿意改进清流账单助手。这个项目处理高度敏感的个人财务数据，隐私安全优先于功能便利。

## 隐私底线

- 不要在 Issue、Pull Request、提交记录、截图或测试文件中上传真实账单。
- 不要提交姓名、账号、订单号、商户记录、备注或可关联个人身份的交易数据。
- 复现解析问题时，请使用完全虚构的数据，并尽量只保留触发问题所需的字段。
- 不要引入默认联网、遥测、云端上传或第三方 API。确需联网的功能必须是明确的可选项，并先在 Issue 中讨论。

## 本地开发

建议使用 Python 3.11 或 3.12：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## 测试

提交前请运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

新增账单格式或解析规则时，请同时增加合成数据测试，覆盖正常数据、退款、失败交易及异常输入。

## 提交 Pull Request

1. 从 `main` 创建功能分支。
2. 保持改动聚焦，并说明改动原因和统计口径影响。
3. 确认测试通过，且变更中不存在真实账单或个人信息。
4. 涉及用户界面时可附截图，但截图必须使用合成数据。
5. 行为变化请更新 README 和 CHANGELOG 的 `Unreleased` 部分。

提交贡献即表示你同意按项目的 MIT 许可证发布你的贡献。
