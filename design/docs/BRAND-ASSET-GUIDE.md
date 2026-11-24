# 品牌素材与图标规范

## 目标素材清单
先以仓库实际适配器 / 配置为准，核实当前真正支持的产品，不要根据想象扩展。

初始盘点候选：
- Agent：Codex、pi、WorkBuddy
- 消息来源：微信、飞书、企业微信
- QQ：仅当当前项目确实支持时才纳入
- Claude 等未来工具：未接入前不得展示为已支持来源

## 获取优先级
1. 产品官网 / 官方品牌资源中心 / 官方 GitHub 仓库。
2. 产品官方组织发布的媒体资源或官方包内资源。
3. 许可明确、可再分发的图标库（例如 Lobe Icons 等），需核实具体图标许可。
4. 官方 favicon 仅作为最后兜底，不能把 favicon 当成高质量 Logo 的默认来源。

不得从不明来源的图标站随意下载，不得使用来源不明的 SVG。

## 本地化要求
- 资源必须下载到项目本地并随应用打包。
- 运行时禁止从互联网加载 Logo / 图标。
- 优先 SVG；只有 PNG 时使用透明背景 PNG。
- 按实际使用尺寸准备 16 / 20 / 24 / 32px 适配或确保 SVG 可缩放。
- 保持原始比例、品牌色与轮廓；不得擅自重绘或变色。
- 不强制所有 Logo 使用相同圆形遮罩；可使用统一的中性容器保证视觉秩序。
- 缺少可信素材时使用通用中性占位图标，并在清单标注待补齐。

## 目录建议
- `assets/branding/`：WinIsland 自身品牌
- `assets/agents/`：Agent 产品 Logo
- `assets/messaging/`：消息应用 Logo
- `assets/icons/`：功能性线性图标

## 清单字段
每个素材记录：
- id、product、category、file_path
- source_url、source_type、license
- attribution_required、official_asset
- downloaded_at、format、notes

商标说明：产品 Logo 仅用于识别集成来源，不暗示官方背书或合作关系。
