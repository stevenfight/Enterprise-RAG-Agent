// -*- coding: utf-8 -*-
/**
 * MessageBubble 组件单元测试
 * 覆盖: 用户/AI/系统消息渲染、Markdown 表格、来源卡片、推理链折叠区
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import MessageBubble from '@/components/chat/MessageBubble';
import type { Message } from '@/types/chat';

/** Mock useTheme */
vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({ isDark: false }),
}));

const baseMessage: Message = {
  id: 'm1',
  role: 'assistant',
  content: '这是一条回答',
  timestamp: 1700000000000,
};

describe('MessageBubble', () => {
  it('TC-AX-003-01 用户消息渲染为 placement=end（右对齐）', () => {
    const { container } = render(
      <MessageBubble message={{ ...baseMessage, role: 'user', content: '你好' }} />,
    );
    expect(container.querySelector('.ant-bubble-end')).toBeInTheDocument();
  });

  it('TC-AX-003-02 AI 消息渲染为 placement=start（左对齐）', () => {
    const { container } = render(<MessageBubble message={baseMessage} />);
    expect(container.querySelector('.ant-bubble-start')).toBeInTheDocument();
  });

  it('TC-AX-003-03 系统消息渲染为居中提示', () => {
    const { container } = render(
      <MessageBubble message={{ ...baseMessage, role: 'system', content: '服务暂时不可用', error: '服务暂时不可用' }} />,
    );
    expect(screen.getByText('服务暂时不可用')).toBeInTheDocument();
    // 系统消息不渲染为气泡
    expect(container.querySelector('.ant-bubble')).toBeNull();
  });

  it('TC-AX-003-04 Markdown 表格渲染为 <table> 元素', () => {
    const { container } = render(
      <MessageBubble
        message={{
          ...baseMessage,
          content: '| 公司 | 营收 |\n|---|---|\n| 中芯国际 | 1000亿 |',
        }}
      />,
    );
    expect(container.querySelector('table')).toBeInTheDocument();
    expect(container.querySelector('td')?.textContent).toContain('中芯国际');
  });

  it('TC-AX-003-05 含来源的消息渲染来源卡片', () => {
    render(
      <MessageBubble
        message={{
          ...baseMessage,
          sources: [
            {
              index: 1,
              source_file: '中芯国际2024年报.pdf',
              pages: [1, 2],
              company_name: '中芯国际',
              scores: { hybrid: 0.9 },
            },
          ],
        }}
      />,
    );
    expect(screen.getByText('引用来源')).toBeInTheDocument();
    expect(screen.getByText('中芯国际2024年报.pdf')).toBeInTheDocument();
  });

  it('TC-AX-003-06 含推理链的消息渲染"推理过程"折叠区', () => {
    render(
      <MessageBubble
        message={{
          ...baseMessage,
          reasoningChain: [
            {
              step_number: 1,
              thought: '检索财务数据',
              action: 'search',
              observation: '命中 3 条结果',
              elapsed_ms: 120,
            },
          ],
        }}
      />,
    );
    expect(screen.getByText(/推理过程.*1 步/)).toBeInTheDocument();
  });

  it('AI 消息含多 Agent 状态时渲染 Worker 运行状态', () => {
    render(
      <MessageBubble
        message={{
          ...baseMessage,
          agentRun: {
            isMultiAgent: true,
            registeredAgents: ['search', 'compare'],
            workers: [
              {
                agent: 'search',
                steps: [],
                done: true,
                success: true,
                elapsed_ms: 500,
              },
            ],
          },
        }}
      />,
    );
    expect(screen.getByText('多 Agent')).toBeInTheDocument();
    expect(screen.getByText(/已注册 2 个 Worker/)).toBeInTheDocument();
  });

  it('TC-UI-003-01 AI 消息流式输出时渲染打字机光标', () => {
    const { container } = render(
      <MessageBubble message={baseMessage} isStreaming />,
    );
    expect(container.querySelector('.typing-cursor')).toBeInTheDocument();
  });

  it('TC-UI-003-02 AI 消息非流式时不渲染打字机光标', () => {
    const { container } = render(
      <MessageBubble message={baseMessage} isStreaming={false} />,
    );
    expect(container.querySelector('.typing-cursor')).toBeNull();
  });

  it('TC-UI-003-03 用户消息不渲染打字机光标', () => {
    const { container } = render(
      <MessageBubble
        message={{ ...baseMessage, role: 'user', content: '你好' }}
        isStreaming
      />,
    );
    expect(container.querySelector('.typing-cursor')).toBeNull();
  });
});
