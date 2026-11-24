"""窗口探针：验证 IM 弹窗抓取是否生效。

用法：
  python tools/window_probe.py --seconds 60

运行期间，让别人给你发一条飞书/企微消息（窗口别在最前面，让它弹通知），
终端会打印命中的窗口与抽到的文本，便于确认解析是否正确。

  --all  连非目标进程的小窗也打印，用于排查「为什么没抓到」
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtCore import QCoreApplication, QTimer  # noqa: E402

import notify_win32  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=60)
    args = ap.parse_args()

    app = QCoreApplication(sys.argv[:1])
    watcher = notify_win32.ToastWatcher()
    watcher.start()
    print(f"钩子已安装: {watcher.active}  目标进程: {sorted(notify_win32.PROC_MAP)}")
    print(f"监听 {args.seconds} 秒，期间请触发一条 IM 消息…\n")

    seen = 0
    deadline = time.time() + args.seconds

    def poll() -> None:
        nonlocal seen
        for n in watcher.drain():
            seen += 1
            print(f"[{seen}] {n['app']} | 会话={n['chat']} | 发送人={n['sender']}")
            print(f"     正文={n['body']}")
            print(f"     原始文本={n['_raw']}")
        if time.time() >= deadline:
            print(f"\n结束，共抓到 {seen} 条。")
            watcher.stop()
            app.quit()

    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(300)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
