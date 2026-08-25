// -*- coding: utf-8 -*-
/** ChatPage SSE 时序回归测试。 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';

const state = vi.hoisted(() => ({
  isLoading: false,
  currentSessionId: 'session-1',
  messages: [] as any[],
  addUserMessage: vi.fn(),
  addAssistantMessage: vi.fn(),
  addErrorMessage: vi.fn(),
  updateLastAssistantMessage: vi.fn(),
  setLoading: vi.fn(),
  researchContext: { mode: 'agent' as 'agent' | 'rag', companyName: undefined as string | undefined },
  setResearchContext: vi.fn(),
}));
const streamAgentQuery = vi.hoisted(() => vi.fn());
const queryQuestion = vi.hoisted(() => vi.fn());

vi.mock('@/stores/chatStore', () => ({
  chatStore: (selector: (value: typeof state) => unknown) => selector(state),
  selectCurrentMessages: (value: typeof state) => value.messages,
}));

vi.mock('@/stores/appStore', () => ({
  appStore: (selector: (value: typeof state) => unknown) => selector(state),
}));

vi.mock('@/hooks/useTheme', () => ({ useTheme: () => ({ isDark: false }) }));
vi.mock('@/services/chatService', () => ({
  getCompanies: vi.fn(() => new Promise(() => {})),
  queryQuestion,
  streamAgentQuery,
}));
vi.mock('@/components/chat/ThoughtChainDrawer', () => ({ default: () => null }));
vi.mock('@/components/chat/ChatContainer', () => ({
  default: ({ onSend }: { onSend: (content: string) => void }) => (
    <button type="button" onClick={() => onSend('测试问题')}>发起测试</button>
  ),
}));

import ChatPage from '@/pages/ChatPage';

describe('ChatPage Agent SSE', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    state.messages = [];
    localStorage.setItem('agent-mode', 'true');
    streamAgentQuery.mockImplementation((_query, _options, onEvent) => {
      onEvent({ type: 'answer', content: '直接返回的最终答案' });
      return { close: vi.fn() };
    });
  });

  it('RW-R05-01: 首事件为 answer 时仍创建并写入助手消息', () => {
    render(<ChatPage />);
    fireEvent.click(screen.getByRole('button', { name: '发起测试' }));

    expect(state.addUserMessage).toHaveBeenCalledWith('测试问题', 'session-1');
    expect(state.addAssistantMessage).toHaveBeenCalledWith('直接返回的最终答案', [], undefined, 'session-1');
  });

  it('RW-R05-02: SSE 连接错误后清理超时计时器，不重复提示错误', () => {
    vi.useFakeTimers();
    let onError: ((error: Event) => void) | undefined;
    streamAgentQuery.mockImplementation((_query, _options, _onEvent, errorHandler) => {
      onError = errorHandler;
      return { close: vi.fn() };
    });

    render(<ChatPage />);
    fireEvent.click(screen.getByRole('button', { name: '发起测试' }));
    onError?.(new Event('error'));

    expect(state.addErrorMessage).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(120000);
    expect(state.addErrorMessage).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it('CP-R15-01: 页面卸载后忽略迟到的 SSE 最终答案', () => {
    let onEvent: ((event: { type: string; content?: string }) => void) | undefined;
    streamAgentQuery.mockImplementation((_query, _options, eventHandler) => {
      onEvent = eventHandler;
      return { close: vi.fn() };
    });

    const { unmount } = render(<ChatPage />);
    fireEvent.click(screen.getByRole('button', { name: '发起测试' }));
    unmount();
    onEvent?.({ type: 'answer', content: '迟到答案' });

    expect(state.addAssistantMessage).not.toHaveBeenCalled();
  });

  it('RW-R03-02: 证据面板不将较早回答的来源归因给当前回答', () => {
    state.messages = [
      {
        id: 'old-answer', role: 'assistant', content: '较早回答', timestamp: 1,
        sources: [{ index: 1, source_file: '较早年报.pdf', pages: [1], company_name: '中芯国际', scores: { hybrid: 0.9 } }],
      },
      { id: 'latest-answer', role: 'assistant', content: '当前回答', timestamp: 2 },
    ];

    render(<ChatPage />);
    fireEvent.click(screen.getByRole('button', { name: /查看证据/ }));

    expect(within(screen.getByRole('dialog')).getByText('当前回答暂无引用来源')).toBeInTheDocument();
    expect(screen.queryByText('较早年报.pdf')).toBeNull();
  });

  it('CP-R01-01: 不再渲染常驻配置栏，研究配置由唯一入口打开', () => {
    const { container } = render(<ChatPage />);

    expect(container.querySelector('.chat-page__config')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '打开研究配置' }));
    expect(screen.getByRole('dialog')).toHaveTextContent('研究配置');
  });

  it('CP-R03-01: 桌面证据侧栏提供证据与分析过程标签', () => {
    state.messages = [{
      id: 'answer-1', role: 'assistant', content: '回答', timestamp: 1,
      analysisTrace: [{ stepNumber: 1, toolLabel: '资料检索', status: 'completed', inputSummary: '检索条件' }],
    }];
    render(<ChatPage />);

    fireEvent.click(screen.getByRole('tab', { name: '分析过程' }));

    expect(screen.getByRole('tab', { name: '证据' })).toHaveAttribute('aria-selected', 'false');
    expect(screen.getByText('资料检索')).toBeInTheDocument();
  });
});
