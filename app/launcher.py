"""点会话 / 通知 → 把对应窗口拉到最前。

Windows 没有「进程 → 窗口」的直接 API，只能自己枚举，按可信度从高到低试：

1. 有 pid（WorkBuddy 心跳带的）→ 该 pid 及其父链 / 子进程上的可见窗口；
2. 按已知宿主进程名找 —— Codex 桌面版是 ``ChatGPT.exe``，WorkBuddy 是
   ``WorkBuddy.exe``，IM 就是各自的 exe；
3. CLI agent（codex / pi）跑在终端里，只能按 cwd 匹配进程再找它的祖先窗口；
4. 实在找不到就打开资源管理器到项目目录，至少不是白点一下。

Windows 有前台锁（前台进程才有权抢焦点），单纯 ``SetForegroundWindow`` 经常静默失败。
这里先 AttachThreadInput 到当前前台线程再抢，失败再退回「轻敲一次 Alt」解锁。

只做「置前」，不改窗口的置顶属性 —— 点了就把窗口激活到最前，不钉住、不锁定，
之后切到别的窗口它照常退到后面。
"""
from __future__ import annotations

import ctypes
import subprocess
import sys
from ctypes import wintypes

import psutil

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindowEnabled.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.POINTER(wintypes.ULONG)]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT,
                                         ctypes.c_void_p, wintypes.UINT]
user32.SystemParametersInfoW.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

SW_RESTORE = 9
SW_SHOW = 5
VK_MENU = 0x12
KEYEVENTF_KEYUP = 0x0002

# 前台锁超时（SystemParametersInfo）：默认 200000ms，临时设 0 可以让抢焦点放行
SPI_GETFOREGROUNDLOCKTIMEOUT = 0x2000
SPI_SETFOREGROUNDLOCKTIMEOUT = 0x2001


# 这些窗口永远不是我们要找的目标
SKIP_TITLES = {"Program Manager", "Default IME", "MSCTFIME UI", "Windows Input Experience"}

# product → 可能的宿主进程名（小写）
HOST_EXE: dict[str, tuple[str, ...]] = {
    "codex": ("chatgpt.exe", "codex.exe", "code.exe"),
    "workbuddy": ("workbuddy.exe",),
    "pi": ("windowsterminal.exe", "wt.exe", "pwsh.exe", "powershell.exe",
           "wezterm-gui.exe", "alacritty.exe", "tabby.exe"),
    "wechat": ("wechat.exe", "weixin.exe"),
    "feishu": ("feishu.exe", "lark.exe"),
    "wecom": ("wxwork.exe", "wework.exe"),
}

# 没有 cwd / pid 线索时的兜底窗口标题关键词
TITLE_HINT: dict[str, str] = {
    "wechat": "微信",
    "feishu": "飞书",
    "wecom": "企业微信",
}


