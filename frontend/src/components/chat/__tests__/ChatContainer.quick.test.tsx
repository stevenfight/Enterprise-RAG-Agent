// -*- coding: utf-8 -*-
/**
 * TDD 测试: 欢迎页 + 快捷指令 (模块 W)
 * 对应文档: openspec/changes/welcome-quick-charts-optimize/specs/tdd-welcome-quick-charts.md
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

const QUICK = ['对比三大运营商2024年营收', '中芯国际2024年净利润是多少？'];

describe('ChatContainer 欢迎页快捷指令 (模块 W)', () => {
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

  it('WQ-01: 传入 quickCommands 时渲染快捷指令胶囊', () => {
    render(<ChatContainer onSend={vi.fn()} quickCommands={QUICK} />);
    QUICK.forEach((q) => {
      expect(screen.getByText(q)).toBeInTheDocument();
    });
  });

  it('WQ-02: 点击胶囊直接发送问题', () => {
    const onSend = vi.fn();
    render(<ChatContainer onSend={onSend} quickCommands={QUICK} />);
    fireEvent.click(screen.getByText(QUICK[0]));
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend).toHaveBeenCalledWith(QUICK[0]);
  });

  it('WQ-03: 未传入 quickCommands 时不渲染快捷指令区', () => {
    render(<ChatContainer onSend={vi.fn()} />);
    QUICK.forEach((q) => {
      expect(screen.queryByText(q)).toBeNull();
    });
  });

  it('WQ-04: 有消息时隐藏快捷指令区', () => {
    state.currentSessionId = 's2';
    render(<ChatContainer onSend={vi.fn()} quickCommands={QUICK} />);
    QUICK.forEach((q) => {
      expect(screen.queryByText(q)).toBeNull();
    });
  });

  it('WQ-05: 快捷指令胶囊带马卡龙样式类', () => {
    const { container } = render(<ChatContainer onSend={vi.fn()} quickCommands={QUICK} />);
    const chips = container.querySelectorAll('.quick-command-chip');
    expect(chips.length).toBe(QUICK.length);
  });
});
