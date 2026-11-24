# Windows 灵动岛（WinIsland）需求与技术规划

> 状态：规划稿 v0.1 · 2026-11-23
> 目标机器：Windows 11 / 深圳视壮科技 田先生本机

## 1. 目标

在 Windows 桌面顶部做一个常驻的「灵动岛」悬浮胶囊，把两类高频信息集中到一个不打扰的视觉入口：

1. **AI 会话状态**：Codex、pi、WorkBuddy 当前正在跑什么、跑到哪、是否在等我确认。
2. **IM 通知**：微信、飞书、企业微信的新消息（谁发的、说了什么、几条未读）。

核心体验：一眼看到「机器上有什么在动」，不用切窗口、不用翻任务栏。

## 2. 功能需求

### 2.1 悬浮窗本体
- 顶部居中、无边框、圆角胶囊、始终置顶、不显示在任务栏/Alt-Tab。
- **收起态**（约 220×38）：每个 Agent 一个状态点 + 未读通知计数。
- **展开态**（约 420×480）：上区 Agent 会话卡片，下区通知流。
- 展开方式：鼠标悬停展开 / 点击展开（待定），鼠标移开自动收起（可配延迟）。
- 拖动可改位置，多显示器下记住所在屏幕与坐标。
- 状态动效：运行中呼吸光、等待确认橙色脉冲、完成绿色一闪、出错红色。
- 托盘图标 + 右键菜单（置顶开关、专注模式、位置重置、开机自启、退出）。
- 全局热键（可选，P1）：`Ctrl+Alt+I` 手动展开/收起。

### 2.2 Agent 会话卡片
每个活跃会话一行，包含：
- Agent 标识（Codex / pi / WorkBuddy）+ 项目名（cwd 末段）
- 状态：`思考中` / `调用工具` / `等确认` / `已完成` / `空闲` / `出错`
- 已持续时长（本轮 turn 起算）
- 最后动作摘要（如 `exec_command: npm test`、`编辑 src/app.ts`、最后一句 assistant 文本前 40 字）
- 超过阈值无活动（默认 90s）自动降级为「空闲」并淡出，不再占据视线

### 2.3 通知流
- 来源：微信 / 飞书 / 企业微信，按应用区分图标与配色。
- 展示：会话名、发送人、正文摘要（≤60 字）、相对时间。
- 同会话连续消息合并为「N 条新消息，最新：…」。
- 未读角标 + 全部已读。
- 点击（P1）：激活对应应用窗口并尝试跳到该会话。
- 专注模式：只留角标不弹动画。

## 3. 数据源（已在本机实测确认）

### 3.1 Codex —— ✅ 确认可用
- 路径：`~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl`
- 结构（JSONL，一行一事件）：
  - `{"type":"session_meta","payload":{session_id,cwd,originator:"Codex Desktop",cli_version,...}}` 首行，**含 cwd**，可用于项目名
  - `{"type":"response_item","payload":{"type":"message"|"function_call"|"function_call_output",...}}`
    - `function_call` 带 `name`（如 `exec_command`）与 `arguments` → 直接当「正在执行的动作」
    - `message.status:"completed"` + `role:"assistant"` → 一轮回答结束
  - `{"type":"token_usage_record", ...}` token 统计（可做 P2 展示）
- 状态判定：按 mtime 取最新文件 → 文件尾部增量 tail → 最后事件类型映射状态；mtime 静默 > 阈值视为空闲。
- 风险：Codex Desktop 可能同时写多个 rollout；需按「最近 5 分钟内被写过的文件」多路跟踪，而不是只取最新一个。

### 3.2 pi —— ✅ 确认可用
- 路径：`~/.pi/agent/sessions/<cwd-slug>/<ISO时戳>_<uuid>.jsonl`（slug 即 cwd 转义，如 `--D--Tyuser-F20-CODE--`）
- 事件类型实测：`session` / `message`（role=user|assistant，含 tool 调用与 stopReason）/ `context_edit` / `compaction` / `model_change` / `thinking_level_change`
- 额外发现：`~/.pi/agent/extensions/orca-agent-status.ts` 证明 **pi 支持扩展 hook 主动上报 agent 状态**（POST 到本地 receiver，含 agent_end 等事件）。
- 结论：P0 用 jsonl tail；P2 可选写一个 pi extension 主动推状态，精准度最高（能拿到 turn 开始/结束与工具名，不必靠超时猜）。

### 3.3 WorkBuddy —— ⚠️ 部分确认
- ✅ `~/.workbuddy/sessions/<pid>.json`：`{pid,lastHeartbeat,sessionId,cwd,url,endpoint,mode,version,hostname}`，**心跳文件 = 会话存活信号**，且带 cwd。
- ⚠️ `~/.workbuddy/projects/<slug>/` 存在但读取被本会话策略拦截，需在用户态进程中验证其内容（预计是与 Codex/Claude 同构的 jsonl 对话记录）。
- 判定策略：`lastHeartbeat` 新鲜（<10s）= 会话存活；状态细化二选一：
  - A. 解析 projects 下的对话 jsonl（若可得）
  - B. 只做「存活 + 项目名 + 运行时长」，状态显示为「运行中」（弱但 100% 可靠）
- 设计上做成「能力探测」：能读到 jsonl 就升级为完整状态，读不到自动降级，不报错。

