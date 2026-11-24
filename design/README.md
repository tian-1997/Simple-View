# WinIsland 玻璃质感 UI 材料包

本材料包用于 WinIsland（Python + PySide6 + QML）桌面通知 / Agent 聚合应用的视觉改版。

## 内容

- `preview/WinIsland-glass-concept.png`：已确认的深色 / 浅色玻璃质感方向概念图。
- `docs/UI-DESIGN-SPEC-v1.0.1.md`：视觉规范、布局、材质、动效、验收标准。
- `docs/BRAND-ASSET-GUIDE.md`：Agent / 聊天应用品牌 Logo 与功能图标素材规范。
- `assets/ASSET-MANIFEST.template.json`：品牌素材清单模板。
- `prompts/CODEX-MASTER-PROMPT.md`：给 Codex 的总提示词，约束先审查、后分阶段实现。
- `prompts/CODEX-ASSET-PROMPT.md`：品牌 Logo 与图标素材采集提示词。
- `prompts/CODEX-STAGE-PROMPTS.md`：分阶段实施提示词与阶段验收门槛。

## 重要边界

1. 这是设计材料包，不是已完成的代码改版。
2. 不要重写数据采集、适配器、状态机、Python/QML Bridge、托盘和窗口行为。
3. 不得伪造不可读取的通知正文、Agent 状态、项目名或操作内容。
4. 先完整检查仓库，再列文件影响范围与测试方案；未经阶段验收，不进入下一阶段。
5. 品牌 Logo 必须以本地资源方式打包，禁止运行时依赖网络加载。
6. 当前概念图是视觉参考，不是运行中的 QML 截图，也不代表真实模糊效果已实现。
