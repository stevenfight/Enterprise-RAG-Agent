// -*- coding: utf-8 -*-
/**
 * ChatInput 组件单元测试
 * 覆盖: Sender 渲染 / 发送 / 空输入 / disabled / fillText
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ChatInput from '@/components/chat/ChatInput';

/** Mock useTheme */
vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({ isDark: false }),
}));

const PLACEHOLDER = '请输入您的问题，Enter 发送 / Shift+Enter 换行';

describe('ChatInput', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('TC-AX-002-05 渲染出 Sender（含 ant-sender 语义类）', () => {
    const { container } = render(<ChatInput onSend={vi.fn()} />);
    expect(container.querySelector('.ant-sender')).toBeInTheDocument();
  });

  it('TC-AX-002-01 输入文本点击发送，onSend 被调用且传入文本，输入框清空', () => {
    const onSend = vi.fn();
    const { container } = render(<ChatInput onSend={onSend} />);

    const textarea = container.querySelector('textarea')!;
    fireEvent.change(textarea, { target: { value: '中芯国际2024年营收' } });

    const sendBtn = container.querySelector('button')!;
    fireEvent.click(sendBtn);

    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend).toHaveBeenCalledWith('中芯国际2024年营收');
    // 发送后输入框清空
    expect(textarea.value).toBe('');
  });

  it('TC-AX-002-02 空输入发送，onSend 不被调用', () => {
    const onSend = vi.fn();
    const { container } = render(<ChatInput onSend={onSend} />);

    const sendBtn = container.querySelector('button')!;
    fireEvent.click(sendBtn);

    expect(onSend).not.toHaveBeenCalled();
  });

  it('TC-AX-002-03 disabled=true 时无法触发发送', () => {
    const onSend = vi.fn();
    const { container } = render(<ChatInput onSend={onSend} disabled />);

    const textarea = container.querySelector('textarea')!;
    expect(textarea).toBeDisabled();

    fireEvent.change(textarea, { target: { value: '测试' } });
    const sendBtn = container.querySelector('button')!;
    fireEvent.click(sendBtn);

    expect(onSend).not.toHaveBeenCalled();
  });

  it('TC-AX-002-04 传入 fillText 后自动填入并触发 onFillTextConsumed', () => {
    const onFillTextConsumed = vi.fn();
    const { container } = render(
      <ChatInput onSend={vi.fn()} fillText="对比三大运营商营收" onFillTextConsumed={onFillTextConsumed} />,
    );

    expect(onFillTextConsumed).toHaveBeenCalledTimes(1);
    const textarea = container.querySelector('textarea')!;
    expect(textarea.value).toBe('对比三大运营商营收');
  });

  it('输入框渲染出占位提示文本', () => {
    render(<ChatInput onSend={vi.fn()} />);
    expect(screen.getByPlaceholderText(PLACEHOLDER)).toBeInTheDocument();
  });
});
