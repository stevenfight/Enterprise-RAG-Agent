// -*- coding: utf-8 -*-
/**
 * ChatContainer 组件单元测试
 * 覆盖: Conversations 会话列表 / 新建对话 / 切换会话 / Welcome 欢迎页
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ChatContainer from '@/components/chat/ChatContainer';

/** Mock useTheme */
vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({ isDark: false }),
}));

/** 可变状态，供 chatStore mock 读取 */
const state = vi.hoisted(() => ({
  sessions: [
    { id: 's1', title: '会话一', createdAt: 1, updatedAt: 2, messages: [] },
    {
      id: 's2',
      title: '会话二',
      createdAt: 3,
      updatedAt: 4,
      messages: [{ id: 'm1', role: 'assistant' as const, content: '这是回答内容', timestamp: 5 }],
    },
  ],
  currentSessionId: 's1',
  isLoading: false,
  createNewSession: vi.fn(),
  switchSession: vi.fn(),
  deleteSession: vi.fn(),
  clearCurrentMessages: vi.fn(),
}));

vi.mock('@/stores/chatStore', () => ({
  chatStore: (selector: (s: any) => any) => selector(state),
  selectCurrentMessages: (s: any) => {
    const session = s.sessions.find((x: any) => x.id === s.currentSessionId);
    return session?.messages || [];
  },
}));

const defaultProps = {
  onSend: vi.fn(),
};

describe('ChatContainer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    state.sessions = [
      { id: 's1', title: '会话一', createdAt: 1, updatedAt: 2, messages: [] },
      {
        id: 's2',
        title: '会话二',
        createdAt: 3,
        updatedAt: 4,
        messages: [{ id: 'm1', role: 'assistant' as const, content: '这是回答内容', timestamp: 5 }],
      },
    ];
    state.currentSessionId = 's1';
    state.isLoading = false;
  });

  it('TC-AX-004-01 会话列表渲染出 Conversations（含 ant-conversations 语义类）', () => {
    const { container } = render(<ChatContainer {...defaultProps} />);
    expect(container.querySelector('.ant-conversations')).toBeInTheDocument();
  });

  it('TC-AX-004-02 点击"新建对话"触发 createNewSession', () => {
    render(<ChatContainer {...defaultProps} />);
    fireEvent.click(screen.getByText('新建对话'));
    expect(state.createNewSession).toHaveBeenCalledTimes(1);
  });

  it('TC-AX-004-03 点击会话项触发 switchSession', () => {
    render(<ChatContainer {...defaultProps} />);
    fireEvent.click(screen.getByText('会话二'));
    expect(state.switchSession).toHaveBeenCalledWith('s2');
  });

  it('TC-AX-004-04 空消息态渲染 Welcome 欢迎组件', () => {
    render(<ChatContainer {...defaultProps} />);
    expect(screen.getByText('您好，我是企业财务年报分析助手')).toBeInTheDocument();
  });

  it('TC-AX-004-05 有消息时隐藏 Welcome，展示消息气泡', () => {
    state.currentSessionId = 's2';
    render(<ChatContainer {...defaultProps} />);
    expect(screen.queryByText('您好，我是企业财务年报分析助手')).toBeNull();
    expect(screen.getByText('这是回答内容')).toBeInTheDocument();
  });
});
