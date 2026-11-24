"""IM 通知抓取（L1）：监听飞书 / 企业微信 / 微信的弹窗窗口，用 UIA 读文案。

原理：
- 这三家都不走系统 toast，而是自己画一个置顶小窗；
- 用 SetWinEventHook 监听 EVENT_OBJECT_SHOW/CREATE，按进程名过滤；
- 对可疑小窗异步做 UI Automation 文本抽取（放工作线程，绝不阻塞 UI 线程）；
- 抽不到文本就只报「有新消息」（L3 降级）。

用法：
    w = ToastWatcher(); w.start()
    ...
    for n in w.drain():   # 每次轮询取走新通知
        ...
"""
from __future__ import annotations

import ctypes
import os
import queue
import re
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any

USER32 = ctypes.WinDLL("user32", use_last_error=True)
OLE32 = ctypes.WinDLL("ole32", use_last_error=True)

EVENT_OBJECT_CREATE = 0x8000
EVENT_OBJECT_SHOW = 0x8002
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002
OBJID_WINDOW = 0

PROC_MAP = {
    "feishu.exe": ("飞书", "#4E7CFF"),
    "lark.exe": ("飞书", "#4E7CFF"),
    "wxwork.exe": ("企微", "#22B8CF"),
    "wxworkweb.exe": ("企微", "#22B8CF"),
    "wechat.exe": ("微信", "#22C55E"),
    "weixin.exe": ("微信", "#22C55E"),
}

# UIA 文本里会夹带应用自己的名字，写法不一定和展示简称一致（「企微」vs「企业微信」）
_LABELS = {
    "飞书": ("飞书", "Lark", "Feishu"),
    "企微": ("企微", "企业微信", "WeCom"),
    "微信": ("微信", "WeChat"),
}

# 弹窗通常小而方；主窗口会被这条规则挡掉
MAX_POPUP_W = 560
MAX_POPUP_H = 360

# 排障开关：WINISLAND_NOTIFY_DEBUG=1，或存在 %LOCALAPPDATA%\WinIsland\notify-debug.flag
# （双击启动的 exe 带不了环境变量，用标记文件更省事）就打开。
# 打开后所有「像弹窗但被过滤掉」的窗口都会进日志，用来定位「一条 notify 都没有」
# 到底是没弹窗、进程名对不上、还是尺寸被 MAX_POPUP 挡了。
DEBUG = (
    os.environ.get("WINISLAND_NOTIFY_DEBUG") == "1"
    or (
        Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        / "WinIsland" / "notify-debug.flag"
    ).exists()
)

# ---- UIA 抽取口径 ----
# 原生控件（微信/企微）2~3 层就能拿到文本，但飞书是 Electron：
#   d0 Window '飞书'
#   ...  d8 全是 Chromium 外壳（NonClientFrameView / PageToolbarBackButton …）
#   d9  'Chrome Legacy Window'  d10 Document 'messenger'  d15+ Text 才是真内容
# 老口径 depth<=3 / 18 个节点只能看到外壳的工具栏按钮，所以飞书通知永远是
# 「未知发送人 / 未读到内容」。这里按 Web 内容的真实深度定参数。
MAX_DEPTH = 22
MAX_NODES = 160

# Chromium 内建节点的名字：既不是消息内容，也不该占用节点预算（只是不收录，仍要往下走）
NOISE_PREFIXES = (
    "PageToolbar", "HeaderToolbar", "NonClientFrameView", "ContentsView", "ClientView",
    "BrowserUserView", "TabContensView", "Chrome Legacy Window", "Chrome_RenderWidgetHostHWND",
    "MultiWebView", "DesktopWindowXamlSource", "MainWidgetDelegateView",
    "scrollable content", "重新加载", "Address and search bar",
)
# 同样要丢、但用精确匹配更安全的（Document 的 Name 就是 webview 的 id）
NOISE_EXACT = {"messenger"}

WINEVENTPROC = ctypes.WINFUNCTYPE(
    None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
    wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD,
)

USER32.SetWinEventHook.restype = wintypes.HANDLE
USER32.SetWinEventHook.argtypes = (
    wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, WINEVENTPROC,
    wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
)
USER32.UnhookWinEvent.argtypes = (wintypes.HANDLE,)

_pid_name_cache: dict[int, str] = {}


def _proc_name(pid: int) -> str:
    if pid in _pid_name_cache:
        return _pid_name_cache[pid]
    name = ""
    try:
        import psutil

        name = psutil.Process(pid).name().lower()
    except Exception:  # noqa: BLE001
        name = ""
    _pid_name_cache[pid] = name
    return name


