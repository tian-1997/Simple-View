"""Windows 玻璃材质：把真实背景模糊作用到 Qt 透明窗上。

三个概念必须分清，代码里也分开处理：
1. 窗口透明      —— Qt 的 color: transparent，靠 QML 根节点透出背景；
2. 背景模糊      —— SetWindowCompositionAttribute 的 acrylic accent，由 DWM 做；
3. 圆角裁切      —— SetWindowRgn，把模糊区域裁成与 QML 一致的圆角，否则四角会露出方形模糊。

QML 那边不再叠加同色半透明底（会和系统 tint 相乘变成不透明），
只在材质不可用时用 tokens.fallbackFill 兜底。
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QTimer

import tokens

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

ACCENT_DISABLED = 0
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
WCA_ACCENT_POLICY = 19


class ACCENT_POLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_uint),
        ("AccentFlags", ctypes.c_uint),
        ("GradientColor", ctypes.c_uint),  # ABGR
        ("AnimationId", ctypes.c_uint),
    ]


class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    ]


def _set_accent(hwnd: int, state: int, tint_abgr: int = 0x00000000, flags: int = 0) -> bool:
    fn = getattr(user32, "SetWindowCompositionAttribute", None)
    if fn is None:
        return False
    policy = ACCENT_POLICY(state, flags, tint_abgr, 0)
    data = WINDOWCOMPOSITIONATTRIBDATA(
        WCA_ACCENT_POLICY,
        ctypes.cast(ctypes.byref(policy), ctypes.c_void_p),
        ctypes.sizeof(policy),
    )
    fn.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
    fn.restype = wintypes.BOOL
    return bool(fn(wintypes.HWND(hwnd), ctypes.byref(data)))


def _set_round_region(hwnd: int, w: int, h: int, radius: int) -> bool:
    if w <= 0 or h <= 0:
        return False
    rgn = gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, max(1, radius) * 2, max(1, radius) * 2)
    if not rgn:
        return False
    # SetWindowRgn 成功后 region 归系统所有，不要再 DeleteObject
    return bool(user32.SetWindowRgn(wintypes.HWND(hwnd), rgn, True))


class GlassMaterial:
    """绑定到一个 QQuickWindow：跟随尺寸/主题变化重设 tint 与圆角裁切。"""

    def __init__(self, window, mode: str = "dark") -> None:
        self.win = window
        self.mode = mode
        self.available = False
        self.last_region: tuple[int, int, int] | None = None
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(10)
        self._timer.timeout.connect(self._apply_region)

    # ---------- 生命周期 ----------
    def start(self) -> bool:
        self.available = self._apply_accent()
        try:
            self.win.widthChanged.connect(self.schedule_region)
            self.win.heightChanged.connect(self.schedule_region)
        except Exception:  # noqa: BLE001
            pass
        self._apply_region()
        return self.available

    def schedule_region(self, *_args) -> None:
        # 尺寸动画每帧都会改窗口大小，合并成少量调用
        if not self._timer.isActive():
            self._timer.start()

    # ---------- 具体实现 ----------
    def _apply_accent(self) -> bool:
        hwnd = int(self.win.winId())
        tint = tokens.ACRYLIC_TINT.get(self.mode, tokens.ACRYLIC_TINT["dark"])
        if _set_accent(hwnd, ACCENT_ENABLE_ACRYLICBLURBEHIND, tint):
            return True
        # Win11 某些版本 acrylic 不生效时退回普通模糊，仍比纯透明可读
        return _set_accent(hwnd, ACCENT_ENABLE_BLURBEHIND, tint)

    def _apply_region(self) -> None:
        try:
            dpr = self.win.devicePixelRatio() or 1.0
            w = int(round(self.win.width() * dpr))
            h = int(round(self.win.height() * dpr))
        except Exception:  # noqa: BLE001
            return
        # 半径跟着高度走：收起态 40 高 → 20；展开态固定 22
        radius = min(round(h / 2), int(tokens.SIZE["panelRadius"] * dpr))
        radius = max(radius, int(8 * dpr))
        sig = (w, h, radius)
        if sig == self.last_region:
            return
        if _set_round_region(int(self.win.winId()), w, h, radius):
            self.last_region = sig

    # ---------- 主题 ----------
    def set_mode(self, mode: str) -> bool:
        self.mode = mode
        self.available = self._apply_accent()
        return self.available

    def release(self) -> None:
        """退出前取消 tint，避免残留模糊窗。"""
        try:
            _set_accent(int(self.win.winId()), ACCENT_DISABLED)
        except Exception:  # noqa: BLE001
            pass
