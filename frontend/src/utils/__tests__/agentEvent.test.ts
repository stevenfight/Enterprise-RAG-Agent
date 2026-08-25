// -*- coding: utf-8 -*-
/** Agent SSE 事件安全投影单元测试。 */
import { describe, it, expect } from 'vitest';
import { isMultiAgentEventType, createEmptyAccumulator, applyAgentEvent, projectAnalysisTrace } from '@/utils/agentEvent';
import type { SSEEvent } from '@/types/chat';

function evt(partial: Partial<SSEEvent> & { type: SSEEvent['type'] }): SSEEvent {
  return partial as SSEEvent;
}

describe('SP10-A: 事件类型识别', () => {
  it('识别多 Agent 事件类型', () => {
    for (const type of ['orchestrator_start', 'delegating', 'worker_step', 'worker_done', 'answer_chunk', 'reflection']) {
      expect(isMultiAgentEventType(type)).toBe(true);
    }
  });

  it('不将单 Agent 事件误判为多 Agent', () => {
    for (const type of ['connected', 'thought', 'action', 'observation', 'answer', 'error', 'done']) {
      expect(isMultiAgentEventType(type)).toBe(false);
    }
  });
});

describe('RW-R08: 分析过程安全投影', () => {
  it('工具投影不保留 thought、原始输入与原始观测', () => {
    const trace = projectAnalysisTrace({
      stepNumber: 1,
      action: 'retrieve',
      actionInput: { company: '中芯国际', api_key: 'secret-value' },
      observation: '包含原始检索片段的敏感内容',
      status: 'completed',
    });

    expect(trace).toEqual({
      stepNumber: 1,
      toolLabel: '资料检索',
      status: 'completed',
      inputSummary: '已提供检索条件',
      observationSummary: '已获取检索结果',
    });
    expect(JSON.stringify(trace)).not.toContain('secret-value');
    expect(JSON.stringify(trace)).not.toContain('敏感内容');
  });

  it('未知工具使用中性标签', () => {
    const trace = projectAnalysisTrace({ stepNumber: 2, action: 'internal-tool', status: 'running' });
    expect(trace.toolLabel).toBe('分析工具');
  });

  it('单 Agent SSE 累积状态不保留原始过程', () => {
    let acc = applyAgentEvent(createEmptyAccumulator(), evt({ type: 'thought', step: 1, content: '内部推理' }));
    acc = applyAgentEvent(acc, evt({ type: 'action', content: 'retrieve', action_input: { token: 'secret' } }));
    acc = applyAgentEvent(acc, evt({ type: 'observation', content: '原始观测内容' }));

    expect(acc.analysisTrace).toEqual([{
      stepNumber: 1,
      toolLabel: '资料检索',
      status: 'completed',
      inputSummary: '已提供检索条件',
      observationSummary: '已获取检索结果',
    }]);
    expect(JSON.stringify(acc)).not.toContain('内部推理');
    expect(JSON.stringify(acc)).not.toContain('secret');
    expect(JSON.stringify(acc)).not.toContain('原始观测内容');
  });

  it('多 Agent SSE 仅产生受控摘要，不保留原始 Worker 信息', () => {
    let acc = applyAgentEvent(createEmptyAccumulator(), evt({ type: 'orchestrator_start', registered_agents: ['InternalAgent'] }));
    acc = applyAgentEvent(acc, evt({ type: 'delegating', agents: ['InternalAgent'] }));
    acc = applyAgentEvent(acc, evt({ type: 'worker_step', agent: 'InternalAgent', content: '内部执行细节', step: 1 }));
    acc = applyAgentEvent(acc, evt({ type: 'worker_done', agent: 'InternalAgent', success: true }));

    expect(acc.analysisTrace.map((step) => step.toolLabel)).toEqual(['协同分析', '协同分析', '协同分析', '协同分析']);
    expect(acc.analysisTrace.at(-1)).toMatchObject({ status: 'completed', observationSummary: '已完成分析步骤' });
    expect(JSON.stringify(acc)).not.toContain('InternalAgent');
    expect(JSON.stringify(acc)).not.toContain('内部执行细节');
  });
});

describe('SP10-C: SSE 回答状态', () => {
  it('answer_chunk 累积并由 answer 覆盖', () => {
    let acc = applyAgentEvent(createEmptyAccumulator(), evt({ type: 'answer_chunk', content: '片段一' }));
    acc = applyAgentEvent(acc, evt({ type: 'answer_chunk', content: '片段二' }));
    expect(acc.answer).toBe('片段一片段二');

    acc = applyAgentEvent(acc, evt({ type: 'answer', content: '完整回答' }));
    expect(acc.answer).toBe('完整回答');
  });

  it('done 标记流结束', () => {
    expect(applyAgentEvent(createEmptyAccumulator(), evt({ type: 'done' })).done).toBe(true);
  });
});
