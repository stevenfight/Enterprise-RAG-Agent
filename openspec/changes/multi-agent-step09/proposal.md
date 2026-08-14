# 变更提案: 多 Agent 升级 - 阶段九 启用/运行验证 + 可靠性回归补测

> 编码: UTF-8
> 状态: 规划中

---

## 1. 变更背景

多 Agent 升级（step01~step08）已上线并对外服务。近期线上联调中发现并修复了 3 个影响正确性与稳定性的缺陷，当时为紧急修复，未同步补齐对应 TDD 用例。

同时，用户新增需求：在多 Agent 升级后，验证「多 Agent 是否真正启用、是否正确运行」。经代码排查确认：

- 多 Agent 组件（OrchestratorAgent + DelegateTool + 5 个 Worker + SharedMemory + QueryRouter）**已实现并注册**，`has_multi_agent=True`；
- 前端 `/api/agent/query`、`/api/agent/stream` 通过 `mode=multi/auto` **已接入多 Agent 链路**；
- 企业微信 `/api/langbot/chat` 与 OpenAI `/v1/chat/completions` **未接入多 Agent 链路**，仍走单 Agent（本次仅验证现状，不改生产代码）。

本次为上述「启用 + 运行」验证与 3 个修复点补充单元测试，并纳入长期回归。

### 1.1 历史修复点（本次回归覆盖）

| 编号 | 修复点 | 位置 | 影响 |
|:--:|------|------|------|
| #1 | delegate 嵌套 JSON 平衡括号解析 | `src/agent_core.py:_extract_json_object` | Orchestrator 委托多任务时嵌套 tasks 数组解析失败 |
| #2 | Action=Final 空正文回退 Thought | `src/agent_core.py:_parse_response` | LLM 将答案写在 Thought、仅输出 `Action: Final` 时返回空答案，触发「抱歉, 未能找到相关信息。」 |
| #3 | 单位换算规则（百万元/万元） | `config/agent_prompts.yaml` + `_default_system_prompt` | 中国移动营收被误算为 1/10（10,408 亿元 → 1,040.76 亿元） |

---

## 2. 变更目标

| 目标 | 衡量标准 |
|------|---------|
| 验证多 Agent 组件正确启用 | 覆盖 AgentRegistry 注册、QueryRouter 路由、OrchestratorAgent 初始化、DelegateTool 分组与 Worker 创建 |
| 验证多 Agent 运行链路正确 | 覆盖 delegate 动作解析、工具路由、Worker 执行写回 SharedMemory、Orchestrator 汇总返回 |
| 为 3 个修复点补充单元测试 | 覆盖 `_extract_json_object` / `_parse_response` / 单位换算规则 |
| 不依赖真实 LLM/网络 | 全部用例 Mock 或直接调用纯函数，秒级完成 |
| 纳入长期回归 | 加入 `tests/run_all.py` 的 `agent-tdd` 类别 |
| 不修改生产逻辑 | `src/`、`config/` 下生产代码零改动（仅补测试 + 文档） |

---

## 3. 变更范围

### 3.1 新增文件

| 文件 | 说明 |
|------|------|
| `tests/tdd_multi_agent_step09.py` | 阶段九单元测试（25 项） |
| `openspec/changes/multi-agent-step09/specs/tdd-step09.md` | TDD 用例规格 |

### 3.2 修改文件

| 文件 | 修改内容 |
|------|---------|
| `tests/run_all.py` | TEST_SUITES 新增 `tdd_multi_agent_step09.py`（agent-tdd, requires_llm=False） |

### 3.3 保留不变

- `src/` 全部生产代码
- `config/` 全部配置
- 已有 `tests/tdd_multi_agent_step01~08.py` 及其他测试

---

## 4. 测试策略

纯单元测试，直接调用被测函数或创建组件实例，通过 MagicMock 隔离 LLM 与 Worker，不触发真实 LLM 调用。

- **SP9-A** 多 Agent 启用验证（6 项）：AgentRegistry 注册 5 Worker / QueryRouter 多公司路由 multi_agent / OrchestratorAgent 初始化 / DelegateTool 分组 / Worker 创建 / 空 tasks 失败
- **SP9-B** 多 Agent 运行链路验证（4 项）：delegate 动作解析 / delegate 工具路由 / Worker 执行写回 SharedMemory / Orchestrator 完整链路汇总
- **SP9-C** 3 个修复点回归（15 项）：`_extract_json_object`（6） / `_parse_response` Action=Final 回退（5） / 单位换算规则（4）

---

## 5. 技术决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 测试层 | 仅单元测试（Mock） | 用户确认本次先跑单元测，集成/线上后续再做 |
| 多 Agent 缺口 | 仅验证现状，不改代码 | 企业微信/OpenAI 未接多 Agent，本次只记录结论 |
| 编号延续 | `multi-agent-step09` | 与 step01~08 命名一致，便于归档 |
| 状态标记 | TDD 先标红、通过后转绿 | 符合项目 TDD 红绿规范 |
