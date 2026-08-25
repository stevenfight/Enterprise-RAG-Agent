// -*- coding: utf-8 -*-
/** 证据面板测试。 */
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import EvidencePanel from '@/components/chat/EvidencePanel';

vi.mock('@/hooks/useTheme', () => ({ useTheme: () => ({ isDark: false }) }));

const sources = [{
  index: 1,
  source_file: '中芯国际2024年报.pdf',
  pages: [18, 19],
  company_name: '中芯国际',
  scores: { hybrid: 0.86 },
}];

describe('EvidencePanel', () => {
  it('RW-R03-01: 展示真实来源并说明证据与分数语义', () => {
    render(<EvidencePanel open onClose={vi.fn()} sources={sources} />);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('回答级证据')).toBeInTheDocument();
    expect(screen.getByText('检索匹配度')).toBeInTheDocument();
    expect(screen.getByText('中芯国际2024年报.pdf')).toBeInTheDocument();
  });

  it('没有引用来源时展示真实空状态', () => {
    render(<EvidencePanel open onClose={vi.fn()} sources={[]} />);
    expect(screen.getByText('当前回答暂无引用来源')).toBeInTheDocument();
  });

  it('关闭按钮触发回调', () => {
    const onClose = vi.fn();
    render(<EvidencePanel open onClose={onClose} sources={sources} />);
    fireEvent.click(document.querySelector('.ant-drawer-close')!);
    expect(onClose).toHaveBeenCalledOnce();
  });
});
