// -*- coding: utf-8 -*-
/**
 * TDD 测试: MessageBubble 微交互（复制 + 重新生成）
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import MessageBubble from '../MessageBubble';
import type { Message } from '@/types/chat';

const mockMessage: Message = {
  id: 'm1',
  role: 'assistant',
  content: '2024年营收1,234.5亿元，净利润567.8亿元',
  timestamp: Date.now(),
  sources: [],
};

const mockUserMessage: Message = {
  id: 'm2',
  role: 'user',
  content: '查询营收',
  timestamp: Date.now(),
};

// mock useTheme
vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({ isDark: false }),
}));

// mock clipboard
Object.assign(navigator, {
  clipboard: {
    writeText: vi.fn().mockResolvedValue(undefined),
  },
});

describe('MessageBubble micro-interactions', () => {
  it('MB-01: hover AI 消息显示复制按钮', async () => {
    render(<MessageBubble message={mockMessage} />);
    const bubble = screen.getByText(/2024年营收/).closest('div');
    expect(bubble).toBeTruthy();
    fireEvent.mouseEnter(bubble!);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /复制/i })).toBeInTheDocument();
    });
  });

  it('MB-02: 点击复制写入剪贴板', async () => {
    render(<MessageBubble message={mockMessage} />);
    const bubble = screen.getByText(/2024年营收/).closest('div');
    fireEvent.mouseEnter(bubble!);
    const copyBtn = await screen.findByRole('button', { name: /复制/i });
    fireEvent.click(copyBtn);
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(mockMessage.content);
    });
  });

  it('MB-03: hover 显示重新生成按钮', async () => {
    const onRegenerate = vi.fn();
    render(<MessageBubble message={mockMessage} onRegenerate={onRegenerate} />);
    const bubble = screen.getByText(/2024年营收/).closest('div');
    fireEvent.mouseEnter(bubble!);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /重新生成/i })).toBeInTheDocument();
    });
  });

  it('MB-04: 点击重新生成触发回调', async () => {
    const onRegenerate = vi.fn();
    render(<MessageBubble message={mockMessage} onRegenerate={onRegenerate} />);
    const bubble = screen.getByText(/2024年营收/).closest('div');
    fireEvent.mouseEnter(bubble!);
    const regenBtn = await screen.findByRole('button', { name: /重新生成/i });
    fireEvent.click(regenBtn);
    expect(onRegenerate).toHaveBeenCalledWith(mockMessage.id);
  });

  it('MB-05: 用户消息不显示操作按钮', () => {
    render(<MessageBubble message={mockUserMessage} />);
    const bubble = screen.getByText(/查询营收/).closest('div');
    fireEvent.mouseEnter(bubble!);
    expect(screen.queryByRole('button', { name: /复制/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /重新生成/i })).not.toBeInTheDocument();
  });
});
