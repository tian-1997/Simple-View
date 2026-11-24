"""WinIsland 启动入口。

用法：
  python app/main.py                          # 桌面常驻（真实数据）
  python app/main.py --state panel            # 指定演示状态
  python app/main.py --theme light            # 固定浅色
  python app/main.py --snapshot panel --out p.png        # 窗口自身渲染图（不含系统模糊）
  python app/main.py --snapshot panel --showcase --out s.png  # 叠在背景上的真实合成图（含 DWM 模糊）
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wintypes
import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QPoint, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import (QColor, QCursor, QFont, QGuiApplication, QIcon, QImage,
                           QLinearGradient, QPainter, QPixmap)
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

APP_DIR = Path(__file__).resolve().parent
# PyInstaller 单文件模式下，入口脚本的 __file__ 在解包目录根上（_MEIPASS/main.py），
# 而 app/ 是作为数据目录整个塞进去的 —— 所以冻结后要显式指回 _MEIPASS/app，
# 否则 QML 和 assets 全都找不到（表现为启动即 "QML 加载失败"）。
FROZEN = bool(getattr(sys, "frozen", False))
ROOT_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR.parent)) if FROZEN else APP_DIR.parent
if FROZEN:
    APP_DIR = ROOT_DIR / "app"
QML_DIR = APP_DIR / "qml"
ASSETS_DIR = ROOT_DIR / "assets"
sys.path.insert(0, str(APP_DIR))

import adapters  # noqa: E402
import backdrop  # noqa: E402
import launcher  # noqa: E402
import material  # noqa: E402
import mock  # noqa: E402
import notify_win32  # noqa: E402
import theme as theme_mod  # noqa: E402
import tokens  # noqa: E402

PRODUCT_OF_AGENT = {"Codex": "codex", "pi": "pi", "WorkBuddy": "workbuddy"}
PRODUCT_OF_APP = {"微信": "wechat", "飞书": "feishu", "企微": "wecom", "企业微信": "wecom"}

BRAND_ICON = ASSETS_DIR / "branding" / "app-icon.png"
LOG_PATH = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "WinIsland" / "WinIsland.log"
MUTEX_NAME = "Local\\WinIsland.SingleInstance"


def _ensure_streams() -> None:
    """打包成窗口程序后 sys.stdout / sys.stderr 是 None。

    代码里到处是 ``print(..., file=sys.stderr)`` 的排障日志，一旦为 None 就会
    直接 AttributeError，而且是在插槽里 —— 表现为点一下胶囊整个进程消失。
    所以这里把它们接到 %LOCALAPPDATA%\\WinIsland\\WinIsland.log，既能跑也能查。
    """
    if sys.stderr is not None and sys.stdout is not None:
        return
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if LOG_PATH.exists() and LOG_PATH.stat().st_size > 2 * 1024 * 1024:
            LOG_PATH.unlink()
        stream = open(LOG_PATH, "a", encoding="utf-8", buffering=1)
        stream.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} 启动 ===\n")
    except OSError:
        stream = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = stream
    if sys.stdout is None:
        sys.stdout = stream


_ensure_streams()

# 胶囊只有一条边框，多会话并存时按「最该被看见」的取：出错 > 等确认 > 推理 > 工具 > 完成
KIND_PRIORITY = ("error", "wait", "think", "tool", "done", "idle")
PILL_MAX_LOGOS = 4


def _kind_rank(agent: dict) -> int:
    kind = tokens.kind_of(agent.get("status", ""))
    return KIND_PRIORITY.index(kind) if kind in KIND_PRIORITY else len(KIND_PRIORITY)

# 无边框窗口拖动：把「按下」伪造成点在标题栏，交给系统模态拖动循环
WM_NCLBUTTONDOWN = 0x00A1
WM_LBUTTONUP = 0x0202
HTCAPTION = 2
_USER32 = ctypes.WinDLL("user32", use_last_error=True)
_USER32.ReleaseCapture.argtypes = []
_USER32.ReleaseCapture.restype = wintypes.BOOL
_USER32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_USER32.SendMessageW.restype = wintypes.LPARAM
_USER32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_USER32.PostMessageW.restype = wintypes.BOOL


class Bridge(QObject):
    """QML 与 Python 之间的桥：只做数据整形与动作转发，不改数据语义。"""

    dataChanged = Signal()
    expandedChanged = Signal()
    focusChanged = Signal()

    def __init__(self, state: dict | None = None, live: bool = False,
                 theme_bridge: theme_mod.ThemeBridge | None = None) -> None:
        super().__init__()
        self._live = live
        self._expanded = False
        self._focus = False
        self._agents: list[dict] = []
        self._notifs: list[dict] = []
        self._win = None
        self._dragging = False
        self._theme = theme_bridge
        self._material: material.GlassMaterial | None = None
        self._menu_provider = None
        if state:
            self.apply_state(state)

    # ---------- 绑定 ----------
    def bind(self, material_ctl: material.GlassMaterial, menu_provider) -> None:
        self._material = material_ctl
        self._menu_provider = menu_provider

    # ---------- 数据 ----------
    def apply_state(self, state: dict) -> None:
        self._agents = state.get("agents", [])
        self._notifs = state.get("notifs", [])
        self._expanded = bool(state.get("expanded", False))
        self.dataChanged.emit()
        self.expandedChanged.emit()

    @Property("QVariantList", notify=dataChanged)
    def agents(self) -> list:
        return self._agents

    @Property("QVariantList", notify=dataChanged)
    def notifs(self) -> list:
        if self._focus:
            return []
        return self._notifs

    @Property(int, notify=dataChanged)
    def unread(self) -> int:
        if self._focus:
            return 0
        return sum(1 for n in self._notifs if n.get("unread"))

    @Property(int, notify=dataChanged)
    def agentsRunning(self) -> int:
        return sum(1 for a in self._agents if a.get("running"))

    @Property(bool, notify=dataChanged)
    def attention(self) -> bool:
        """有会话在等确认或出错，胶囊要点出来。"""
        return any(tokens.kind_of(a.get("status", "")) in ("wait", "error") for a in self._agents)

    @Property(str, notify=dataChanged)
    def pillText(self) -> str:
        # 优先级：错误 > 等待确认 > 运行中 > 刚完成 > 未读数量 > 空闲
        # 胶囊固定 240 宽，文案必须短：agent 是谁由左边的 logo 表示，这里只说状态。
        for kind in ("error", "wait"):
            hit = next((a for a in self._agents if tokens.kind_of(a.get("status", "")) == kind), None)
            if hit:
                return hit.get("status", "")
        # 按 agent 去重：胶囊上摆的是 logo，文字也就该数 agent，不然「2 个会话」对不上 1 个 logo
        running = {a.get("name") or id(a) for a in self._agents if a.get("running")}
        if running:
            return f"{len(running)} 个运行中"
        done = [a for a in self._agents if tokens.kind_of(a.get("status", "")) == "done"]
        if done:
            return f"{len(done)} 个已完成" if len(done) > 1 else "已完成"
        if self.unread:
            return f"{self.unread} 条新消息"
        if self._agents:
            return "全部空闲"
        return "没有会话"

    @Property(bool, constant=True)
    def liveMode(self) -> bool:
        return self._live

    # ---------- 胶囊上的主 agent ----------
    def _primary_agent(self) -> dict | None:
        """胶囊边框代表谁：按状态紧急度取，同状态优先正在跑的。"""
        if not self._agents:
            return None
        # min 稳定，同优先级保持 _agents 原有的「最近有动静」顺序
        return min(self._agents, key=lambda a: (_kind_rank(a), 0 if a.get("running") else 1))

    @Property("QVariantList", notify=dataChanged)
    def pillAgents(self) -> list:
        """收起态的 logo 列表：一个 agent 一个，按状态紧急度排，最多 4 个。

        同一个 agent 可能同时开多个会话（比如两个 Codex），这里按 agent 去重 ——
        用户看的是「谁在干活」，不是「开了几个窗口」。
        """
        rows: list[dict] = []
        seen: set[str] = set()
        for a in sorted(self._agents, key=_kind_rank):
            product = PRODUCT_OF_AGENT.get(a.get("name", ""), "")
            if not product or product in seen:
                continue
            seen.add(product)
            kind = tokens.kind_of(a.get("status", ""))
            rows.append({
                "product": product,
                "kind": kind,
                # 空闲的压暗，避免和真在跑的一起抢注意力
                "dim": kind == "idle" and not a.get("running"),
            })
            if len(rows) >= PILL_MAX_LOGOS:
                break
        return rows

    @Property(str, notify=dataChanged)
    def pillKind(self) -> str:
        """整条胶囊外圈的边框色：多会话时取最紧急的那个。"""
        a = self._primary_agent()
        return tokens.kind_of(a.get("status", "")) if a else "idle"

    # ---------- 打开 ----------
    @Slot(str, str, int)
    def openAgent(self, product: str, cwd: str, pid: int) -> None:
        try:
            how = launcher.open_agent(product, cwd, int(pid))
        except Exception as exc:  # noqa: BLE001
            print(f"open agent failed: {exc!r}", file=sys.stderr)
        else:
            print(f"open agent {product!r} -> {how}", file=sys.stderr)
        self.setExpanded(False)     # 人要过去干活了，岛让位

    @Slot(str)
    def openIm(self, product: str) -> None:
        try:
            how = launcher.open_im(product)
        except Exception as exc:  # noqa: BLE001
            print(f"open im failed: {exc!r}", file=sys.stderr)
        else:
            print(f"open im {product!r} -> {how}", file=sys.stderr)
        self.setExpanded(False)

    @Property(bool, notify=focusChanged)
    def focusMode(self) -> bool:
        return self._focus

    # ---------- 视觉映射 ----------
    @Slot(str, result=str)
    def productOf(self, agent_name: str) -> str:
        return PRODUCT_OF_AGENT.get(agent_name, "")

    @Slot(str, result=str)
    def notifyProduct(self, app_label: str) -> str:
        return PRODUCT_OF_APP.get(app_label, "")

    # ---------- 窗口 ----------
    def attach(self, window) -> None:
        self._win = window

    @Property(bool, notify=expandedChanged)
    def expanded(self) -> bool:
        return self._expanded

    @Slot(bool)
    def setExpanded(self, value: bool) -> None:
        value = bool(value)
        if value == self._expanded:
            return
        self._expanded = value
        self.endDrag()          # 胶囊/面板切换时会话行可能被隐藏，拖动状态不能留到下一次
        self.expandedChanged.emit()

    @Slot()
    def toggle(self) -> None:
        self.setExpanded(not self._expanded)

    @Slot()
    def hideWindow(self) -> None:
        if self._win:
            self._win.hide()

    @Slot()
    def openMenu(self) -> None:
        if self._menu_provider:
            self._menu_provider()

    # ---------- 动作 ----------
    @Slot()
    def markAllRead(self) -> None:
        for n in self._notifs:
            n["unread"] = False
        self.dataChanged.emit()

    @Slot()
    def clearRead(self) -> None:
        self._notifs = [n for n in self._notifs if n.get("unread")]
        self.dataChanged.emit()

    @Slot()
    def toggleFocus(self) -> None:
        self._focus = not self._focus
        self.focusChanged.emit()
        self.dataChanged.emit()

    @Slot()
    def toggleTheme(self) -> None:
        if not self._theme:
            return
        self._theme.toggleTheme()
        if self._material:
            ok = self._material.set_mode(self._theme.mode)
            self._theme.set_material_ready(ok)

    # ---------- 实时数据 ----------
    # 拖动期间拒绝更新：系统拖动是嵌套事件循环，这时改模型会让 Repeater 重建行对象，
    # 而这些对象正处在信号处理器栈上 —— Qt 会直接崩。丢一次更新没关系，下一轮轮询会补。
    def set_agents(self, rows: list[dict]) -> None:
        if self._dragging:
            return
        self._agents = rows
        self.dataChanged.emit()

    def set_notifs(self, rows: list[dict]) -> None:
        if self._dragging:
            return
        self._notifs = rows
        self.dataChanged.emit()

    # ---------- 拖动 ----------
    @Slot()
    def beginDrag(self) -> None:
        """交给系统做窗口拖动。

        无边框窗口的标准做法：ReleaseCapture 后伪造一次「点在标题栏」，
        Windows 会自己跑模态拖动循环。比手工按光标位移算位置可靠得多 ——
        手算在高 DPI + 鼠标加速下会累积误差，实测拖 90px 能偏到 450px。
        """
        if not self._win:
            return
        self._dragging = True
        hwnd = wintypes.HWND(int(self._win.winId()))
        try:
            _USER32.ReleaseCapture()
            _USER32.SendMessageW(hwnd, WM_NCLBUTTONDOWN, HTCAPTION, 0)
        finally:
            self._dragging = False
            # 系统拖动把 release 吞了，Qt 的 MouseArea 会一直以为按着：
            # 补一个 WM_LBUTTONUP 让它复位，否则紧接着的第一次点击会被当成「还在拖」而不响应。
            _USER32.PostMessageW(hwnd, WM_LBUTTONUP, 0, 0)

    def is_dragging(self) -> bool:
        """拖动跑在系统模态循环里，期间不能刷新会话数据。

        否则 Repeater 会在信号处理器还在栈上时重建行对象，Qt 直接报
        "Object destroyed while one of its QML signal handlers is in progress" 并崩溃。
        """
        return self._dragging

    @Slot()
    def dragMove(self) -> None:
        # 位置由系统拖动接管，这里留空只是为了 QML 不用改调用点
        return

    @Slot()
    def endDrag(self) -> None:
        # 系统拖动循环里松手后没有需要清的状态，保留空实现让 QML 调用点统一
        return


# --------------------------------------------------------------------------- #
# 引擎与窗口
# --------------------------------------------------------------------------- #
def _load_engine(bridge: Bridge, theme_bridge: theme_mod.ThemeBridge,
                 extra: dict | None = None,
                 providers: dict | None = None) -> tuple[QQmlApplicationEngine, object]:
    engine = QQmlApplicationEngine()
    for name, provider in (providers or {}).items():
        engine.addImageProvider(name, provider)
    engine.warnings.connect(
        lambda ws: [print(f"QML: {w.toString()} (line {w.line()})", file=sys.stderr) for w in ws]
    )
    ctx = engine.rootContext()
    ctx.setContextProperty("islandBridge", bridge)
    ctx.setContextProperty("theme", theme_bridge)
    for key, value in (extra or {}).items():
        ctx.setContextProperty(key, value)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        raise SystemExit("QML 加载失败，检查上面的报错")
    win = engine.rootObjects()[0]
    bridge.attach(win)
    return engine, win


def _as_quick_window(win) -> QQuickWindow:
    if isinstance(win, QQuickWindow):
        return win
    import shiboken6

    return shiboken6.wrapInstance(shiboken6.getCppPointer(win)[0], QQuickWindow)


def _place_top_center(win, margin: int = 8) -> None:
    screen = QGuiApplication.primaryScreen().availableGeometry()
    win.setPosition(screen.x() + (screen.width() - win.width()) // 2, screen.y() + margin)


def _tray_icon() -> QIcon:
    """托盘 / 窗口图标：优先用品牌图（assets/branding/app-icon.png，由 logo 归一而来）。"""
    icon = QIcon(str(BRAND_ICON))
    if not icon.isNull():
        return icon

    # 素材缺失时的兜底，至少托盘里有个东西可点
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#2E7BF0"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(10, 16, 10, 32, 5, 5)
    p.drawRoundedRect(26, 16, 10, 32, 5, 5)
    p.end()
    return QIcon(pix)


def _single_instance() -> bool:
    """已经有一个在跑就直接退出，避免叠出两条胶囊。

    用命名互斥体而不是找窗口：窗口是 Qt.Tool + 无边框且标题会被 DWM 隐藏，
    按标题找很容易误判。FALSE = 首次创建，183 = ERROR_ALREADY_EXISTS。
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    # 必须先清零：use_last_error 保存的是「上一次出错」的码，可能是别处留下的 183，
    # 直接读会误判成「已有实例在运行」，于是第二次启动直接退出（反过来也可能漏判）。
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    # handle 故意不释放：进程活着就该一直持有，退出时系统自动回收
    if not handle:
        return True             # 建锁失败就别拦着人启动
    return ctypes.get_last_error() != 183


