"""列出进程的 cwd / 父进程链 / 是否有可见窗口，用来确定「点击会话该唤醒谁」。

    python tools/proc_probe.py                # 只看候选（终端 / agent / IM）
    python tools/proc_probe.py --all          # 全部有可见窗口的进程
    python tools/proc_probe.py --cwd D:\\proj  # 指定一个 cwd 看谁在里面跑
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
from pathlib import Path

import psutil

u32 = ctypes.windll.user32

AGENT_HINTS = ("codex", "pi", "node", "python", "workbuddy")
HOST_HINTS = ("windowsterminal", "wt", "conhost", "powershell", "pwsh", "cmd",
              "wezterm", "alacritty", "code", "cursor", "tabby")
IM_HINTS = ("wechat", "weixin", "feishu", "lark", "wxwork", "wework")


def window_title_for_pid(pid: int) -> str:
    """EnumWindows 找该 pid 的顶层可见窗口标题。"""
    hits: list[str] = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _l):
        if not u32.IsWindowVisible(hwnd):
            return True
        owner = wt.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value != pid:
            return True
        n = u32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(hwnd, buf, n + 1)
            hits.append(buf.value)
        return True

    u32.EnumWindows(cb, 0)
    return hits[0] if hits else ""


def safe_cwd(proc: psutil.Process) -> str:
    try:
        return proc.cwd()
    except (psutil.Error, OSError):
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="列出所有有窗口的进程")
    ap.add_argument("--cwd", default="", help="只显示 cwd 以该前缀开头的进程")
    args = ap.parse_args()

    rows = []
    for p in psutil.process_iter(["pid", "name", "exe"]):
        try:
            name = (p.info["name"] or "").lower()
            exe = (p.info["exe"] or "").lower()
            cwd = safe_cwd(p)
            title = window_title_for_pid(p.info["pid"])

            if args.cwd:
                if not cwd.lower().startswith(args.cwd.lower()):
                    continue
            elif not args.all:
                blob = f"{name} {exe} {cwd.lower()}"
                if not any(h in blob for h in AGENT_HINTS + HOST_HINTS + IM_HINTS):
                    continue
                if not (title or cwd):
                    continue

            rows.append((p.info["pid"], p.info["name"], cwd, title, p))
        except (psutil.Error, OSError):
            continue

    for pid, name, cwd, title, p in rows:
        chain = []
        try:
            for anc in p.parents():
                chain.append(f"{anc.name()}({anc.pid})")
                if len(chain) >= 4:
                    break
        except psutil.Error:
            pass
        print(f"{pid:>6}  {name:<22} win={title[:42]!r}")
        if cwd:
            print(f"        cwd={cwd}")
        if chain:
            print(f"        up={' < '.join(chain)}")
    print(f"\n共 {len(rows)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
