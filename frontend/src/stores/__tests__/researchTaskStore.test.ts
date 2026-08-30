// -*- coding: utf-8 -*-
/**
 * C2.8 研究任务状态 store 测试。
 * store 仅持有按 revision 合并后的任务状态，多任务相互隔离。
 */
import { beforeEach, describe, expect, it } from 'vitest';

import { researchTaskStore } from '@/stores/researchTaskStore';

describe('researchTaskStore', () => {
  beforeEach(() => {
    researchTaskStore.setState({ tasks: {} });
  });

  it('applyEvent 按任务合并事件状态', () => {
    researchTaskStore.getState().applyEvent('task-a', {
      event_id: 1,
      event_type: 'run_created',
      revision: 0,
    });
    researchTaskStore.getState().applyEvent('task-a', {
      event_id: 2,
      event_type: 'run_transitioned',
      revision: 1,
      status: 'running',
    });

    expect(researchTaskStore.getState().tasks['task-a']).toEqual({
      taskId: 'task-a',
      status: 'running',
      revision: 1,
      lastEventId: 2,
      resumed: false,
    });
  });

  it('多任务状态相互隔离', () => {
    researchTaskStore.getState().applyEvent('task-a', {
      event_id: 1,
      event_type: 'run_created',
      revision: 0,
    });
    researchTaskStore.getState().applyEvent('task-b', {
      event_id: 1,
      event_type: 'run_created',
      revision: 0,
    });
    researchTaskStore.getState().applyEvent('task-b', {
      event_id: 2,
      event_type: 'run_transitioned',
      revision: 1,
      status: 'failed',
    });

    const tasks = researchTaskStore.getState().tasks;
    expect(tasks['task-a']).toMatchObject({ status: 'pending' });
    expect(tasks['task-b']).toMatchObject({ status: 'failed' });
  });

  it('resetTask 移除任务恢复初始', () => {
    researchTaskStore.getState().applyEvent('task-a', {
      event_id: 1,
      event_type: 'run_created',
      revision: 0,
    });

    researchTaskStore.getState().resetTask('task-a');

    expect(researchTaskStore.getState().tasks['task-a']).toBeUndefined();
  });

  it('旧 revision 事件经由 store 也不回退状态', () => {
    researchTaskStore.getState().applyEvent('task-a', {
      event_id: 1,
      event_type: 'run_created',
      revision: 0,
    });
    researchTaskStore.getState().applyEvent('task-a', {
      event_id: 2,
      event_type: 'run_transitioned',
      revision: 2,
      status: 'running',
    });
    researchTaskStore.getState().applyEvent('task-a', {
      event_id: 3,
      event_type: 'run_transitioned',
      revision: 1,
      status: 'paused',
    });

    expect(researchTaskStore.getState().tasks['task-a']).toMatchObject({ status: 'running', revision: 2 });
  });
});
