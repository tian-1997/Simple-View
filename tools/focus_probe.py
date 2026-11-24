"""验证 launcher.focus：点一下「岛」→ 目标窗口是否被拉到最前，且**不被锁定**。

为什么这么绕：Windows 的前台锁只允许「刚收到用户输入」的进程抢焦点。
真实的岛是 `WindowDoesNotAcceptFocus`（点了也不会变成前台窗口），所以这里也造一个
同样不抢焦点的假岛，用真实鼠标事件点它 —— 复现真机路径，而不是在拿到焦点的
进程里测一个必然成立的情况。

    python tools/focus_probe.py
"""
from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
import launcher  # noqa: E402

u32 = ctypes.windll.user32
u32.GetForegroundWindow.restype = ctypes.c_void_p
u32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
u32.GetWindowLongW.restype = ctypes.c_long
LEFTDOWN, LEFTUP = 0x0002, 0x0004
GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008


def topmost(hwnd: int) -> bool:
    return bool(u32.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE) & WS_EX_TOPMOST)


def click(x: int, y: int) -> None:
    u32.SetCursorPos(x, y)
    time.sleep(0.08)
    u32.mouse_event(LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    u32.mouse_event(LEFTUP, 0, 0, 0, 0)
    time.sleep(0.35)


def main() -> int:
    app = QApplication(sys.argv[:1])

    island = QLabel("fake island")
    island.setWindowTitle("WinIsland Probe Island")
    island.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus
                          | Qt.WindowStaysOnTopHint)
    island.setGeometry(200, 160, 220, 48)
    island.show()

    target = QLabel("probe target window")
    target.setWindowTitle("WinIsland Probe Target")
    target.setGeometry(200, 320, 360, 180)
    target.show()

    results: list[tuple[str, bool | None]] = []

    def run() -> None:
        th = int(target.winId())
        saved = wintypes.POINT()
        u32.GetCursorPos(ctypes.byref(saved))

        # 用真实点击打在假岛中心：进程拿到输入，但前台窗口不变（DoesNotAcceptFocus）
        click(200 + 110, 160 + 24)
        desktop_active = u32.GetForegroundWindow() is not None

        how = launcher.focus(th)
        results.append((f"focus 返回「{how}」", how == "前台" or not desktop_active))
        results.append(("没有被设成 topmost（不锁定）", not topmost(th)))

        if desktop_active:
            results.append((f"目标是前台（fg={u32.GetForegroundWindow()} 期望 {th}）",
                            u32.GetForegroundWindow() == th))
        else:
            results.append(("目标是前台 —— 跳过：桌面未激活（锁屏 / 黑屏），谁也抢不到前台",
                            None))

        u32.SetCursorPos(saved.x, saved.y)
        for text, ok in results:
            tag = "OK  " if ok else ("SKIP" if ok is None else "FAIL")
            print(f"{tag} {text}")
        island.close()
        target.close()
        app.quit()

    QTimer.singleShot(500, run)
    app.exec()
    return 0 if all(ok is not False for _, ok in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
