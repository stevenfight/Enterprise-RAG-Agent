# TDD 测试用例: DAG 节点详情展示与点击交互

> 编码: UTF-8
> 图例: 红色 = 未验证（待实现）, 绿色 = 已通过
> 验证方式: npx vitest run src/components/dag/__tests__/DagFlow.test.tsx

---

## 模块 DD: 节点详情弹窗

| ID | 测试用例 | 操作 | 期望 | 状态 |
|----|---------|------|------|:--:|
| DD-01 | 点击节点弹出任务详情 | 触发 node:click (T1) | 显示「任务详情 - T1」与任务描述 | 绿色 |
| DD-02 | 详情弹窗展示工具参数 | 触发 node:click (带 tool_params 节点) | 显示公司/指标等参数 | 绿色 |

> 回归说明: 既有 8 个用例（渲染/空状态/实例管理/卸载/高度）在 `labelText`、`graph.on` 改动后仍全部通过（mock 补充 `on: vi.fn()`）。
