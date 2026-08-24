# TDD 测试用例：前端代码审查问题修复

| 用例编号 | 测试目标 | 初始状态 | 通过标准 |
| --- | --- | --- | --- |
| TC-FR-01 | 图表服务与图表组件引用共享 ChartData 类型 | <span style="color:green">绿</span> | `chartService` 不再从 `components` 导入类型 |
| TC-FR-02 | DAG 计划节点类型受联合类型约束 | <span style="color:green">绿</span> | `dagService`、`DagFlow`、`DagBoardPage` 复用 `DagNodeType` |
| TC-FR-03 | ChartTable 分页测试不依赖 `list` role | <span style="color:green">绿</span> | 测试断言分页器可见页码并通过 |
| TC-FR-04 | 前端验证无回归 | <span style="color:green">绿</span> | Vitest、TypeScript 检查和生产构建通过 |
