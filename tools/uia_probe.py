"""诊断：飞书（Electron/Chromium）窗口的 UIA 文本树长什么样。

用来回答「为什么飞书通知抓不到发送人和正文」：
- Chromium 默认不开无障碍树，只有检测到 UIA 客户端才启用（首次查询后要一点时间才建起来）；
- 树比原生控件深，backdrop 里 max_depth=3 / max_nodes=18 可能直接截断。

用法：python tools/uia_probe.py [窗口标题关键字]
"""
from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes

USER32 = ctypes.WinDLL("user32", use_last_error=True)
OLE32 = ctypes.WinDLL("ole32", use_last_error=True)


def windows_of(proc_name: str) -> list[tuple[int, str, str, int, int, bool]]:
    import psutil

    pids = {p.pid for p in psutil.process_iter(["pid", "name"])
            if (p.info["name"] or "").lower() == proc_name}
    out = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(h, _l):
        pid = wintypes.DWORD()
        USER32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value not in pids:
            return True
        cls = ctypes.create_unicode_buffer(256)
        USER32.GetClassNameW(h, cls, 256)
        t = ctypes.create_unicode_buffer(512)
        USER32.GetWindowTextW(h, t, 512)
        r = wintypes.RECT()
        USER32.GetWindowRect(h, ctypes.byref(r))
        out.append((int(h), cls.value, t.value, r.right - r.left, r.bottom - r.top,
                    bool(USER32.IsWindowVisible(h))))
        return True

    USER32.EnumWindows(WNDENUMPROC(cb), 0)
    return out


def dump(hwnd: int, max_depth: int, max_nodes: int) -> tuple[list[tuple[int, str, str]], float]:
    import uiautomation as auto

    rows: list[tuple[int, str, str]] = []
    t0 = time.time()

    def walk(ctrl, depth: int) -> None:
        if depth > max_depth or len(rows) >= max_nodes:
            return
        try:
            name = (ctrl.Name or "").strip()
            if name:
                rows.append((depth, ctrl.ControlTypeName or "", name))
            for child in ctrl.GetChildren():
                walk(child, depth + 1)
        except Exception:  # noqa: BLE001
            return

    root = auto.ControlFromHandle(hwnd)
    if root is not None:
        walk(root, 0)
    return rows, time.time() - t0


def main() -> int:
    proc = sys.argv[1] if len(sys.argv) > 1 else "feishu.exe"
    try:
        OLE32.CoInitializeEx(None, 0x2)
    except Exception:  # noqa: BLE001
        pass

    wins = [w for w in windows_of(proc) if w[5] and w[3] > 100 and w[4] > 100]
    if not wins:
        print(f"没有 {proc} 的可见窗口")
        return 1

    hwnd, cls, title, w, h, _vis = max(wins, key=lambda x: x[3] * x[4])
    print(f"目标窗口 {cls!r} title={title!r} {w}x{h} hwnd={hwnd}")
    print()

    for label, depth, nodes in (("第一遍（冷，触发 Chromium 开无障碍）", 8, 80),
                                ("第二遍（热，等 1.2s）", 8, 80)):
        if label.startswith("第二遍"):
            time.sleep(1.2)
        rows, dt = dump(hwnd, depth, nodes)
        print(f"---- {label} ----")
        print(f"节点 {len(rows)} 个，耗时 {dt * 1000:.0f} ms")
        if rows:
            print(f"最大深度 {max(r[0] for r in rows)}")
            for d, ct, name in rows[:40]:
                print(f"  {'  ' * d}d{d} [{ct}] {name[:70]!r}")
        else:
            print("  （空 —— UIA 一句都没拿到）")
        print()

    # 对照：老逻辑的口径（depth<=3, 18 个节点）
    rows3, dt3 = dump(hwnd, 3, 18)
    print(f"---- 老口径 depth<=3 / 18 节点 ----")
    print(f"节点 {len(rows3)} 个，耗时 {dt3 * 1000:.0f} ms")
    for d, ct, name in rows3[:18]:
        print(f"  d{d} [{ct}] {name[:70]!r}")

    try:
        OLE32.CoUninitialize()
    except Exception:  # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
