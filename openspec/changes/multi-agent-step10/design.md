# 技术设计: 前端多 Agent 流式可视化

> 编码: UTF-8

---

## 一、后端 SSE 事件协议（本次对齐，不改动）

`/api/agent/stream` 多 Agent 模式（`_stream_multi_agent`）事件序列与 payload：

| 事件 type | payload 关键字段 | 说明 |
|-----------|------------------|------|
| `connected` | `timestamp` | 连接建立 |
| `orchestrator_start` | `registered_agents: string[]` | 已注册的 Worker 能力列表 |
| `delegating` | `batch: number`, `agents: string[]` | 委派的 Worker 列表 |
| `worker_step` | `agent: string`, `step_type: thought/action/observation`, `step: number`, `content: string` | 某个 Worker 的某一步 |
| `worker_done` | `agent: string`, `success: bool`, `total_steps: number`, `total_elapsed_ms: number` | 某个 Worker 完成 |
| `workers_done` | `worker_count: number` | 全部 Worker 完成 |
| `answer_chunk` | `content: string` | 最终答案的逐句片段 |
| `answer` | `content: string`, `workers: number`, `total_tokens: number` | 最终完整答案 |
| `reflection` | `score: number`, `issues: []`, `corrected_answer: string|null` | 反思验证结果 |
| `done` | `timestamp` | 流结束 |

单 Agent 模式（`_stream_single_agent`）事件（保留原有前端处理）：

| 事件 type | payload 关键字段 |
|-----------|------------------|
| `thought` | `step`, `content` |
| `action` | `step`, `content`, `action_input` |
| `observation` | `step`, `content` |
| `answer` | `content` |
| `error` | `content` |
| `done` | `total_steps`, `total_elapsed_ms`, `forced_stop` |

---

## 二、前端改动设计

### 2.1 类型扩展（types/chat.ts）

```typescript
// 扩展 SSE 事件类型
export type SSEEventType =
  | 'connected' | 'thought' | 'action' | 'observation' | 'answer' | 'error' | 'done'
  | 'orchestrator_start' | 'delegating' | 'worker_step' | 'worker_done'
  | 'workers_done' | 'answer_chunk' | 'reflection';

// 多 Agent Worker 单步
export interface MultiAgentWorkerStep {
  agent: string;
  step_type: 'thought' | 'action' | 'observation';
  step: number;
  content: string;
}

// 多 Agent Worker 状态
export interface MultiAgentWorkerStatus {
  agent: string;
  steps: MultiAgentWorkerStep[];
  done: boolean;
  success?: boolean;
  elapsed_ms?: number;
}

// 多 Agent 运行状态（挂到 Message.agentRun）
export interface MultiAgentRunState {
  isMultiAgent: boolean;
  registeredAgents: string[];
  workers: MultiAgentWorkerStatus[];
}
```

`SSEEvent` 接口增加多 Agent 字段（`registered_agents`、`agents`、`agent`、`step_type`、`worker_count`、`success`、`workers`、`total_tokens`）。

`Message` 增加 `agentRun?: MultiAgentRunState`。

### 2.2 纯函数模块（utils/agentEvent.ts）

核心是两个纯函数，供组件与测试复用：

```typescript
// 判断是否为多 Agent 事件类型
export function isMultiAgentEventType(type: string): boolean

// SSE 事件累积 reducer（不可变）
export interface AgentEventAccumulator {
  reasoningChain: AgentStepInfo[];      // 单 Agent 推理链（回归保留）
  agentRun: MultiAgentRunState | null;  // 多 Agent 运行状态
  answer: string;                        // 当前答案
  done: boolean;                         // 是否完成
}

export function createEmptyAccumulator(): AgentEventAccumulator
export function applyAgentEvent(acc: AgentEventAccumulator, event: SSEEvent): AgentEventAccumulator
```

`applyAgentEvent` 处理规则：

| 事件 | 行为 |
|------|------|
| `orchestrator_start` | 初始化 `agentRun = { isMultiAgent: true, registeredAgents, workers: [] }` |
| `delegating` | 为 `agents` 中尚未存在的 Worker 初始化空状态 |
| `worker_step` | 找到对应 Worker，追加一条步骤；Worker 不存在则先创建 |
| `worker_done` | 标记对应 Worker `done=true`，写入 `success/elapsed_ms` |
| `workers_done` | 记录 worker_count（可选，用于 UI 文案） |
| `answer_chunk` | `answer += content`（逐句追加） |
| `answer` | `answer = content`（最终答案，覆盖） |
| `reflection` | 保留反思信息（可选挂到 agentRun，本次最小化可忽略展示） |
| `done` | `done = true` |
| `thought` | 追加 `reasoningChain` 步骤（保留原有单 Agent 行为） |
| `action` | 更新 `reasoningChain` 最后一步的 `action/action_input` |
| `observation` | 更新 `reasoningChain` 最后一步的 `observation` |

### 2.3 状态层（chatStore.ts）

`updateLastAssistantMessage` 的 `partial` 增加 `agentRun`，写入最后一条 assistant 消息。

### 2.4 UI 层

**ChatPage.tsx**：SSE 事件回调内，用 `applyAgentEvent(acc, event)` 替换现有 switch-case；每个事件后通过 `updateLastAssistantMessage` 同步 `reasoningChain / agentRun / content`。

**MessageBubble.tsx**：当 `message.agentRun?.isMultiAgent` 时，展示：
- 「多 Agent」标识 Tag + 已注册 Worker 数量
- 每个 Worker 一行：Agent 名 + 运行中/完成状态 + 步骤数

**ThoughtChainDrawer.tsx**（可选扩展）：多 Agent 时按 Worker 分组展示步骤时间线；单 Agent 保持原有展示。

---

## 三、TDD 红绿流程

1. 先写 `agentEvent.test.ts`（此时 `agentEvent.ts` 尚未实现 → 红）。
2. 实现 `types/chat.ts` 扩展 + `utils/agentEvent.ts` → 测试转绿。
3. 接入 UI 后，运行 `npm test` + `npm run build`（tsc）验证整体无回归。

---

## 四、边界与约束

- 不改后端 SSE 协议，严格对齐现有 payload 字段。
- 单 Agent 事件处理逻辑保持与现有一致（回归覆盖）。
- 多 Agent 与单 Agent 事件可能在同一流中不混用（后端按 mode 分流），reducer 需能独立处理两类。
- `answer_chunk` 与 `answer` 并存时，`answer` 为最终完整答案（覆盖累积值）。
