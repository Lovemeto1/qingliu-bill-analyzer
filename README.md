# 清流 · 本地账单分析助手

清流是一款本地优先的微信与支付宝账单分析工具。它可以解析官方导出的账单，展示收支结构、消费排行和时间趋势，并基于可解释的本地规则给出财务建议。

账单只在当前设备中处理。项目不要求注册账号、不调用外部 API，也不把账单上传到第三方服务器。

> [!IMPORTANT]
> 账单包含交易对方、订单号、金额和备注等敏感信息。请勿在 Issue、Pull Request、截图或测试文件中上传真实账单。

## 主要功能

- 读取微信官方导出的 XLSX 账单。
- 读取支付宝官方导出的 CSV 账单，包括 GB18030 编码。
- 读取只包含一份账单的 ZIP 压缩包。
- 自动跳过账单说明区并定位真实表头。
- 统一处理成功、失败、关闭、退款和不计收支交易。
- 区分消费支出、全部资金流出、资金流入和转账还款。
- 展示支出排行榜、消费结构、资金流入结构和月度现金流。
- 提供星期与时段热力图、大额消费和疑似周期性支出分析。
- 使用本地规则生成带有依据、建议动作和可信度的财务提示。
- 支持修正商户分类并导出清洗后的 CSV。

## 隐私设计

- 本地服务只监听 `127.0.0.1`，默认无法从其他设备访问。
- 上传文件只在当前本地程序会话中处理。
- 不使用 OpenAI 或其他外部 API。
- 不建立云端账户，不保存云端历史记录。
- 默认关闭 Streamlit 使用统计。
- `.gitignore` 排除常见账单格式、运行环境和构建产物。

导出的清洗 CSV 仍可能包含交易对方和订单号，请妥善保存。有关漏洞和隐私事件的报告方式，请参阅 [SECURITY.md](SECURITY.md)。

## 获取桌面版

在 GitHub 仓库的 **Releases** 页面下载 Windows 压缩包，完整解压后双击 `清流账单助手.exe`。

请保留 EXE 与同目录的 `_internal` 文件夹。桌面版无需安装 Python，也不需要联网。未经代码签名的版本可能触发 Windows SmartScreen 提示，请只从项目官方 Release 下载并核对发布页提供的 SHA-256。

## 从源码启动

建议使用 Python 3.11 或 3.12。

### Windows 快速启动

双击 `start_app.cmd`。首次运行会在项目目录创建 `.venv` 并安装依赖；之后会打开本机页面。

如果文件关联被第三方软件拦截，可以在项目目录的终端中运行：

```powershell
cmd.exe /d /c start_app.cmd
```

也可以手动启动：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

浏览器没有自动打开时，访问 `http://127.0.0.1:8501`。关闭启动窗口或按 `Ctrl+C` 即可停止程序。

## 使用方法

1. 在微信或支付宝中申请并下载官方交易账单。
2. 启动本程序。
3. 选择自动识别、微信或支付宝。
4. 上传 CSV、XLSX 或 ZIP 文件。
5. 首先检查“数据质量与统计口径”。
6. 如有需要，修正商户消费分类。
7. 使用日期、分类和支付方式筛选器查看分析。
8. 在“交易明细”中下载清洗后的数据。

支付宝导出的 ZIP 可能带有密码。请先在本地解压，再上传其中的 CSV；程序不会要求或保存解压密码。

## 统计口径

- **消费支出**：有效的商品与服务净支出，不包含转账、红包、理财划转和信用卡还款。
- **全部资金流出**：账单内所有有效出账，退款按净额扣减。
- **资金流入**：账单内识别到的有效入账，可能包含工资、收款和他人转账，不自动等同于可支配收入。
- **净现金流**：资金流入减去全部资金流出。
- 失败或关闭交易不纳入统计。
- 全额退款的消费净金额为零；可识别退款金额时，部分退款按原金额减退款金额计算。

自动分类、周期性支出检测和财务建议均为启发式结果，应由用户自行核对。本项目不提供投资、税务、会计或其他专业财务建议。

## 支持范围与已知限制

- 支持当前测试覆盖的微信 XLSX 和支付宝 CSV 导出结构；平台调整字段后可能需要更新解析器。
- ZIP 仅接受单个受支持账单文件，不处理加密 ZIP。
- 自动分类依赖商户与商品文字，无法保证完全准确。
- 不同平台的“收入”“退款”和“不计收支”口径并不完全一致，界面会展示统一后的统计说明。

遇到解析问题时，请使用完全虚构的最小样例复现，不要上传原始账单。

## 开发与测试

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

桌面版构建：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build_desktop.ps1
```

构建结果位于被 Git 忽略的 `release` 目录。打包流程会附带项目许可证、第三方软件说明及从当前构建环境导出的第三方许可证文本。

## 项目结构

```text
app.py                         Streamlit 界面
desktop_launcher.py            桌面窗口与本地服务启动器
bill_analyzer/parsers.py       平台识别、解析、清洗和分类
bill_analyzer/analytics.py     统计指标和行为分析
bill_analyzer/advice.py        本地规则建议
tests/                         仅使用合成数据的自动测试
tools/                         图标与许可证构建工具
.github/                       GitHub 模板与自动测试
```

## 参与贡献

欢迎提交 Issue 和 Pull Request。开始前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 和 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。任何示例、日志和截图都必须使用虚构数据。

## 版本与发布

版本变化记录在 [CHANGELOG.md](CHANGELOG.md)。桌面二进制文件应通过 GitHub Releases 发布，不应提交到源码仓库。

## 许可证

项目由无问西东维护，源代码按 [MIT License](LICENSE) 开源。第三方组件继续适用各自许可证，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

微信、支付宝及相关名称和标识属于其各自权利人。本项目为独立的非官方工具，与腾讯、微信或支付宝（中国）网络技术有限公司不存在隶属、授权或背书关系。
