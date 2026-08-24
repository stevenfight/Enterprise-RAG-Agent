# 变更提案: 前端多 Agent 流式可视化（SSE 事件消费 + 多 Agent 步骤展示）

> 编码: UTF-8
> 状态: 规划中

---

## 1. 变更背景

多 Agent 升级（step01~step09）已在后端完成并部署上线。后端 SSE 接口 `/api/agent/stream` 已经会推送完整的多 Agent 事件序列：

```
connected → orchestrator_start → delegating
→ worker_step(N次) → worker_done(N次) → workers_done
→ answer_chunk(N次) → answer → reflection → done
```

其中 `orchestrator_start`（含 `registered_agents`）、`delegating`、`worker_step`（含 `agent`）、`worker_done`（含 `agent`）正是「是否多 Agent」与「每一步哪个 Agent 在运行」的信息来源。

但线上联调发现（用户查询「对比三大运营商2024年的营业收入，并展示图表」）：

1. **后端多 Agent 确实正常运行**（日志证明 DelegateTool 委托了 ChartAgent / CompareAgent 等 Worker，图表已生成）。
2. **前端看不到 SSE 流式**，也**看不到「是否多 Agent」和「每一步哪个 Agent 运行」**。

根因定位在**前端**：

- 前端 `SSEEventType` 类型只声明了 `connected / thought / action / observation / answer / error / done`，**缺失多 Agent 事件类型**；
- 前端 `ChatPage.tsx` 的 SSE 事件处理 `switch` 只处理单 Agent 事件，**完全忽略多 Agent 事件**（`orchestrator_start / delegating / worker_step / worker_done / workers_done / answer_chunk / reflection`）。

后端能力已具备，卡在前端没有把多 Agent 的流式事件接到 UI 上。

---

## 2. 变更目标

| 目标 | 衡量标准 |
|------|---------|
| 前端识别「是否多 Agent」 | 消费 `orchestrator_start` 事件，展示已注册的 Worker 列表 |
| 前端展示「每一步哪个 Agent 运行」 | 消费 `worker_step / worker_done` 事件，按 Worker 分组展示执行步骤 |
| 前端 SSE 流式逐条渲染 | 消费 `answer_chunk` 逐句追加，`worker_step` 实时追加，非等全部完成 |
| 不修改后端 | 后端 SSE 协议已就绪，本次 `src/`、`config/` 零改动 |
| 可单元测试（TDD） | 事件识别与映射逻辑抽为纯函数，Vitest 秒级测试，不依赖浏览器/网络 |
| 纳入长期回归 | 前端 `npm test` 可运行新增测试 |

---

## 3. 变更范围

### 3.1 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/src/utils/agentEvent.ts` | 纯函数模块：多 Agent 事件类型识别 + SSE 事件 → 状态 reducer |
| `frontend/src/utils/__tests__/agentEvent.test.ts` | 上述纯函数的 Vitest 单元测试（约 15 项） |
| `openspec/changes/multi-agent-step10/proposal.md` | 本提案 |
| `openspec/changes/multi-agent-step10/design.md` | 技术设计 |
| `openspec/changes/multi-agent-step10/tasks.md` | 任务清单 |
| `openspec/changes/multi-agent-step10/specs/tdd-step10.md` | TDD 用例规格 |

### 3.2 修改文件

| 文件 | 修改内容 |
|------|---------|
| `frontend/src/types/chat.ts` | 扩展 `SSEEventType` 增加多 Agent 事件类型；新增 `MultiAgentWorkerStep` / `MultiAgentWorkerStatus` / `MultiAgentRunState`；`Message` 增加 `agentRun` 字段 |
| `frontend/src/pages/ChatPage.tsx` | SSE 事件循环改用 `applyAgentEvent` reducer，消费多 Agent 事件并更新消息状态 |
| `frontend/src/stores/chatStore.ts` | `updateLastAssistantMessage` 支持更新 `agentRun` |
| `frontend/src/components/chat/MessageBubble.tsx` | 展示「多 Agent」标识 + 每个 Worker 的运行状态与步骤摘要 |

### 3.3 保留不变

- `src/` 全部后端生产代码
- `config/` 全部配置
- 后端 SSE 事件协议（`/api/agent/stream`）

---

## 4. 测试策略

纯单元测试（Vitest），针对抽离的纯函数 `applyAgentEvent` 与 `isMultiAgentEventType`，直接输入后端真实的 SSE 事件 JSON 结构，断言输出状态。不触发真实网络 / EventSource / 浏览器。

- **SP10-A** 多 Agent 事件类型识别（2 项）
- **SP10-B** 多 Agent 事件 reducer 映射（8 项）
- **SP10-C** 单 Agent 事件 reducer 回归（5 项）

---

## 5. 技术决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 事件处理抽纯函数 | `applyAgentEvent` reducer | 便于 Vitest 单元测试（TDD），避免逻辑散落在组件 switch 中不可测 |
| 事件协议来源 | 对齐后端 `_stream_multi_agent` 实际 payload | `worker_step` 字段为 `agent/step_type/step/content`，`worker_done` 字段为 `agent/success/total_steps/total_elapsed_ms` |
| 状态载体 | `Message.agentRun` | 复用现有消息模型，随消息持久化到 localStorage |
| 展示位置 | 复用 `MessageBubble` + `ThoughtChainDrawer` | 最小变更，不新增页面 |
| 编号延续 | `multi-agent-step10` | 与 step01~09 命名一致，便于归档 |
| 状态标记 | TDD 先标红、通过后转绿 | 符合项目 TDD 红绿规范 |
