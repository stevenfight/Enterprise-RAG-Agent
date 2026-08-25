// -*- coding: utf-8 -*-
/**
 * Agent SSE 事件处理纯函数模块。
 *
 * 原始推理、工具输入、观测内容和 Worker 标识只在 SSE 回调中短暂存在，
 * 此模块仅输出可展示、可持久化的安全分析摘要。
 */

import type { SSEEvent, AnalysisTraceStep } from '@/types/chat';

export type { AnalysisTraceStep } from '@/types/chat';

const TOOL_LABELS: Record<string, string> = {
  retrieve: '资料检索',
  search: '资料检索',
  compare: '指标对比',
  calculate: '财务计算',
  chart: '图表分析',
};

const WORKER_LABELS: Record<string, string> = {
  DataAgent: '资料检索',
  CalcAgent: '财务计算',
  ChartAgent: '图表分析',
};

/** 将原始工具过程投影为安全摘要。 */
export function projectAnalysisTrace(input: {
  stepNumber: number;
  action?: string | null;
  actionInput?: Record<string, unknown> | null;
  observation?: string | null;
  status: AnalysisTraceStep['status'];
}): AnalysisTraceStep {
  const hasInput = Boolean(input.actionInput && Object.keys(input.actionInput).length > 0);
  const isRetrieval = input.action === 'retrieve' || input.action === 'search';
  return {
    stepNumber: input.stepNumber,
    toolLabel: input.action ? (TOOL_LABELS[input.action] ?? '分析工具') : '分析工具',
    status: input.status,
    ...(hasInput ? { inputSummary: isRetrieval ? '已提供检索条件' : '已提供分析条件' } : {}),
    ...(input.observation ? { observationSummary: '已获取检索结果' } : {}),
  };
}

/** 多 Agent 事件类型集合。 */
const MULTI_AGENT_EVENT_TYPES = new Set<string>([
  'orchestrator_start',
  'delegating',
  'worker_step',
  'worker_done',
  'answer_chunk',
  'reflection',
]);

/** 判断是否为多 Agent 事件类型。 */
export function isMultiAgentEventType(type: string): boolean {
  return MULTI_AGENT_EVENT_TYPES.has(type);
}

/** SSE 事件累积状态。只包含安全过程摘要与最终回答。 */
export interface AgentEventAccumulator {
  analysisTrace: AnalysisTraceStep[];
  answer: string;
  done: boolean;
}

/** 创建空累积状态。 */
export function createEmptyAccumulator(): AgentEventAccumulator {
  return { analysisTrace: [], answer: '', done: false };
}

function nextStepNumber(acc: AgentEventAccumulator, event: SSEEvent): number {
  return event.step ?? acc.analysisTrace.length + 1;
}

function workerLabel(agent?: string): string {
  return agent ? (WORKER_LABELS[agent] ?? '协同分析') : '协同分析';
}

function appendTrace(acc: AgentEventAccumulator, trace: AnalysisTraceStep): AgentEventAccumulator {
  return { ...acc, analysisTrace: [...acc.analysisTrace, trace] };
}

/** 应用单个 SSE 事件，返回新的安全累积状态。 */
export function applyAgentEvent(acc: AgentEventAccumulator, event: SSEEvent): AgentEventAccumulator {
  switch (event.type) {
    case 'orchestrator_start':
      return appendTrace(acc, {
        stepNumber: nextStepNumber(acc, event),
        toolLabel: '协同分析',
        status: 'running',
      });

    case 'delegating':
      return appendTrace(acc, {
        stepNumber: nextStepNumber(acc, event),
        toolLabel: '协同分析',
        status: 'running',
        inputSummary: '已分配分析任务',
      });

    case 'worker_step':
      return appendTrace(acc, {
        stepNumber: nextStepNumber(acc, event),
        toolLabel: workerLabel(event.agent),
        status: 'running',
        inputSummary: '正在执行分析步骤',
      });

    case 'worker_done':
      return appendTrace(acc, {
        stepNumber: nextStepNumber(acc, event),
        toolLabel: workerLabel(event.agent),
        status: event.success === false ? 'failed' : 'completed',
        observationSummary: event.success === false ? '分析步骤未完成' : '已完成分析步骤',
      });

    case 'answer_chunk':
      return { ...acc, answer: acc.answer + (event.content ?? '') };

    case 'thought':
      return appendTrace(acc, projectAnalysisTrace({
        stepNumber: nextStepNumber(acc, event),
        status: 'running',
      }));

    case 'action': {
      if (acc.analysisTrace.length === 0) return acc;
      const analysisTrace = acc.analysisTrace.map((step, index) =>
        index === acc.analysisTrace.length - 1
          ? projectAnalysisTrace({
              stepNumber: step.stepNumber,
              action: event.content,
              actionInput: event.action_input,
              status: 'running',
            })
          : step,
      );
      return { ...acc, analysisTrace };
    }

    case 'observation': {
      if (acc.analysisTrace.length === 0) return acc;
      const analysisTrace = acc.analysisTrace.map((step, index) =>
        index === acc.analysisTrace.length - 1
          ? { ...step, status: 'completed' as const, ...(event.content ? { observationSummary: '已获取检索结果' } : {}) }
          : step,
      );
      return { ...acc, analysisTrace };
    }

    case 'answer':
      return { ...acc, answer: event.content ?? '' };

    case 'done':
      return { ...acc, done: true };

    default:
      return acc;
  }
}
