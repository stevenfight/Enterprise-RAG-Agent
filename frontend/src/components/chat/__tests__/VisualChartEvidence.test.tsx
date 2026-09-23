// -*- coding: utf-8 -*-
/** M4.3 识别图表系列与原始图表证据展示测试。 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { SourceInfo } from '@/types/chat';
import VisualChartEvidence from '@/components/chat/VisualChartEvidence';

vi.mock('@/components/charts/ChartContainer', () => ({
  default: ({ data }: { data: { title: string } }) => <div data-testid="visual-chart-container">{data.title}</div>,
}));

const locator = {
  manifest_id: 'manifest-1', page_artifact_id: 'page-1', visual_region_id: 'region-1',
  normalized_bbox: [0.1, 0.2, 0.8, 0.9] as [number, number, number, number], artifact_status: 'complete' as const,
};

describe('VisualChartEvidence', () => {
  it('M4.3: 高置信且可定位的识别图表复用 ChartContainer 展示系列', () => {
    const source: SourceInfo = {
      index: 1, source_file: '图表年报.pdf', pages: [12], company_name: '示例公司', scores: {}, visual_locator: locator,
      visual_chart: {
        title: '营业收入趋势', chart_type: 'line', labels: ['2023', '2024'], values: [100, 120],
        ylabel: '亿元', numeric_confidence: 0.93,
      },
    };

    render(<VisualChartEvidence source={source} />);

    expect(screen.getByText('识别图表系列')).toBeInTheDocument();
    expect(screen.getByTestId('visual-chart-container')).toHaveTextContent('营业收入趋势');
    expect(screen.getByText('原始图表证据由本卡页图高亮定位。')).toBeInTheDocument();
  });

  it('M4.3: 低置信或不可定位的图表不展示数值图形，只提示趋势或完整性问题', () => {
    const source: SourceInfo = {
      index: 2, source_file: '图表年报.pdf', pages: [13], company_name: '示例公司', scores: {},
      visual_chart: {
        title: '毛利率趋势', chart_type: 'line', labels: ['2023', '2024'], values: [30, 32],
        numeric_confidence: 0.42, trends: ['毛利率上升'],
      },
    };

    render(<VisualChartEvidence source={source} />);

    expect(screen.queryByTestId('visual-chart-container')).toBeNull();
    expect(screen.getByRole('alert')).toHaveTextContent('图表数值置信度不足');
    expect(screen.getByText('毛利率上升')).toBeInTheDocument();
  });
});
