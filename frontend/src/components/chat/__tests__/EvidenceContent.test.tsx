// -*- coding: utf-8 -*-
/** 证据内容复用测试。 */
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import EvidenceContent from '@/components/chat/EvidenceContent';

vi.mock('@/hooks/useTheme', () => ({ useTheme: () => ({ isDark: false }) }));

describe('EvidenceContent', () => {
  it('CP-R06-01: 可脱离 Drawer 展示回答级真实来源', () => {
    render(<EvidenceContent sources={[{
      index: 1,
      source_file: '中芯国际2024年报.pdf',
      pages: [18],
      company_name: '中芯国际',
      scores: { hybrid: 0.86 },
    }]} />);

    expect(screen.getByText('回答级证据')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /中芯国际.*中芯国际2024年报.pdf.*P18/ })).toBeInTheDocument();
  });

  it('CP-R08-01: 没有来源时保留真实空状态', () => {
    render(<EvidenceContent sources={[]} />);
    expect(screen.getByText('当前回答暂无引用来源')).toBeInTheDocument();
  });

  it('CP-R32、CP-R33: Agent 来源显示回答证据，并以可访问按钮展开同报告来源', () => {
    render(<EvidenceContent sources={[
      { index: 1, source_file: '移动2024年度报告.pdf', pages: [17], company_name: '中国移动', scores: {} },
      { index: 2, source_file: '移动2024年度报告.pdf', pages: [18], company_name: '中国移动', scores: {} },
    ]} />);

    const trigger = screen.getByRole('button', { name: /中国移动.*移动2024年度报告.pdf.*P17.*P18/ });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(trigger).toHaveTextContent('回答证据');
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(screen.queryByText('匹配度未提供')).toBeNull();
  });

  it('CP-R38: 检索证据分组将条数标为证据数量，不将数量误称为匹配度', () => {
    render(<EvidenceContent sources={[
      { index: 1, source_file: '移动2024年度报告.pdf', pages: [3], company_name: '中国移动', scores: { hybrid: 0.86 } },
      { index: 2, source_file: '移动2024年度报告.pdf', pages: [18], company_name: '中国移动', scores: { hybrid: 0.73 } },
    ]} />);

    const trigger = screen.getByRole('button', { name: /中国移动.*移动2024年度报告.pdf/ });
    expect(trigger).toHaveTextContent('检索证据 · 2 条');
    expect(trigger).not.toHaveTextContent('检索匹配度 · 2 条');
  });

  it('CP-R40: 指定来源会展开所属证据组并高亮该条证据', () => {
    render(<EvidenceContent highlightedSourceIndex={2} sources={[
      { index: 1, source_file: '移动2024年度报告.pdf', pages: [3], company_name: '中国移动', scores: { hybrid: 0.86 } },
      { index: 2, source_file: '移动2024年度报告.pdf', pages: [18], company_name: '中国移动', scores: { hybrid: 0.73 } },
    ]} />);

    expect(screen.getByRole('button', { name: /中国移动.*移动2024年度报告.pdf/ })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByTestId('source-card-2')).toHaveClass('source-card--highlighted');
  });

  it('CP-R33: 切换当前回答来源后不残留上一条回答的证据包', () => {
    const { rerender } = render(<EvidenceContent sources={[
      { index: 1, source_file: '移动2024年度报告.pdf', pages: [17], company_name: '中国移动', scores: {} },
    ]} />);

    expect(screen.getByRole('button', { name: /中国移动.*移动2024年度报告.pdf/ })).toBeInTheDocument();
    rerender(<EvidenceContent sources={[
      { index: 8, source_file: '电信2024年度报告.pdf', pages: [18], company_name: '中国电信', scores: {} },
    ]} />);

    expect(screen.queryByRole('button', { name: /中国移动.*移动2024年度报告.pdf/ })).toBeNull();
    expect(screen.getByRole('button', { name: /中国电信.*电信2024年度报告.pdf/ })).toBeInTheDocument();
  });
});
