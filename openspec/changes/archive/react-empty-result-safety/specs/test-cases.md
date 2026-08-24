# 测试用例清单: ReAct 空结果安全阀

> 编码: UTF-8 | 变更: react-empty-result-safety

---

## 测试文件规划

| 测试文件 | 对应模块 | 类型 |
|---------|---------|:--:|
| `tests/test_agent_mock_boundary.py` | agent_core.py `_is_empty_result` + 计数器 | 纯 Mock |
| `tests/test_agent_boundary_verify.py` | agent_core.py 端到端空结果路径 | 端到端 |

---

## test_agent_mock_boundary.py 用例

| # | 用例ID | 描述 | 类型 |
|---|--------|------|:--:|
| TC-S01 | test_empty_string | 空字符串判定为 True | 边界 |
| TC-S02 | test_error_prefix | `[错误]` 前缀判定为 True | 边界 |
| TC-S03 | test_tool_failure_prefix | `[工具执行失败]` 前缀判定为 True (新增) | 边界 |
| TC-S04 | test_no_data_found_marker | `未检索到相关数据` 判定为 True (新增) | 边界 |
| TC-S05 | test_no_data_found_alt | `未找到相关数据` 判定为 True | 边界 |
| TC-S06 | test_no_data_marker | `无数据` 判定为 True | 边界 |
| TC-S07 | test_no_retrieve_marker | `没有检索到` 判定为 True | 边界 |
| TC-S08 | test_no_find_marker | `没有找到` 判定为 True | 边界 |
| TC-S09 | test_no_valid_value | `无有效数值` 判定为 True | 边界 |
| TC-S10 | test_insufficient_source | `来源文本不足` 判定为 True | 边界 |
| TC-S11 | test_unavailable_marker | `unavailable` 判定为 True | 边界 |
| TC-S12 | test_normal_result_false | 正常财务数据判定为 False | 功能 |
| TC-S13 | test_another_normal_false | 另一组正常数据判定为 False | 功能 |
| TC-C01 | test_continuous_empty_accumulate | 连续 3 次空结果，计数器累加到 3 | 功能 |
| TC-C02 | test_valid_result_reset | 有数据后计数器从 3 退回 0 | 功能 |
| TC-C03 | test_reset_log_output | 计数器重置时输出 INFO 日志 | 日志 |
| TC-C04 | test_empty_valid_empty_sequence | 空→有效→再空序列，计数器正确波动 | 功能 |
| TC-N01 | test_generate_forced_signature | `_generate_forced_answer` 签名包含 `reasoning_chain` | 修复 |
| TC-N02 | test_generate_forced_no_name_error | 调用 `_generate_forced_answer` 不触发 NameError | 修复 |
| TC-L01 | test_empty_detection_info_logs | 空结果判定输出 INFO 级日志 | 日志 |

---

## test_agent_boundary_verify.py 用例

| # | 用例ID | 描述 | 类型 |
|---|--------|------|:--:|
| TC-V01 | test_real_llm_empty_result | 真实 LLM 查询非注册公司，验证空结果路径 | 端到端 |
| TC-V02 | test_synthetic_empty_forced_stop | monkey-patch 全部返回 `[工具执行失败]`，验证 forced_stop=True + 降级答案非空 | 端到端 |
| TC-V03 | test_observation_markers_coverage | 手动传入 7 种 Observation，验证标记判定 | 边界 |
