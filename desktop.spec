# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata


root = Path(SPECPATH)
datas = [
    (str(root / "app.py"), "."),
    (str(root / ".streamlit" / "config.toml"), ".streamlit"),
]
binaries = []
hiddenimports = [
    "bill_analyzer",
    "bill_analyzer.parsers",
    "bill_analyzer.analytics",
    "bill_analyzer.advice",
    "openpyxl",
    "pandas",
    "numpy",
    "plotly",
    "plotly.express",
    "plotly.graph_objects",
    "pyarrow",
    "streamlit.web.bootstrap",
]

for package in ("streamlit", "webview"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

for distribution in ("streamlit", "pywebview", "plotly", "pandas", "openpyxl", "altair"):
    try:
        datas += copy_metadata(distribution)
    except Exception:
        pass

a = Analysis(
    [str(root / "desktop_launcher.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "cefpython3",
        "gtk",
        "pytest",
        "_pytest",
        "streamlit.testing",
        "streamlit.hello",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="清流账单助手",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(root / "assets" / "qingliu.ico"),
    version=str(root / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="清流账单助手",
)