def _window_info(hwnd: int) -> tuple[int, str, str, tuple[int, int]] | None:
    pid = wintypes.DWORD()
    USER32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    if not pid.value:
        return None
    if not USER32.IsWindowVisible(wintypes.HWND(hwnd)):
        return None
    rect = wintypes.RECT()
    if not USER32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
        return None
    buf = ctypes.create_unicode_buffer(256)
    USER32.GetClassNameW(wintypes.HWND(hwnd), buf, 256)
    cls = buf.value
    tbuf = ctypes.create_unicode_buffer(512)
    USER32.GetWindowTextW(wintypes.HWND(hwnd), tbuf, 512)
    return pid.value, cls, tbuf.value, (rect.right - rect.left, rect.bottom - rect.top)


def _uia_texts(hwnd: int, max_nodes: int = MAX_NODES, max_depth: int = MAX_DEPTH) -> list[str]:
    """在工作线程里调用；抽窗口的可读文本。

    对 Electron/Chromium（飞书）要一路走到 Document 下面才有内容，所以默认深度给到 22；
    外壳节点的名字不收录但继续遍历，避免 160 个名额被工具栏按钮吃光。
    """
    try:
        OLE32.CoInitializeEx(None, 0x2)  # STA
    except Exception:  # noqa: BLE001
        pass
    out: list[str] = []
    try:
        import uiautomation as auto

        root = auto.ControlFromHandle(hwnd)
        if root is None:
            return out

        def walk(ctrl, depth: int) -> None:
            if len(out) >= max_nodes or depth > max_depth:
                return
            try:
                name = (ctrl.Name or "").strip()
                if (name and name not in NOISE_EXACT
                        and not name.startswith(NOISE_PREFIXES) and name not in out):
                    out.append(name)
                for child in ctrl.GetChildren():
                    walk(child, depth + 1)
            except Exception:  # noqa: BLE001
                return

        walk(root, 0)
    except Exception:  # noqa: BLE001
        pass
    finally:
        try:
            OLE32.CoUninitialize()
        except Exception:  # noqa: BLE001
            pass
    return out


def _best_window(proc_names: tuple[str, ...], min_side: int = 120) -> int:
    """找某个 IM 的主窗口 hwnd —— 只用来预热 UIA（触发 Chromium 开无障碍树）。"""
    import psutil

    pids = {p.pid for p in psutil.process_iter(["pid", "name"])
            if (p.info["name"] or "").lower() in proc_names}
    if not pids:
        return 0
    best = (0, 0)
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(h, _l):
        nonlocal best
        pid = wintypes.DWORD()
        USER32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value not in pids or not USER32.IsWindowVisible(wintypes.HWND(h)):
            return True
        rect = wintypes.RECT()
        if not USER32.GetWindowRect(wintypes.HWND(h), ctypes.byref(rect)):
            return True
        w, hh = rect.right - rect.left, rect.bottom - rect.top
        if w < min_side or hh < min_side:
            return True
        if w * hh > best[0]:
            best = (w * hh, int(h))
        return True

    USER32.EnumWindows(WNDENUMPROC(cb), 0)
    return best[1]


