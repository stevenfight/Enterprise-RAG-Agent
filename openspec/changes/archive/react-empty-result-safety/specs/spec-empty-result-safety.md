# Spec: ReAct 空结果安全阀

> 编码: UTF-8 | 变更: react-empty-result-safety

---

## 概述

在 ReAct 主循环中增加三层安全阀，防止 LLM 在空结果检索上陷入无效循环。

## Requirement: 空结果检测

Agent SHALL 能准确识别工具返回的空结果/失败结果。

### Scenario: 工具执行失败被识别为空结果
- **WHEN** Observation 以 `[错误]` 或 `[工具执行失败]` 开头
- **THEN** `_is_empty_result()` 返回 True

### Scenario: 空检索结果被识别为空结果
- **WHEN** Observation 包含 `未检索到相关数据` 或 `未找到相关数据`
- **THEN** `_is_empty_result()` 返回 True

### Scenario: 正常结果不被误判为空
- **WHEN** Observation 包含有效的财务数据（如"营收 578 亿元"）
- **THEN** `_is_empty_result()` 返回 False

## Requirement: 空结果计数器

Agent SHALL 维护 `empty_result_count`，连续空结果时累加，有有效结果时退回。

### Scenario: 连续空结果累加
- **GIVEN** 当前 empty_result_count = 0
- **WHEN** 连续 3 次工具返回空结果
- **THEN** empty_result_count = 3
- **AND** 达到 2 时输出 WARNING 日志

### Scenario: 有效结果后计数器退回
- **GIVEN** 当前 empty_result_count = 2
- **WHEN** 下一次工具返回有效结果
- **THEN** empty_result_count = 1
- **AND** 若归零则输出 INFO 日志"计数器已重置为0"

## Requirement: 强制降级答案

Agent SHALL 在 max_steps 耗尽且未输出 Final Answer 时，给出非空的降级答案。

### Scenario: 步数耗尽触发 forced_stop
- **GIVEN** max_steps = 2
- **AND** 两步均为空结果
- **WHEN** 循环结束
- **THEN** AgentResult.forced_stop = True
- **AND** AgentResult.success = True
- **AND** answer 非空且包含"未能找到"或"建议查看"

### Scenario: 降级答案生成不崩溃
- **WHEN** `_generate_forced_answer()` 被调用
- **THEN** 不触发 NameError（reasoning_chain 已显式传参）
- **AND** 即使 LLM 不返回 Final Answer，也返回兜底文案

## Requirement: 日志可观测

Agent SHALL 在空结果路径的关键节点输出 INFO 级日志。

### Scenario: 空结果判定日志
- **WHEN** `_is_empty_result()` 返回 True
- **THEN** 日志包含"空结果判定: [原因]"

### Scenario: 计数器重置日志
- **WHEN** empty_result_count 从非零重置到 0
- **THEN** 日志包含"空结果计数器: 发现有效结果, 计数器已重置为0"
