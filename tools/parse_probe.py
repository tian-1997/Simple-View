"""飞书 / 微信 / 企微通知文案解析的回归测试。

`_build_notification` 只有一堆字符串启发式，最容易「修一个坏一个」，
所以把已知形态和踩过的坑都钉成断言。跑法：

    .venv\\Scripts\\python.exe tools\\parse_probe.py

任何一条 FAIL 都会打印期望与实际，退出码非 0。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from notify_win32 import _build_notification, _is_meta, _meta_split  # noqa: E402

FEISHU = "feishu.exe"
WEWORK = "wxwork.exe"
WECHAT = "wechat.exe"

# (说明, 进程, 标题, UIA 文本, 期望 sender, 期望 chat, 期望 body)
CASES: list[tuple[str, str, str, list[str], str, str, str]] = [
    # ---- 飞书三种主形态 ----
    ("三行：人 / 在群中说 / 正文", FEISHU, "飞书",
     ["飞书", "陈杰铭（吉米）", "在 PCR02软件 中说：", "上来了，快动"],
     "陈杰铭（吉米）", "PCR02软件", "上来了，快动"),
    ("群名带「中」加空格", FEISHU, "飞书",
     ["飞书", "刘秋林", "在 研发中心 中 说：", "周四发版，今天先出一个版本"],
     "刘秋林", "研发中心", "周四发版，今天先出一个版本"),
    ("人和群挤在一行", FEISHU, "飞书",
     ["飞书", "Miles（韦俊来） 在 项目群", "周报填写新表格"],
     "Miles（韦俊来）", "项目群", "周报填写新表格"),
    ("人和正文挤在一行", FEISHU, "飞书",
     ["飞书", "曹忠文: 曹总，请问下午有空吗？需要找您签个转正申请表"],
     "曹忠文", "飞书", "曹总，请问下午有空吗？需要找您签个转正申请表"),
    ("单独一行「XX 说：」也算发送人", FEISHU, "飞书",
     ["飞书", "张三 说：", "明天见"],
     "张三", "飞书", "明天见"),

    # ---- 回归：之前修掉的 bug ----
    ("【旧 bug】正文不是取最长，不能把「在 XX 中说：」当正文", FEISHU, "飞书",
     ["飞书", "张三", "在 项目群 中说：", "好"],
     "张三", "项目群", "好"),
    ("【旧 bug】正文以冒号结尾不能被当成元信息丢掉", FEISHU, "飞书",
     ["飞书", "张三", "请把日志发我："],
     "张三", "飞书", "请把日志发我："),
    ("【旧 bug】时间戳不能当正文", FEISHU, "飞书",
     ["飞书", "曹忠文: 曹总，请问下午有空吗？", "17:49"],
     "曹忠文", "飞书", "曹总，请问下午有空吗？"),
    ("【旧 bug】[图片] 不能当发送人", FEISHU, "飞书",
     ["飞书", "[图片]"],
     "未知发送人", "飞书", "[图片]"),

    # ---- 边缘 ----
    ("正文正好是「今天」，不能被时间词吃掉", FEISHU, "飞书",
     ["飞书", "张三", "今天"],
     "张三", "飞书", "今天"),
    ("正文正好是「现在」", FEISHU, "飞书",
     ["飞书", "张三", "现在"],
     "张三", "飞书", "现在"),
    ("名字里带「在」不能拆错", FEISHU, "飞书",
     ["飞书", "李在明", "在 项目群", "会议改到下午"],
     "李在明", "项目群", "会议改到下午"),
    ("超长群名（>40 字）也要认得出来", FEISHU, "飞书",
     ["飞书", "张三", "在 " + "很长的部门群名称" * 6 + " 中说：", "收到"],
     "张三", "很长的部门群名称" * 6, "收到"),
    ("「在 XX 中：」不带「说」", FEISHU, "飞书",
     ["飞书", "张三", "在 项目群 中：", "下午三点开会"],
     "张三", "项目群", "下午三点开会"),
    ("只有人 + 图片占位", FEISHU, "飞书",
     ["飞书", "李鸿", "16:28", "在 研发中心 中说：", "[图片]"],
     "李鸿", "研发中心", "[图片]"),
    ("同一个人又说了一句（sender 不重复取）", FEISHU, "飞书",
     ["飞书", "张三", "他说：", "明天见"],
     "张三", "飞书", "明天见"),
    ("一行全含：人 在 群 中说：", FEISHU, "飞书",
     ["飞书", "张三 在 项目群 中说：", "明天上午十点评审"],
     "张三", "项目群", "明天上午十点评审"),
    ("正文里带「在…：」不能被当群名吞掉", FEISHU, "飞书",
     ["飞书", "张三", "张三 在 会议室等你了："],
     "张三", "飞书", "张三 在 会议室等你了："),
    ("正文是半句话（以「了」结尾）不能被拆成 人+群", FEISHU, "飞书",
     ["飞书", "张三 在 会议室等你了"],
     "未知发送人", "飞书", "张三 在 会议室等你了"),
    ("通知卡片上的「回复」按钮不能当正文", FEISHU, "飞书",
     ["飞书", "张三", "在 项目群 中说：", "好", "回复"],
     "张三", "项目群", "好"),
    ("「@所有人」不能当发送人", FEISHU, "飞书",
     ["飞书", "@所有人", "明天开会"],
     "未知发送人", "飞书", "明天开会"),
    ("未读数是纯数字，不能被当发送人（宁可未知）", FEISHU, "飞书",
     ["飞书", "3", "张三", "明天开会"],
     "未知发送人", "飞书", "明天开会"),
    # ---- 真机日志（2026-11-24 18:37 飞书助手弹窗）----
    ("【真机】正文带「发送人: 」前缀要剥掉", FEISHU, "飞书",
     ["田圆的飞书助手", "飞书助手: 翻阅资料,生成答案中。"],
     "田圆的飞书助手", "飞书", "翻阅资料,生成答案中。"),
    ("正文里的「时间: 明天」不能被当成发送人前缀", FEISHU, "飞书",
     ["张三", "会议时间: 明天上午十点"],
     "张三", "飞书", "会议时间: 明天上午十点"),
    ("整块抽空 → 降级", FEISHU, "飞书",
     ["飞书"],
     "未知发送人", "飞书", "（有新消息，未读到内容）"),    ("完全没抽到", FEISHU, "飞书",
     [],
     "未知发送人", "飞书", "（有新消息，未读到内容）"),

    # ---- 其它 IM 不能因为改飞书而回归 ----
    ("企业微信：人 / 群 / 正文", WEWORK, "企业微信",
     ["企业微信", "张三", "项目群", "消息内容"],
     "张三", "企微", "消息内容"),
    ("微信：人 / 正文 / 时间", WECHAT, "微信",
     ["微信", "张三", "你好", "10:32"],
     "张三", "微信", "你好"),
]


def main() -> int:
    fails = 0
    for note, proc, title, texts, want_sender, want_chat, want_body in CASES:
        got = _build_notification(proc, title, texts, 0)
        bad = []
        if got["sender"] != want_sender:
            bad.append(f"sender={got['sender']!r} 期望 {want_sender!r}")
        if got["chat"] != want_chat:
            bad.append(f"chat={got['chat']!r} 期望 {want_chat!r}")
        if got["body"] != want_body:
            bad.append(f"body={got['body']!r} 期望 {want_body!r}")
        if bad:
            fails += 1
            print(f"FAIL  {note}")
            for b in bad:
                print(f"        {b}")
            print(f"        raw={texts}")
        else:
            print(f"OK    {note}")

    print()
    # 元信息判据的几个直接断言
    meta_cases = [
        ("在 PCR02软件 中说：", ("chat", "PCR02软件")),
        ("在 研发中心 中 说：", ("chat", "研发中心")),
        ("张三 说：", ("sender", "张三")),
        ("在 项目群 中：", ("chat", "项目群")),
        ("请把日志发我：", None),
        ("会议纪要如下：", None),
        ("张三: 你好", None),
    ]
    for text, want in meta_cases:
        got = _meta_split(text)
        if got != want:
            fails += 1
            print(f"FAIL  _meta_split({text!r}) = {got!r} 期望 {want!r}")
        else:
            print(f"OK    _meta_split({text!r}) = {got!r}")

    time_cases = [("刚刚", True), ("12:30", True), ("昨天 08:15", True),
                  ("今天", False), ("现在", False), ("上午", False),
                  ("领导刚刚说下周发版", False)]
    for text, want in time_cases:
        got = _is_meta(text)
        if got != want:
            fails += 1
            print(f"FAIL  _is_meta({text!r}) = {got} 期望 {want}")
        else:
            print(f"OK    _is_meta({text!r}) = {got}")

    print()
    print(f"{len(CASES) + len(meta_cases) + len(time_cases)} 项，失败 {fails} 项")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
