// -*- coding: utf-8 -*-
/** 研究工作台摘要条测试。 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ResearchContextBar from '@/components/chat/ResearchContextBar';

describe('ResearchContextBar', () => {
  it('RW-R02-01: 展示只读研究范围', () => {
    render(<ResearchContextBar companyName="中芯国际" mode="agent" />);

    expect(screen.getByRole('region', { name: '研究摘要' })).toBeInTheDocument();
    expect(screen.getByText('研究工作台')).toBeInTheDocument();
    expect(screen.getByText('下次提问：中芯国际')).toBeInTheDocument();
  });

  it('未选择公司时明确展示全部公司范围', () => {
    render(<ResearchContextBar mode="rag" />);
    expect(screen.getByText('下次提问：全部公司')).toBeInTheDocument();
  });

  it('CP-R48: 顶栏可承载右侧研究配置，范围摘要保持只读', () => {
    render(
      <ResearchContextBar
        companyName="中芯国际"
        mode="rag"
        configuration={<section aria-label="研究配置"><button type="button">高级选项</button></section>}
      />,
    );

    expect(screen.getByText('下次提问：中芯国际')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '调整研究范围和模式' })).not.toBeInTheDocument();
    expect(screen.getByRole('region', { name: '研究配置' })).toBeInTheDocument();
  });

  it('CP-R53: 顶栏直配存在时不重复渲染只读模式标签', () => {
    const { container } = render(
      <ResearchContextBar
        mode="rag"
        configuration={<section aria-label="研究配置">研究配置</section>}
        onOpenEvidence={vi.fn()}
      />,
    );

    expect(container.querySelector('.research-context-bar__mode')).toBeNull();
    expect(screen.getByRole('region', { name: '研究配置' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '查看证据' })).toBeInTheDocument();
  });

  it('CP-R18: 窄屏操作可隐藏文字但保留无障碍名称', () => {
    const onOpenEvidence = vi.fn();
    const { container } = render(
      <ResearchContextBar mode="rag" onOpenEvidence={onOpenEvidence} />,
    );

    expect(container.querySelector('.research-context-bar')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '查看证据' })).toBeInTheDocument();
  });
});
