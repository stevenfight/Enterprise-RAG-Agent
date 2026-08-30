// -*- coding: utf-8 -*-
/**
 * C2.8 前端按 revision 合并研究任务事件的纯逻辑测试。
 * 核心契约：乱序或重放的旧 revision 事件不得回退已应用的任务状态（C-T18）。
 */
import { describe, expect, it } from 'vitest';

import {
  applyResearchTaskEvent,
  createResearchTaskState,
  type ResearchTaskStreamStateEvent,
} from '@/services/researchTaskState';

/** 构造 run_transitioned 事件帧，字段与后端 SSE 契约一致 */
function transitioned(revision: number, status: string, eventId?: number): ResearchTaskStreamStateEvent {
  return { event_id: eventId ?? revision + 1, event_type: 'run_transitioned', revision, status };
}

describe('researchTaskState', () => {
  it('run_created 事件初始化 pending 状态与 revision 0', () => {
    const state = applyResearchTaskEvent(createResearchTaskState('task-1'), {
      event_id: 1,
      event_type: 'run_created',
      revision: 0,
    });

    expect(state).toEqual({ taskId: 'task-1', status: 'pending', revision: 0, lastEventId: 1, resumed: false });
  });

  it('run_transitioned 事件按 revision 顺序更新状态', () => {
    let state = createResearchTaskState('task-1');
    state = applyResearchTaskEvent(state, { event_id: 1, event_type: 'run_created', revision: 0 });
    state = applyResearchTaskEvent(state, transitioned(1, 'running'));
    state = applyResearchTaskEvent(state, transitioned(2, 'paused'));

    expect(state).toEqual({ taskId: 'task-1', status: 'paused', revision: 2, lastEventId: 3, resumed: false });
  });

  it('旧 revision 事件乱序到达时被忽略，不回退状态', () => {
    let state = createResearchTaskState('task-1');
    state = applyResearchTaskEvent(state, { event_id: 1, event_type: 'run_created', revision: 0 });
    state = applyResearchTaskEvent(state, transitioned(2, 'running'));

    const stale = applyResearchTaskEvent(state, transitioned(1, 'paused'));

    expect(stale).toEqual({ taskId: 'task-1', status: 'running', revision: 2, lastEventId: 3, resumed: false });
  });

  it('相同 revision 事件重放幂等，不重复应用', () => {
    let state = createResearchTaskState('task-1');
    state = applyResearchTaskEvent(state, { event_id: 1, event_type: 'run_created', revision: 0 });
    state = applyResearchTaskEvent(state, transitioned(1, 'running'));

    const replayed = applyResearchTaskEvent(state, transitioned(1, 'running', 2));

    expect(replayed).toEqual(state);
  });

  it('paused 到 running 的恢复事件标记 resumed，其余迁移不标记', () => {
    let state = createResearchTaskState('task-1');
    state = applyResearchTaskEvent(state, { event_id: 1, event_type: 'run_created', revision: 0 });
    state = applyResearchTaskEvent(state, transitioned(1, 'running'));
    state = applyResearchTaskEvent(state, transitioned(2, 'paused'));
    state = applyResearchTaskEvent(state, transitioned(3, 'running'));

    expect(state.resumed).toBe(true);

    let direct = createResearchTaskState('task-2');
    direct = applyResearchTaskEvent(direct, { event_id: 1, event_type: 'run_created', revision: 0 });
    direct = applyResearchTaskEvent(direct, transitioned(1, 'running'));
    direct = applyResearchTaskEvent(direct, transitioned(2, 'waiting_approval'));

    expect(direct.resumed).toBe(false);
  });

  it('window_end 与未知事件类型不改变状态', () => {
    const before = createResearchTaskState('task-1');

    const afterWindowEnd = applyResearchTaskEvent(before, {
      event_type: 'window_end',
      next_event_id: 3,
      oldest_event_id: 1,
      resync_required: false,
    });
    const afterUnknown = applyResearchTaskEvent(before, {
      event_id: 9,
      event_type: 'step_committed',
      revision: 5,
    });

    expect(afterWindowEnd).toEqual(before);
    expect(afterUnknown).toEqual(before);
  });

  it('支持全部六类运行状态顺序应用', () => {
    const statuses = ['running', 'waiting_approval', 'paused', 'failed', 'cancelled', 'completed'] as const;
    let state = createResearchTaskState('task-1');
    state = applyResearchTaskEvent(state, { event_id: 1, event_type: 'run_created', revision: 0 });
    statuses.forEach((status, index) => {
      state = applyResearchTaskEvent(state, transitioned(index + 1, status));
      expect(state.status).toBe(status);
    });
    expect(state.revision).toBe(statuses.length);
  });
});
