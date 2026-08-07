# Spec: 步骤 0.2 Prompt 配置化

> 编码: UTF-8 | 变更: multi-agent-step02 | 关联风险: R-10

---

## 概述

本文档定义步骤 0.2 的需求规格：将 ReActAgent 中硬编码的 `_default_system_prompt` 外置为 YAML 配置文件，支持多 Agent 角色模板，同时保证向后兼容与兜底能力。

### 背景与动机

步骤 0.1 已为 ReActAgent 增加了 `prompt_name` 参数和 `_load_prompt_template` 方法，可从 `config/agent_prompts.yaml` 加载模板。步骤 0.2 在此基础上完成 Prompt 的全面配置化：

1. 创建 `config/agent_prompts.yaml`，包含 7 个角色模板
2. `default` 节与硬编码 `_default_system_prompt` 行为完全一致
3. 各 Worker 节只保留与本角色相关的规则，降低上下文噪声
4. YAML 不存在或解析失败时自动回退到硬编码
5. `agent_core.py` 的日志增强：5 种加载场景细分

### 关联风险

- **R-10**: Prompt 配置化后，YAML 文件缺失或格式错误会导致 Agent 行为退化。必须保证兜底逻辑健壮，并通过日志细分 5 种场景便于排障。

---

## Requirement: config/agent_prompts.yaml 文件结构 (R-10)

系统 SHALL 创建 `config/agent_prompts.yaml` 文件，包含 7 个角色模板节。

### Scenario: 文件存在且可解析
- **WHEN** 读取 config/agent_prompts.yaml
- **THEN** yaml.safe_load 返回字典
- **AND** 字典包含 version 字段，值为字符串类型
- **AND** 字典包含 7 个角色节: default / orchestrator / data_agent / calc_agent / compare_agent / chart_agent / verify_agent

### Scenario: 每个角色节含 template 子键
- **WHEN** 遍历 7 个角色节
- **THEN** 每个节都包含 "template" 子键
- **AND** template 值为字符串

### Scenario: version 字段为字符串
- **WHEN** 读取 YAML 顶层 version 字段
- **THEN** 其类型为 str
- **AND** 不被 YAML 解析器当作数字

---

## Requirement: 模板变量规范 (R-10)

所有角色模板 SHALL 使用 string.Template 的 `$variable` 语法，包含必要的模板变量。

### Scenario: 所有模板含 $tool_descriptions
- **WHEN** 遍历 7 个角色模板
- **THEN** 每个模板字符串中包含 "$tool_descriptions"

### Scenario: 所有模板含 $context
- **WHEN** 遍历 7 个角色模板
- **THEN** 每个模板字符串中包含 "$context"

### Scenario: 数据消费 Worker 含 $shared_context
- **WHEN** 遍历 calc_agent / compare_agent / chart_agent / verify_agent 模板
- **THEN** 每个模板字符串中包含 "$shared_context"
- **AND** data_agent 模板不含 "$shared_context"（data_agent 是数据生产者，不需要上游数据）

### Scenario: orchestrator 含 $agent_descriptions
- **WHEN** 检查 orchestrator 模板
- **THEN** 模板字符串中包含 "$agent_descriptions"

---

## Requirement: default 节与硬编码行为一致 (R-10, 兼容性)

`default` 节的 template SHALL 与 `agent_core.py` 中 `_default_system_prompt` 的行为完全一致。

### Scenario: default 模板加载成功
- **WHEN** prompt_name="default" 且 YAML 文件存在
- **THEN** _load_prompt_template 返回 YAML 中 default 节的 template
- **AND** 返回值不等于 _default_system_prompt（来自 YAML 而非硬编码）

### Scenario: _build_system_prompt 输出一致
- **WHEN** 使用 default 模板构建 System Prompt
- **AND** 使用硬编码 _default_system_prompt 构建同样 System Prompt
- **THEN** 两者 .rstrip() 后比对完全一致
- **AND** 差异仅可能来自 YAML | 块标量的尾随换行

---

## Requirement: Worker 节规则过滤 (R-10)

各 Worker 节 SHALL 只包含与本角色相关的业务规则，过滤掉无关规则以降低上下文噪声。

### Scenario: data_agent 不含规则 8（图表展示）
- **WHEN** 检查 data_agent 模板
- **THEN** "规则8" 或 "图表展示" 不在模板中
- **AND** data_agent 保留安全规则 S1-S5 和检索相关规则

### Scenario: chart_agent 只含规则 1/8/9
- **WHEN** 检查 chart_agent 模板
- **THEN** "规则2" ~ "规则7" 不在模板中
- **AND** chart_agent 含规则 1（每步一个工具）、规则 8（图表展示）、规则 9（优先年报来源）

