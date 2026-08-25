// -*- coding: utf-8 -*-
/** 分析成果页的真实数据摘要回归测试。 */
import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const getCharts = vi.hoisted(() => vi.fn());

vi.mock('@/hooks/useTheme', () => ({ useTheme: () => ({ isDark: false }) }));
vi.mock('@/services/chartService', () => ({ getCharts }));
vi.mock('@/components/charts/ChartContainer', () => ({ default: () => <div>图表画布</div> }));
vi.mock('@/components/charts/ChartMeta', () => ({ default: () => null }));

import ChartsPage from '@/pages/ChartsPage';

describe('ChartsPage', () => {
  it('AP-R01-01: 仅根据现有图表数据展示成果总数和实际类型分布', async () => {
    getCharts.mockResolvedValue([
      { chart_type: 'bar', title: '营收对比' },
      { chart_type: 'line', title: '趋势分析' },
      { chart_type: 'bar', title: '利润对比' },
    ]);

    render(<ChartsPage />);

    expect(await screen.findByText('3')).toBeInTheDocument();
    const summary = screen.getByRole('region', { name: '成果摘要' });
    expect(within(summary).getByText('柱状图').closest('.ant-card')).toHaveTextContent('2项');
    expect(within(summary).getByText('折线图').closest('.ant-card')).toHaveTextContent('1项');
    expect(screen.queryByText(/公司|年度/)).toBeNull();
  });

  it('QA-R06-02: 筛选操作位于统一研究操作区', async () => {
    getCharts.mockResolvedValue([]);
    render(<ChartsPage />);

    await screen.findByText('暂无图表数据');
    expect(screen.getByRole('radio', { name: /全部/ }).closest('.page-toolbar')).toBeInTheDocument();
  });
});
