// -*- coding: utf-8 -*-
/**
 * ChatContainer 组件单元测试
 * 覆盖: Conversations 会话列表 / 新建对话 / 切换会话 / Welcome 欢迎页
 */
import { render, screen, fireEvent, within } from '@testing-library/react';
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
    expect(screen.getByRole('region', { name: '研究启动页' })).toBeInTheDocument();
  });

  it('TC-AX-004-05 有消息时隐藏 Welcome，展示消息气泡', () => {
    state.currentSessionId = 's2';
    render(<ChatContainer {...defaultProps} />);
    expect(screen.queryByText('您好，我是企业财务年报分析助手')).toBeNull();
    expect(screen.getByText('这是回答内容')).toBeInTheDocument();
  });

  it('RW-R10-03: 提供可访问的移动端会话入口', () => {
    render(<ChatContainer {...defaultProps} />);

    fireEvent.click(screen.getByRole('button', { name: '打开会话列表' }));

    expect(within(screen.getByRole('dialog')).getByText('会话列表')).toBeInTheDocument();
  });

  it('CP-R04-01: 页面可受控关闭移动会话抽屉', () => {
    const onMobileSessionsOpenChange = vi.fn();
    render(
      <ChatContainer
        {...defaultProps}
        mobileSessionsOpen
        onMobileSessionsOpenChange={onMobileSessionsOpenChange}
      />,
    );

    fireEvent.click(document.querySelector('.ant-drawer-close')!);

    expect(onMobileSessionsOpenChange).toHaveBeenCalledWith(false);
  });

  it('CP-R09-01: 请求进行中禁用新建、切换和移动会话入口', () => {
    render(<ChatContainer {...defaultProps} isLoading />);

    fireEvent.click(screen.getByText('新建对话'));
    fireEvent.click(screen.getByText('会话二'));

    expect(state.createNewSession).not.toHaveBeenCalled();
    expect(state.switchSession).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: '打开会话列表' })).toBeDisabled();
  });

  it('CP-R54: 主消息区具有研究画布滚动样式钩子', () => {
    const { container } = render(<ChatContainer {...defaultProps} />);
    expect(container.querySelector('.chat-scroll-area--refined')).toBeInTheDocument();
  });

  it('CP-R55: 空会话启动页不自动滚离首屏', () => {
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: scrollIntoView });

    try {
      render(<ChatContainer {...defaultProps} />);
      expect(scrollIntoView).not.toHaveBeenCalled();
    } finally {
      Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: originalScrollIntoView });
    }
  });

  it('CP-R12-01: prefers-reduced-motion 下自动滚动不使用平滑动画', () => {
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: scrollIntoView });
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = ((query: string) => ({
      matches: query.includes('prefers-reduced-motion'),
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    })) as unknown as typeof window.matchMedia;

    try {
      state.currentSessionId = 's2';
      render(<ChatContainer {...defaultProps} />);
      expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'auto' });
    } finally {
      Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: originalScrollIntoView });
      window.matchMedia = originalMatchMedia;
    }
  });
});
