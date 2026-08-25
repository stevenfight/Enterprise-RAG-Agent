// -*- coding: utf-8 -*-
/** 历史会话过程字段清理测试 */

import { describe, expect, it } from 'vitest';
import { sanitizeSessions } from '@/stores/chatStore';
import type { Session } from '@/types/chat';

describe('历史会话安全清理', () => {
  it('RW-R08-02 删除遗留原始过程字段并保留问答', () => {
    const sessions = [{
      id: 's1', title: '测试', createdAt: 1, updatedAt: 1,
      messages: [{
        id: 'm1', role: 'assistant', content: '最终回答', timestamp: 1,
        reasoningChain: [{ step_number: 1, thought: '敏感推理', action_input: { token: 'secret' }, elapsed_ms: 0 }],
        agentRun: { isMultiAgent: true, registeredAgents: ['RawWorker'], workers: [] },
      }],
    }] as unknown as Session[];

    const result = sanitizeSessions(sessions);

    expect(result.changed).toBe(true);
    expect(result.sessions[0].messages[0]).toMatchObject({ content: '最终回答' });
    expect(JSON.stringify(result.sessions)).not.toContain('敏感推理');
    expect(JSON.stringify(result.sessions)).not.toContain('secret');
    expect(JSON.stringify(result.sessions)).not.toContain('RawWorker');
  });

  it('RW-R08-03 过程字段为 null 时也会删除', () => {
    const sessions = [{
      id: 's2', title: '测试', createdAt: 1, updatedAt: 1,
      messages: [{ id: 'm2', role: 'assistant', content: '最终回答', timestamp: 1, reasoningChain: null }],
    }] as unknown as Session[];

    const result = sanitizeSessions(sessions);

    expect(result.changed).toBe(true);
    expect(Object.hasOwn(result.sessions[0].messages[0], 'reasoningChain')).toBe(false);
  });
});
