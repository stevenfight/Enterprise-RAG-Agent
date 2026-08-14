// -*- coding: utf-8 -*-
/**
 * 前端多 Agent 流式可视化 - 纯函数单元测试 (SP10)
 * 覆盖: 事件类型识别 / 多 Agent reducer 映射 / 单 Agent reducer 回归
 */
import { describe, it, expect } from 'vitest';
import {
  isMultiAgentEventType,
  createEmptyAccumulator,
  applyAgentEvent,
} from '@/utils/agentEvent';
import type { SSEEvent } from '@/types/chat';

/** 便捷构造 SSE 事件 */
function evt(partial: Partial<SSEEvent> & { type: SSEEvent['type'] }): SSEEvent {
  return partial as SSEEvent;
}

describe('SP10-A: 多 Agent 事件类型识别', () => {
  it('TC-10-A-01 识别多 Agent 事件类型', () => {
    const multi = [
      'orchestrator_start',
      'delegating',
      'worker_step',
      'worker_done',
      'answer_chunk',
      'reflection',
    ];
    for (const type of multi) {
      expect(isMultiAgentEventType(type)).toBe(true);
    }
  });

  it('TC-10-A-02 识别单 Agent 事件类型', () => {
    const single = [
      'connected',
      'thought',
      'action',
      'observation',
      'answer',
      'error',
      'done',
    ];
    for (const type of single) {
      expect(isMultiAgentEventType(type)).toBe(false);
    }
  });
});

describe('SP10-B: 多 Agent 事件 reducer 映射', () => {
  it('TC-10-B-01 orchestrator_start 初始化多 Agent 状态', () => {
    const acc = applyAgentEvent(
      createEmptyAccumulator(),
      evt({ type: 'orchestrator_start', registered_agents: ['DataAgent', 'CalcAgent'] }),
    );
    expect(acc.agentRun?.isMultiAgent).toBe(true);
    expect(acc.agentRun?.registeredAgents).toEqual(['DataAgent', 'CalcAgent']);
    expect(acc.agentRun?.workers).toHaveLength(0);
  });

  it('TC-10-B-02 delegating 初始化 Worker 状态', () => {
    let acc = applyAgentEvent(
      createEmptyAccumulator(),
      evt({ type: 'orchestrator_start', registered_agents: ['DataAgent', 'CalcAgent'] }),
    );
    acc = applyAgentEvent(
      acc,
      evt({ type: 'delegating', batch: 1, agents: ['DataAgent', 'ChartAgent'] }),
    );
    expect(acc.agentRun?.workers).toHaveLength(2);
    expect(acc.agentRun?.workers.every((w) => w.done === false)).toBe(true);
  });

  it('TC-10-B-03 worker_step 追加步骤', () => {
    let acc = applyAgentEvent(
      createEmptyAccumulator(),
      evt({ type: 'orchestrator_start', registered_agents: ['DataAgent'] }),
    );
    acc = applyAgentEvent(
      acc,
      evt({ type: 'delegating', batch: 1, agents: ['DataAgent'] }),
    );
    acc = applyAgentEvent(
      acc,
      evt({
        type: 'worker_step',
        agent: 'DataAgent',
        step_type: 'thought',
        step: 1,
        content: '检索三大运营商营收数据',
      }),
    );
    const worker = acc.agentRun?.workers.find((w) => w.agent === 'DataAgent');
    expect(worker?.steps).toHaveLength(1);
    expect(worker?.steps[0]).toMatchObject({
      agent: 'DataAgent',
      step_type: 'thought',
      step: 1,
      content: '检索三大运营商营收数据',
    });
  });

  it('TC-10-B-04 worker_step 未知 Worker 自动创建', () => {
    const acc = applyAgentEvent(
      createEmptyAccumulator(),
      evt({
        type: 'worker_step',
        agent: 'ChartAgent',
        step_type: 'action',
        step: 1,
        content: '生成对比图表',
      }),
    );
    expect(acc.agentRun?.isMultiAgent).toBe(true);
    expect(acc.agentRun?.workers).toHaveLength(1);
    expect(acc.agentRun?.workers[0].agent).toBe('ChartAgent');
    expect(acc.agentRun?.workers[0].steps).toHaveLength(1);
  });

  it('TC-10-B-05 worker_done 标记完成', () => {
    let acc = applyAgentEvent(
      createEmptyAccumulator(),
      evt({ type: 'orchestrator_start', registered_agents: ['DataAgent'] }),
    );
    acc = applyAgentEvent(
      acc,
      evt({ type: 'delegating', batch: 1, agents: ['DataAgent'] }),
    );
    acc = applyAgentEvent(
      acc,
      evt({
        type: 'worker_done',
        agent: 'DataAgent',
        success: true,
        total_steps: 4,
        total_elapsed_ms: 6916,
      }),
    );
    const worker = acc.agentRun?.workers.find((w) => w.agent === 'DataAgent');
    expect(worker?.done).toBe(true);
    expect(worker?.success).toBe(true);
    expect(worker?.elapsed_ms).toBe(6916);
  });

  it('TC-10-B-06 answer_chunk 追加答案', () => {
    let acc = applyAgentEvent(
      createEmptyAccumulator(),
      evt({ type: 'answer_chunk', content: '中国移动营收...' }),
    );
    acc = applyAgentEvent(
      acc,
      evt({ type: 'answer_chunk', content: '中国联通...' }),
    );
    expect(acc.answer).toBe('中国移动营收...中国联通...');
  });

  it('TC-10-B-07 answer 设置最终答案', () => {
    let acc = applyAgentEvent(
      createEmptyAccumulator(),
      evt({ type: 'answer_chunk', content: '片段' }),
    );
    acc = applyAgentEvent(
      acc,
      evt({ type: 'answer', content: '完整答案', workers: 2, total_tokens: 1234 }),
    );
    expect(acc.answer).toBe('完整答案');
  });

  it('TC-10-B-08 done 标记完成', () => {
    const acc = applyAgentEvent(
      createEmptyAccumulator(),
      evt({ type: 'done', timestamp: Date.now() }),
    );
    expect(acc.done).toBe(true);
  });
});

