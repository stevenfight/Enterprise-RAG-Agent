# 变更提案: 多 Agent 回答来源标注具体页码（阶段十一）

> 编码: UTF-8
> 状态: 规划中

---

## 1. 变更背景

前端多 Agent 流式可视化（step10）已完成并可在浏览器实测。用户在实测「对比三大运营商2024年的营业收入，并展示图表」时发现：

> 答案正文里的「来源：中国移动2024年度报告」等引用**只有文件名/公司名，没有具体页码**。

### 根因定位

1. 检索结果**本身已带页码**：[retrieve_tool.py](file:///d:/文件信息/AI应用开发/AI实战练习/github-project/企业级财务年报分析智能RAG—AGENT/src/tools/retrieve_tool.py) 的 `_format_results` 会把 `pages` 字段格式化为「第23-25页」并注入到 LLM 的 Observation 中。
2. 但各 Agent 的 prompt 规则只写了「标注来源」，**没有要求「标注具体页码」**，因此 LLM 在生成答案时把页码省略了。

这是 prompt 配置缺陷，不是检索链路缺陷。

---

## 2. 变更目标

| 目标 | 衡量标准 |
|------|---------|
| 答案来源引用带上页码 | 涉及「标注来源」的 prompt 规则强化为「标注来源及具体页码」 |
| 保持 default 与硬编码 fallback 一致 | `agent_core.py` 的 `_default_system_prompt` 同步更新 |
| 可单元测试（TDD） | 页码格式化 + prompt 规则静态断言，Python unittest 秒级测试 |
| 纳入长期回归 | `tests/run_all.py` 可运行新增测试 |

---

## 3. 变更范围

### 3.1 修改文件

| 文件 | 修改内容 |
|------|---------|
| `config/agent_prompts.yaml` | `default` / `data_agent` / `compare_agent` / `verify_agent` 的「标注来源」规则，以及 `orchestrator` 的 Final Answer 汇总，均强化为「含具体页码」 |
| `src/agent_core.py` | 硬编码 `_default_system_prompt` 的规则 3 同步强化（保证 yaml 缺失时 fallback 行为一致） |

### 3.2 新增文件

| 文件 | 说明 |
|------|------|
| `tests/tdd_multi_agent_step11.py` | 页码格式化回归 + prompt 页码规则静态断言（8 项） |
| `openspec/changes/multi-agent-step11/*.md` | 本变更的 SDD 文档 |

### 3.3 保留不变

- 前端全部代码（`SourceCard` 已展示页码，无需改动）
- 检索链路 `retrieve_tool.py` 的页码格式化逻辑（仅补测试锁定行为）
- `calc_agent` / `chart_agent` prompt（不产生文字来源列表，非本次范围）

---

## 4. 测试策略

Python `unittest`（后端 TDD），不依赖 LLM API：

- **SP11-A 页码格式化回归**（3 项）：锁定 `RetrieveTool._format_results` 的 pages 格式化行为。
- **SP11-B prompt 页码规则静态断言**（5 项）：读取 `config/agent_prompts.yaml`，断言 `default / data_agent / compare_agent / verify_agent / orchestrator` 各节 template 含「页码」标注规则。

---

## 5. 技术决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 修复方式 | 仅改 prompt 配置 | 页码已存在于检索结果，只缺 prompt 引导 |
| default 与硬编码一致性 | 同步改 `agent_core.py` | 项目约定「default 节必须与硬编码行为完全一致」 |
| 测试粒度 | 静态断言关键词「页码」 | prompt 是自然语言，无法做行为断言，静态关键词断言可防回归 |
| 编号延续 | `multi-agent-step11` | 与 step01~10 命名一致，便于归档 |
| 状态标记 | TDD 先标红、通过后转绿 | 符合项目 TDD 红绿规范 |
