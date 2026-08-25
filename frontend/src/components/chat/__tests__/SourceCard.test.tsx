// -*- coding: utf-8 -*-
/** 引用来源匹配度语义测试。 */
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import SourceCard from '@/components/chat/SourceCard';

vi.mock('@/hooks/useTheme', () => ({ useTheme: () => ({ isDark: false }) }));

describe('SourceCard', () => {
  it('RW-R03-03: 仅将 hybrid 分数显示为检索匹配度百分比', () => {
    render(<SourceCard source={{
      index: 1,
      source_file: '示例年报.pdf',
      pages: [1],
      company_name: '中芯国际',
      scores: { bm25: 18.6, rerank: 7.2 },
    }} />);

    expect(screen.getByText('匹配度未提供')).toBeInTheDocument();
    expect(screen.queryByText('100%')).toBeNull();
  });

  it('CP-R19: 展开后显示后端提供的受限命中摘要', () => {
    const { container } = render(<SourceCard source={{
      index: 1,
      source_file: '移动2024年度报告.pdf',
      pages: [17],
      company_name: '中国移动',
      excerpt: '营业收入为 1,040,759 百万元。',
      scores: { hybrid: 0.9 },
    }} />);

    fireEvent.click(container.querySelector('.ant-card')!);
    expect(screen.getByText('命中文本摘要')).toBeInTheDocument();
    expect(screen.getByText('营业收入为 1,040,759 百万元。')).toBeInTheDocument();
  });

  it('CP-R21: 评分详情可展示后端返回的非数值状态字段', () => {
    render(<SourceCard source={{
      index: 1,
      source_file: '示例年报.pdf',
      pages: [1],
      company_name: '中芯国际',
      scores: { hybrid: 0.9, confidence: 'unknown' },
    }} />);

    expect(screen.getByText('90%')).toBeInTheDocument();
  });
});
