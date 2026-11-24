"""会话适配器：从 Codex / pi / WorkBuddy 的本地日志推断「正在做什么」。

设计原则：
- 只读本地文件，不改任何 agent 的状态；
- 增量 tail，不整文件重读（单文件可达数 MB）；
- 每个适配器独立 try/except，一个坏了不影响其他；
- 状态靠事件解析，静默超时只作为兜底（避免「日志没写但人还在想」被误判为结束）。
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

HOME = Path.home()

CODEX_DIR = HOME / ".codex" / "sessions"
PI_DIR = HOME / ".pi" / "agent" / "sessions"
WB_DIR = HOME / ".workbuddy" / "sessions"

# 语义色，与 QML Theme.js 保持一致
C_RUN = "#5B9DFF"
C_THINK = "#A78BFA"
C_WAIT = "#FFB020"
C_DONE = "#3DD68C"
C_ERR = "#FF5C5C"

RUNNING_TTL = 30.0     # 事件静默超过这个秒数，就不算「正在跑」
RECENT_FILE = 3 * 3600  # 只看 3 小时内写过的会话文件


# --------------------------------------------------------------------------- #
# 增量读取
# --------------------------------------------------------------------------- #
class JsonlTailer:
    """按 offset 增量读 JSONL；文件被截断/替换时自动重置。"""

    def __init__(self, path: Path, tail_bytes: int = 96 * 1024) -> None:
        self.path = path
        self.offset = 0
        self._sig: tuple[int, int] | None = None
        self._tail_bytes = tail_bytes

    def _stat(self) -> os.stat_result | None:
        try:
            return self.path.stat()
        except OSError:
            return None

    def read_new(self) -> list[dict[str, Any]]:
        st = self._stat()
        if st is None:
            return []
        sig = (st.st_ino, st.st_size)
        if self._sig is None:
            # 首次：只读尾巴，避免历史大文件
            self.offset = max(0, st.st_size - self._tail_bytes)
            self._sig = sig
        elif st.st_size < self.offset or st.st_ino != self._sig[0]:
            self.offset = 0  # 被截断或换了文件
        self._sig = sig
        if st.st_size <= self.offset:
            return []

        try:
            with self.path.open("rb") as fh:
                fh.seek(self.offset)
                chunk = fh.read(st.st_size - self.offset)
        except OSError:
            return []

        # 只消费到最后一个换行，半行留到下次
        cut = chunk.rfind(b"\n")
        if cut < 0:
            return []
        self.offset += cut + 1

        out: list[dict[str, Any]] = []
        for raw in chunk[: cut + 1].split(b"\n"):
            raw = raw.strip()
            if not raw:
                continue
            try:
                out.append(json.loads(raw))
            except (ValueError, UnicodeDecodeError):
                continue
        return out


@dataclass
class Session:
    agent: str            # Codex / pi / WorkBuddy
    letter: str
    color: str
    cwd: str
    status: str = "空闲"
    action: str = ""
    started_at: float = field(default_factory=time.time)
    last_event_at: float = field(default_factory=time.time)
    error: str = ""
    session_id: str = ""
    title: str = ""       # 会话名：首条用户消息摘要，取不到就用项目目录名
    pid: int = 0          # 宿主进程（目前只有 WorkBuddy 心跳里带）

    @property
    def proj(self) -> str:
        if not self.cwd:
            return self.agent
        name = Path(self.cwd.rstrip("\\/")).name
        return name or self.cwd

    @property
    def running(self) -> bool:
        return self.status in ("推理中", "执行工具") and (time.time() - self.last_event_at) < RUNNING_TTL

    def to_dict(self) -> dict[str, Any]:
        status = self.status if self.running else ("已完成" if self.status in ("推理中", "执行工具") else self.status)
        color = {
            "执行工具": C_RUN, "推理中": C_THINK, "等确认": C_WAIT,
            "已完成": C_DONE, "出错": C_ERR,
        }.get(status, "#6B7280")
        elapsed = ""
        if self.running:
            sec = max(0, int(time.time() - self.started_at))
            elapsed = f"{sec // 60:02d}:{sec % 60:02d}"
        return {
            "name": self.agent,
            "letter": self.letter,
            "letterColor": self.color,
            "title": self.title or self.proj,
            "proj": self.proj,
            "cwd": self.cwd,
            "pid": self.pid,
            "status": status,
            "statusColor": color,
            "action": self.action or self.cwd,
            "elapsed": elapsed or "—",
            "running": self.running,
        }


def read_head(path: Path) -> dict[str, Any]:
    """读第一行 JSON（session 元信息在文件头，tail 读不到）。"""
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            return json.loads(fh.readline())
    except (OSError, ValueError):
        return {}


def _latest(paths: Iterable[Path], limit: int, window: float = RECENT_FILE) -> list[Path]:
    now = time.time()
    items: list[tuple[float, Path]] = []
    for p in paths:
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if now - m <= window:
            items.append((m, p))
    items.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in items[:limit]]


# --------------------------------------------------------------------------- #
# Codex
# --------------------------------------------------------------------------- #
class CodexAdapter:
    NAME, LETTER, COLOR = "Codex", "C", C_RUN

    def __init__(self) -> None:
        self._tailers: dict[Path, JsonlTailer] = {}
        self._sessions: dict[Path, Session] = {}

    def poll(self) -> list[Session]:
        if not CODEX_DIR.exists():
            return []
        files = _latest(CODEX_DIR.glob("*/*/*/*.jsonl"), limit=3)
        live: dict[Path, Session] = {}
        for path in files:
            tailer = self._tailers.setdefault(path, JsonlTailer(path))
            sess = self._sessions.get(path) or Session(
                agent=self.NAME, letter=self.LETTER, color=self.COLOR, cwd=""
            )
            if not sess.cwd:
                head = read_head(path)
                sess.cwd = (head.get("payload") or {}).get("cwd") or ""
            for ev in tailer.read_new():
                self._apply(sess, ev)
            self._sessions[path] = sess
            live[path] = sess
        self._sessions = live
        self._tailers = {p: t for p, t in self._tailers.items() if p in live}
        return list(live.values())

    def _apply(self, s: Session, ev: dict[str, Any]) -> None:
        ts = _iso_to_epoch(ev.get("timestamp")) or time.time()
        s.last_event_at = max(s.last_event_at, ts)

        if ev.get("type") == "session_meta":
            p = ev.get("payload") or {}
            s.cwd = p.get("cwd") or s.cwd
            s.session_id = p.get("session_id") or s.session_id
            return

        if ev.get("type") != "event_msg" and ev.get("type") != "response_item":
            return
        p = ev.get("payload") or {}
        kind = p.get("type")

        if kind == "task_started":
            s.status, s.started_at = "推理中", ts
            s.action = "正在推理"
        elif kind == "user_message":
            # 会话名取用户第一条指令：后面再出现也不再覆盖
            if not s.title:
                s.title = _clean_text(str(p.get("message") or ""))[:28]
        elif kind == "task_complete":
            s.status, s.action = "已完成", _summarize_last_message(p)
        elif kind in ("custom_tool_call", "function_call"):
            name = p.get("name") or "tool"
            arg = p.get("input") or p.get("arguments") or ""
            s.status, s.action = "执行工具", f"{name} · {_arg_brief(arg)}"
        elif kind in ("custom_tool_call_output", "function_call_output"):
            s.status, s.action = "推理中", "读取工具结果"
        elif kind == "reasoning":
            s.status = "推理中"
        elif kind == "message" and p.get("role") == "assistant":
            s.action = _text_brief(p.get("content")) or s.action
        elif kind == "error":
            s.status, s.action = "出错", str(p.get("message", ""))[:60]


def _clean_text(text: str) -> str:
    """去掉 markdown 记号，压成单行，便于在胶囊里显示。"""
    import re

    text = re.sub(r"[*_`#>•]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _summarize_last_message(p: dict) -> str:
    msg = p.get("last_agent_message")
    if isinstance(msg, str) and msg.strip():
        return _clean_text(msg)[:60]
    return "本轮结束"


def _text_brief(content: Any) -> str:
    if isinstance(content, list):
        for blk in content:
            if isinstance(blk, dict) and blk.get("type") in ("output_text", "text"):
                text = _clean_text((blk.get("text") or ""))
                if text:
                    return text[:60]
    elif isinstance(content, str):
        text = _clean_text(content)
        return text[:60] if text else ""
    return ""


def _arg_brief(arg: Any) -> str:
    data = arg
    if isinstance(arg, str):
        try:
            data = json.loads(arg)
        except ValueError:
            return arg.replace("\n", " ")[:60]
    if isinstance(data, dict):
        for key in ("cmd", "command", "path", "file_path", "query", "pattern"):
            if data.get(key):
                return str(data[key]).replace("\n", " ")[:60]
        return json.dumps(data, ensure_ascii=False)[:60]
    return str(data)[:60]


def _iso_to_epoch(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        from datetime import datetime

        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# pi
# --------------------------------------------------------------------------- #
class PiAdapter:
    NAME, LETTER, COLOR = "pi", "π", C_THINK

    def __init__(self) -> None:
        self._tailers: dict[Path, JsonlTailer] = {}
        self._sessions: dict[Path, Session] = {}

    def poll(self) -> list[Session]:
        if not PI_DIR.exists():
            return []
        files = _latest(PI_DIR.glob("*/*.jsonl"), limit=3)
        live: dict[Path, Session] = {}
        for path in files:
            tailer = self._tailers.setdefault(path, JsonlTailer(path))
            sess = self._sessions.get(path) or Session(
                agent=self.NAME, letter=self.LETTER, color=self.COLOR,
                cwd=_pi_cwd_from_dir(path),
            )
            if not sess.cwd or sess.cwd.startswith("--"):
                sess.cwd = read_head(path).get("cwd") or sess.cwd
            for ev in tailer.read_new():
                self._apply(sess, ev)
            self._sessions[path] = sess
            live[path] = sess
        self._sessions = live
        self._tailers = {p: t for p, t in self._tailers.items() if p in live}
        return list(live.values())

    def _apply(self, s: Session, ev: dict[str, Any]) -> None:
        ts = _iso_to_epoch(ev.get("timestamp")) or time.time()
        s.last_event_at = max(s.last_event_at, ts)
        kind = ev.get("type")

        if kind == "session":
            s.session_id = str(ev.get("id", ""))
            cwd = ev.get("cwd") or (ev.get("session") or {}).get("cwd")
            if cwd:
                s.cwd = cwd
            return
        if kind != "message":
            return

        msg = ev.get("message") or {}
        role = msg.get("role")
        if role == "user":
            s.status, s.started_at = "推理中", ts
            s.action = "收到指令，开始思考"
            if not s.title:
                s.title = _text_brief(msg.get("content"))[:28]
            return
        if role != "assistant":
            return

        blocks = msg.get("content") or []
        tool = next((b for b in blocks if isinstance(b, dict) and b.get("type") == "toolCall"), None)
        stop = msg.get("stopReason")
        if msg.get("errorMessage"):
            s.status, s.action = "出错", str(msg["errorMessage"])[:60]
        elif stop == "toolUse" and tool:
            s.status = "执行工具"
            s.action = f"{tool.get('name', 'tool')} · {_arg_brief(tool.get('arguments'))}"
        elif stop == "stop":
            s.status, s.action = "已完成", _text_brief(blocks) or "本轮结束"
        else:
            s.status = "推理中"


def _pi_cwd_from_dir(path: Path) -> str:
    """pi 的目录名是 cwd 转义（--D--Tyuser-F20-CODE--），只做粗略还原。"""
    stem = path.parent.name
    if stem.startswith("--") and stem.endswith("--"):
        inner = stem.strip("-").replace("--", "\\")
        return inner.replace("-", "\\") if inner else stem
    return stem


# --------------------------------------------------------------------------- #
# WorkBuddy（心跳文件）
# --------------------------------------------------------------------------- #
class WorkBuddyAdapter:
    NAME, LETTER, COLOR = "WorkBuddy", "W", "#2DD4BF"

    def __init__(self) -> None:
        self._seen: dict[int, Session] = {}

    def poll(self) -> list[Session]:
        if not WB_DIR.exists():
            return []
        now = time.time()
        out: list[Session] = []
        for path in WB_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            pid = data.get("pid")
            hb = (data.get("lastHeartbeat") or 0) / 1000.0
            if not pid or not hb:
                continue
            age = now - hb
            if age > 600:          # 10 分钟没心跳，视为已退出
                self._seen.pop(pid, None)
                continue
            sess = self._seen.get(pid)
            if sess is None:
                sess = Session(
                    agent=self.NAME, letter=self.LETTER, color=self.COLOR,
                    cwd=data.get("cwd") or "",
                    started_at=(data.get("startedAt") or 0) / 1000.0 or now,
                    pid=pid,
                )
                self._seen[pid] = sess
            sess.cwd = data.get("cwd") or sess.cwd
            if age < 20:
                sess.status, sess.last_event_at = "推理中", hb
                sess.action = f"会话进行中 · {data.get('mode', 'local')}"
            else:
                sess.status = "已完成"
            out.append(sess)
        return out


# --------------------------------------------------------------------------- #
# 汇总
# --------------------------------------------------------------------------- #
class AgentRegistry:
    def __init__(self) -> None:
        self.adapters = [CodexAdapter(), PiAdapter(), WorkBuddyAdapter()]
        self.errors: list[str] = []

    def poll(self) -> list[dict[str, Any]]:
        sessions: list[Session] = []
        self.errors = []
        for ad in self.adapters:
            try:
                sessions.extend(ad.poll())
            except Exception as exc:  # noqa: BLE001
                self.errors.append(f"{type(ad).__name__}: {exc!r}")
        sessions.sort(key=lambda s: (not s.running, -s.last_event_at))
        return [s.to_dict() for s in sessions[:4]]
