# TDD 测试用例: 前端多 Agent 流式可视化（阶段十）

> 编码: UTF-8
> 约定: <span style="color:red">红色</span> = 未通过, <span style="color:green">绿色</span> = 已通过

---

## 一、测试文件规划

| 文件 | 测试范围 |
|------|---------|
| `frontend/src/utils/__tests__/agentEvent.test.ts` | SP10-A / SP10-B / SP10-C 的纯函数单元测试（Vitest，不依赖浏览器/网络） |

---

## 二、测试用例

### SP10-A: 多 Agent 事件类型识别

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-10-A-01 | 识别多 Agent 事件类型 | 对 `orchestrator_start/delegating/worker_step/worker_done/workers_done/answer_chunk/reflection` 调用 `isMultiAgentEventType` | 均返回 `true` | <span style="color:green">GREEN</span> |
| TC-10-A-02 | 识别单 Agent 事件类型 | 对 `connected/thought/action/observation/answer/error/done` 调用 `isMultiAgentEventType` | 均返回 `false` | <span style="color:green">GREEN</span> |

---

### SP10-B: 多 Agent 事件 reducer 映射

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-10-B-01 | orchestrator_start 初始化多 Agent 状态 | 对空 accumulator 应用 `orchestrator_start`（registered_agents=[DataAgent,CalcAgent]） | `agentRun.isMultiAgent==true`，`registeredAgents` 记录 2 个，`workers` 为空 | <span style="color:green">GREEN</span> |
| TC-10-B-02 | delegating 初始化 Worker 状态 | 在 B-01 基础上应用 `delegating`（agents=[DataAgent,ChartAgent]） | `workers` 含 2 个状态，均为 `done=false` | <span style="color:green">GREEN</span> |
| TC-10-B-03 | worker_step 追加步骤 | 应用 `worker_step`（agent=DataAgent, step_type=thought, step=1, content=...） | 对应 Worker 的 `steps` 增加 1 条，含 agent/step_type/step/content | <span style="color:green">GREEN</span> |
| TC-10-B-04 | worker_step 未知 Worker 自动创建 | 对空 accumulator 直接应用 `worker_step`（agent=ChartAgent） | 自动创建 ChartAgent Worker 并追加步骤 | <span style="color:green">GREEN</span> |
| TC-10-B-05 | worker_done 标记完成 | 应用 `worker_done`（agent=DataAgent, success=true, total_elapsed_ms=6916） | 对应 Worker `done=true`，`success=true`，`elapsed_ms=6916` | <span style="color:green">GREEN</span> |
| TC-10-B-06 | answer_chunk 追加答案 | 依次应用两个 `answer_chunk`（"中国移动营收..."，"中国联通..."） | `answer` 累积为两段拼接 | <span style="color:green">GREEN</span> |
| TC-10-B-07 | answer 设置最终答案 | 在 B-06 基础上应用 `answer`（content=完整答案, workers=2） | `answer` 覆盖为完整答案 | <span style="color:green">GREEN</span> |
| TC-10-B-08 | done 标记完成 | 应用 `done` 事件 | `done==true` | <span style="color:green">GREEN</span> |

---

### SP10-C: 单 Agent 事件 reducer 回归

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-10-C-01 | thought 追加推理链 | 应用 `thought`（step=1, content=...） | `reasoningChain` 增加 1 条，含 step_number/thought | <span style="color:green">GREEN</span> |
| TC-10-C-02 | action 更新最后一步 | 先 thought 再 action（step=1, content=retrieve, action_input=...） | 最后一步的 action/action_input 更新 | <span style="color:green">GREEN</span> |
| TC-10-C-03 | observation 更新最后一步 | 先 thought 再 observation（step=1, content=...） | 最后一步的 observation 更新 | <span style="color:green">GREEN</span> |
| TC-10-C-04 | answer 设置最终答案 | 应用 `answer`（content=最终答案） | `answer` 为最终答案，`agentRun` 保持 null | <span style="color:green">GREEN</span> |
| TC-10-C-05 | done 标记完成 | 应用 `done` | `done==true` | <span style="color:green">GREEN</span> |

---

## 三、测试统计

| 规范 | 测试用例数 | 已通过 | 未通过 |
|------|:--:|:--:|:--:|
| SP10-A | 2 | 2 | 0 |
| SP10-B | 8 | 8 | 0 |
| SP10-C | 5 | 5 | 0 |
| **合计** | **15** | **15** | **0** |