def _apply_app_font(app) -> None:
    f = QFont("Microsoft YaHei UI")
    # 用 pointSize 而不是 pixelSize：托盘菜单（QMenu）会把 app font 的 pointSize
    # 拷进自己的字体，而 pixelSize 模式下 pointSize() 返回 -1，Qt 就会刷
    # "QFont::setPointSize: Point size <= 0" 警告。QML 里 15 个 Text 全部显式设了
    # pixelSize，不继承 app font，所以改单位对界面没有影响。9.75pt ≈ 13px @96dpi。
    f.setPointSizeF(9.75)
    # 透明窗口上不能用子像素抗锯齿：边缘会出现彩色描边，叠在玻璃上很脏
    f.setStyleStrategy(QFont.NoSubpixelAntialias)
    app.setFont(f)
    # 强制走 Qt 自己的灰度抗锯齿，别用 GDI 的 ClearType（后者的彩色描边在上面那条
    # 字体策略上不生效，必须在渲染器层面关掉）
    try:
        QQuickWindow.setTextRenderType(QQuickWindow.QtTextRendering)
    except Exception:  # noqa: BLE001
        pass


def _start_glass(win, sampler: backdrop.BackdropSampler, theme_bridge) -> material.GlassMaterial | None:
    """先试自绘玻璃；失败则退回系统 acrylic（方角问题只在回退态出现）。"""
    if sampler.attach(win):
        theme_bridge.set_material_ready(True)
        print(f"glass: self-rendered backdrop mode={theme_bridge.mode}")
        return None
    glass = material.GlassMaterial(win, theme_bridge.mode)
    ok = glass.start()
    theme_bridge.set_material_ready(ok)
    print(f"glass: {'acrylic fallback' if ok else 'flat fallback（抓不到背景）'} mode={theme_bridge.mode}")
    return glass


