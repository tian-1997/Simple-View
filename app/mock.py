"""演示数据：界面设计阶段用，后续被真实适配器替换。"""
from __future__ import annotations

import copy

RUN = "#3988F5"
THINK = "#A78BFA"
WAIT = "#E5A13A"
DONE = "#8993A1"
FEISHU = "#3370FF"
WECOM = "#0082EF"
WECHAT = "#07C160"


def _agent(name, letter, color, proj, title, status, action, elapsed, running,
           status_color=None, cwd=""):
    return {
        "name": name,
        "letter": letter,
        "letterColor": color,
        "title": title,
        "proj": proj,
        "cwd": cwd or proj,
        "pid": 0,
        "status": status,
        "statusColor": status_color or color,
        "action": action,
        "elapsed": elapsed,
        "running": running,
    }


ACTIVE_AGENTS = [
    _agent("Codex", "C", RUN, "gd32l235_framework", "排查时钟树配置",
           "执行工具", "exec_command · npm test -- --watch=false", "01:24", True),
    _agent("pi", "π", THINK, "fitness-miniapp", "训练页图表重构",
           "推理中", "reading src/pages/train/index.tsx", "00:38", True),
    _agent("WorkBuddy", "W", DONE, "win-dynamic-island", "玻璃质感改版",
           "已完成", "写入 6 个文件 · QML 界面骨架", "02:11", False, DONE),
]

IDLE_AGENTS = [
    _agent("Codex", "C", RUN, "gd32l235_framework", "上次 · git status",
           "空闲", "上次动作 · git status", "—", False),
    _agent("pi", "π", THINK, "fitness-miniapp", "上次 · 构建产物",
           "空闲", "上次动作 · npm run build", "—", False),
    _agent("WorkBuddy", "W", DONE, "win-dynamic-island", "上次 · 写入 PLAN.md",
           "空闲", "上次动作 · 写入 PLAN.md", "—", False),
]

ALERT_AGENTS = [
    _agent("Codex", "C", WAIT, "gd32l235_framework", "清理构建目录",
           "等确认", "需要批准 · rm -rf build/ 是否继续", "01:52", True, WAIT),
    _agent("pi", "π", THINK, "fitness-miniapp", "打包前的静态检查",
           "执行工具", "bash · npm run build", "00:12", True),
]

NOTIFS = [
    {
        "app": "微信", "appColor": WECHAT, "chat": "老同学群", "sender": "张工",
        "body": "测试数据已经整理好了，你看一下时序对不对", "time": "2 分钟前",
        "unread": True,
    },
    {
        "app": "飞书", "appColor": FEISHU, "chat": "硬件组", "sender": "李工",
        "body": "明天下午评审的 PPT 记得带上，9 点三楼会议室", "time": "8 分钟前",
        "unread": True,
    },
    {
        "app": "企微", "appColor": WECOM, "chat": "视壮科技 · 硬件组", "sender": "王敏",
        "body": "灵动岛的配色我看了，偏冷一点更稳", "time": "23 分钟前",
        "unread": False,
    },
]

# 单独一个会话的极简态：用来核对胶囊边框的状态色（推理中紫 / 已完成绿）
THINK_ONLY = [
    _agent("pi", "π", THINK, "fitness-miniapp", "训练页图表重构",
           "推理中", "reading src/pages/train/index.tsx", "00:38", True),
]

DONE_ONLY = [
    _agent("WorkBuddy", "W", DONE, "win-dynamic-island", "玻璃质感改版",
           "已完成", "写入 6 个文件 · QML 界面骨架", "02:11", False, DONE),
]

STATES = {
    "active": {"expanded": False, "agents": ACTIVE_AGENTS, "notifs": NOTIFS},
    "idle": {"expanded": False, "agents": IDLE_AGENTS, "notifs": []},
    "alert_pill": {"expanded": False, "agents": ALERT_AGENTS, "notifs": NOTIFS[:1]},
    "think_pill": {"expanded": False, "agents": THINK_ONLY, "notifs": []},
    "done_pill": {"expanded": False, "agents": DONE_ONLY, "notifs": []},
    "panel": {"expanded": True, "agents": ACTIVE_AGENTS, "notifs": NOTIFS},
    "alert": {"expanded": True, "agents": ALERT_AGENTS, "notifs": NOTIFS[:1]},
}


def get_state(name: str) -> dict:
    return copy.deepcopy(STATES.get(name, STATES["panel"]))
