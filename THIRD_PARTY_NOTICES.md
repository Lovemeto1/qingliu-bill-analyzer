# 第三方软件说明

清流账单助手基于多个开源项目构建。直接依赖及其许可证包括：

| 项目 | 许可证 |
| --- | --- |
| Streamlit | Apache-2.0 |
| pandas | BSD-3-Clause |
| openpyxl | MIT |
| Plotly.py | MIT |
| pywebview | BSD-3-Clause |
| PyInstaller | GPL-2.0-or-later with Bootloader Exception |
| pytest（仅开发与测试） | MIT |

这些项目及其传递依赖仍分别受各自许可证约束。桌面版构建流程会根据实际构建环境生成 `THIRD_PARTY_LICENSES.txt`，并随发布包分发完整的许可证文本。

本文件仅用于归纳说明，不改变任何第三方许可证的条款。项目源代码本身按根目录 [LICENSE](LICENSE) 中的 MIT 许可证发布。