def run_app(state_name: str, theme_pref: str | None = None) -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("WinIsland")
    app.setApplicationDisplayName("WinIsland")
    app.setWindowIcon(_tray_icon())
    _apply_app_font(app)
    # 让任务栏 / 跳转列表把 exe 认成独立应用，而不是「python.exe 的一个窗口」
    try:
        ctypes.WinDLL("shell32").SetCurrentProcessExplicitAppUserModelID("WinIsland.Desktop.1")
    except OSError:
        pass

    theme_bridge = theme_mod.ThemeBridge()
    if theme_pref:
        theme_bridge.setPreference(theme_pref)

    live = state_name == "live"
    bridge = Bridge(None if live else mock.get_state(state_name), live=live, theme_bridge=theme_bridge)
    provider = backdrop.BackdropProvider()
    sampler = backdrop.BackdropSampler(provider)
    engine, win = _load_engine(bridge, theme_bridge, {"backdrop": sampler}, {"backdrop": provider})
    _place_top_center(win)

    # 玻璃底材：优先自绘（能精确圆角）；抓不到背景时退回系统 acrylic
    glass = _start_glass(win, sampler, theme_bridge)

    registry: adapters.AgentRegistry | None = None
    watcher: notify_win32.ToastWatcher | None = None
    if live:
        registry = adapters.AgentRegistry()
        watcher = notify_win32.ToastWatcher()
        watcher.start()
        # 诊断用：确认 WinEvent 钩子真的装上了（hook=0 时永远收不到通知）
        print(f"notify watcher active={watcher.active} hooks={len(watcher._hooks)}", file=sys.stderr)
        inbox: list[dict] = []

        def refresh() -> None:
            if bridge.is_dragging():
                return      # 拖动在系统模态循环里，刷新会重建会话行并把正在执行的信号处理器连对象一起删掉
            try:
                bridge.set_agents(registry.poll())
            except Exception as exc:  # noqa: BLE001
                print(f"agent poll failed: {exc!r}", file=sys.stderr)
            try:
                fresh = watcher.drain()
                if fresh:
                    for n in reversed(fresh):
                        inbox.insert(0, n)
                    del inbox[10:]
                    bridge.set_notifs(inbox)
            except Exception as exc:  # noqa: BLE001
                print(f"notify poll failed: {exc!r}", file=sys.stderr)

        refresh()
        timer = QTimer()
        timer.timeout.connect(refresh)
        timer.start(1000)

    # 跟随系统主题（用户没手动固定时才生效）
    theme_timer = QTimer()
    theme_timer.timeout.connect(theme_bridge.refresh)
    theme_timer.start(5000)

    def on_theme_changed() -> None:
        if glass is not None:                       # acrylic 回退态要重设 tint
            theme_bridge.set_material_ready(glass.set_mode(theme_bridge.mode))
        sampler.schedule()                          # 自绘态只需重抓一帧

    theme_bridge.changed.connect(on_theme_changed)

    def toggle() -> None:
        # 定位由 Main.qml 的 onWidthChanged 负责：围绕当前中心开合，和点胶囊走同一套逻辑
        bridge.toggle()

    def popup_menu() -> None:
        menu.popup(QCursor.pos())

    bridge.bind(glass, popup_menu)

    menu = QMenu()
    menu.addAction("展开 / 收起", toggle)
    menu.addSeparator()
    theme_menu = menu.addMenu("主题")
    theme_menu.addAction("跟随系统", lambda: theme_bridge.setPreference("system"))
    theme_menu.addAction("深色", lambda: theme_bridge.setPreference("dark"))
    theme_menu.addAction("浅色", lambda: theme_bridge.setPreference("light"))
    menu.addAction("重新居中", lambda: _place_top_center(win))
    menu.addSeparator()
    menu.addAction("退出", app.quit)

    tray = QSystemTrayIcon(_tray_icon(), app)
    tray.setContextMenu(menu)
    tray.setToolTip("WinIsland")
    tray.activated.connect(lambda reason: toggle() if reason == QSystemTrayIcon.Trigger else None)
    tray.show()

    def cleanup() -> None:
        if glass is not None:
            glass.release()

    app.aboutToQuit.connect(cleanup)
    return app.exec()


