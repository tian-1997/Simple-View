"""批量渲染设计评审图。

自绘玻璃之后，窗口自身抓图就已包含真实的模糊背景，评审图直接就是成品，
不再需要整屏截图 + 手动裁切。

用法：
    python tools/render_showcase.py                # 渲染全部状态
    python tools/render_showcase.py panel light    # 只渲染指定状态 / 主题
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "preview"

# (快照状态, 主题, 输出名)
CASES = [
    ("panel", "dark", "panel_dark"),
    ("panel", "light", "panel_light"),
    ("active", "dark", "pill_dark"),
    ("active", "light", "pill_light"),
    ("alert", "dark", "panel_alert"),
    ("idle", "light", "pill_idle"),
    ("think_pill", "dark", "pill_think"),
    ("done_pill", "dark", "pill_done"),
]


def shoot(state: str, theme: str, name: str) -> bool:
    target = OUT / f"{name}.png"
    cmd = [
        sys.executable, "-u", "app/main.py",
        "--snapshot", state,
        "--showcase",
        "--theme", theme,
        "--out", str(target),
        "--settle", "2200",
    ]
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=150)
    for line in res.stdout.splitlines():
        if line.startswith(("glass", "saved")):
            print("   ", line)
    if not target.exists():
        print(f"!! {name} 渲染失败：{res.stderr[-500:]}")
        return False
    return True


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    only = sys.argv[1:] or None
    failed = 0
    for state, theme, name in CASES:
        if only and not any(k in (state, theme, name) for k in only):
            continue
        print(f"[{name}] state={state} theme={theme}")
        if not shoot(state, theme, name):
            failed += 1
    print(f"done, {failed} failed" if failed else "done")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
