# WinIsland · Windows 灵动岛

盯着 Codex / pi / WorkBuddy 的会话状态，以及微信 / 飞书 / 企业微信的 IM 通知。
PySide6 + QML 单进程实现，无边框置顶胶囊，点开是**同宽**面板（固定 240px，只向下长高度）；玻璃是**自绘真实背景模糊**。

## 现在能做什么

| 能力 | 状态 | 数据来源 |
|---|---|---|
| Codex 会话状态（推理中/执行工具/已完成 + 当前命令） | ✅ 已实测 | `~/.codex/sessions/**/rollout-*.jsonl` |
| pi 会话状态（含工具名、出错原因） | ✅ 已实测 | `~/.pi/agent/sessions/*/*.jsonl` |
| WorkBuddy 会话存活 + 项目名 + 时长 | ✅ 心跳 | `~/.workbuddy/sessions/<pid>.json` |
| 胶囊按 agent 个数摆 logo + 状态色描边环 | ✅ 已实测 | `pillAgents` / `pillKind` |
| 点会话行 / 通知行 → 跳到对应窗口 | ✅ 已实测 | `app/launcher.py` |
| 飞书 / 企微 / 微信弹窗 → 通知（发送人 / 群 / 正文） | ✅ 飞书真机通过；⚠️ 企微能命中但抽不到文本 | Win32 窗口钩子 + UIA 深度抽取（见下方「飞书正文」） |
| 胶囊 UI + 面板 + 托盘 + 拖动 + 深/浅主题 | ✅ | `app/qml/` |
| 玻璃材质（背景模糊 + 精确圆角） | ✅ 实测 | `app/backdrop.py` + `GlassSurface.qml` |

## 收起态：有几个 agent 就摆几个 logo

收起态不写应用名，左边按「有几个 agent 有会话」摆几个 logo（Codex 花标 / pi 的 π / WorkBuddy 的 app 图标），
同一个 agent 开多个会话只算一个。收起态和展开态**宽度都是 240px**（`theme.metrics.islandW`），
所以点开时只有高度在变，胶囊不会横向甩出去。顺序按状态紧急度：出错 → 等确认 → 推理中 → 执行工具 → 已完成 → 空闲。
每个 logo 外面套一圈 1.5px 状态描边（和胶囊外圈同一套颜色），空闲的整体压暗、不挂环。

胶囊外圈那条 1.5px 渐变描边取「最该被看见」的那个状态：

| 状态 | 边框 |
|---|---|
| 推理中 | 紫色渐变，缓慢呼吸（1.3s 一上一下） |
| 执行工具 | 蓝色渐变，同样呼吸 |
| 已完成 | 绿色渐变，常亮 |
| 等确认 | 琥珀渐变，呼吸 |
| 出错 | 红色渐变，常亮 |
| 空闲 / 无会话 | 无彩环，只有普通 1px 描边 |

「已完成」会一直亮到下一次有新事件为止（状态本来就保留，没有做倒计时回退）。

## 怎么用

| 操作 | 效果 |
|---|---|
| 点胶囊 | 展开面板 |
| 再点顶栏（胶囊原位那一带，右侧三个按钮除外） | 收起面板 |
| 点某个会话行 | 跳到那个 agent 的窗口（Codex→ChatGPT 桌面端，WorkBuddy→WorkBuddy，pi→它所在的终端），**拉到最前**；找不到就打开项目目录。跳转后岛自动收起 |
| 点某条通知 | 跳到对应 IM 的主窗口，同样拉到最前 |
| 按住拖动 | 移动岛的位置（系统级拖动），拖完松手不会误触发点击 |
| 托盘图标 | 左键切换开合，右键菜单有主题 / 重新居中 / 退出 |
| 面板右上三个按钮 | 浅深主题、设置、隐藏窗口 |

展开时窗口是围绕当前中心向两侧打开、收起时向中线合拢，所以岛不会一边长；拖到屏幕边上再开合也不会跳回屏幕中间。

### 点会话 / 通知之后：只拉最前，不锁定

不做置顶（不改窗口的 `WS_EX_TOPMOST`）：点了就激活到最前，之后你切到别的窗口它照常退到后面。
步骤是：

1. 最小化就先 `SW_RESTORE`，没最小化就 `SW_SHOW`；
2. 抢前台 —— 先 `AttachThreadInput` 挂到前台线程和目标线程共享输入状态再 `SetForegroundWindow`，
   被拒就轻敲一次 Alt 再试，最后才临时把前台锁超时设为 0（用完立刻还原）。

