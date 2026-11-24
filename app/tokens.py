"""设计 token 的唯一来源：与 design/docs/UI-DESIGN-SPEC-v1.0.1.md 对齐。

颜色、尺寸、动效时长都从这里出去，QML 不自己写死色值，
这样才能保证主题切换、回退、验收取的是同一套值。
"""
from __future__ import annotations

# --------------------------------------------------------------------------- #
# 颜色
# --------------------------------------------------------------------------- #
DARK = {
    "bg": "#191B1F",
    "surface": "#202329",
    "surfaceElevated": "#292E36",
    "textPrimary": "#F3F5F8",
    "textSecondary": "#A6ACB7",
    "textMuted": "#737B88",
    "border": "#1CFFFFFF",
    "borderStrong": "#33FFFFFF",
    "divider": "#18FFFFFF",
    "accent": "#3988F5",
    # 回退底材：系统材质不可用时，QML 自己填这个（alpha 高一些保证可读）
    "fallbackFill": "#F2191D24",
    "rowHover": "#0FFFFFFF",
    "controlBg": "#14FFFFFF",
    "controlHover": "#22FFFFFF",
    "brandA": "#67B2FF",
    "brandB": "#2E7BF0",
    "logoPlate": "#12FFFFFF",
    "pillVeil": "#2BFFFFFF",
}

LIGHT = {
    "bg": "#F3F5F8",
    "surface": "#FFFFFF",
    "surfaceElevated": "#E9EDF3",
    "textPrimary": "#20242B",
    "textSecondary": "#606A79",
    "textMuted": "#858E9C",
    "border": "#DCE1E8",
    "borderStrong": "#C3CBD6",
    "divider": "#E5E9EF",
    "accent": "#2674E8",
    "fallbackFill": "#F7FFFFFF",
    "rowHover": "#0A000000",
    "controlBg": "#0A000000",
    "controlHover": "#14000000",
    "brandA": "#4E9BFF",
    "brandB": "#1F6FE0",
    "logoPlate": "#00000008",
    "pillVeil": "#66FFFFFF",
}

# 语义状态色：只表达状态，不承担产品身份
STATUS = {
    "think": "#A78BFA",
    "tool": "#3988F5",
    "wait": "#E5A13A",
    "idle": "#8993A1",
    "done": "#8993A1",
    "error": "#E45858",
}

# 状态文本 → 语义种类（只做视觉映射，不改数据语义）
KIND_OF = {
    "推理中": "think",
    "执行工具": "tool",
    "等确认": "wait",
    "已完成": "done",
    "出错": "error",
}

# --------------------------------------------------------------------------- #
# 尺寸（逻辑像素）
# --------------------------------------------------------------------------- #
SIZE = {
    # 收起态和展开态共用同一个宽度：展开只向下长高度，不做横向拉伸
    "islandW": 240,
    "pillH": 40,
    "pillRadius": 20,
    "panelW": 240,
    "panelRadius": 20,
    "panelMaxH": 560,
    "pad": 12,
    "sectionGap": 12,
    "agentRowH": 60,
    "notifyRowH": 56,
    "logo": 36,
    "logoRadius": 12,
}

# 动效（毫秒）：不使用持续吸引注意力的循环动画
MOTION = {
    "expand": 220,
    "collapse": 160,
    "panelIn": 200,
    "hover": 100,
    "stateChange": 180,
    "themeChange": 180,
}

# --------------------------------------------------------------------------- #
# 系统材质 tint（ABGR，交给 DWM 绘制，QML 不再叠加同色 alpha）
# --------------------------------------------------------------------------- #
# 深色：能感知背景光影但压住细节；浅色：白色磨砂，遮挡感更强以保证黑字可读
ACRYLIC_TINT = {
    "dark": 0x8A241C18,   # RGBA(24,28,36,0.54) → 深蓝黑玻璃
    "light": 0xA8F7F9FB,  # RGBA(251,249,247,0.66) → 冷白磨砂
}

# 自绘玻璃的着色层（QML #AARRGGBB）：背景已模糊，这里只负责压暗/提亮与色偏
GLASS_TINT = {
    "dark": "#A80A0D13",    # 63% 深蓝黑，让白字稳在 7:1 以上
    "light": "#B4F6F8FB",   # 65% 冷白，压住壁纸颜色保住黑字
}

# 玻璃模糊强度（MultiEffect blur 0~1），越大越"毛玻璃"
GLASS_BLUR = {"dark": 0.74, "light": 0.82}


def tokens(mode: str) -> dict[str, str]:
    return LIGHT if mode == "light" else DARK


def kind_of(status_text: str) -> str:
    return KIND_OF.get(status_text, "idle")
