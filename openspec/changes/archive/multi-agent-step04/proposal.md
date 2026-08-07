# 变更提案: 多 Agent 升级 - 步骤 1.1 DataAgent

> 编码: UTF-8
> 状态: 实施中
> 日期: 2026-08-06

---

## 1. 变更背景

步骤 0.1 已完成 LLMProvider + AgentResult 扩展 + ReActAgent 改造，步骤 0.2 已完成 Prompt 配置化（含 data_agent 节），步骤 0.3 已完成三层路由。步骤 1.1 是阶段一的唯一步骤，目标是创建第一个 Worker Agent（DataAgent），验证 ReActAgent 可被继承并独立完成检索任务。

---

## 2. 变更目标

| 目标 | 衡量标准 |
|------|---------|
| DataAgent 类 | 继承 ReActAgent，只持有 retrieve 工具 |
| Prompt 加载 | 通过 prompt_name="data_agent" 加载 YAML 中检索专用规则 |
| 独立检索 | DataAgent.run() 可独立检索，结果与现有 Agent 核心数据一致 |
| 来源收集 | AgentResult.sources 正确填充 |
| 向后兼容 | 不改动任何现有文件，现有测试 100% 通过 |

---

## 3. 变更范围

### 3.1 新增模块

| 模块 | 文件名 | 职责 |
|------|--------|------|
| Worker 包 | `src/worker_agents/__init__.py` | 包初始化 |
| DataAgent | `src/worker_agents/data_agent.py` | 财务数据检索 Worker Agent |

### 3.2 不修改模块

`src/agent_core.py`、`src/planner.py`、`src/api_service.py`、`src/router.py`、`src/llm_provider.py`、`config/agent_prompts.yaml`、所有工具、配置文件、前端、部署、测试

---

## 4. 前置依赖

- 步骤 0.1: ReActAgent.__init__ 已有 llm_provider、prompt_name、temperature、model、max_steps 参数
- 步骤 0.2: agent_prompts.yaml 中 data_agent 节已定义

## 5. 关联风险

无新增风险。DataAgent 是纯新增文件，不改动任何现有代码。所有风险已在步骤 0.1/0.2/0.3 中识别并消解。
