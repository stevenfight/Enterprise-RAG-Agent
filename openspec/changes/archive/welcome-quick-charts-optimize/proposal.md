# 变更提案: 欢迎页 + 快捷指令 + 图表优化

> 编码: UTF-8

## 背景

方向 A（财务卡片 + 表格美化）与 B+C（主题切换 + 消息动效）已完成，前端观感明显提升。但仍有三个薄弱点：

1. **欢迎页过于朴素**：空对话态仅展示 `Welcome` 图标 + 标题 + 描述，缺少品牌质感和快捷入口，视觉重量不足。
2. **快捷指令入口弱**：示例问题仅存在于左侧「检索配置」面板，点击后只"填入输入框"（需再点一次发送），引导效率低。
3. **图表无暗色适配**：`ChartContainer` 与 `ChartsPage` 大量硬编码亮色（`#ffffff`、`#3D3554`、`#888`），暗色主题下图表区域颜色割裂。

## 目标

1. **欢迎页增强**：保留 `@ant-design/x` 的 `Welcome`，在其下方增加「快捷指令」区，点击直接发送问题；整体视觉融入马卡龙品牌色。
2. **图表暗色适配**：`ChartContainer` 通过可选 `dark` prop 切换图表配色与容器背景；`ChartsPage` 跟随全局主题。

## 方案

### W. 欢迎页 + 快捷指令

- `ChatContainer` 新增可选 prop `quickCommands?: string[]`：
  - 空消息态时，在 `Welcome` 下方渲染快捷指令胶囊按钮（马卡龙色描边 + hover 动效）
  - 点击直接调用 `onSend(command)` 发送问题
  - 未传入时不渲染该区域（向后兼容，不破坏现有测试）
- `ChatPage` 将已有 `EXAMPLE_QUESTIONS` 作为 `quickCommands` 传入，复用同一份问题列表。
- `Welcome` 图标卡片已使用 `gradients.hero` 渐变，保持并微调阴影，增强品牌感。

### G. 图表暗色适配

- `ChartContainer` 新增可选 prop `dark?: boolean`（默认 false，向后兼容）：
  - ECharts `option` 中标题、坐标轴文字、图例、tooltip 等颜色按 `dark` 切换
  - 外层卡片容器背景/边框按 `dark` 切换
  - 空数据占位文案颜色按 `dark` 切换
- `ChartsPage` 使用 `useTheme()` 获取 `isDark` 并传入 `dark`，同时适配页面标题与卡片配色。

## 非目标

- 不修改后端任何接口与数据格式。
- 不改变 SSE 流式、多 Agent、思维链逻辑。
- 不引入新的图表库或动画库。
- 不改动左侧「检索配置」面板布局结构。
