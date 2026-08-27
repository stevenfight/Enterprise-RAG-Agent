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
    const sources = [{ index: 1, source_file: '移动2024年度报告.pdf', pages: [3], company_name: '中国移动', scores: {} }];
    streamAgentQuery.mockImplementation((_query, _options, onEvent) => {
      onEvent({ type: 'answer', content: '直接返回的最终答案', sources });
      return { close: vi.fn() };
    });
    render(<ChatPage />);
    fireEvent.click(screen.getByRole('button', { name: '发起测试' }));

    expect(state.addUserMessage).toHaveBeenCalledWith('测试问题', 'session-1');
    expect(state.addAssistantMessage).toHaveBeenCalledWith(
      '直接返回的最终答案',
      sources,
      undefined,
      'session-1',
      undefined,
      { mode: 'agent', companyName: '全部公司' },
    );
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

    expect(within(screen.getByRole('complementary', { name: '回答级证据' })).getByText('当前回答暂无引用来源')).toBeInTheDocument();
    expect(screen.queryByText('较早年报.pdf')).toBeNull();
  });

  it('CP-R48: 初始工作台在顶栏右侧直接提供研究配置，不打开抽屉', () => {
    const { container } = render(<ChatPage />);

    expect(container.querySelector('.chat-page__config')).toBeNull();
    const config = screen.getByRole('region', { name: '研究配置' });
    expect(config).toHaveTextContent('选择公司');
    expect(screen.getByRole('switch', { name: '启用 Agent 深度推理' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '高级选项' })).toHaveAttribute('aria-expanded', 'false');
    expect(config).not.toHaveTextContent('检索返回条数');
    fireEvent.click(screen.getByRole('button', { name: '高级选项' }));
    expect(config).toHaveTextContent('检索返回条数');
    expect(screen.queryByRole('dialog', { name: '研究配置' })).not.toBeInTheDocument();
  });

  it('CP-R45: 研究配置不重复展示首页示例问题', () => {
    render(<ChatPage />);

    expect(screen.getByRole('region', { name: '研究配置' })).not.toHaveTextContent('示例问题');
  });

  it('CP-R03-01: 桌面证据侧栏提供证据与分析过程标签', () => {
    state.messages = [{
      id: 'answer-1', role: 'assistant', content: '回答', timestamp: 1,
      analysisTrace: [{ stepNumber: 1, toolLabel: '资料检索', status: 'completed', inputSummary: '检索条件' }],
    }];
    render(<ChatPage />);

    fireEvent.click(screen.getByRole('button', { name: '查看证据' }));
    fireEvent.click(screen.getByRole('tab', { name: '分析过程' }));

    expect(screen.getByRole('tab', { name: '证据' })).toHaveAttribute('aria-selected', 'false');
    expect(screen.getByText('资料检索')).toBeInTheDocument();
  });

  it('CP-R34: 桌面证据工作栏默认关闭，仅由查看证据入口打开并可关闭', () => {
    state.messages = [{
      id: 'answer-1', role: 'assistant', content: '回答', timestamp: 1,
      sources: [{ index: 1, source_file: '移动2024年度报告.pdf', pages: [3], company_name: '中国移动', scores: { hybrid: 0.9 } }],
    }];
    const { container } = render(<ChatPage />);

    expect(container.querySelector('.chat-evidence-aside')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '查看证据' }));
    expect(container.querySelector('.chat-evidence-aside')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '关闭证据栏' }));
    expect(container.querySelector('.chat-evidence-aside')).toBeNull();
  });

  it('CP-R35: 1024px 以下查看证据继续打开既有 Drawer，不渲染桌面工作栏', () => {
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = vi.fn().mockReturnValue({ matches: true }) as unknown as typeof window.matchMedia;
    state.messages = [{ id: 'answer-1', role: 'assistant', content: '回答', timestamp: 1 }];
    const { container } = render(<ChatPage />);

    fireEvent.click(screen.getByRole('button', { name: '查看证据' }));
    expect(screen.getByRole('dialog')).toHaveTextContent('证据面板');
    expect(container.querySelector('.chat-evidence-aside')).toBeNull();
    window.matchMedia = originalMatchMedia;
  });

  it('CP-R24-01: 研究配置抽屉不使用已弃用的 width 属性', () => {
    const warningSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    render(<ChatPage />);

    expect(warningSpy).not.toHaveBeenCalledWith(
      expect.stringContaining('[antd: Drawer] `width` is deprecated'),
    );
    warningSpy.mockRestore();
  });
});
