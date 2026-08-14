// -*- coding: utf-8 -*-
/**
 * Agent SSE 事件处理纯函数模块
 *
 * 将 SSE 事件流转换为可测试的不可变累积状态 (AgentEventAccumulator)。
 * 单 Agent 与多 Agent 事件均可由 applyAgentEvent 处理，组件层只负责把
 * 返回的新状态同步到 Zustand store，便于 Vitest 单元测试。
 */

import type {
  SSEEvent,
  AgentStepInfo,
  MultiAgentRunState,
  MultiAgentWorkerStatus,
  MultiAgentWorkerStep,
} from '@/types/chat';

/** 多 Agent 事件类型集合 */
const MULTI_AGENT_EVENT_TYPES = new Set<string>([
  'orchestrator_start',
  'delegating',
  'worker_step',
  'worker_done',
  'answer_chunk',
  'reflection',
]);

/** 判断是否为多 Agent 事件类型 */
export function isMultiAgentEventType(type: string): boolean {
  return MULTI_AGENT_EVENT_TYPES.has(type);
}

/** SSE 事件累积状态 (不可变) */
export interface AgentEventAccumulator {
  /** 单 Agent 推理链（回归保留） */
  reasoningChain: AgentStepInfo[];
  /** 多 Agent 运行状态 */
  agentRun: MultiAgentRunState | null;
  /** 当前答案（answer_chunk 累积，answer 覆盖） */
  answer: string;
  /** 是否完成 */
  done: boolean;
}

/** 创建空累积状态 */
export function createEmptyAccumulator(): AgentEventAccumulator {
  return {
    reasoningChain: [],
    agentRun: null,
    answer: '',
    done: false,
  };
}

/** 返回一个空的 Worker 状态（未完成） */
function createWorker(agent: string): MultiAgentWorkerStatus {
  return {
    agent,
    steps: [],
    done: false,
  };
}

/** 从累积状态中取得多 Agent 运行状态；若尚未初始化则返回空运行状态 */
function ensureRun(acc: AgentEventAccumulator): MultiAgentRunState {
  return acc.agentRun ?? { isMultiAgent: true, registeredAgents: [], workers: [] };
}

/** 应用单个 SSE 事件，返回新的累积状态 */
export function applyAgentEvent(acc: AgentEventAccumulator, event: SSEEvent): AgentEventAccumulator {
  switch (event.type) {
    // ===== 多 Agent 事件 =====
    case 'orchestrator_start':
      return {
        ...acc,
        agentRun: {
          isMultiAgent: true,
          registeredAgents: event.registered_agents ?? [],
          workers: [],
        },
      };

    case 'delegating': {
      const run = ensureRun(acc);
      const agents = event.agents ?? [];
      const workers = [...run.workers];
      for (const agent of agents) {
        if (!workers.some((w) => w.agent === agent)) {
          workers.push(createWorker(agent));
        }
      }
      return { ...acc, agentRun: { ...run, workers } };
    }

    case 'worker_step': {
      const agent = event.agent ?? '未知 Worker';
      const step: MultiAgentWorkerStep = {
        agent,
        step_type: event.step_type ?? 'thought',
        step: event.step ?? 0,
        content: event.content ?? '',
      };
      const run = ensureRun(acc);
      const existing = run.workers.find((w) => w.agent === agent);
      const workers = existing
        ? run.workers.map((w) =>
            w.agent === agent ? { ...w, steps: [...w.steps, step] } : w,
          )
        : [...run.workers, { ...createWorker(agent), steps: [step] }];
      return { ...acc, agentRun: { ...run, workers } };
    }

    case 'worker_done': {
      const agent = event.agent ?? '未知 Worker';
      const run = ensureRun(acc);
      const existing = run.workers.find((w) => w.agent === agent);
      const finished: MultiAgentWorkerStatus = {
        agent,
        steps: existing?.steps ?? [],
        done: true,
        success: event.success,
        elapsed_ms: event.total_elapsed_ms,
      };
      const workers = existing
        ? run.workers.map((w) => (w.agent === agent ? finished : w))
        : [...run.workers, finished];
      return { ...acc, agentRun: { ...run, workers } };
    }

    case 'answer_chunk':
      return { ...acc, answer: acc.answer + (event.content ?? '') };

    // ===== 单 Agent 事件 =====
    case 'thought': {
      const step: AgentStepInfo = {
        step_number: event.step ?? 0,
        thought: event.content ?? '',
        elapsed_ms: 0,
      };
      return { ...acc, reasoningChain: [...acc.reasoningChain, step] };
    }

    case 'action': {
      if (acc.reasoningChain.length === 0) return acc;
      const chain = acc.reasoningChain.map((s, i) =>
        i === acc.reasoningChain.length - 1
          ? { ...s, action: event.content ?? '', action_input: event.action_input ?? null }
          : s,
      );
      return { ...acc, reasoningChain: chain };
    }

    case 'observation': {
      if (acc.reasoningChain.length === 0) return acc;
      const chain = acc.reasoningChain.map((s, i) =>
        i === acc.reasoningChain.length - 1
          ? { ...s, observation: event.content ?? null }
          : s,
      );
      return { ...acc, reasoningChain: chain };
    }

    case 'answer':
      return { ...acc, answer: event.content ?? '' };

    case 'done':
      return { ...acc, done: true };

    // connected / error / reflection 等无状态变更事件
    default:
      return acc;
  }
}
