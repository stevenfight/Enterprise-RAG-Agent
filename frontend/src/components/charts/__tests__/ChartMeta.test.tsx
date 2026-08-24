import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ChartMeta from '../ChartMeta';

describe('ChartMeta', () => {
  it('显示图表维度、来源和生成时间', () => {
    render(
      <ChartMeta
        data={{
          xlabel: '公司',
          ylabel: '营收(亿元)',
          file_name: '营收对比.json',
          generated_at: '2026-08-22T01:59:53.433967',
        }}
      />,
    );

    expect(screen.getByRole('group', { name: '图表信息' })).toBeInTheDocument();
    expect(screen.getByText('横轴：公司')).toBeInTheDocument();
    expect(screen.getByText('纵轴：营收(亿元)')).toBeInTheDocument();
    expect(screen.getByText('来源：营收对比.json')).toBeInTheDocument();
    expect(screen.getByText('生成于：2026-08-22 01:59:53')).toBeInTheDocument();
  });

  it('没有元信息时不渲染', () => {
    const { container } = render(<ChartMeta data={{}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
