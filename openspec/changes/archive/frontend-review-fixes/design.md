# 技术设计：前端代码审查问题修复

## 类型分层

新增 `frontend/src/types/chart.ts` 定义 `ChartData`。图表组件、页面、图表服务和相关测试均从该模块导入，避免 `services` 依赖 `components`。

## DAG 节点类型

在 `frontend/src/constants/dag.ts` 从任务类型常量派生并导出 `DagNodeType`。`dagService` 的计划节点、`DagFlow` 的输入节点和 `DagBoardPage` 图例均引用该类型。后端返回的合法任务类型保持为 retrieve、calculate、compare、chart、verify、report。

## 测试

`ChartTable` 分页测试断言分页器中用户可见的页码文本，不再依赖 Ant Design 生成的 `list` role。
