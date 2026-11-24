"""验证灵动岛的点击开合：点胶囊 → 展开；再点顶栏 → 收起。

用真实鼠标事件（SetCursorPos + mouse_event）打，不依赖 QML 内部状态，
所以能同时验证「窗口尺寸动画」和「热区位置是否正确」。

    python tools/click_probe.py
    python tools/click_probe.py --title WinIsland --y 20
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import sys
import time

u32 = ctypes.windll.user32

LEFTDOWN = 0x0002
LEFTUP = 0x0004


def find_window(title: str) -> int | None:
    hits: list[int] = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _lparam):
        n = u32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value == title:
                hits.append(hwnd)
        return True

    u32.EnumWindows(cb, 0)
    return hits[0] if hits else None


def rect(hwnd: int) -> tuple[int, int, int, int]:
    r = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def click(x: int, y: int, settle: float = 0.55) -> None:
    u32.SetCursorPos(x, y)
    time.sleep(0.08)
    u32.mouse_event(LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.04)
    u32.mouse_event(LEFTUP, 0, 0, 0, 0)
    time.sleep(settle)


def drag(x: int, y: int, dx: int, steps: int = 12, settle: float = 0.45) -> None:
    """按住后水平移动 dx，用来确认「拖动不会被当成点击」。

    用 SetCursorPos 逐帧设绝对位置，而不是 mouse_event 的相对移动：合成相对移动会被
    系统的指针加速放大，而且系统模态拖动循环对相对移动的响应和真实鼠标不一致。
    """
    u32.SetCursorPos(x, y)
    time.sleep(0.1)
    u32.mouse_event(LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.1)
    for i in range(1, steps + 1):
        u32.SetCursorPos(x + dx * i // steps, y)
        time.sleep(0.03)
    time.sleep(0.1)
    u32.mouse_event(LEFTUP, 0, 0, 0, 0)
    time.sleep(settle)


def describe(tag: str, hwnd: int) -> tuple[int, int, int, int]:
    x, y, w, h = rect(hwnd)
    print(f"{tag:<10} x={x:<6} y={y:<4} w={w:<5} h={h:<5} 中心=({x + w // 2}, {y + h // 2})")
    return x, y, w, h


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="WinIsland")
    ap.add_argument("--y", type=int, default=20, help="点击点相对窗口顶部的 y")
    ap.add_argument("--keep-cursor", action="store_true", help="结束后不还原鼠标位置")
    ap.add_argument("--drag", type=int, default=0,
                    help="改测拖动：按住后水平移动这么多像素，期望窗口跟着走且不展开")
    args = ap.parse_args()

    hwnd = find_window(args.title)
    if not hwnd:
        print(f"没找到标题为 {args.title!r} 的窗口，先 run.bat 起岛", file=sys.stderr)
        return 2

    dpi = u32.GetDpiForWindow(hwnd) if hasattr(u32, "GetDpiForWindow") else 96
    print(f"窗口句柄 {hwnd}，DPI {dpi}（{dpi / 96:.0%} 缩放）")

    saved = wt.POINT()
    u32.GetCursorPos(ctypes.byref(saved))

    if args.drag:
        x0, y0, w0, h0 = describe("拖动前", hwnd)
        cx, cy = x0 + w0 // 2, y0 + args.y
        print(f"\n按住 ({cx}, {cy}) 水平移动 {args.drag}px —— 期望窗口跟走且保持收起")
        drag(cx, cy, args.drag)
        x1, y1, w1, h1 = describe("拖动后", hwnd)

        u32.SetWindowPos(hwnd, 0, x0, y0, 0, 0, 0x0001 | 0x0004)   # NOSIZE | NOZORDER
        time.sleep(0.3)
        if not args.keep_cursor:
            u32.SetCursorPos(saved.x, saved.y)

        moved_ok = abs((x1 - x0) - args.drag) <= 8
        closed_ok = abs(w1 - w0) <= 2 and abs(h1 - h0) <= 2
        print()
        print(f"跟手: {'OK' if moved_ok else 'FAIL'}（位移 {x1 - x0}，期望 {args.drag}）")
        print(f"未误开: {'OK' if closed_ok else 'FAIL'}（{w0}x{h0} → {w1}x{h1}）")
        return 0 if (moved_ok and closed_ok) else 1

    x0, y0, w0, h0 = describe("收起态", hwnd)
    cx = x0 + w0 // 2
    cy = y0 + args.y

    print(f"\n第 1 次点击 ({cx}, {cy}) —— 期望展开（只长高度，宽度不变）")
    click(cx, cy)
    x1, y1, w1, h1 = describe("点击后", hwnd)

    print(f"第 2 次点击 ({cx}, {cy}) —— 期望收起")
    click(cx, cy)
    x2, y2, w2, h2 = describe("再点击后", hwnd)

    if not args.keep_cursor:
        u32.SetCursorPos(saved.x, saved.y)

    ok_open = h1 > h0 and abs(w1 - w0) <= 1
    ok_anchor = abs(x1 - x0) <= 1
    ok_close = abs(w2 - w0) <= 2 and abs(h2 - h0) <= 2
    print()
    print(f"展开: {'OK' if ok_open else 'FAIL'}"
          f"（{w0}x{h0} → {w1}x{h1}，宽度应不变、高度应变大）")
    print(f"左上角不动: {'OK' if ok_anchor else 'FAIL'}（x {x0} → {x1}）")
    print(f"收起: {'OK' if ok_close else 'FAIL'}（{w1}x{h1} → {w2}x{h2}，初始 {w0}x{h0}）")
    return 0 if (ok_open and ok_anchor and ok_close) else 1


if __name__ == "__main__":
    raise SystemExit(main())
