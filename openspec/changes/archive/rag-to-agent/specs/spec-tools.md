# Spec: 工具系统

> 编码: UTF-8 | 变更: rag-to-agent

---

## 概述

`src/tools/` 目录实现 Agent 的工具系统，包括工具基类、注册框架和 5 个业务工具。

---

## Requirement: 工具统一接口

所有工具 SHALL 实现 `BaseTool` 基类，遵循统一的输入输出规范。

### Scenario: 工具定义
- **WHEN** 定义一个工具类继承 BaseTool
- **THEN** 必须包含 name, description, parameters 三个属性
- **AND** 必须实现 run(**kwargs) → ToolResult 方法

### Scenario: 参数校验
- **WHEN** 调用 tool.run() 时缺少必填参数
- **THEN** 返回 ToolResult(success=False, error="缺少必填参数: xxx")

### Scenario: 工具描述生成
- **WHEN** 调用 ToolRegistry.get_tool_descriptions()
- **THEN** 返回 LLM 可直接使用的工具说明文本（包含名称、功能、参数）

---

## Requirement: retrieve_tool（检索工具）

检索工具 SHALL 封装现有 HybridRetriever + RAGGenerator，提供财报数据库检索能力。

### Scenario: 不限公司检索
- **WHEN** retrieve_tool.run(query="营收增长", top_n=5)
- **THEN** 并行检索所有 4 家公司
- **AND** 返回合并后的检索结果（含来源信息）

### Scenario: 指定公司检索
- **WHEN** retrieve_tool.run(query="营收", company_name="中芯国际", top_n=3)
- **THEN** 仅检索中芯国际的索引
- **AND** 返回 3 条结果

### Scenario: 检索结果为空
- **WHEN** 检索未命中任何相关数据
- **THEN** 返回 ToolResult(success=True, data=[])
- **AND** data 中提示未找到相关数据

---

## Requirement: calculator_tool（计算工具）

计算工具 SHALL 支持财务指标的数学计算，包括增长率、利润率等。

### Scenario: 同比增长率计算
- **WHEN** calculator_tool.run(expression="(1250-1000)/1000*100")
- **THEN** 返回 ToolResult(data={"result": 25.0, "expression": "(1250-1000)/1000*100", "unit": "%"})

### Scenario: 命名指标计算
- **WHEN** calculator_tool.run(metric_name="营收同比增速", current="1250亿", previous="1000亿")
- **THEN** 自动解析数值并计算增长率
- **AND** 返回结果含计算公式

### Scenario: 非法表达式
- **WHEN** calculator_tool.run(expression="import os; ...")
- **THEN** 安全沙箱拦截
- **AND** 返回 ToolResult(success=False, error="表达式包含不允许的操作")

---

## Requirement: compare_tool（对比工具）

对比工具 SHALL 支持多公司、多指标的横向对比分析。

### Scenario: 多公司营收对比
- **WHEN** compare_tool.run(companies=["中国移动","中国联通","中国电信"], metrics=["营收"], year="2024")
- **THEN** 逐公司检索营收数据
- **AND** 返回结构化对比表（Markdown 表格格式）

### Scenario: 公司覆盖保底
- **WHEN** 某家公司检索结果不足
- **THEN** 触发三层保底机制（公平分配→替换策略→重新检索）
- **AND** 至少 1 条数据代表每家公司

---

## Requirement: chart_tool（图表工具）

图表工具 SHALL 根据数据生成财务趋势图表。

### Scenario: 生成柱状图
- **WHEN** chart_tool.run(data={"中国移动": 1250, "中国联通": 900, "中国电信": 1100}, chart_type="bar", title="2024年营收对比(亿元)")
- **THEN** 生成 PNG 图片文件
- **AND** 返回图片文件路径

### Scenario: 无 matplotlib 回退
- **WHEN** matplotlib 未安装
- **THEN** 返回 ToolResult(success=False, error="图表生成需要 matplotlib")
- **AND** 不抛出异常

---

## Requirement: verify_tool（验证工具）

验证工具 SHALL 对生成的数据陈述进行来源验证，检测幻觉。

### Scenario: 数据验证通过
- **WHEN** verify_tool.run(claim="中芯国际2024年营收为1250亿元", source_text="2024年度公司实现营业收入1250.38亿元")
- **THEN** 返回 ToolResult(data={"valid": True, "confidence": 0.95, "match_detail": "数值1250与来源一致"})

### Scenario: 数据不匹配
- **WHEN** claim 中的数值与 source_text 不一致
- **THEN** 返回 ToolResult(data={"valid": False, "confidence": 0.0, "mismatch": "claim: 1300, source: 1250.38"})

### Scenario: 来源不足
- **WHEN** source_text 为空或无法支撑验证
- **THEN** 返回 ToolResult(data={"valid": None, "confidence": 0.0, "error": "来源文本不足以验证该陈述"})

---

## 工具注册表

所有业务工具通过 `ToolRegistry` 注册和管理：

```python
registry = ToolRegistry()
registry.register(RetrieveTool())
registry.register(CalculatorTool())
registry.register(CompareTool())
registry.register(ChartTool())
registry.register(VerifyTool())
```
