// -*- coding: utf-8 -*-
/** 安全分析过程内容复用测试。 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import AnalysisTraceContent from '@/components/chat/AnalysisTraceContent';

vi.mock('@/hooks/useTheme', () => ({ useTheme: () => ({ isDark: false }) }));

describe('AnalysisTraceContent', () => {
  it('CP-R03-01: 只渲染安全分析步骤及真实空状态', () => {
    const { rerender } = render(<AnalysisTraceContent steps={[{
      stepNumber: 1,
      toolLabel: '资料检索',
      status: 'completed',
      inputSummary: '已提供检索条件',
      observationSummary: '已获取检索结果',
    }]} />);

    expect(screen.getByText(/步骤 1.*已完成/)).toBeInTheDocument();
    expect(screen.getByText('资料检索')).toBeInTheDocument();
    rerender(<AnalysisTraceContent steps={[]} />);
    expect(screen.getByText('当前回答暂无分析过程')).toBeInTheDocument();
  });
});