class ToastWatcher:
    def __init__(self) -> None:
        self._hooks: list[int] = []
        self._callbacks: list[Any] = []
        self._queue: queue.Queue[tuple[int, str, str]] = queue.Queue(maxsize=64)
        self._out: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._seen: dict[tuple[int, str], float] = {}
        self._worker: threading.Thread | None = None
        self._running = False
        self._recent_ok: dict[str, float] = {}   # app → 最近一次成功解析的时间
        self.raw_log: list[dict[str, Any]] = []   # 调试用：记录所有命中窗口

    # ---------- 生命周期 ----------
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._worker = threading.Thread(target=self._run, name="toast-uia", daemon=True)
        self._worker.start()
        # 预热：Chromium（飞书）的无障碍树是按需开启的，先碰一次主窗口，
        # 之后弹出的通知小窗才会带内容，否则第一次抽永远是空的。
        threading.Thread(target=self._warm_up, name="uia-warmup", daemon=True).start()
        for event in (EVENT_OBJECT_SHOW, EVENT_OBJECT_CREATE):
            cb = WINEVENTPROC(self._on_event)
            hook = USER32.SetWinEventHook(
                event, event, None, cb, 0, 0,
                WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS,
            )
            if hook:
                self._hooks.append(hook)
                self._callbacks.append(cb)   # 必须持引用，否则回调被回收直接崩

    def _warm_up(self) -> None:
        for names in (("feishu.exe", "lark.exe"), ("wxwork.exe", "wxworkweb.exe")):
            try:
                hwnd = _best_window(names)
                if hwnd:
                    _uia_texts(hwnd, max_nodes=40, max_depth=12)
            except Exception:  # noqa: BLE001
                continue

    def stop(self) -> None:
        self._running = False
        for hook in self._hooks:
            try:
                USER32.UnhookWinEvent(wintypes.HANDLE(hook))
            except Exception:  # noqa: BLE001
                pass
        self._hooks.clear()
        self._callbacks.clear()

    @property
    def active(self) -> bool:
        return bool(self._hooks)

    # ---------- 钩子回调（系统线程 → 只做过滤和入队） ----------
    def _on_event(self, hook, event, hwnd, id_object, id_child, thread, ms) -> None:
        try:
            if id_object != OBJID_WINDOW or not hwnd:
                return
            info = _window_info(hwnd)
            if not info:
                return
            pid, cls, title, (w, h) = info
            name = _proc_name(pid)
            if name not in PROC_MAP:
                if DEBUG:
                    print(f"notify-skip proc={name!r} cls={cls!r} title={title!r} {w}x{h}",
                          file=sys.stderr)
                return
            if w <= 0 or h <= 0 or w > MAX_POPUP_W or h > MAX_POPUP_H:
                if DEBUG:
                    print(f"notify-skip size proc={name!r} cls={cls!r} title={title!r} {w}x{h}",
                          file=sys.stderr)
                return
            key = (int(hwnd), title)
            now = time.time()
            if now - self._seen.get(key, 0) < 5:
                return
            self._seen[key] = now
            try:
                self._queue.put_nowait((int(hwnd), name, title))
            except queue.Full:
                pass
        except Exception:  # noqa: BLE001
            return

    # ---------- 工作线程：UIA 抽文本 ----------
    # 窗口刚 SHOW 时内容往往还没画完（Electron 尤其），一次抽空就降级成「未读到内容」。
    # 这里按 0 / 0.35 / 0.9 秒抽三次，抽到有效内容就停。
    RETRY_DELAYS = (0.0, 0.35, 0.9)

    def _run(self) -> None:
        while self._running:
            try:
                hwnd, proc, title = self._queue.get(timeout=0.4)
            except queue.Empty:
                continue
            notif: dict[str, Any] | None = None
            texts: list[str] = []
            for attempt, delay in enumerate(self.RETRY_DELAYS):
                if delay:
                    time.sleep(delay)
                texts = _uia_texts(hwnd)
                notif = _build_notification(proc, title, texts, hwnd)
                notif["_attempts"] = attempt + 1
                if notif["sender"] != "未知发送人" and not notif["body"].startswith("（有新消息"):
                    break
                try:
                    if not USER32.IsWindow(wintypes.HWND(hwnd)):
                        break       # 通知窗已被收掉，再抽也是空
                except Exception:  # noqa: BLE001
                    break
            if notif is None:
                continue
            now = time.time()
            # 同一条通知会派发多个 hwnd（外壳窗 + 0x0 的渲染子窗），其中通常只有一个能抽到文本。
            # 抽空的那条如果紧跟在一条成功解析之后，就是同一个弹窗的影子事件 —— 丢掉，
            # 否则每次都会多出一条「未知发送人 / 未读到内容」。
            if not texts and now - self._recent_ok.get(proc, 0) < 6:
                if DEBUG:
                    print(f"notify-drop empty echo proc={proc!r} hwnd={hwnd}", file=sys.stderr)
                continue
            if texts:
                self._recent_ok[proc] = now
            print(
                f"notify {notif['app']} sender={notif['sender']!r} body={notif['body'][:40]!r} "
                f"tries={notif['_attempts']} nodes={len(texts)} raw={[t[:24] for t in texts[:6]]}",
                file=sys.stderr,
            )
            with self._lock:
                self.raw_log.append(notif)
                del self.raw_log[:-40]
                self._out.append(notif)
                del self._out[:-20]

    def drain(self) -> list[dict[str, Any]]:
        with self._lock:
            items, self._out = self._out, []
        return items


_TIME_WORDS = {"刚刚", "刚才", "昨天", "前天"}

