"""主题桥：把 tokens 暴露给 QML，并跟随 Windows 深/浅色设置。

QML 只读 `theme.colors.xxx`，不写死色值；切换主题时整张表换掉，
所有绑定自动更新（包括状态色以外的一切视觉）。
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

import tokens

try:  # Windows 注册表读系统主题；非 Windows 或读取失败时按深色处理
    import winreg
except ImportError:  # pragma: no cover
    winreg = None  # type: ignore[assignment]


def system_is_light() -> bool:
    if winreg is None:
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        try:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return bool(value)
        finally:
            key.Close()
    except OSError:
        return False


class ThemeBridge(QObject):
    changed = Signal()
    materialChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._pref = "system"          # system / dark / light
        self._material = False

    # ---------- 对外属性 ----------
    @Property("QVariantMap", notify=changed)
    def colors(self) -> dict:
        return tokens.tokens(self.mode)

    @Property("QVariantMap", constant=True)
    def metrics(self) -> dict:
        return {**tokens.SIZE, **tokens.MOTION}

    @Property(str, notify=changed)
    def mode(self) -> str:
        if self._pref == "system":
            return "light" if system_is_light() else "dark"
        return self._pref

    @Property(str, notify=changed)
    def preference(self) -> str:
        return self._pref

    @Property(bool, notify=materialChanged)
    def materialReady(self) -> bool:
        """系统级模糊是否真的生效；false 时 QML 用 fallbackFill 兜底。"""
        return self._material

    @Property(str, notify=changed)
    def glassTint(self) -> str:
        """自绘玻璃的着色层颜色（QML #AARRGGBB）。"""
        return tokens.GLASS_TINT.get(self.mode, tokens.GLASS_TINT["dark"])

    @Property(float, notify=changed)
    def glassBlur(self) -> float:
        return tokens.GLASS_BLUR.get(self.mode, 0.6)

    def set_material_ready(self, value: bool) -> None:
        if value != self._material:
            self._material = bool(value)
            self.materialChanged.emit()

    # ---------- 操作 ----------
    @Slot()
    def toggleTheme(self) -> None:
        self._pref = "light" if self.mode == "dark" else "dark"
        self.changed.emit()

    @Slot(str)
    def setPreference(self, pref: str) -> None:
        if pref in ("system", "dark", "light") and pref != self._pref:
            self._pref = pref
            self.changed.emit()

    @Slot()
    def refresh(self) -> None:
        """系统主题可能被用户在别处改了，交给定时器轮询。"""
        if self._pref == "system":
            self.changed.emit()

    # ---------- 工具 ----------
    @Slot(str, result=str)
    def statusColor(self, kind: str) -> str:
        return tokens.STATUS.get(kind, tokens.STATUS["idle"])

    @Slot(str, result=str)
    def kindOf(self, status_text: str) -> str:
        return tokens.kind_of(status_text)
