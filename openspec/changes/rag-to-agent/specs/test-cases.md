# 测试用例清单: RAG-Agent

> 编码: UTF-8 | 变更: rag-to-agent

---

## 测试文件规划

| 测试文件 | 对应模块 | 优先级 |
|---------|---------|:---:|
| `tests/test_agent_core.py` | agent_core.py | P0 |
| `tests/test_agent_tools.py` | tools/* | P0 |
| `tests/test_agent_memory.py` | agent_memory.py | P1 |
| `tests/test_reflector.py` | reflector.py | P1 |

---

## test_agent_core.py 用例

| # | 用例ID | 描述 | 类型 |
|---|--------|------|:--:|
| TC-A01 | test_single_step_retrieve | 单步检索查询"中芯国际2024年营收"，预期 ≤2 步完成 | 功能 |
| TC-A02 | test_multi_step_comparison | 多公司对比查询，预期 ≥3 步，结果包含两家公司数据 | 功能 |
| TC-A03 | test_max_steps_forced_stop | 设置 max_steps=2，模拟复杂查询，验证强制停止 | 边界 |
| TC-A04 | test_final_answer_detection | 验证 LLM 返回 Final Answer 时正确识别并停止 | 功能 |
| TC-A05 | test_format_error_retry | 模拟 LLM 返回非法格式，验证重试机制 | 异常 |
| TC-A06 | test_tool_not_found | Action 指定不存在的工具，验证错误处理 | 异常 |
| TC-A07 | test_tool_execution_failure | 工具返回 success=False，验证不终止流程 | 异常 |
| TC-A08 | test_llm_timeout | LLM 调用超时，验证优雅终止 | 异常 |
| TC-A09 | test_reasoning_chain_complete | 完成查询后验证 reasoning_chain 包含完整步骤 | 功能 |
| TC-A10 | test_empty_tool_registry | ToolRegistry 为空时的行为 | 边界 |

---

## test_agent_tools.py 用例

| # | 用例ID | 描述 | 类型 |
|---|--------|------|:--:|
| TC-T01 | test_retrieve_no_company | 不限公司检索，验证返回 4 家公司的结果 | 功能 |
| TC-T02 | test_retrieve_specific_company | 指定"中芯国际"检索，验证仅返回该公司结果 | 功能 |
| TC-T03 | test_retrieve_empty_result | 检索无匹配，验证返回空列表 | 边界 |
| TC-T04 | test_calculator_growth_rate | 计算同比增长率 (1250-1000)/1000*100，预期 25.0% | 功能 |
| TC-T05 | test_calculator_invalid_expression | 传入非法表达式，验证安全拦截 | 安全 |
| TC-T06 | test_compare_two_companies | 对比中国移动和联通营收，验证返回对比表 | 功能 |
| TC-T07 | test_compare_coverage_guarantee | 某公司数据不足，验证保底机制触发 | 边界 |
| TC-T08 | test_chart_bar_generation | 生成柱状图，验证文件存在 | 功能 |
| TC-T09 | test_chart_no_matplotlib | matplotlib 未安装，验证优雅降级 | 异常 |
| TC-T10 | test_verify_data_match | 验证数据与来源一致，预期 valid=True | 功能 |
| TC-T11 | test_verify_data_mismatch | 验证数据与来源不一致，预期 valid=False | 功能 |
| TC-T12 | test_verify_insufficient_source | 来源文本不足，预期 valid=None | 边界 |

---

## test_agent_memory.py 用例

| # | 用例ID | 描述 | 类型 |
|---|--------|------|:--:|
| TC-M01 | test_working_memory_add | 添加 3 步记录，验证 get_working_context() 完整 | 功能 |
| TC-M02 | test_working_memory_reset | reset_working() 后验证列表为空 | 功能 |
| TC-M03 | test_working_memory_limit | 超过 10 条记录，验证自动淘汰 | 边界 |
| TC-M04 | test_episodic_summarize | summarize_to_episodic() 后验证摘要追加 | 功能 |
| TC-M05 | test_episodic_context | 3 轮历史后获取上下文，验证返回最近轮次 | 功能 |
| TC-M06 | test_long_term_disabled | enable_long_term=false 时验证 get_long_term 返回 None | 功能 |
| TC-M07 | test_conversation_manager_compat | 与 ConversationManager 同时存在，验证不干扰 | 兼容 |

---

## test_reflector.py 用例

| # | 用例ID | 描述 | 类型 |
|---|--------|------|:--:|
| TC-R01 | test_hallucination_detected | 答案数值与来源不一致，验证检测 | 功能 |
| TC-R02 | test_no_hallucination | 答案数值与来源一致，验证通过 | 功能 |
| TC-R03 | test_multi_datapoint_verify | 3 个数据点逐条验证，返回逐条结果 | 功能 |
| TC-R04 | test_source_completeness_full | 全部有来源，评分 ≥ 0.9 | 功能 |
| TC-R05 | test_source_completeness_partial | 部分无来源，评分 < 1.0 | 功能 |
| TC-R06 | test_answer_completeness_check | 问题有两问，答案只答一问，评分 < 0.5 | 功能 |
| TC-R07 | test_auto_correct_hallucination | 检测到幻觉且 auto_correct=True，验证修正 | 功能 |
| TC-R08 | test_auto_correct_disabled | auto_correct=False 时验证仅追加警告 | 功能 |

---

## 回归测试（管道模式保持不变）

| 测试文件 | 说明 |
|---------|------|
| `tests/integration_test.py` | 端到端 RAG 流程，Agent 开发全周期持续运行 |
| `tests/tdd_all_optimizations.py` | 全量 TDD 回归，每阶段完成后运行 |
| `tests/test_document_integration.py` | 文档接入自动化测试 |

**回归标准**: Agent 开发过程中，3 个回归测试文件的通过率不得低于开发前基线。

---

## 运行命令

```bash
# 全量测试
python tests/tdd_all_optimizations.py

# Agent 专项测试
python tests/test_agent_core.py
python tests/test_agent_tools.py
python tests/test_agent_memory.py
python tests/test_reflector.py

# 集成验证
python tests/integration_test.py
python tests/test_document_integration.py
```
