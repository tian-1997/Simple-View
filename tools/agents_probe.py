"""探测当前能识别到哪些 agent 会话。

用法：
  python tools/agents_probe.py                       # 实时轮询一次
  python tools/agents_probe.py --watch 10            # 连续轮询 10 秒
  python tools/agents_probe.py --file <jsonl>        # 用历史会话文件校验解析逻辑
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import adapters  # noqa: E402
from adapters import Session  # noqa: E402


def show(rows: list[dict]) -> None:
    if not rows:
        print("  （无活跃会话）")
        return
    for r in rows:
        flag = "▶" if r["running"] else " "
        print(f"  {flag} {r['name']:<10} {r['proj']:<24} {r['status']:<6} "
              f"{r['elapsed']:>6}  {r['action'][:52]}")


def check_file(path: Path) -> None:
    text = str(path).lower()
    if path.suffix != ".jsonl":
        ad = adapters.WorkBuddyAdapter()
        print(json.dumps(ad.poll(), ensure_ascii=False, indent=2))
        return
    if ".pi" in text:
        ad, name = adapters.PiAdapter(), "pi"
    elif ".codex" in text:
        ad, name = adapters.CodexAdapter(), "Codex"
    else:
        print("未知来源，跳过")
        return

    sess = Session(agent=name, letter="?", color="#888", cwd="")
    tailer = adapters.JsonlTailer(path, tail_bytes=4 * 1024 * 1024)
    events = tailer.read_new()
    for ev in events:
        ad._apply(sess, ev)
    print(f"解析 {len(events)} 条事件 → {json.dumps(sess.to_dict(), ensure_ascii=False, indent=2)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", type=int, default=0, help="连续轮询秒数")
    ap.add_argument("--file", default=None)
    args = ap.parse_args()

    if args.file:
        check_file(Path(args.file))
        return 0

    reg = adapters.AgentRegistry()
    deadline = time.time() + args.watch
    first = True
    while True:
        rows = reg.poll()
        if not first and args.watch:
            print()
        first = False
        show(rows)
        if reg.errors:
            for e in reg.errors:
                print(f"  ! {e}")
        if time.time() >= deadline:
            break
        time.sleep(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
