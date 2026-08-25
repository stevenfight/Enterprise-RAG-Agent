// -*- coding: utf-8 -*-
/** 证据内容复用测试。 */
import { render, screen } from '@testing-library/react';
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
    expect(screen.getByText('中芯国际2024年报.pdf')).toBeInTheDocument();
  });

  it('CP-R08-01: 没有来源时保留真实空状态', () => {
    render(<EvidenceContent sources={[]} />);
    expect(screen.getByText('当前回答暂无引用来源')).toBeInTheDocument();
  });
});
