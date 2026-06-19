# Spec: 答案反思与验证

> 编码: UTF-8 | 变更: rag-to-agent

---

## 概述

`src/reflector.py` 对 Agent 生成的中间/最终答案进行质量验证，检测幻觉并支持自动修正。

---

## Requirement: 数值准确性验证

Reflector SHALL 对答案中的财务数值与来源文本进行交叉验证。

### Scenario: 单数据点验证通过
- **WHEN** 答案包含"中芯国际2024年营收为1250.38亿元"
- **AND** 来源文本包含"1250.38亿"
- **THEN** check_hallucination 返回 True（非幻觉）
- **AND** confidence ≥ 0.9

### Scenario: 单数据点验证失败（幻觉检测）
- **WHEN** 答案包含"中国移动2024年营收为1500亿元"
- **AND** 来源文本实际值为"1250亿元"
- **THEN** check_hallucination 返回 False（幻觉）
- **AND** 错误信息指明具体偏差

### Scenario: 多数据点逐条验证
- **WHEN** 答案包含 3 个不同的财务数据
- **THEN** 对每个数据点独立验证
- **AND** 返回逐条验证结果

---

## Requirement: 来源完整性检查

Reflector SHALL 检查答案中每个数据陈述是否有对应的来源支撑。

### Scenario: 全部有来源
- **WHEN** 答案中 5 条数据陈述，均有 source_index 标注
- **THEN** 来源完整性检查通过
- **AND** check_completeness 返回 ≥ 0.9

### Scenario: 部分无来源
- **WHEN** 答案中 3 条数据陈述，仅 2 条有来源
- **THEN** 来源完整性检查标记为"部分缺失"
- **AND** check_completeness 返回 0.67

---

## Requirement: 回答完整性检查

Reflector SHALL 检查答案是否完整回答了用户的所有问题。

### Scenario: 完整回答
- **WHEN** 用户问"中国移动2024年营收和利润"
- **AND** 答案包含营收数据和利润数据
- **THEN** 回答完整性评分 ≥ 0.8

### Scenario: 不完整回答
- **WHEN** 用户问"中国移动和中国联通营收对比"
- **AND** 答案仅包含中国移动数据，缺少中国联通
- **THEN** 回答完整性评分 < 0.5
- **AND** 建议补充缺失的公司数据

---

## Requirement: 自动修正

当 Reflector 检测到问题且配置 auto_correct=True 时，SHALL 触发修正流程。

### Scenario: 幻觉数据自动修正
- **WHEN** Reflector 检测到某个数值存在幻觉
- **AND** auto_correct=True
- **THEN** 从来源文本中提取正确数值
- **AND** 替换答案中的错误数据
- **AND** 日志记录修正操作

### Scenario: 信息不足不再修正
- **WHEN** Reflector 检测到信息缺失但无法从已有来源中补充
- **AND** auto_correct=True
- **THEN** 在答案末尾追加"[注：部分信息无法从现有数据中获取]"
- **AND** 不尝试无依据的修正

### Scenario: 关闭自动修正
- **WHEN** auto_correct=False
- **THEN** 检测到问题后仅在答案末尾追加警告
- **AND** 不修改原始答案

---

## Requirement: 反思结果输出

Reflector SHALL 输出结构化的验证结果，供 API 和界面使用。

### Scenario: 完整验证结果
- **WHEN** 调用 reflector.verify(answer, sources)
- **THEN** 返回 ReflectionResult 包含：
  - hallucination_check: {valid, confidence, details}
  - source_completeness: {score, missing_items}
  - answer_completeness: {score, missing_aspects}
  - suggestion: 修改建议文本

---

## 配置项

| 参数 | 默认值 | 说明 |
|------|--------|------|
| enable_verification | true | 是否启用答案验证 |
| enable_hallucination_check | true | 是否启用幻觉检测 |
| auto_correct | true | 是否自动修正 |
| hallucination_threshold | 0.7 | 幻觉检测置信度阈值 |
