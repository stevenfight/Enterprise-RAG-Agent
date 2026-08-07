# TDD: 步骤 0.2 Prompt 配置化

> 编码: UTF-8 | 变更: multi-agent-step02
>
> 图例: :red_circle: 未通过 | :green_circle: 已通过
>
> 最后验证: 2026-08-06 | 25/25 通过

---

## TC-14: YAML 文件格式验证

| 编号 | 测试项 | 类型 | 验证点 | 状态 |
|:--:|------|:--:|------|:--:|
| TC-14-01 | YAML 文件存在性 | 文件 | config/agent_prompts.yaml 文件存在 | :green_circle: |
| TC-14-02 | YAML version 字段 | 格式 | version 字段值为字符串类型 | :green_circle: |
| TC-14-03 | YAML 7 个角色节齐全 | 格式 | default/orchestrator/data_agent/calc_agent/compare_agent/chart_agent/verify_agent 全部存在 | :green_circle: |
| TC-14-04 | 每个节含 template 子键 | 格式 | 每个角色节 "template" in section | :green_circle: |
| TC-14-05 | 所有模板含 $tool_descriptions | 格式 | 每个模板含 $tool_descriptions 变量 | :green_circle: |
| TC-14-06 | 所有模板含 $context | 格式 | 每个模板含 $context 变量 | :green_circle: |
| TC-14-07 | calc/compare/chart/verify 含 $shared_context | 格式 | 4 个数据消费 Worker 模板含 $shared_context（data_agent 是数据生产者，不需要） | :green_circle: |
| TC-14-08 | orchestrator 含 $agent_descriptions | 格式 | orchestrator 模板含 $agent_descriptions | :green_circle: |

---

## TC-15: 模板加载功能

| 编号 | 测试项 | 类型 | 验证点 | 状态 |
|:--:|------|:--:|------|:--:|
| TC-15-01 | default 模板加载成功 | 功能 | prompt_name="default" -> YAML 模板 | :green_circle: |
| TC-15-02 | orchestrator 模板加载成功 | 功能 | prompt_name="orchestrator" -> YAML 模板 | :green_circle: |
| TC-15-03 | data_agent 模板加载成功 | 功能 | prompt_name="data_agent" -> YAML 模板 | :green_circle: |
| TC-15-04 | calc_agent 模板加载成功 | 功能 | prompt_name="calc_agent" -> YAML 模板 | :green_circle: |
| TC-15-05 | compare_agent 模板加载成功 | 功能 | prompt_name="compare_agent" -> YAML 模板 | :green_circle: |
| TC-15-06 | chart_agent 模板加载成功 | 功能 | prompt_name="chart_agent" -> YAML 模板 | :green_circle: |
| TC-15-07 | verify_agent 模板加载成功 | 功能 | prompt_name="verify_agent" -> YAML 模板 | :green_circle: |

---

## TC-16: Worker 规则过滤

| 编号 | 测试项 | 类型 | 验证点 | 状态 |
|:--:|------|:--:|------|:--:|
| TC-16-01 | data_agent 不含规则 8 | 规则过滤 | "规则8" 或 "图表展示" 不在 data_agent 模板中 | :green_circle: |
| TC-16-02 | chart_agent 不含规则 2-7 | 规则过滤 | chart_agent 只有规则 1/8/9，"规则2"~"规则7" 不在其中 | :green_circle: |
| TC-16-03 | calc_agent 不含规则 8/9/10 | 规则过滤 | 规则8/9/10 不在 calc_agent 模板中 | :green_circle: |
| TC-16-04 | orchestrator 不含检索/计算/对比/图表规则 | 规则过滤 | orchestrator 无规则 2/3/4/8/9/10/11，仅含调度规则 1/5 | :green_circle: |

---

## TC-17: 兼容性与兜底

| 编号 | 测试项 | 类型 | 验证点 | 状态 |
|:--:|------|:--:|------|:--:|
| TC-17-01 | default 模板与硬编码行为一致 | 兼容性 | _build_system_prompt 输出一致（rstrip 后比对） | :green_circle: |
| TC-17-02 | prompt_name 不存在时回退到 hardcoded | 兜底 | 不存在 prompt_name -> _default_system_prompt | :green_circle: |
| TC-17-03 | 删除 YAML 文件后回退到 hardcoded | 兜底 | 模拟 YAML 不存在 -> _default_system_prompt | :green_circle: |

---

## TC-18: API 兼容性

| 编号 | 测试项 | 类型 | 验证点 | 状态 |
|:--:|------|:--:|------|:--:|
| TC-18-01 | YAML 存在时不影响现有 API | 兼容性 | 现有单 Agent API 查询正常返回 | :green_circle: |

---

## TC-19: 鲁棒性与正确性

| 编号 | 测试项 | 类型 | 验证点 | 状态 |
|:--:|------|:--:|------|:--:|
| TC-19-01 | string.Template safe_substitute 处理缺失变量 | 鲁棒性 | 缺失的 $variable -> 保持原样而非报错 | :green_circle: |
| TC-19-02 | 安全规则不在 data_agent 的"规则排除"测试中被误判 | 正确性 | data_agent 含 S1-S5 但不含规则 8，两者不冲突 | :green_circle: |

---

## 测试统计

| 类别 | 数量 | 通过 | 未通过 |
|------|:--:|:--:|:--:|
| TC-14 YAML 格式验证 | 8 | 8 | 0 |
| TC-15 模板加载功能 | 7 | 7 | 0 |
| TC-16 Worker 规则过滤 | 4 | 4 | 0 |
| TC-17 兼容性与兜底 | 3 | 3 | 0 |
| TC-18 API 兼容性 | 1 | 1 | 0 |
| TC-19 鲁棒性与正确性 | 2 | 2 | 0 |
| **总计** | **25** | **25** | **0** |
