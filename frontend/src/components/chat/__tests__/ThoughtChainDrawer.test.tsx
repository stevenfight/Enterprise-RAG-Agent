// -*- coding: utf-8 -*-
/** 分析过程抽屉组件单元测试。 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ThoughtChainDrawer from '@/components/chat/ThoughtChainDrawer';
import type { AnalysisTraceStep } from '@/types/chat';

vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({ isDark: false }),
}));

const mockSteps: AnalysisTraceStep[] = [
  {
    stepNumber: 1,
    toolLabel: '资料检索',
    status: 'completed',
    inputSummary: '已提供检索条件',
    observationSummary: '已获取检索结果',
  },
  {
    stepNumber: 2,
    toolLabel: '财务计算',
    status: 'running',
    inputSummary: '已提供分析条件',
  },
];

describe('ThoughtChainDrawer', () => {
  beforeEach(() => vi.clearAllMocks());

  it('打开时展示安全分析过程摘要', () => {
    render(<ThoughtChainDrawer open onClose={vi.fn()} steps={mockSteps} />);

    expect(screen.getByText(/分析过程.*2 步/)).toBeInTheDocument();
    expect(screen.getByText(/步骤 1.*已完成/)).toBeInTheDocument();
    expect(screen.getByText('资料检索')).toBeInTheDocument();
    expect(screen.getByText('已提供检索条件')).toBeInTheDocument();
    expect(screen.getByText('已获取检索结果')).toBeInTheDocument();
  });

  it('关闭时不展示抽屉内容', () => {
    render(<ThoughtChainDrawer open={false} onClose={vi.fn()} steps={mockSteps} />);
    expect(screen.queryByText(/分析过程/)).toBeNull();
  });

  it('关闭按钮触发回调', () => {
    const onClose = vi.fn();
    render(<ThoughtChainDrawer open onClose={onClose} steps={mockSteps} />);

    fireEvent.click(document.querySelector('.ant-drawer-close')!);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('空步骤列表可正常展示', () => {
    render(<ThoughtChainDrawer open onClose={vi.fn()} steps={[]} />);
    expect(screen.getByText(/分析过程.*0 步/)).toBeInTheDocument();
  });
});