def visible_windows() -> list[tuple[int, int, str]]:
    """[(hwnd, pid, title)]：只收可见、有标题的顶层窗口。"""
    out: list[tuple[int, int, str]] = []

    def cb(hwnd, _lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            n = user32.GetWindowTextLengthW(hwnd)
            if n <= 0:
                return True
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            title = buf.value.strip()
            if not title or title in SKIP_TITLES or title == "WinIsland":
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            out.append((int(hwnd), pid.value, title))
        except Exception:  # noqa: BLE001
            pass
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return out


def _pid_family(pid: int) -> set[int]:
    """pid 及其祖先、直接子进程 —— Electron / CEF 的窗口常常挂在别的进程上。"""
    try:
        proc = psutil.Process(pid)
    except psutil.Error:
        return {pid}
    ids = {pid}
    try:
        for anc in proc.parents():
            ids.add(anc.pid)
            if len(ids) >= 8:
                break
    except psutil.Error:
        pass
    try:
        for child in proc.children(recursive=False):
            ids.add(child.pid)
    except psutil.Error:
        pass
    return ids


def _pids_by_exe(names: tuple[str, ...]) -> list[int]:
    hits: list[int] = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = (proc.info["name"] or "").lower()
            if name in names:
                hits.append(proc.info["pid"])
        except psutil.Error:
            continue
    return hits


def _pids_by_cwd(cwd: str) -> list[int]:
    needle = cwd.rstrip("\\/").lower()
    if not needle:
        return []
    hits: list[int] = []
    for proc in psutil.process_iter(["pid"]):
        try:
            pcwd = (proc.cwd() or "").rstrip("\\/").lower()
        except (psutil.Error, OSError):
            continue
        if pcwd == needle or pcwd.startswith(needle + "\\"):
            hits.append(proc.info["pid"])
    return hits


def _pick(windows: list[tuple[int, int, str]], pids: set[int]) -> int | None:
    for hwnd, pid, _title in windows:
        if pid in pids:
            return hwnd
    return None


def _activate(hwnd: int) -> bool:
    """把窗口拉到前台。

    ``SetForegroundWindow`` 受前台锁约束：调用方不是「刚收到用户输入」的进程时，
    它只会闪任务栏。真实场景里我们是靠用户点岛拿到输入的，但锁屏 / 切换用户后
    （GetForegroundWindow() == NULL）、或者前台窗口属于提权进程时，仍然会被拒。
    所以这里按代价从小到大试三条路：
      1. AttachThreadInput 到前台线程和目标线程，共享输入状态后抢焦点；
      2. 轻敲一次 Alt —— 有些系统只认「有按键」的前台请求；
      3. 临时把前台锁超时设为 0（进程级，马上还原），最后一招。
    """
    if user32.IsIconic(wintypes.HWND(hwnd)):
        user32.ShowWindow(wintypes.HWND(hwnd), SW_RESTORE)
    else:
        user32.ShowWindow(wintypes.HWND(hwnd), SW_SHOW)

    if user32.GetForegroundWindow() == hwnd:
        return True

    cur_tid = kernel32.GetCurrentThreadId()
    fg = user32.GetForegroundWindow()
    tids = set()
    if fg:
        tids.add(user32.GetWindowThreadProcessId(wintypes.HWND(fg), None))
    tids.add(user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), None))
    tids.discard(0)
    tids.discard(cur_tid)

    attached: list[int] = []
    for tid in tids:
        if user32.AttachThreadInput(cur_tid, tid, True):
            attached.append(tid)
    try:
        user32.BringWindowToTop(wintypes.HWND(hwnd))
        if user32.SetForegroundWindow(wintypes.HWND(hwnd)) or \
                user32.GetForegroundWindow() == hwnd:
            return True

        user32.keybd_event(VK_MENU, 0, 0, None)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, None)
        if user32.SetForegroundWindow(wintypes.HWND(hwnd)) or \
                user32.GetForegroundWindow() == hwnd:
            return True

        old = wintypes.DWORD(0)
        got = user32.SystemParametersInfoW(SPI_GETFOREGROUNDLOCKTIMEOUT, 0,
                                           ctypes.byref(old), 0)
        if got:
            user32.SystemParametersInfoW(SPI_SETFOREGROUNDLOCKTIMEOUT, 0,
                                         ctypes.c_void_p(0), 0)
            try:
                if user32.SetForegroundWindow(wintypes.HWND(hwnd)) or \
                        user32.GetForegroundWindow() == hwnd:
                    return True
            finally:
                user32.SystemParametersInfoW(SPI_SETFOREGROUNDLOCKTIMEOUT, 0,
                                             ctypes.c_void_p(old.value), 0)
        return False
    finally:
        for tid in attached:
            user32.AttachThreadInput(cur_tid, tid, False)


def focus(hwnd: int) -> str:
    """把窗口拉到最前，返回一句说明（写进日志，也用来核对行为）。

    只抢前台，不动窗口的 topmost 属性：激活后用户切走，它照常退到后面。
    """
    return "前台" if _activate(hwnd) else "置前失败"


def _open_folder(path: str) -> bool:
    if not path:
        return False
    try:
        subprocess.Popen(["explorer", path])
        return True
    except OSError:
        return False


def find_window(product: str, cwd: str = "", pid: int = 0) -> tuple[int, str] | None:
    """按可信度依次尝试，返回 (hwnd, 说明)。"""
    windows = visible_windows()

    if pid:
        hwnd = _pick(windows, _pid_family(pid))
        if hwnd:
            return hwnd, f"pid {pid} 同族窗口"

    names = HOST_EXE.get(product, ())
    if names:
        for host_pid in _pids_by_exe(names):
            hwnd = _pick(windows, _pid_family(host_pid))
            if hwnd:
                return hwnd, f"{product} 宿主 {names[0]}"

    if cwd:
        for work_pid in _pids_by_cwd(cwd):
            hwnd = _pick(windows, _pid_family(work_pid))
            if hwnd:
                return hwnd, f"cwd 匹配进程 {work_pid}"

    hint = TITLE_HINT.get(product, "")
    if hint:
        for hwnd, _pid, title in windows:
            if hint in title:
                return hwnd, f"标题含「{hint}」"

    return None


def open_agent(product: str, cwd: str = "", pid: int = 0) -> str:
    """打开某个 agent 会话：优先唤醒已有窗口，实在没有就开项目目录。"""
    hit = find_window(product, cwd, pid)
    if hit:
        hwnd, why = hit
        return f"{focus(hwnd)}({why})"
    if _open_folder(cwd):
        return f"explorer({cwd})"
    return "未找到可打开的窗口"


def open_im(product: str) -> str:
    """打开 IM 主窗口。"""
    hit = find_window(product)
    if hit:
        hwnd, why = hit
        return f"{focus(hwnd)}({why})"
    return f"未找到 {product} 窗口"


if __name__ == "__main__":  # 手动试跑：python app/launcher.py wechat
    target = sys.argv[1] if len(sys.argv) > 1 else "codex"
    cwd_arg = sys.argv[2] if len(sys.argv) > 2 else ""
    print(open_agent(target, cwd_arg))