describe('SP10-C: 单 Agent 事件 reducer 回归', () => {
  it('TC-10-C-01 thought 追加推理链', () => {
    const acc = applyAgentEvent(
      createEmptyAccumulator(),
      evt({ type: 'thought', step: 1, content: '检索数据' }),
    );
    expect(acc.reasoningChain).toHaveLength(1);
    expect(acc.reasoningChain[0]).toMatchObject({
      step_number: 1,
      thought: '检索数据',
    });
  });

  it('TC-10-C-02 action 更新最后一步', () => {
    let acc = applyAgentEvent(
      createEmptyAccumulator(),
      evt({ type: 'thought', step: 1, content: '检索数据' }),
    );
    acc = applyAgentEvent(
      acc,
      evt({ type: 'action', step: 1, content: 'retrieve', action_input: { company: '中国移动' } }),
    );
    const last = acc.reasoningChain[acc.reasoningChain.length - 1];
    expect(last.action).toBe('retrieve');
    expect(last.action_input).toEqual({ company: '中国移动' });
  });

  it('TC-10-C-03 observation 更新最后一步', () => {
    let acc = applyAgentEvent(
      createEmptyAccumulator(),
      evt({ type: 'thought', step: 1, content: '检索数据' }),
    );
    acc = applyAgentEvent(
      acc,
      evt({ type: 'observation', step: 1, content: '营收 10,408 亿元' }),
    );
    const last = acc.reasoningChain[acc.reasoningChain.length - 1];
    expect(last.observation).toBe('营收 10,408 亿元');
  });

  it('TC-10-C-04 answer 设置最终答案且 agentRun 保持 null', () => {
    const acc = applyAgentEvent(
      createEmptyAccumulator(),
      evt({ type: 'answer', content: '最终答案' }),
    );
    expect(acc.answer).toBe('最终答案');
    expect(acc.agentRun).toBeNull();
  });

  it('TC-10-C-05 done 标记完成', () => {
    const acc = applyAgentEvent(
      createEmptyAccumulator(),
      evt({ type: 'done', timestamp: Date.now() }),
    );
    expect(acc.done).toBe(true);
  });
});
