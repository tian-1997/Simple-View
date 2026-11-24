# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配方：产出单文件 dist/WinIsland.exe。

为什么不用 `pyinstaller app/main.py` 直接打：
- QML 与素材不是 Python 模块，PyInstaller 不会自己发现，必须显式声明；
  而且目录结构要保住 —— app/qml 里的 "../../assets/..." 是相对路径。
- PySide6 的 QML 插件（QtQuick / QtQuick.Effects / QtQuick.Shapes）在
  site-packages/PySide6/qml 下，不声明的话 exe 起来就是白窗 + "module not installed"。
- uiautomation 是 notify_win32 里延迟导入的，静态分析看不到。
"""
import os
from pathlib import Path

import PySide6

ROOT = Path(SPECPATH).resolve()
PYSIDE = Path(PySide6.__file__).parent

# QML 插件：只带项目真正 import 的那几个（QtQuick 里含 Effects / Shapes / Window）
QML_MODULES = ("QtQuick", "QtQml", "QtCore")

datas = [
    # QML 源码与素材按原相对位置摆放，QML 里的相对路径才成立
    (str(ROOT / "app" / "qml"), "app/qml"),
    (str(ROOT / "assets"), "assets"),
]
for name in QML_MODULES:
    src = PYSIDE / "qml" / name
    if src.exists():
        datas.append((str(src), f"PySide6/qml/{name}"))
for extra in ("builtins.qmltypes", "jsroot.qmltypes"):
    src = PYSIDE / "qml" / extra
    if src.exists():
        datas.append((str(src), "PySide6/qml"))

hiddenimports = [
    "uiautomation",          # 延迟导入，静态分析看不见
    "comtypes",
    "comtypes.client",
    "comtypes.automation",
    "PySide6.QtSvg",         # AppLogo 用 svg，少了它图标全空
]

excludes = [
    "tkinter",
    "unittest",
    "PIL",                    # 只有打包脚本用，运行时不需要
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebChannel",
    "PySide6.Qt3DCore",
    "PySide6.QtMultimedia",
    "PySide6.QtCharts",
    "PySide6.QtPdf",
]

a = Analysis(
    [str(ROOT / "app" / "main.py")],
    pathex=[str(ROOT / "app")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

# --------------------------------------------------------------------------- #
# 瘦身：hook-PySide6.QtQml 会把 PySide6 下**所有** QML 模块及其依赖 dll 全收进来，
# 连 194MB 的 Qt6WebEngineCore.dll、Quick3D、Charts、Multimedia 都在里面 ——
# 一个 400MB 的包，光解包就要好几秒。这里按 dest 名做黑名单裁剪，
# 只留 QtQuick / QtQml / QtSvg / QtWidgets（托盘菜单）真正用到的部分。
# --------------------------------------------------------------------------- #
PRUNE_PREFIXES = (
    "pyside6/qt6webengine", "pyside6/qtwebengineprocess", "pyside6/qt6quick3d",
    "pyside6/qt63d", "pyside6/qt6charts", "pyside6/qt6graphs",
    "pyside6/qt6datavisualization", "pyside6/qt6multimedia", "pyside6/qt6spatialaudio",
    "pyside6/qt6texttospeech", "pyside6/qt6pdf", "pyside6/qt6webview",
    "pyside6/qt6webchannel", "pyside6/qt6websockets", "pyside6/qt6location",
    "pyside6/qt6positioning", "pyside6/qt6sensors", "pyside6/qt6scxml",
    "pyside6/qt6remoteobjects", "pyside6/qt6test", "pyside6/qt6sql",
    "pyside6/qt6bluetooth", "pyside6/translations",
    "pyside6/resources/qtwebengine", "pyside6/resources/icudtl",
    "pyside6/resources/v8_context", "pyside6/resources/qtwebengine_devtools",
    "pyside6/qml/qtquick3d", "pyside6/qml/qt3d", "pyside6/qml/qtcharts",
    "pyside6/qml/qtgraphs", "pyside6/qml/qtmultimedia", "pyside6/qml/qtlocation",
    "pyside6/qml/qtpositioning", "pyside6/qml/qtsensors",
    "pyside6/qml/qttexttospeech", "pyside6/qml/qtweb", "pyside6/qml/qtquick/pdf",
    "pyside6/qml/qtquick/timeline", "pyside6/qml/qtquick/localstorage",
    "pyside6/qml/qtquick/virtualkeyboard", "pyside6/qml/qtquick/scene2d",
    "pyside6/qml/qtquick/scene3d",
)


def _keep(entry) -> bool:
    dest = str(entry[0]).replace("\\", "/").lower()
    return not any(dest.startswith(p) for p in PRUNE_PREFIXES)


_before = len(a.binaries) + len(a.datas)
a.binaries = [e for e in a.binaries if _keep(e)]
a.datas = [e for e in a.datas if _keep(e)]
print(f"[spec] 裁剪 {_before - len(a.binaries) - len(a.datas)} 个文件，"
      f"剩 {len(a.binaries)} binaries + {len(a.datas)} datas")

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="WinIsland",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # UPX 压 Qt 的 dll 容易被杀软误报，且省不了多少
    runtime_tmpdir=None,
    console=False,             # 常驻小工具，不要黑框
    disable_windowed_traceback=False,
    icon=str(ROOT / "build" / "WinIsland.ico"),
    version=str(ROOT / "tools" / "version_info.txt"),
)
