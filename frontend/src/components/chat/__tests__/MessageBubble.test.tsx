// -*- coding: utf-8 -*-
/**
 * MessageBubble 组件单元测试
 * 覆盖: 用户/AI/系统消息渲染、Markdown 表格、来源卡片、推理链折叠区
 */
import { fireEvent, render, screen } from '@testing-library/react';
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

  it('CP-R10-01: 主回答区仅展示紧凑证据入口', () => {
    const onViewEvidence = vi.fn();
    render(
      <MessageBubble
        onViewEvidence={onViewEvidence}
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
    expect(screen.getByRole('button', { name: '查看 1 条证据' })).toBeInTheDocument();
    expect(screen.queryByText('中芯国际2024年报.pdf')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '查看 1 条证据' }));
    expect(onViewEvidence).toHaveBeenCalledWith('m1');
  });

  it('CP-R86: 证据链入口展开当前回答的来源关系', () => {
    const onViewEvidence = vi.fn();
    render(<MessageBubble
      onViewEvidence={onViewEvidence}
      message={{
        ...baseMessage,
        content: '结论内容[来源1]',
        sources: [{ index: 1, source_file: '报告.pdf', pages: [3], company_name: '中国移动', scores: {} }],
      }}
    />);

    expect(screen.queryByRole('region', { name: '回答级证据链' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '查看证据链' }));
    expect(screen.getByRole('region', { name: '回答级证据链' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /报告\.pdf/ }));
    expect(onViewEvidence).toHaveBeenCalledWith('m1', 1);
  });

  it('CP-R39: 正文来源编号可打开并定位当前回答的对应证据', () => {
    const onViewEvidence = vi.fn();
    render(
      <MessageBubble
        onViewEvidence={onViewEvidence}
        message={{
          ...baseMessage,
          content: '营业收入为 10,408 亿元。[来源2]',
          sources: [
            { index: 2, source_file: '移动2024年度报告.pdf', pages: [3], company_name: '中国移动', scores: { hybrid: 0.9 } },
          ],
        }}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '查看来源 2' }));
    expect(onViewEvidence).toHaveBeenCalledWith('m1', 2);
  });

  it('CP-R27-01: 回答只展示随消息保存的真实研究摘要', () => {
    render(
      <MessageBubble
        message={{
          ...baseMessage,
          sources: [
            { index: 1, source_file: '报告.pdf', pages: [3], company_name: '中国移动', scores: {} },
            { index: 2, source_file: '报告2.pdf', pages: [9], company_name: '中国联通', scores: {} },
          ],
          researchMeta: { mode: 'agent', companyName: '全部公司', processingTimeMs: 1200 },
        }}
      />,
    );

    expect(screen.getByText('Agent 深度分析')).toBeInTheDocument();
    expect(screen.getByText('全部公司')).toBeInTheDocument();
    expect(screen.getByText('2 条证据')).toBeInTheDocument();
    expect(screen.getByText('1.2 秒')).toBeInTheDocument();
  });

  it('CP-R29、CP-R30: 带持久化研究元数据的助手回答使用研究报告画布', () => {
    const { container } = render(
      <MessageBubble message={{
        ...baseMessage,
        researchMeta: { mode: 'rag', companyName: '全部公司', processingTimeMs: 800 },
      }} />,
    );

    expect(screen.getByRole('article', { name: '研究报告' })).toBeInTheDocument();
    expect(screen.getByText('研究交付摘要')).toBeInTheDocument();
    expect(screen.getByText('研究结论')).toBeInTheDocument();
    expect(container.querySelector('.message-bubble--research .ant-bubble-content')).toHaveStyle({ maxWidth: '100%' });
  });

  it('CP-R42: 研究报告以消息自身的真实条件展示交付摘要', () => {
    render(<MessageBubble message={{
      ...baseMessage,
      sources: [{ index: 1, source_file: '移动2024年度报告.pdf', pages: [3], company_name: '中国移动', scores: {} }],
      comparison: { available: true, metric_key: 'operating_revenue', fiscal_year: 2024, unit: '亿元', fact_ids: [], items: [] },
      researchMeta: { mode: 'rag', companyName: '全部公司', processingTimeMs: 800 },
    }} />);

    expect(screen.getByRole('region', { name: '研究交付摘要' })).toBeInTheDocument();
    expect(screen.getByText('RAG 问答')).toBeInTheDocument();
    expect(screen.getByText('全部公司')).toBeInTheDocument();
    expect(screen.getByText('1 条证据')).toBeInTheDocument();
    expect(screen.getByText('0.8 秒')).toBeInTheDocument();
    expect(screen.getByText('已核验比较')).toBeInTheDocument();
  });

  it('CP-R49: 研究报告为表格和独立来源编号提供受控阅读结构', () => {
    const onViewEvidence = vi.fn();
    const { container } = render(<MessageBubble
      onViewEvidence={onViewEvidence}
      message={{
        ...baseMessage,
        content: '| 公司 | 营收 |\n| --- | --- |\n| 中国移动 | 10,408 亿元 |\n\n[来源1]',
        sources: [{ index: 1, source_file: '移动2024年度报告.pdf', pages: [3], company_name: '中国移动', scores: {} }],
        researchMeta: { mode: 'rag', companyName: '全部公司', processingTimeMs: 800 },
      }}
    />);

    expect(container.querySelector('.research-answer-card__reading-surface')).toBeInTheDocument();
    expect(container.querySelector('.markdown-table-scroll table')).toBeInTheDocument();
    expect(container.querySelector('.markdown-citation-row')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '查看来源 1' }));
    expect(onViewEvidence).toHaveBeenCalledWith('m1', 1);
  });

  it('CP-R64: 已核验比较提供仅含真实比较条件的成果浏览入口', () => {
    const onViewCharts = vi.fn();
    render(<MessageBubble
      onViewCharts={onViewCharts}
      message={{
        ...baseMessage,
        comparison: {
          available: true,
          metric_key: 'operating_revenue',
          fiscal_year: 2024,
          unit: '亿元',
          fact_ids: [],
          items: [
            { company_name: '中国移动', value: 10408, source_file: '移动2024年度报告.pdf', pages: [3], excerpt: '营业收入 10,408 亿元' },
            { company_name: '中国联通', value: 3896, source_file: '联通2024年度报告.pdf', pages: [9], excerpt: '营业收入 3,896 亿元' },
          ],
        },
      }}
    />);

    fireEvent.click(screen.getByRole('button', { name: '查看分析成果' }));
    expect(onViewCharts).toHaveBeenCalledWith({ metric_key: 'operating_revenue', fiscal_year: 2024, unit: '亿元' });
  });

  it('CP-R52: 研究报告以紧凑交付信息展示真实元数据', () => {
    const { container } = render(<MessageBubble message={{
      ...baseMessage,
      sources: [{ index: 1, source_file: '报告.pdf', pages: [3], company_name: '中国移动', scores: {} }],
      researchMeta: { mode: 'agent', companyName: '全部公司', processingTimeMs: 1200 },
    }} />);

    expect(container.querySelector('.research-delivery-summary__brief')).toHaveTextContent('Agent 深度分析');
    expect(container.querySelector('.research-delivery-summary__brief')).toHaveTextContent('全部公司');
    expect(container.querySelector('.research-delivery-summary__items')).toBeNull();
  });

  it('CP-R57: 研究回答使用编辑式阅读层级，交付摘要收敛为报告前言', () => {
    const { container } = render(<MessageBubble message={{
      ...baseMessage,
      researchMeta: { mode: 'rag', companyName: '全部公司', processingTimeMs: 800 },
    }} />);

    expect(container.querySelector('.research-answer-card--editorial')).toBeInTheDocument();
    expect(container.querySelector('.research-delivery-summary--inline')).toBeInTheDocument();
  });

  it('CP-R54: 助手回答 hover 后使用统一操作区样式钩子', () => {
    const { container } = render(<MessageBubble message={baseMessage} />);
    fireEvent.mouseEnter(container.firstElementChild!);
    expect(container.querySelector('.message-bubble__actions')).toBeInTheDocument();
  });

  it('CP-R30: 没有研究元数据的历史助手回答保持普通阅读结构', () => {
    render(<MessageBubble message={baseMessage} />);
    expect(screen.queryByRole('article', { name: '研究报告' })).toBeNull();
  });

  it('CP-R36: 用户问题气泡使用当前主体色，不再使用紫色渐变', () => {
    const { container } = render(<MessageBubble message={{ ...baseMessage, role: 'user', content: '你好' }} />);
    expect(container.querySelector('.ant-bubble-content')).toHaveStyle({ background: 'var(--page-primary, #0f766e)' });
    expect(container.querySelector('.ant-bubble-content')?.getAttribute('style')).not.toContain('linear-gradient');
  });

  it('TC-AX-003-06 含安全分析过程的消息渲染摘要折叠区', () => {
    render(
      <MessageBubble
        message={{
          ...baseMessage,
          analysisTrace: [
            {
              stepNumber: 1,
              toolLabel: '资料检索',
              status: 'completed',
              inputSummary: '已提供检索条件',
              observationSummary: '已获取检索结果',
            },
          ],
        }}
      />,
    );
    expect(screen.getByText(/分析过程.*1 步/)).toBeInTheDocument();
  });

  it('AI 消息不渲染遗留的原始过程字段', () => {
    render(
      <MessageBubble
        message={{
          ...baseMessage,
          reasoningChain: [{ thought: '内部推理' }],
          agentRun: { workers: [{ agent: 'InternalAgent', steps: [{ content: '原始步骤' }] }] },
        } as Message}
      />,
    );
    expect(screen.queryByText('内部推理')).toBeNull();
    expect(screen.queryByText('原始步骤')).toBeNull();
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
