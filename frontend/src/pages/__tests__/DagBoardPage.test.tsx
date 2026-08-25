// -*- coding: utf-8 -*-
/** 分析流程页的定位与窄屏降级回归测试。 */
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const getAgentPlan = vi.hoisted(() => vi.fn());
vi.mock('@/services/dagService', () => ({ getAgentPlan }));
vi.mock('@/components/dag/DagFlow', () => ({ default: () => <div>流程画布</div> }));

import DagBoardPage from '@/pages/DagBoardPage';

describe('DagBoardPage', () => {
  it('AP-R03-01: 标识高级分析流程，并为复杂画布提供窄屏降级钩子', () => {
    getAgentPlan.mockResolvedValue({
      category: '检索', message: '已生成任务计划', nodes: [], edges: [], execution_order: [],
    });
    const { container } = render(<DagBoardPage />);

    fireEvent.change(screen.getByRole('textbox'), { target: { value: '测试问题' } });
    fireEvent.click(screen.getByRole('button', { name: /分析/ }));

    expect(screen.getByRole('heading', { name: '高级分析流程' })).toBeInTheDocument();
    return screen.findByRole('region', { name: '任务摘要' }).then(() => {
      expect(container.querySelector('.dag-flow-panel')).toBeInTheDocument();
    });
  });

  it('QA-R06-03: 查询操作位于统一研究操作区', () => {
    render(<DagBoardPage />);

    expect(screen.getByRole('textbox').closest('.page-toolbar')).toBeInTheDocument();
  });
});
