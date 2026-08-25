// -*- coding: utf-8 -*-
/** 研究工作台摘要条测试。 */
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ResearchContextBar from '@/components/chat/ResearchContextBar';

describe('ResearchContextBar', () => {
  it('RW-R02-01: 展示只读研究范围与分析模式', () => {
    render(<ResearchContextBar companyName="中芯国际" mode="agent" />);

    expect(screen.getByRole('region', { name: '研究摘要' })).toBeInTheDocument();
    expect(screen.getByText('研究工作台')).toBeInTheDocument();
    expect(screen.getByText('下次提问：中芯国际')).toBeInTheDocument();
    expect(screen.getByText('Agent 深度分析')).toBeInTheDocument();
  });

  it('未选择公司时明确展示全部公司范围', () => {
    render(<ResearchContextBar mode="rag" />);
    expect(screen.getByText('下次提问：全部公司')).toBeInTheDocument();
    expect(screen.getByText('RAG 问答')).toBeInTheDocument();
  });

  it('CP-R07-01: 通过唯一的可访问按钮打开研究配置', () => {
    const onOpenConfig = vi.fn();
    render(<ResearchContextBar mode="rag" onOpenConfig={onOpenConfig} />);

    fireEvent.click(screen.getByRole('button', { name: '打开研究配置' }));

    expect(onOpenConfig).toHaveBeenCalledTimes(1);
  });

  it('CP-R18: 窄屏操作可隐藏文字但保留无障碍名称', () => {
    const onOpenEvidence = vi.fn();
    const { container } = render(
      <ResearchContextBar mode="rag" onOpenConfig={vi.fn()} onOpenEvidence={onOpenEvidence} />,
    );

    expect(container.querySelector('.research-context-bar')).toBeInTheDocument();
    expect(container.querySelector('.research-context-bar__mode')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '打开研究配置' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '查看证据' })).toBeInTheDocument();
  });
});
