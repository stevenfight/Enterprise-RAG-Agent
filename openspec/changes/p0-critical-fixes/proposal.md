# 变更提案: P0 关键缺陷修复 (v5.1)

> 编码: UTF-8
> 状态: 规划中

---

## 1. 变更背景

2026-07-31 项目全量代码核查发现了 26+ 个优化点和 12 个新增发展方向。其中存在 5 个 P0 级别缺陷，直接影响生产的**正确性、并发安全和安全性**:

| 编号 | 缺陷 | 严重度 | 位置 |
|:--:|------|:--:|------|
| #1 | empty_result_count 阶梯递减而非直接重置 | P0 | `agent_core.py:262` |
| #2 | run_stream 强制答案传入空推理链 | P0 | `agent_core.py:463` |
| #3 | memory 配置未生效 | P0 | `api_service.py:385` |
| #4 | Agent 全局单例并发不安全 | P0 | `api_service.py:589-595` |
| #5 | API 无任何鉴权 | P0 | `api_service.py` 全文 |

企业微信智能机器人「财务年报助手」正在对外提供服务，这些缺陷直接影响线上服务的稳定性和安全性，必须在专栏继续发布前修复。

---

## 2. 变更目标

| 目标 | 衡量标准 |
|------|---------|
| 修复 empty_result_count 重置逻辑 | 有有效结果时计数器归零，而非递减 |
| 修复 run_stream 空推理链 | 强制答案生成时传入正确的推理链历史 |
| memory 配置生效 | api_service 初始化 AgentMemory 时读取 `config/agent_config.json` 中 `memory` 段配置 |
| 消除 Agent 全局单例并发竞争 | 每个请求独立创建 Agent 实例，不再共享全局 agent 对象状态 |
| 添加 API Key 鉴权 | `/api/*` 和 `/v1/*` 接口需携带 `Authorization: Bearer <key>` 请求头 |
| 不影响现有功能 | 所有已有 TDD 测试用例回归通过 |
| 最小变更 | 不改动专栏已发布的 10 篇文章涉及的架构描述 |

---

## 3. 变更范围

### 3.1 修改模块

| 模块 | 文件 | 修改内容 |
|------|------|---------|
| Agent 核心 | `src/agent_core.py` | 修复 #1（L262）和 #2（L463）|
| API 服务 | `src/api_service.py` | 修复 #3（L385）+ #4（L589-595）+ #5（新增 API Key 中间件）|
| Agent 配置 | `config/agent_config.json` | 新增 `api_key` 配置项 |
| 环境变量/配置 | `.env.example` 或说明 | 新增 `API_KEY` 环境变量说明 |

### 3.2 保留不变

- `src/tools/` - 全部工具模块不变
- `src/query_processor.py` - 意图识别不变
- `src/planner.py` - 规划器不变
- `src/reflector.py` - 反思器不变
- `src/conversation.py` - 对话管理不变
- `src/agent_memory.py` - AgentMemory 类本身不变（仅调用方传参变更）
- `src/retrieval.py` - 检索模块不变
- `src/monitoring.py` - 监控模块不变
- `frontend/` - 前端不变
- 全部 `data/` 文件不变

---

## 4. 技术方案概要

### 4.1 修复 #1: empty_result_count 重置逻辑

**问题**: `agent_core.py:262` 写 `empty_result_count = max(0, empty_result_count - 1)`，注释说"重置"但实际是递减。连续 2 次空结果后出现 1 次有效结果，计数器只降到 1 而非 0。

**修复**: 改为 `empty_result_count = 0`，逻辑与语义一致。

### 4.2 修复 #2: run_stream 强制答案传入空推理链

**问题**: `agent_core.py:463` 调用 `self._generate_forced_answer(messages, [])`，传入空列表作为推理链，导致日志和追踪信息误导。

**修复**: 传入 `reasoning_chain` 变量（流式模式中已累积的推理步骤）。

### 4.3 修复 #3: memory 配置生效

**问题**: `api_service.py:385` 创建 `AgentMemory()` 使用默认参数（`working_memory_limit=10, episodic_memory_turns=5, enable_long_term=False`），未读取 `config/agent_config.json` 中 `memory` 段配置。

**修复**: 启动时从 `config/agent_config.json` 读取 `memory` 段参数，传入 `AgentMemory()`。配置中 `memory.enable_long_term=true` 时启用长期记忆持久化。

### 4.4 修复 #4: Agent 全局单例并发安全

**问题**: `api_service.py:589-595` 在每次请求时直接修改全局 `agent` 对象:
```python
agent.memory = cm.agent_memory      # 覆盖全局单例的 memory
agent.max_steps = request.max_steps  # 覆盖全局单例的 max_steps
agent.temperature = request.temperature  # 覆盖全局单例的 temperature
```
并发请求 A 修改后，B 再次修改，A 最终使用的是 B 的参数。

**修复**: 改为 per-request 创建 `ReActAgent` 实例，不再共享全局 `agent`。复用已初始化的 `tool_registry`、`planner`、`reflector`，仅 Agent 实例按请求创建。

### 4.5 修复 #5: API Key 鉴权

**问题**: 所有接口（含管理接口）无任何鉴权，客户端可通过请求体控制 `max_steps` 拉高 token 消耗。

**修复**: 添加 FastAPI 中间件，校验 `Authorization: Bearer <key>` 请求头：
- `key` 从 `config/agent_config.json` 的 `api.key` 或环境变量 `API_KEY` 读取
- 健康检查 `/api/health` 豁免鉴权
- 鉴权失败返回 401 `{"detail": "未授权: 缺少或无效的 API Key"}`
- 添加 `max_steps` 硬上限 15 防止客户端滥用

---

## 5. 技术决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 并发安全方案 | per-request 创建 Agent 实例 | 最简单、最安全，不引入 contextvar 等新概念 |
| API Key 存储 | `config/agent_config.json` + 环境变量 | 开发用配置文件，生产用环境变量，符合 12-Factor |
| API Key 校验粒度 | 全局中间件 + `/health` 白名单 | 健康检查需要给监控系统用，不能拦 |
| max_steps 硬上限 | 15 | 当前配置 10，留 50% 余量 |

---

## 6. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| per-request 创建 Agent 增加延迟 | 每次请求需调用 `ReActAgent.__init__` | 初始化成本极低（仅属性赋值），实测可忽略 |
| API Key 配置缺失导致服务不可用 | 现有调用方（LangBot、前端）调用失败 | 启动时检查配置，未设置时打印 WARNING 日志但不阻止启动 |
| API Key 加鉴权后 LangBot 调用失败 | 企业微信机器人失联 | 修复后同步更新服务器 LangBot 数据库中的 `api_keys` 字段 |

---

## 7. 受影响的规范

- `openspec/changes/rag-to-agent/` - Agent 核心推理链路（修复 #1, #2）
- `openspec/changes/quality-robustness-enhancement/` - 健壮性增强（修复 #3）
- `openspec/changes/docker-deployment/` - 部署配置（新增 API Key 环境变量）

## 8. 专栏文章影响

- 文章 19（LangBot 接入企业微信实战）: 第 57 行 SQL `api_keys` 字段从 `["no-key-needed"]` 改为 `["<your-api-key>"]`，第 291 行 curl 命令新增 `Authorization: Bearer <key>` Header
- 其余 22 篇文章不受影响