### Scenario: calc_agent 不含规则 8/9/10
- **WHEN** 检查 calc_agent 模板
- **THEN** "规则8"、"规则9"、"规则10" 不在模板中
- **AND** calc_agent 含计算相关规则 1/2/3/5/11

### Scenario: orchestrator 不含检索/计算/对比/图表规则
- **WHEN** 检查 orchestrator 模板
- **THEN** 规则 2/3/4/8/9/10/11 不在模板中
- **AND** orchestrator 仅含调度规则 1/5

---

## Requirement: YAML 不存在时自动回退 (R-10, 兜底)

`_load_prompt_template` SHALL 在 YAML 文件缺失或解析失败时回退到硬编码 `_default_system_prompt`。

### Scenario: prompt_name 不存在时回退
- **WHEN** YAML 文件存在但不含 prompt_name 指定的节
- **THEN** 回退到 _default_system_prompt
- **AND** 记录 WARNING 日志说明可用节列表

### Scenario: 删除 YAML 文件后回退
- **WHEN** YAML 文件不存在（被删除或重命名）
- **THEN** 回退到 _default_system_prompt
- **AND** 记录 INFO 日志"agent_prompts.yaml 不存在"

### Scenario: PyYAML 未安装时回退
- **WHEN** yaml 模块为 None（PyYAML 未安装）
- **THEN** 回退到 _default_system_prompt
- **AND** 记录 DEBUG 日志"PyYAML 未安装"

---

## Requirement: agent_core.py 日志增强 (R-10)

`_load_prompt_template` SHALL 在 5 种场景下输出细分日志，便于排障。

### Scenario: 场景 1 - PyYAML 未安装
- **WHEN** yaml is None
- **THEN** 输出 DEBUG 日志"PyYAML 未安装，使用硬编码默认模板"

### Scenario: 场景 2 - YAML 文件不存在
- **WHEN** yaml_path.exists() 为 False
- **THEN** 输出 INFO 日志"agent_prompts.yaml 不存在"
- **AND** 日志包含 yaml_path 路径

### Scenario: 场景 3 - YAML 加载成功
- **WHEN** YAML 文件存在且含对应节
- **THEN** 输出 INFO 日志"从 agent_prompts.yaml 加载模板"
- **AND** 日志包含 prompt_name 和 yaml_path

### Scenario: 场景 4 - YAML 存在但无对应节
- **WHEN** YAML 文件存在但 prompts.get(prompt_name) 为 None
- **THEN** 输出 WARNING 日志"无 'xxx' 节"
- **AND** 日志包含可用节列表

### Scenario: 场景 5 - YAML 解析异常
- **WHEN** yaml.safe_load 抛出异常
- **THEN** 输出 WARNING 日志"加载失败"
- **AND** 日志包含异常类型和消息

---

## Requirement: 向后兼容性 (R-10)

YAML 文件的存在 SHALL 不影响现有单 Agent API 的正常运行。

### Scenario: 现有单 Agent API 查询正常
- **WHEN** YAML 文件存在
- **AND** 使用 default prompt_name 构造 Agent
- **THEN** Agent 正常运行
- **AND** 行为与升级前一致

### Scenario: string.Template safe_substitute 鲁棒性
- **WHEN** 模板含未提供的 $variable
- **THEN** safe_substitute 保持原样而非抛出 KeyError
- **AND** 不影响其他变量的正常替换

### Scenario: 安全规则与业务规则不冲突
- **WHEN** 检查 data_agent 模板
- **THEN** data_agent 含安全规则 S1-S5
- **AND** data_agent 不含规则 8（图表展示）
- **AND** 两者不冲突（安全规则编号 1-5 与业务规则编号 1-11 独立计数）

---

## 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| config/agent_prompts.yaml | 新增 | 7 个角色模板的 YAML 配置文件 |
| src/agent_core.py | 修改 | _load_prompt_template 日志增强（5 种场景细分） |

---

## 配置项

| 参数 | 默认值 | 说明 |
|------|--------|------|
| version | "2.0" | YAML 配置版本号（字符串类型） |
| default.template | (与硬编码一致) | 默认全量规则模板 |
| orchestrator.template | (调度规则) | 调度器 Agent 模板，含 $agent_descriptions |
| data_agent.template | (检索规则) | 数据检索 Agent 模板，不含 $shared_context |
| calc_agent.template | (计算规则) | 计算 Agent 模板，含 $shared_context |
| compare_agent.template | (对比规则) | 对比 Agent 模板，含 $shared_context |
| chart_agent.template | (图表规则) | 图表 Agent 模板，含 $shared_context |
| verify_agent.template | (审核规则) | 审核 Agent 模板，含 $shared_context |
