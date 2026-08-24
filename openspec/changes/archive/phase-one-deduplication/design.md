# 设计方案：第一阶段重复逻辑收敛

## 请求服务层

新增图表服务和 DAG 服务，复用 `services/api.ts` 的 `apiClient`。健康检查继续使用 `chatService.checkHealth`。页面只负责加载状态和展示错误。

## 状态概览

新增通用 `StatusOverview`，接收状态卡片数组和无障碍标签；业务组件继续负责计算自身统计数据和状态。

## 图表表格

新增 `ChartTable`，统一处理 `columns`、`rows` 和普通图表 `labels`/`values` 的转换。`ChartContainer` 和 `ChartsPage` 均复用该组件，保留现有分页行为和页面视图布局。

## 兼容性

保留现有组件对外导出和图表数据类型，不改变 API 响应结构。改动完成后运行前端测试、TypeScript 检查和生产构建。
