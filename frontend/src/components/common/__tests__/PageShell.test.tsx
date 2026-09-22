import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PageHeader, PageShell } from '../PageShell';


describe('PageShell', () => {
  it('渲染统一页面容器并保留子内容', () => {
    render(
      <PageShell className="custom-shell">
        <span>页面内容</span>
      </PageShell>,
    );

    const shell = screen.getByTestId('page-shell');
    expect(shell).toHaveClass('page-shell', 'custom-shell');
    expect(screen.getByText('页面内容')).toBeInTheDocument();
  });

  it('FWC-T03: 页面容器保留跨页面的唯一布局语义', () => {
    render(<PageShell>页面内容</PageShell>);

    expect(screen.getByTestId('page-shell')).toHaveClass('page-shell');
  });

  it('渲染统一标题、描述和图标', () => {
    render(
      <PageHeader
        title="数据图表中心"
        description="查看已生成的财务分析图表"
        icon={<span aria-label="页面图标" />}
      />,
    );

    expect(screen.getByRole('heading', { name: '数据图表中心' })).toBeInTheDocument();
    expect(screen.getByText('查看已生成的财务分析图表')).toBeInTheDocument();
    expect(screen.getByLabelText('页面图标')).toBeInTheDocument();
  });

  it('QA-R06-01: 渲染统一的产品域标签', () => {
    render(
      <PageHeader
        eyebrow="分析成果"
        title="数据图表中心"
      />,
    );

    expect(screen.getByText('分析成果')).toHaveClass('page-header-eyebrow');
  });
});