### 3.4 IM 通知 —— 无统一接口，三档方案
本机实测：`Feishu.exe`（多进程）、`WXWorkWeb.exe` 正在运行；微信为 4.x（数据目录 `AppData/Roaming/Tencent/xwechat`，当前未运行）。

| 层级 | 手段 | 能拿到什么 | 稳定性 | 成本 |
|---|---|---|---|---|
| L1 | `SetWinEventHook(EVENT_OBJECT_CREATE/SHOW)` 监听三家进程新建窗口 + UI Automation 读文本 | 完整弹窗：会话名+发送人+正文 | 中（需按实际窗口类名/树逐个适配） | 中 |
| L2 | WinRT `UserNotificationListener` | 系统 toast 的 app+title+body | 低（未打包 Win32 应用授权常被拒，需 MSIX 身份） | 低-中 |
| L3 | UIA 扫聊天列表未读角标 | 「谁有几条未读」，无正文 | 高 | 低 |

推荐策略：**L1 为主，失败自动降级 L3**；L2 作为可选开关（能通就白拿）。
注意：微信/企微/飞书都是自绘弹窗，不走系统 toast，所以 L1 是拿到正文的现实主路径。

## 4. 技术方案

### 4.1 技术栈选型
| 方案 | 优点 | 缺点 |
|---|---|---|
| **A. Python 3.13 + PySide6 (Qt Quick/QML)** ← 推荐 | 本机已有 Python；win32 交互用 ctypes/comtypes 最直接；单进程单语言；QML 做动画与毛玻璃质感快；改一行即生效 | 打包体积中等 |
| B. Electron + TS | UI 最好写 | 原生钩子需 helper 进程或原生模块，多进程两层；体积大 |
| C. .NET 8 + WPF | 原生性能、体积最优 | 需装 SDK，UI 迭代慢 |

### 4.2 分层架构
```
win-dynamic-island/
  app/main.py              # 启动、托盘、热键、单实例锁
  app/island.py            # 悬浮窗（置顶/透明/非激活/点击穿透）+ QML 桥
  app/ui/Island.qml        # 收起胶囊 / 展开面板 / 卡片 / 动画
  adapters/base.py         # Adapter 接口：session_update / notification 事件
  adapters/codex.py        # rollout jsonl 增量 tail
  adapters/pi.py           # pi session jsonl 增量 tail
  adapters/workbuddy.py    # 心跳 + 可选 jsonl
  adapters/im_win32.py     # WinEvent hook + UIA 文本抽取
  core/state.py            # 会话状态机、通知去重/合并/未读
  core/jsonl_tail.py       # 增量读取（记录 offset + inode，防截断）
  core/config.py           # 配置与持久化（位置、屏蔽词、阈值）
  tests/                   # 用真实日志片段做 fixture 的单测
```

### 4.3 关键实现要点
- **非激活悬浮窗**：`WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_LAYERED`，避免点击抢焦点。
- **增量 tail**：按 (path, offset, size, mtime) 记录；文件变小/被替换则重置 offset，避免重复解析。
- **状态机**：`idle → thinking → tool_running → waiting_user → done`，事件驱动 + 静默超时双保险（事件缺位时也能收敛）。
- **线程模型**：所有适配器在 QThread / asyncio 或 `QThreadPool` 里跑 IO，主线程只收 signal 刷 UI；禁止阻塞主线程导致动画卡顿。
- **性能红线**：空闲时 CPU < 1%，轮询间隔 ≥ 1s，文件监听优先用 `QFileSystemWatcher` / ReadDirectoryChangesW，不暴力全盘扫。

## 5. 分期计划

### P0（先把画面跑起来）
1. 悬浮窗骨架：置顶胶囊 + 展开面板 + QML 动画 + 托盘 + 位置记忆
2. Codex 适配器（jsonl tail + 状态机 + 项目名 + 动作摘要）
3. pi 适配器（同构，复用 jsonl_tail）
4. WorkBuddy 适配器（心跳存活版）
5. 通知：L1 窗口钩子（先适配飞书，因其常开）
6. 配置文件 + 开机自启

### P1（变得好用）
- 通知去重合并、全部已读、专注模式
- 点击卡片/通知跳转（激活窗口 + UIA 定位会话）
- 企微、微信适配补齐
- 多显示器、DPI 缩放、深浅色主题跟随

### P2（变得精准）
- pi extension 主动上报（替代超时猜测）
- Codex 进程级校验（区分 Desktop / CLI / 已退出）
- L2 系统 toast 监听增强
- token/耗时统计、声音提示

## 6. 待你确认的问题

1. **技术栈**：Python + PySide6（推荐）/ Electron / .NET WPF？
2. **通知抓取策略**：直接上 L1 抓弹窗正文（效果好、需按你机器逐个适配）/ 先跑 L3 只报未读数（稳、但没内容）/ L1+L3 双路降级（推荐）？
3. **优先顺序**：先做 Agent 状态（确定性高），还是先啃 IM 通知（不确定性高）？
4. **微信**：常用吗？当前进程未运行，是否值得为它单独适配（4.x 版本弹窗结构需现场抓）？

## 7. 已知风险
- IM 三家的弹窗窗口类名与 UIA 树在版本升级后可能变化 → 适配层需可配置 + 提供「窗口探针」调试模式（打印新窗口的 class/title/text），坏了自己能修。
- WorkBuddy 会话日志是否可解析未验证 → 必须有降级路径。
- 微信 4.x / 企微新版可能对 UIA 做了限制 → 最差退化为「有新消息」提示，正文抓不到。
