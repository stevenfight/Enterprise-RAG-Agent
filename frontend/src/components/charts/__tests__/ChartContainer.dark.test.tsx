// -*- coding: utf-8 -*-
/**
 * TDD 测试: 图表暗色适配 (模块 G)
 * 对应文档: openspec/changes/welcome-quick-charts-optimize/specs/tdd-welcome-quick-charts.md
 */
import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ChartContainer from '@/components/charts/ChartContainer';
import type { ChartData } from '../../../types/chart';

/** Mock echarts-for-react: 捕获 option 引用（保留函数类型属性） */
let capturedOption: Record<string, unknown> | null = null;

vi.mock('echarts-for-react/esm/core', () => ({
  default: ({ option, style }: Record<string, unknown>) => {
    capturedOption = option as Record<string, unknown>;
    return (
      <div data-testid="echarts" style={style as Record<string, string>}>
        mock-chart
      </div>
    );
  },
}));

function getOption(): Record<string, unknown> {
  return capturedOption || {};
}

const barData: ChartData = {
  chart_type: 'bar',
  title: '2024年营收对比',
  xlabel: '公司',
  ylabel: '亿元',
  labels: ['移动', '联通', '电信'],
  values: [10408, 3896, 5236],
};

/** 从渲染结果中获取外层容器 div 的内联背景色 */
function getCardBackground(container: HTMLElement): string | undefined {
  const el = container.querySelector('[data-testid="chart-card"]') as HTMLElement | null;
  return el?.style.background || undefined;
}

describe('ChartContainer 暗色适配 (模块 G)', () => {
  it('GC-01: 默认亮色标题颜色不变', () => {
    render(<ChartContainer data={barData} />);
    const option = getOption();
    const title = (option.title as Record<string, unknown>).textStyle as Record<string, unknown>;
    expect(title.color).toBe('#3D3554');
  });

  it('GC-02: dark=true 标题颜色切换', () => {
    render(<ChartContainer data={barData} dark />);
    const option = getOption();
    const title = (option.title as Record<string, unknown>).textStyle as Record<string, unknown>;
    expect(title.color).toBe('#e8e8e8');
  });

  it('GC-03: dark=true 坐标轴文字颜色切换', () => {
    render(<ChartContainer data={barData} dark />);
    const option = getOption();
    const axis = option.xAxis as Record<string, unknown>;
    const axisLabel = axis.axisLabel as Record<string, unknown>;
    expect(axisLabel.color).toBe('#8c8c8c');
  });

  it('GC-04: dark=true 容器卡片为暗色背景', () => {
    const { container } = render(<ChartContainer data={barData} dark />);
    expect(getCardBackground(container)).toBe('rgb(31, 31, 31)');
  });

  it('GC-05: 亮色容器卡片背景不变', () => {
    const { container } = render(<ChartContainer data={barData} />);
    expect(getCardBackground(container)).toBe('rgb(255, 255, 255)');
  });
});