# --------------------------------------------------------------------------- #
# 渲染（设计评审用）
# --------------------------------------------------------------------------- #
def _settle_then(win, callback, settle_ms: int = 900) -> None:
    probe = {"last": None, "stable": 0, "ticks": 0}

    def tick() -> None:
        probe["ticks"] += 1
        size = (win.width(), win.height())
        if size == probe["last"]:
            probe["stable"] += 1
        else:
            probe["last"] = size
            probe["stable"] = 0
        if probe["stable"] >= 4 or probe["ticks"] > 60:
            callback()
            return
        QTimer.singleShot(120, tick)

    QTimer.singleShot(settle_ms, tick)


def _present(img: QImage, mode: str, pad: int = 26) -> QImage:
    """把带透明通道的窗口抓图摆到中性渐变底上，便于评审（否则白字压在透明背景上看不见）。"""
    dpr = QGuiApplication.primaryScreen().devicePixelRatio()
    p = int(pad * dpr)
    # 抓图带 dpr 元数据，直接 drawImage 会按逻辑尺寸画小；这里按物理像素处理
    img.setDevicePixelRatio(1.0)
    out = QImage(img.width() + p * 2, img.height() + p * 2, QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.Antialiasing)
    grad = QLinearGradient(0, 0, out.width(), out.height())
    if mode == "light":
        grad.setColorAt(0.0, QColor("#F2F5F9"))
        grad.setColorAt(1.0, QColor("#C7D0DD"))
    else:
        grad.setColorAt(0.0, QColor("#1C2532"))
        grad.setColorAt(1.0, QColor("#0A0D12"))
    painter.fillRect(out.rect(), grad)
    painter.drawImage(p, p, img)
    painter.end()
    return out