三种会失败的情况：目标以管理员权限运行（UIPI 挡住普通权限进程）、屏幕锁定
（`GetForegroundWindow()` 返回 NULL，谁也抢不到前台）、目标在别的虚拟桌面。
失败时日志里会写「置前失败」，成功是「前台」。

注意：岛自己是常驻置顶窗口，目标窗口不会被置顶，所以它会压在岛下面一角（不会压在别的窗口下面）。


## 快速开始

依赖装在工程自己的 `.venv` 里，**不要用系统 Python**（本机 PATH 上的 `python` 是 3.14.7，
和装依赖的解释器不是同一个，直接 `python main.py` 会报 `No module named 'PySide6'`）。

```bash
# 首次：建 venv 并装依赖（一次性，PySide6 约 150MB）
python -m venv .venv
.venv\Scripts\python.exe -m pip install PySide6 comtypes psutil uiautomation

# 起岛
run.bat                    # 静默启动，不留控制台窗口
run-debug.bat              # 带控制台，能看到 traceback 和 QML 警告
run.bat --theme light      # 参数会透传给 main.py

# 不走 bat 时（任何目录都可以，路径按 __file__ 解析）
.venv\Scripts\python.exe app\main.py

# 指定演示状态 / 固定主题
.venv\Scripts\python.exe app\main.py --state panel --theme light

# 渲染评审图（自绘玻璃，窗口抓图即成品）
.venv\Scripts\python.exe app\main.py --snapshot panel --showcase --out docs/preview/panel_dark.png
.venv\Scripts\python.exe tools/render_showcase.py     # 一次渲全部六个状态

# 看现在识别到哪些会话（不开界面）
.venv\Scripts\python.exe tools/agents_probe.py
.venv\Scripts\python.exe tools/agents_probe.py --file <某个 rollout.jsonl>   # 校验解析逻辑

# 校验 IM 弹窗抓取：运行期间让别人给你发条消息
.venv\Scripts\python.exe tools/window_probe.py --seconds 60
```

`--state` 取值：`live`（默认，接实时数据）/ `pill` / `panel` / `attention` / `empty`。
`--theme` 取值：`dark` / `light` / `system`。

## 打包成 exe

```bat
build.bat
```

产出 `dist\WinIsland.exe`：单文件、双击即用、不依赖本机 Python。两步流水线：

1. `tools\make_icon.py` —— 把 `logo\simple-view-icon.png`（透明底）裁掉空边、按 88% 占比居中，
   输出 `assets\branding\app-icon.png`（运行时托盘/窗口图标）和 `build\WinIsland.ico`（9 个尺寸，exe 图标）。
   想换成深色圆角底板那版：`python tools\make_icon.py --src logo\simple-view-icon-dark.png`。
2. `pyinstaller WinIsland.spec` —— QML、assets、PySide6 的 QML 插件按原相对位置塞进去，
   再按黑名单裁掉用不到的 Qt 库（WebEngine / Quick3D / Charts / Multimedia 等，见 spec 里的 `PRUNE_PREFIXES`）。

窗口程序没有控制台，`print(..., file=sys.stderr)` 会因为 `sys.stderr is None` 直接抛异常，
所以冻结后日志统一写到 `%LOCALAPPDATA%\WinIsland\WinIsland.log`（超 2MB 自动清一次）。

## 目录

```
run.bat                 # 静默启动（pythonw，无控制台）
run-debug.bat           # 带控制台启动（排查用）
build.bat               # 打包：logo → 图标 → dist\WinIsland.exe
WinIsland.spec          # PyInstaller 配方（QML/素材/裁剪规则都在这）
.venv/                  # 工程专用虚拟环境（不进版本库）
logo/                   # 品牌源图（透明底 png/svg + 深色底板版）
assets/branding/        # 由 logo 归一出来的 app-icon.png（运行时图标）
app/main.py             # 入口：QML 窗口 + 桥 + 托盘 + 1s 轮询
app/launcher.py         # 点会话/通知 → 找宿主窗口并置前（含前台锁规避）
app/backdrop.py         # 自绘玻璃：抓窗口背后的屏幕（排除自身）→ 降采样
app/material.py         # 系统 acrylic 回退（抓不到背景时用）
app/adapters.py         # Codex / pi / WorkBuddy 适配器 + 增量 tail
app/notify_win32.py     # SetWinEventHook + UIA 抽取（工作线程）
app/tokens.py           # 颜色 / 尺寸 / 动效 / 玻璃 tint 的唯一来源
app/theme.py            # 主题桥（跟随系统深浅色）
app/mock.py             # 演示数据
app/qml/                # Main / Island / Pill / Panel / GlassSurface / 行组件
tools/render_showcase.py# 批量渲染六个状态
tools/click_probe.py    # 用真实鼠标事件验证「点击开合 / 拖动跟手」
tools/proc_probe.py     # 列出进程的 cwd / 父链 / 可见窗口，用来确认「点击该唤醒谁」
tools/make_icon.py      # logo → app-icon.png + 多尺寸 ico
tools/focus_probe.py    # 验证「点岛 → 目标窗口拉最前且不被设 topmost」
tools/parse_probe.py    # 通知文案解析的回归测试（42 项，含飞书三种形态与踩过的坑）
tools/uia_probe.py      # dump 任意 IM 窗口的 UIA 文本树，查「抽不到内容」用
tools/version_info.txt  # exe 版本资源（属性面板里那几行）
tools/material_probe.py # 材质对照实验（有/无模糊、多级 tint）
docs/PLAN.md            # 需求与技术方案
docs/preview/           # 界面渲染图 + index.html 展示页
design/                 # UI 设计包（规范 / 提示词 / 概念图）
```

