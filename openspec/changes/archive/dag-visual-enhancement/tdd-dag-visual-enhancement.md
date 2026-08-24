# TDD 测试记录：DAG 看板视觉增强

| ID | 测试用例 | 验证方式 | 状态 |
|---|---|---|:--:|
| TC-DAG-01 | 任务摘要显示节点、连线和批次数量 | Vitest + RTL | 绿色 |
| TC-DAG-02 | 任务摘要显示任务类型和当前状态 | Vitest + RTL | 绿色 |
| TC-DAG-03 | 执行批次时间线显示每个批次及节点名称 | Vitest + RTL | 绿色 |
| TC-DAG-04 | 空执行批次不渲染时间线 | Vitest + RTL | 绿色 |
| TC-DAG-05 | DAG 页面现有流程图和查询逻辑不受影响 | Vitest / tsc / build | 绿色 |
