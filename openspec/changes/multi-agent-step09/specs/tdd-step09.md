# TDD 测试用例: 多 Agent 升级 - 阶段九 启用/运行验证 + 可靠性回归补测

> 编码: UTF-8
> 约定: <span style="color:red">红色</span> = 未通过, <span style="color:green">绿色</span> = 已通过

---

## 一、测试文件规划

| 文件 | 测试范围 |
|------|---------|
| `tests/tdd_multi_agent_step09.py` | SP9-A / SP9-B / SP9-C 的单元测试（不依赖 LLM） |

---

## 二、测试用例

### SP9-A: 多 Agent 启用验证

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-09-A-01 | AgentRegistry 注册 5 个 Worker | 注册 DataAgent/CalcAgent/CompareAgent/ChartAgent/VerifyAgent 能力 | `list_all()` 返回 5 个名称，`get_agent_descriptions()` 包含全部名称 | <span style="color:green">GREEN</span> |
| TC-09-A-02 | QueryRouter 多公司对比路由到 multi_agent | `route("中国移动和中国联通2024年营收对比")` | `mode == "multi_agent"` 且 `trace == "regex"` | <span style="color:green">GREEN</span> |
| TC-09-A-03 | OrchestratorAgent 初始化正确 | 创建 OrchestratorAgent，传入 delegate_tool + agent_registry | 工具仅含 `delegate`，`model == "qwen-max"`，`_agent_descriptions` 含 Worker 名 | <span style="color:green">GREEN</span> |
| TC-09-A-04 | DelegateTool 依赖分组正确 | 传入 DataAgent/CalcAgent/CompareAgent/ChartAgent/VerifyAgent 任务 | 分两批：`[DataAgent, CalcAgent]` 并行，其余为下游批 | <span style="color:green">GREEN</span> |
| TC-09-A-05 | DelegateTool 创建 5 种 Worker | 对 5 种 cap 调用 `_create_agent` | 返回对应 Worker 实例类型 | <span style="color:green">GREEN</span> |
| TC-09-A-06 | DelegateTool 空 tasks 返回失败 | `run(tasks=[])` | `success == False` | <span style="color:green">GREEN</span> |

---

### SP9-B: 多 Agent 运行链路验证

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-09-B-01 | delegate 动作解析（嵌套 tasks JSON） | `_parse_response` 解析含 `Action: delegate` + 嵌套 tasks 数组 | `action == "delegate"`，`action_input` 为含 tasks 的 dict | <span style="color:green">GREEN</span> |
| TC-09-B-02 | delegate 工具路由 | `_execute_action("delegate", {"tasks": [...]})` | 调用 delegate 工具并返回其 Observation | <span style="color:green">GREEN</span> |
| TC-09-B-03 | Worker 执行写回 SharedMemory | mock `_create_agent` 返回 fake worker，调用 `_run_worker_task` | 返回 success，SharedMemory 写入 `DataAgent(公司)` 结果 | <span style="color:green">GREEN</span> |
| TC-09-B-04 | Orchestrator 完整链路汇总 | mock `_call_llm`（delegate → Final Answer）+ mock Worker | 返回最终答案，SharedMemory 含 Worker 结果，推理链含 delegate 步骤 | <span style="color:green">GREEN</span> |

---

### SP9-C: 3 个修复点回归

#### SP9-C1: delegate 嵌套 JSON 平衡括号解析（`_extract_json_object`）

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-09-C1-01 | 简单 JSON 对象提取 | 输入 `{"a": 1}` | 返回 `{"a": 1}` | <span style="color:green">GREEN</span> |
| TC-09-C1-02 | 嵌套 JSON（delegate tasks 数组）完整提取 | 输入含多层花括号的 tasks 数组 JSON | 返回完整 JSON（到匹配的 `}`） | <span style="color:green">GREEN</span> |
| TC-09-C1-03 | 字符串值内含花括号不提前结束 | 输入 `{"text": "a{b}c"}` | 返回完整 JSON | <span style="color:green">GREEN</span> |
| TC-09-C1-04 | 字符串值内含转义引号正确跳过 | 输入含 `\"` 的 JSON | 返回完整 JSON | <span style="color:green">GREEN</span> |
| TC-09-C1-05 | 无 `{` 返回 None | 输入 `no json here` | 返回 None | <span style="color:green">GREEN</span> |
| TC-09-C1-06 | 缺失闭合括号返回 None | 输入 `{"a": 1` | 返回 None | <span style="color:green">GREEN</span> |

#### SP9-C2: Action=Final 空正文回退 Thought（`_parse_response`）

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-09-C2-01 | `Action: Final` 无正文回退 Thought | 输入 `Thought: 答案X\nAction: Final` | 返回 `(thought, "Final Answer", "答案X")` | <span style="color:green">GREEN</span> |
| TC-09-C2-02 | `Final Answer:` 正常正文 | 输入 `Thought: ...\nFinal Answer: 完整答案` | 返回 `(thought, "Final Answer", "完整答案")` | <span style="color:green">GREEN</span> |
| TC-09-C2-03 | `Action: Final` 带 JSON answer 提取 | 输入含 `Action Input: {"answer": "答案"}` | 返回 `(thought, "Final Answer", "答案")` | <span style="color:green">GREEN</span> |
| TC-09-C2-04 | `Action: Final` 无正文且无 Thought | 输入 `Action: Final` | 返回空答案 | <span style="color:green">GREEN</span> |
| TC-09-C2-05 | 非 JSON Action Input 回退 | 输入含 `Action Input: 纯文本参数` | action_input 为纯文本字符串 | <span style="color:green">GREEN</span> |

#### SP9-C3: 单位换算规则 prompt 覆盖

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-09-C3-01 | YAML 6 个 section 含百万元换算 | 检查 default/data_agent/calc_agent/compare_agent/verify_agent/orchestrator | 均含 `百万元 ÷ 100` | <span style="color:green">GREEN</span> |
| TC-09-C3-02 | fallback prompt 含换算公式与示例 | 检查 `_default_system_prompt` | 含 `百万元 ÷ 100 = 亿元` 和 `10,407.59亿元` | <span style="color:green">GREEN</span> |
| TC-09-C3-03 | YAML default 含正确示例值 | 检查 default.template | 含 `10,407.59亿元` | <span style="color:green">GREEN</span> |
| TC-09-C3-04 | 换算数值正确性 | 计算 `1040759 / 100` | 等于 10407.59，不等于 1040.76 | <span style="color:green">GREEN</span> |

---

## 三、测试统计

| 规范 | 测试用例数 | 已通过 | 未通过 |
|------|:--:|:--:|:--:|
| SP9-A | 6 | 6 | 0 |
| SP9-B | 4 | 4 | 0 |
| SP9-C1 | 6 | 6 | 0 |
| SP9-C2 | 5 | 5 | 0 |
| SP9-C3 | 4 | 4 | 0 |
| **合计** | **25** | **25** | **0** |