## 玻璃是怎么做的（以及为什么不用系统 acrylic）

系统 `SetWindowCompositionAttribute` 的模糊层由 DWM 合成，**不受 `SetWindowRgn` 约束**：
胶囊是圆角时，模糊底会是一个方角矩形从圆角外面露出来（本机实测复现，见 `tools/material_probe.py`）。

所以改成自绘：

1. `SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)` —— 窗口不出现在自己的截屏里，否则会自我反馈；
2. `QScreen.grabWindow(0)` 抓窗口覆盖的那块屏幕，按 1/6 降采样（降采样本身就是廉价模糊）；
3. QML 侧 `Image` 拉回原尺寸 + `MultiEffect` 高斯模糊 + 圆角遮罩 + 着色层 + 顶部高光 + 1px 描边。

刷新策略：尺寸/位置变化后 90ms 合并抓一次；静止时每 2.5s 刷一帧（背后窗口变了玻璃跟着变），
窗口建好后额外补抓 180/480/1100ms 三帧，避免抓到还没画出来的桌面。

抓不到背景时自动回退：先用系统 acrylic（会露出方角），再不行用不透明底色 `fallbackFill`。

## 踩过的坑

- `font.pixelSize` 在 Qt6 是整型，写 `11.5` 会让整个组件静默失效。
- Column 的 `id` 不能和 delegate 的属性同名（曾用 `id: body` 撞上 NotifyRow 的 `body`，delegate 创建失败、高度 0）。
- `Repeater` 创建的子项会追加到父项末尾，靠声明顺序定位不可靠 —— 面板里全部改成显式 `y`。
- `Font.DemiBold` 在微软雅黑里不存在，Qt 会合成加粗（叠画偏移，看起来发虚），改用 `Font.Bold`。
- 透明窗上 ClearType 会画出彩色描边：除了 `QFont.NoSubpixelAntialias`，还要 `QQuickWindow.setTextRenderType(QtTextRendering)`。
- `QImage.scaled()` 不接受裸整数枚举；`QImage` 带 dpr 时 `drawImage` 会按逻辑尺寸缩小。
- `MultiEffect` 的遮罩源要单独成项（`visible: false` + `layer.enabled: true`，内部放圆角矩形），直接把带 radius 的 Rectangle 当 maskSource 不生效。
- `onPressed: (mouse) => {...}` 这种箭头函数写在**内联 component** 里不会被当成信号处理器（点击完全没反应，且不报错）；用 `mouseX / mouseY` 属性代替信号参数最稳，也顺手避开了「向信号处理器注入参数已废弃」的警告。
- `MouseArea` 的 `clicked` 在按下后拖动再松手时**仍会触发**，所以「点击」和「拖动」不能共存于 `onClicked`；必须自己记按下点、位移超阈值就不算点击。
- 曾经展开时窗口要往两侧长，试过让窗口跟着 QML 的宽度动画逐帧 `setX` 居中：每次移动都触发背板抓图，主线程被阻塞，定时器跑不完动画就收工（实测只居中到一半）。
  现在展开态与收起态同宽（240px），宽度恒定、只有高度动画，这套居中逻辑直接删掉了。
