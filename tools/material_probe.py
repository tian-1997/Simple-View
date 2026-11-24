"""材质可行性探针：验证 Windows 真实背景模糊 + 圆角裁切 + Qt 透明窗是否可共存。

跑法：
    python tools/material_probe.py            # 演示窗口 + 玻璃窗，截全屏存 docs/preview/material_probe.png
    python tools/material_probe.py --bg 图  # 指定背景图
    python tools/material_probe.py --no-acrylic   # 对照组：只做半透明 tint，不做模糊

输出：docs/preview/material_probe.png（整屏截图，能同时看到背景与玻璃窗真实合成结果）
"""
from __future__ import annotations

import argparse
import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow

ROOT = Path(__file__).resolve().parent.parent

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

# --- SetWindowCompositionAttribute ---
ACCENT_DISABLED = 0
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
WCA_ACCENT_POLICY = 19


class ACCENT_POLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_uint),
        ("AccentFlags", ctypes.c_uint),
        ("GradientColor", ctypes.c_uint),   # ABGR
        ("AnimationId", ctypes.c_uint),
    ]


class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    ]


def apply_accent(hwnd: int, state: int, tint_abgr: int = 0x00000000, flags: int = 0) -> bool:
    policy = ACCENT_POLICY(state, flags, tint_abgr, 0)
    data = WINDOWCOMPOSITIONATTRIBDATA(
        WCA_ACCENT_POLICY, ctypes.cast(ctypes.byref(policy), ctypes.c_void_p), ctypes.sizeof(policy)
    )
    fn = getattr(user32, "SetWindowCompositionAttribute", None)
    if fn is None:
        return False
    fn.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
    fn.restype = wintypes.BOOL
    return bool(fn(wintypes.HWND(hwnd), ctypes.byref(data)))


def set_round_region(hwnd: int, w: int, h: int, radius: int) -> bool:
    """把窗口裁成圆角矩形，避免模糊区域露出方形角。"""
    rgn = gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, radius * 2, radius * 2)
    if not rgn:
        return False
    ok = user32.SetWindowRgn(wintypes.HWND(hwnd), rgn, True)
    # SetWindowRgn 成功后 region 归系统所有，不要再 DeleteObject
    return bool(ok)


def hwnd_of(win) -> int:
    return int(win.winId())


def _find_window_by_title(title: str) -> tuple[int, int, int] | None:
    """按标题找窗口，返回 (hwnd, 宽, 高)。QML 里的子 Window 拿不到 Python 引用，只能走 Win32。"""
    hits: list[tuple[int, int, int]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _lp):
        n = user32.GetWindowTextLengthW(hwnd)
        if n == 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        if buf.value == title and user32.IsWindowVisible(hwnd):
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            hits.append((int(hwnd), r.right - r.left, r.bottom - r.top))
        return True

    user32.EnumWindows(cb, 0)
    return hits[0] if hits else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bg", default=str(ROOT / "design" / "preview" / "WinIsland-glass-concept.png"))
    ap.add_argument("--no-acrylic", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "docs" / "preview" / "material_probe.png"))
    args = ap.parse_args()

    app = QGuiApplication(sys.argv[:1])
    engine = QQmlApplicationEngine()
    engine.warnings.connect(
        lambda ws: [print(f"QML: {w.toString()} line {w.line()}", file=sys.stderr) for w in ws]
    )
    engine.rootContext().setContextProperty("bgPath", Path(args.bg).as_posix())
    engine.load(QUrl.fromLocalFile(str(ROOT / "tools" / "material_probe.qml")))
    if not engine.rootObjects():
        print("QML 加载失败", file=sys.stderr)
        return 1

    root_win = engine.rootObjects()[0]
    report: dict[str, object] = {}

    def setup() -> None:
        found = _find_window_by_title("material-probe-glass")
        if found is None:
            print("没拿到玻璃窗句柄", file=sys.stderr)
            app.quit()
            return
        hwnd, g_w, g_h = found
        dpr = root_win.devicePixelRatio()
        print(f"根窗 hwnd={hwnd_of(root_win)} | 玻璃窗 hwnd={hwnd} 物理尺寸={g_w}x{g_h} dpr={dpr}")
        ok_rgn = set_round_region(hwnd, g_w, g_h, int(22 * dpr))
        report["region"] = ok_rgn
        if args.no_acrylic:
            report["accent"] = "skipped"
        else:
            # 深色蓝黑玻璃：GradientColor 为 ABGR，A 越大遮挡越强
            report["accent"] = apply_accent(hwnd, ACCENT_ENABLE_ACRYLICBLURBEHIND, 0x99201814)
        print(f"round_region={ok_rgn} acrylic={report.get('accent')}")

    tint_levels = [0x99, 0x77, 0x55]
    seq = {"i": 0}

    def next_tint() -> None:
        if args.no_acrylic:
            shot(None)
            return
        i = seq["i"]
        if i >= len(tint_levels):
            app.quit()
            return
        alpha = tint_levels[i]
        found = _find_window_by_title("material-probe-glass")
        if not found:
            app.quit()
            return
        hwnd = found[0]
        color = (alpha << 24) | 0x201A17  # ABGR: 深蓝黑
        ok = apply_accent(hwnd, ACCENT_ENABLE_ACRYLICBLURBEHIND, color)
        print(f"tint alpha=0x{alpha:02X} -> {ok}")
        seq["i"] += 1
        QTimer.singleShot(500, lambda: shot(alpha))

    def shot(tag) -> None:
        screen = QGuiApplication.primaryScreen()
        out = Path(args.out)
        path = out if tag is None else out.with_name(f"{out.stem}_a{tag:02X}{out.suffix}")
        screen.grabWindow(0).save(str(path), "PNG")
        print(f"saved {path}")
        if tag is None:
            app.quit()
        else:
            QTimer.singleShot(200, next_tint)

    QTimer.singleShot(900, setup)
    QTimer.singleShot(1600, next_tint)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