# 「[图片]」「[表情]」这类占位符是消息内容，不是发送人
_PLACEHOLDER_RE = re.compile(r"^\[[^\[\]]{1,10}\]$")
# 元信息行的收尾词：「…说：」「…发送：」「…发来：」
_SAY_TAIL_RE = re.compile(r"(说|发送|发来|发消息)$")
_PLACE_TAIL_RE = re.compile(r"[中里]$")
_SENTENCE_TAIL = ("：", ":", "。", "！", "？", "!", "?", "，", ",", "；", ";")
# 通知卡片上的按钮文本：正文没抽到时会被当成「最长的一条」顶上来
_BUTTON_WORDS = {"回复", "标为已读", "标记已读", "忽略", "关闭", "查看", "全部已读",
                 "稍后提醒", "打开", "不再提醒", "知道了"}
# 句子语气词收尾 —— 群名几乎不会以这些结尾，用来挡住「会议室等你了」被拆成群名
_CLAUSE_TAIL = ("了", "吗", "呢", "吧", "啊", "的", "过", "呀", "嘛")


def _place_name(text: str) -> str:
    """'在 PCR02软件 中说：' / 'PCR02软件 中' → 'PCR02软件'。"""
    s = text.strip().rstrip("：:").strip()
    if s.startswith("在 "):
        s = s[2:].strip()
    s = _SAY_TAIL_RE.sub("", s).strip()
    s = _PLACE_TAIL_RE.sub("", s).strip()
    return s


def _is_meta(text: str) -> bool:
    """时间戳、「刚刚」这类标签 —— 既不是发送人也不是正文，先剔掉再解析。

    只认几乎不可能是正文的：纯时间、「刚刚/刚才/昨天/前天」。
    「今天」「现在」「上午」单独出现完全可能是消息内容，不能删。
    """
    if text in _TIME_WORDS:
        return True
    if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", text):
        return True
    return bool(re.fullmatch(r"(昨天|前天|今天|星期[一二三四五六日])\s*\d{1,2}:\d{2}", text))


def _split_person_place(text: str) -> tuple[str, str]:
    """'张三 在 项目群' → ('张三', '项目群')；拆不开就原样返回、地点为空。

    两个坑：
    - 名字本身可能含「在」（李在明），所以无空格写法要求两侧都 ≥2 字；
    - 正文也常写成「张三 在 会议室等你了」，以语气词收尾的一律不拆，
      否则半句正文会被当成群名、正文整条丢掉。
    """
    m = (re.match(r"^(?P<who>.+?)\s+在\s*(?P<where>.+)$", text)
         or re.match(r"^(?P<who>.{2,}?)\s*在\s*(?P<where>.{2,})$", text))
    if m:
        who, where = m.group("who").strip(), m.group("where").strip()
        if who and where and not where.endswith(_CLAUSE_TAIL):
            return who, where
    return text.strip(), ""


def _meta_split(text: str) -> tuple[str, str] | None:
    """元信息行 → ('chat', 群名) 或 ('sender', 人名)；不是元信息返回 None。

    判据刻意从严：只认明确带「说 / 发送 / 发来」或以「中 / 里」收尾的句子。
    宁可把群名当正文，也不要把正文当群名丢掉 —— 之前就是因为「凡以冒号结尾且短」
    都算元信息，正文里的「请把日志发我：」被剔除出候选，最后 body 显示成别的东西。

    「张三 在 会议室等你了：」这种正文不会被误判：它虽然含「在」且以冒号结尾，
    但既没有「说」也不以「中/里」收尾，会原样落进内容候选。
    """
    t = text.strip()
    if not t.endswith(("：", ":")):
        return None
    core = t.rstrip("：:").strip()
    if not core:
        return None

    said = bool(_SAY_TAIL_RE.search(core))
    located = bool(_PLACE_TAIL_RE.search(core)) or core.startswith("在 ")
    if not (said or located):
        return None

    body = _place_name(core)
    if not body:
        return None

    who, place = _split_person_place(body)
    if place:
        return ("chat", place)
    return ("chat" if located else "sender", body or who)


def _strip_sender_prefix(text: str, sender: str, aliases: set[str]) -> str:
    """'飞书助手: 翻阅资料,生成答案中。' → '翻阅资料,生成答案中。'

    真机实测（2026-11-24）：飞书助手类通知只有两行，第二行是「发送人简称: 正文」，
    而发送人已经在第一行定下了，正文却带着前缀整行进候选，最后 body 显示成
    「飞书助手: 翻阅资料,生成答案中。」。

    只剥「左半确实是这个发送人」的情况：左半必须命中应用别名，或是已定发送人的
    后缀/前缀。所以正文里的「会议时间: 明天」不会被误伤。
    """
    for sep in ("：", ":"):
        if sep not in text:
            continue
        left, _, right = text.partition(sep)
        left, right = left.strip(), right.strip()
        if not left or not right or len(left) > 24:
            return text
        if left in aliases or (
            sender and sender != "未知发送人"
            and (sender.endswith(left) or left.endswith(sender))
        ):
            return right
        return text
    return text