def run_snapshot(state_name: str, out_path: Path, settle_ms: int = 900,
                 showcase: bool = False, theme_pref: str | None = None) -> int:
    app = QGuiApplication(sys.argv[:1])
    _apply_app_font(app)

    theme_bridge = theme_mod.ThemeBridge()
    theme_bridge.setPreference(theme_pref or "dark")

    if state_name.startswith("live"):
        state = {
            "expanded": state_name == "live",
            "agents": adapters.AgentRegistry().poll(),
            "notifs": [],
        }
        bridge = Bridge(state, live=True, theme_bridge=theme_bridge)
    else:
        bridge = Bridge(mock.get_state(state_name), theme_bridge=theme_bridge)

    backdrop_win = None
    if showcase:
        # 背景窗先建，保证叠放顺序在岛下面
        bg_engine = QQmlApplicationEngine()
        bg_engine.rootContext().setContextProperty(
            "bgPath", (ASSETS_DIR / "wallpaper.png").as_posix()
        )
        bg_engine.load(QUrl.fromLocalFile(str(QML_DIR / "Backdrop.qml")))
        if bg_engine.rootObjects():
            backdrop_win = bg_engine.rootObjects()[0]

    provider = backdrop.BackdropProvider()
    sampler = backdrop.BackdropSampler(provider)
    engine, win = _load_engine(bridge, theme_bridge, {"backdrop": sampler}, {"backdrop": provider})
    win.setPosition(120, 80)

    glass = _start_glass(win, sampler, theme_bridge)

    # 背景窗只跟窗口一样大（多留 24px 边），测试时不会糊住整块屏幕
    if backdrop_win is not None:
        wall = QImage(str(ASSETS_DIR / "wallpaper.png"))
        scr_w = QGuiApplication.primaryScreen().geometry().width()
        # 壁纸按屏幕宽度 1:1 铺，裁剪时用它换算成图片像素
        img_scale = (wall.width() / scr_w) if scr_w else 1.0

        def fit_backdrop(*_args) -> None:
            margin = 24
            backdrop_win.setGeometry(
                win.x() - margin, win.y() - margin,
                win.width() + margin * 2, win.height() + margin * 2,
            )
            backdrop_win.setProperty("imgScale", img_scale)
            backdrop_win.setProperty("clipX", win.x() - margin)
            backdrop_win.setProperty("clipY", win.y() - margin)
            sampler.schedule()

        for sig in ("widthChanged", "heightChanged", "xChanged", "yChanged"):
            handler = getattr(win, sig, None)
            if handler is not None:
                handler.connect(fit_backdrop)
        fit_backdrop()

    def grab() -> None:
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            # 自绘玻璃后，窗口自身抓图就已经包含真实的模糊背景，
            # 不再需要整屏截图（而且窗口已被排除在截屏之外，整屏也拍不到它）
            img = _as_quick_window(win).grabWindow()
            if showcase:
                img = _present(img, theme_bridge.mode)
            print(f"saved {out_path} size={img.width()}x{img.height()}"
                  f"{' (showcase)' if showcase else ''}")
            img.save(str(out_path), "PNG")
        except Exception as exc:  # noqa: BLE001
            print(f"capture failed: {exc!r}", file=sys.stderr)
        finally:
            app.quit()

    _settle_then(win, grab, settle_ms)
    return app.exec()


def main() -> int:
    ap = argparse.ArgumentParser()
    choices = ["live", "live_pill"] + list(mock.STATES)
    ap.add_argument("--state", default="live", choices=choices)
    ap.add_argument("--snapshot", default=None, choices=choices, help="渲染静帧后退出")
    ap.add_argument("--out", default="preview.png")
    ap.add_argument("--settle", type=int, default=900, help="抓图前等待毫秒，等动画收敛")
    ap.add_argument("--showcase", action="store_true", help="叠在背景图上截整屏，含真实系统模糊")
    ap.add_argument("--theme", default=None, choices=["dark", "light", "system"])
    args = ap.parse_args()

    if args.snapshot:
        return run_snapshot(args.snapshot, Path(args.out), args.settle, args.showcase, args.theme)
    if not _single_instance():
        print("已有实例在运行，退出", file=sys.stderr)
        return 0
    return run_app(args.state, args.theme)


if __name__ == "__main__":
    raise SystemExit(main())
