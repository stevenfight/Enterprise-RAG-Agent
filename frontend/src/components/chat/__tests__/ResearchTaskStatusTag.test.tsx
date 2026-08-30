// -*- coding: utf-8 -*-
/**
 * C2.8 研究任务状态展示组件测试。
 * 覆盖运行、暂停、等待审批、失败、取消、恢复状态的中文标签展示。
 */
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';

import { researchTaskStore } from '@/stores/researchTaskStore';
import type { ResearchTaskState } from '@/services/researchTaskState';
import ResearchTaskStatusTag from '@/components/chat/ResearchTaskStatusTag';

function taskWith(status: ResearchTaskState['status'], resumed = false): Record<string, ResearchTaskState> {
  return {
    'task-1': { taskId: 'task-1', status, revision: 2, lastEventId: 3, resumed },
  };
}

describe('ResearchTaskStatusTag', () => {
  beforeEach(() => {
    researchTaskStore.setState({ tasks: {} });
  });

  it('渲染各类状态的中文标签', () => {
    const cases: Array<[ResearchTaskState['status'], string]> = [
      ['pending', '等待开始'],
      ['running', '运行中'],
      ['waiting_approval', '等待审批'],
      ['paused', '已暂停'],
      ['failed', '失败'],
      ['cancelled', '已取消'],
      ['completed', '已完成'],
    ];

    for (const [status, label] of cases) {
      researchTaskStore.setState({ tasks: taskWith(status) });
      const { unmount } = render(<ResearchTaskStatusTag taskId="task-1" />);
      expect(screen.getByText(label)).toBeInTheDocument();
      unmount();
    }
  });

  it('恢复后的运行中任务同时显示运行中与已恢复标记', () => {
    researchTaskStore.setState({ tasks: taskWith('running', true) });

    render(<ResearchTaskStatusTag taskId="task-1" />);

    expect(screen.getByText('运行中')).toBeInTheDocument();
    expect(screen.getByText('已恢复')).toBeInTheDocument();
  });

  it('未知任务显示未开始', () => {
    render(<ResearchTaskStatusTag taskId="task-missing" />);

    expect(screen.getByText('未开始')).toBeInTheDocument();
  });
});