def _looks_like_sender(text: str) -> bool:
    """窄判据：短、不带句读标点、不是「[图片]」这类占位符、不像半句话。"""
    if not text or len(text) > 32:
        return False
    if text.endswith(_SENTENCE_TAIL) or _PLACEHOLDER_RE.match(text):
        return False
    # 「@所有人」「@张三」是提醒标记；纯数字/符号是未读数或分隔线
    if text.startswith("@"):
        return False
    if re.fullmatch(r"[\d\s\W_]+", text):
        return False
    # 「张三 在 会议室等你了」这种是正文，拆不成「人+群」时也不能当发送人
    return " 在 " not in text


def _build_notification(proc: str, title: str, texts: list[str], hwnd: int) -> dict[str, Any]:
    label, color = PROC_MAP.get(proc, ("通知", "#8A90A0"))
    # UIA 文本里常夹带应用自身名字（飞书 / 企业微信 / Lark…），和展示用的简称不一定一致
    skip = set(_LABELS.get(label, (label,)))
    cleaned = [t for t in (s.strip() for s in texts) if t and t not in skip and not _is_meta(t)]
    sender, chat, body = "", "", ""

    # 飞书通知的 UIA 文本常见形态：
    #   ① ["张三", "在 项目群 中说：", "正文"]
    #   ② ["张三 在 项目群", "正文"]
    #   ③ ["张三: 正文"]
    # 策略：先把「谁 / 在哪」挑出来，剩下的一律进「内容候选」，
    # 正文从内容候选里取最长的一条 —— 绝不从元信息行里取，否则会把
    # 「在 XX 中说：」当成正文（它常比真消息还长）。
    if cleaned:
        head, rest = cleaned[0], cleaned[1:]
        buckets: list[str] = []

        # ① 先定第一行：可能是人、人+群、人: 正文、或「[图片]」这类内容
        if _PLACEHOLDER_RE.match(head):
            buckets.append(head)
        else:
            who, where = _split_person_place(head)
            meta = _meta_split(who)
            if meta is not None:
                if meta[0] == "chat":
                    chat = chat or meta[1]
                elif not sender:
                    sender = sender or meta[1]
            elif re.search(r"[：:]", who):
                # 「张三: 正文」一行形态；冒号右边为空说明是条被截断的正文，归内容
                split_ok = False
                for sep in ("：", ":"):
                    if sep in who:
                        left, _, right = who.partition(sep)
                        if left.strip() and right.strip() and len(left) <= 24:
                            sender = sender or left.strip()
                            buckets.insert(0, right.strip())
                            split_ok = True
                        break
                if not split_ok:
                    buckets.append(who)
            elif _looks_like_sender(who):
                sender = sender or who
            else:
                buckets.append(who)
            if where:
                chat = chat or _place_name(where) or where

        # ② 再扫剩下的行（必须在 head 之后 —— 否则「他说：」会抢走发送人）
        for t in rest:
            t = _strip_sender_prefix(t, sender, skip)
            meta = _meta_split(t)
            if meta is None:
                # 「在 项目群」这种不带冒号的写法：当群名，但仍然保留成内容候选，
                # 免得把正文误吞（正文也常以「在 …」开头）。
                if (not chat and t.startswith("在 ") and len(t) <= 30
                        and not t.endswith(_SENTENCE_TAIL)):
                    chat = _place_name(t) or t[2:].strip()
                buckets.append(t)
            elif meta[0] == "chat":
                chat = chat or meta[1]
            elif not sender:
                sender = meta[1]
            # sender 已确定时，后面的「XX 说：」是正文里的引述，丢弃它本身

        if buckets:
            # 按钮文本只在有别的候选时才剔；整条通知只有「回复」两个字时只能认它
            solid = [b for b in buckets if b not in _BUTTON_WORDS]
            cands = solid or buckets
            # 长度优先、平局取靠后的：通知里正文总在标记（@所有人、[图片]）之后
            body = max(reversed(cands), key=len)

    if not body and title and title != label:
        body = title

    return {
        "app": label,
        "appColor": color,
        "chat": chat or label,
        "sender": sender or "未知发送人",
        "body": body[:80] or "（有新消息，未读到内容）",
        "time": "刚刚",
        "unread": True,
        "_hwnd": hwnd,
        "_raw": texts,
    }