- **不要手算 `mouseX` 位移来区分点击和拖动**：窗口自己展开/收起时会移动，MouseArea 会连续收到 positionChanged，坐标甚至会归零，点击被误判成拖动（表现为「点一下没反应」）。用 MouseArea 自带的 `drag.threshold` + `drag.onActiveChanged`。
- 用 `SendMessage(WM_NCLBUTTONDOWN, HTCAPTION)` 让系统拖动无边框窗口最跟手，但它是**嵌套事件循环**：里面刷新数据会让 Repeater 重建行对象、把正在执行的信号处理器连对象删掉，Qt 直接崩溃（`Object destroyed while one of its QML signal handlers is in progress`）。拖动期间要挡住 `set_agents` / `set_notifs`。

## 已知限制（重要）

1. **飞书正文**（2026-11-24 真机验证通过）：飞书是 Electron，UIA 树前 8 层全是 Chromium 外壳
   （`NonClientFrameView`、几十个 `PageToolbar*` 按钮），Web 内容在 d9 的 `Chrome Legacy Window`
   之下、`Document 'messenger'`（d10）里面，真实文本要到 **d15~d22**。
   旧参数 `max_depth=3 / max_nodes=18` 只够看到外壳（实测同一个窗口只能抽到 1 条 `'飞书'`），
   于是永远降级成「未知发送人 / 未读到内容」。现在深度给到 22、节点 160，外壳名字不占预算；
   再加两层兜底：启动时预热一次主窗口（Chromium 的无障碍树是按需开启的），
   通知窗刚弹出时按 0 / 0.35 / 0.9 秒重试三次。
   实测日志（发消息后把飞书最小化，等机器人回复）：
   `notify 飞书 sender='田圆的飞书助手' body='翻阅资料,生成答案中。' tries=1 nodes=2`
   - 飞书助手这类弹窗的第二行是「发送人简称: 正文」，正文原本带着 `飞书助手: ` 前缀，
     现按「左半是应用别名 / 是已定发送人的后缀」剥掉；
   - 一条弹窗会派发多个 hwnd（外壳窗 + 0x0 渲染子窗），抽空的那个紧跟在成功解析 6 秒内
     视为影子事件丢弃，否则每次都会多出一条「未知发送人」。
   排障开关：建 `%LOCALAPPDATA%\WinIsland\notify-debug.flag`（或设 `WINISLAND_NOTIFY_DEBUG=1`），
   会打印 `notify-skip proc=… WxH` / `notify-skip size …` / `notify-drop empty echo …`。
   解析规则和踩过的坑锁在 `tools/parse_probe.py`（42 项断言，改启发式前先跑一遍）。
2. **一条通知只显示一条正文**：受 UIA 树形态限制，多行消息目前取「最长的一行」，
   不是整段拼接；同一窗口 5 秒内的多条消息会被去重成一条。
3. **pi 没有官方 logo**：只有 Codex（simple-icons）和 WorkBuddy（从 exe 提取）是真图标，
   pi 用紫渐变圆角底 + π 字标占位。
4. **点「打开」是按进程猜的**：Codex 桌面版找到的是 `ChatGPT.exe` 的窗口，pi 只能按 cwd 找它所在的终端；
   找不到窗口时不启动新进程，只打开项目目录。目标以管理员权限运行时抢不到前台（UIPI），
   这种时候只能退到任务栏闪烁；屏幕锁定期间任何程序都抢不到前台。
5. **企业微信仍是「未知发送人 / 未读到内容」**（2026-11-24 实测）：企微弹窗能命中，但
   `nodes=0` —— 那个窗口的 UIA 树一句文本都没有，重试三次也一样。飞书那套深度参数救不了它，
   得先确认企微 4.x 通知窗是不是纯自绘（DuiLib / XAML Island），再决定走 OCR 还是别的入口。
6. 会话耗时从「岛上第一次看到它」开始算，不是从 `task_started` 算（尾读窗口里没有起点）。
7. 会话名取首条用户消息的前 28 字，取不到就退回项目目录名。
8. 通知只跳到 IM 主窗口，没有跳到具体会话；也没有去重合并（同一会话连发仍是两条）。
9. 「已完成」的绿色边框会一直亮着，直到下一次有新事件，没有做倒计时回退。
10. 自绘玻璃在「窗口背后正好是视频/游戏」时会频繁重抓，暂未做按内容变化率自适应。

## 下一步

- P1：OCR 兜底拿到 IM 正文；通知跳到具体会话；同会话合并
- P1：悬停展开 / 移开收起（目前是点胶囊展开、再点顶栏收起）
- P1：给 pi 补一张真 logo；「已完成」按时间回退到空闲
- P2：pi 扩展主动上报状态（比解析日志更准）；Codex 进程级校验
