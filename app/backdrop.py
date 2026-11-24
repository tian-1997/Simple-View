"""自绘玻璃底材：抓取窗口背后的真实桌面，交给 QML 做模糊 + 圆角遮罩。

为什么不用系统 acrylic（material.py 里那条路）：
SetWindowCompositionAttribute 的模糊层由 DWM 合成，**不受 SetWindowRgn 约束**，
窗口是圆角胶囊时，模糊底会是一个方角矩形露在圆角外面（实测确认）。
所以改成自己抓背景：

1. 把本窗口标记成 WDA_EXCLUDEFROMCAPTURE —— 抓屏时不会拍到自己（否则会自我反馈）；
2. 抓窗口覆盖的那块屏幕，按 1/6 降采样（降采样本身就是一次廉价模糊）；
3. QML 侧 Image 拉回原尺寸 + MultiEffect 再做一次高斯模糊 + 圆角遮罩。

代价是每次移动/改尺寸要重抓一次（约 1~3 ms），对 60~600 px 的小窗完全够用。
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import Property, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQuick import QQuickImageProvider

user32 = ctypes.WinDLL("user32", use_last_error=True)

WDA_EXCLUDEFROMCAPTURE = 0x00000011

# 降采样倍数：越大越模糊、越省内存。6 在 40px 高的胶囊上已经足够细腻
DOWNSCALE = 6


class BackdropProvider(QQuickImageProvider):
    """把最新一帧背景交给 QML 的 Image（image://backdrop/<seq>）。"""

    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.Image)
        self.image = QImage()

    def requestImage(self, image_id, size, requested_size):  # noqa: N802, ARG002
        img = self.image
        if size is not None:
            size.setWidth(img.width())
            size.setHeight(img.height())
        return img


class BackdropSampler(QObject):
    """跟随窗口位置/尺寸抓取背景，供玻璃层使用。"""

    frameChanged = Signal()

    def __init__(self, provider: BackdropProvider) -> None:
        super().__init__()
        self.win = None
        self.provider = provider
        self._seq = 0
        self._ok = False
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(90)      # 尺寸动画每帧都变，合并成少数几次抓取
        self._timer.timeout.connect(self.sample)
        # 低频刷新：背后的窗口/壁纸变了，玻璃跟着变（静止时几乎没有代价）
        self._watch = QTimer()
        self._watch.setInterval(2500)
        self._watch.timeout.connect(self.sample)

    # ---------- 生命周期 ----------
    def attach(self, window) -> bool:
        """窗口建好后再绑：QML 里 backdrop 的绑定从第一帧就存在，不会报未定义。"""
        self.win = window
        hwnd = int(window.winId())
        try:
            user32.SetWindowDisplayAffinity(wintypes.HWND(hwnd), WDA_EXCLUDEFROMCAPTURE)
        except Exception:  # noqa: BLE001
            pass
        for sig in ("widthChanged", "heightChanged", "xChanged", "yChanged"):
            handler = getattr(window, sig, None)
            if handler is not None:
                handler.connect(self.schedule)
        self.sample()
        # 窗口刚建好时背后的东西可能还没画出来，补抓几帧
        for delay in (180, 480, 1100):
            QTimer.singleShot(delay, self.sample)
        self._watch.start()
        return self._ok

    def stop(self) -> None:
        self._watch.stop()

    def schedule(self, *_args) -> None:
        if not self._timer.isActive():
            self._timer.start()

    # ---------- 抓取 ----------
    def sample(self) -> bool:
        if self.win is None:
            return False
        try:
            dpr = self.win.devicePixelRatio() or 1.0
            w, h = int(self.win.width()), int(self.win.height())
            if w <= 0 or h <= 0:
                return False
            centre = self.win.position()
            screen = QGuiApplication.screenAt(centre) or QGuiApplication.primaryScreen()
            geo = screen.geometry()
            shot = screen.grabWindow(0)
            if shot.isNull():
                return False

            # 窗口位置换算成该屏的物理像素，取窗口正下方那块
            left = int(round((centre.x() - geo.x()) * dpr))
            top = int(round((centre.y() - geo.y()) * dpr))
            pw, ph = int(round(w * dpr)), int(round(h * dpr))
            # 贴边时裁到屏幕内，避免超界拿到黑边
            left = max(0, min(left, shot.width() - 1))
            top = max(0, min(top, shot.height() - 1))
            pw = max(1, min(pw, shot.width() - left))
            ph = max(1, min(ph, shot.height() - top))

            crop = shot.copy(left, top, pw, ph).toImage()
            small = crop.scaled(
                max(1, pw // DOWNSCALE),
                max(1, ph // DOWNSCALE),
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation,
            )
            self.provider.image = small
            self._seq += 1
            self._ok = True
            self.frameChanged.emit()
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"backdrop sample failed: {exc!r}")
            self._ok = False
            return False

    # ---------- 暴露给 QML ----------
    @Property(str, notify=frameChanged)
    def source(self) -> str:
        # seq 变化 → URL 变化 → Image 重新向 provider 取图
        return f"image://backdrop/frame{self._seq}"

    @Property(bool, notify=frameChanged)
    def hasFrame(self) -> bool:
        return self._ok and not self.provider.image.isNull()
