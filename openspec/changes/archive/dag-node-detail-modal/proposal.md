# 变更提案: DAG 节点详情展示与点击交互

> 编码: UTF-8

## 背景

DAG 看板（DagFlow）之前存在两个展示问题：

1. **节点无文字**：G6 v5 节点 `labelText` 配置为空字符串 `''`，导致画布上节点不显示任何文字，只有空白圆角方块。
2. **无详情交互**：节点仅显示简短标识，点击无反馈，用户看不到任务描述、使用工具、工具参数等具体详情。

## 目标

1. 节点显示主标签（任务 ID + 中文类型名）与副标签（任务描述）。
2. 点击节点弹出详情弹窗（Modal），展示任务 ID、类型、描述、工具、状态、工具参数。
3. 画布下方增加交互提示文案。

## 方案

- `DagFlow.tsx`:
  - `node.style.labelText` 由 `''` 改为 `'${data.label}'`，`data.label` 用 `T1 · 多公司对比`（复用 `TYPE_NAMES`）。
  - 新增副标签 `label2Text: '${data.description}'`（描述超 12 字截断）。
  - `DagNode` 接口新增 `tool_params`，写入节点 data。
  - 绑定 `graph.on('node:click', ...)`，点击后 `setSelectedNode` 打开 antd Modal。
  - Modal 内用 `Descriptions` 展示完整任务详情。

## 非目标

- 不改动后端 `/api/agent/plan` 返回结构。
- 不改变 DAG 布局算法与缩放/拖拽行为。
