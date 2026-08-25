# 发布检查清单

## 源码仓库

- [ ] 运行全部测试并确认通过。
- [ ] 确认 `git status --ignored --short` 中没有准备提交的账单或构建产物。
- [ ] 确认 `git diff --cached --name-only` 不包含 `.csv`、`.xlsx`、`.xls`、`.zip`、`.venv`、`build` 或 `release`。
- [ ] 检查源码、文档、测试、截图和提交历史中没有姓名、账号、订单号、真实交易或密钥。
- [ ] 更新 `CHANGELOG.md` 和 `version_info.txt`。
- [ ] 从干净环境安装依赖并运行测试。

## Windows 桌面版

- [ ] 运行 `build_desktop.ps1` 生成完整目录。
- [ ] 确认发布目录包含 `LICENSE.txt`、`THIRD_PARTY_NOTICES.txt` 和 `THIRD_PARTY_LICENSES.txt`。
- [ ] 在无 Python 的 Windows 环境试运行桌面版。
- [ ] 使用虚构账单验证导入、筛选、图表和导出。
- [ ] 将完整发布目录压缩成 ZIP，不要单独发布 EXE。
- [ ] 生成 ZIP 的 SHA-256 校验值。

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath '.\清流账单助手-v1.0.0-windows-x64.zip'
```

## GitHub Release

- [ ] 创建与版本一致的标签，例如 `v1.0.0`。
- [ ] 发布说明包含主要变化、已知限制、隐私提示和校验值。
- [ ] 上传 ZIP，不把二进制文件提交到源码分支。
- [ ] 发布后从 GitHub 重新下载并核对 SHA-256。
