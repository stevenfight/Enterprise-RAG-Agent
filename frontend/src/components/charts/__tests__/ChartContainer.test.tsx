// -*- coding: utf-8 -*-
/**
 * ChartContainer 组件单元测试
 * 覆盖: 颜色不被覆盖 / 类型切换 / 空状态 / 边缘情况
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ChartContainer from '@/components/charts/ChartContainer';
import type { ChartData } from '@/components/charts/ChartContainer';

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

/** 获取最近一次渲染的 ECharts option */
function getOption(): Record<string, unknown> {
  return capturedOption || {};
}

/** 柱状图示例数据 */
const barData: ChartData = {
  chart_type: 'bar',
  title: '2024年营收对比',
  xlabel: '公司',
  ylabel: '亿元',
  labels: ['移动', '联通', '电信'],
  values: [10408, 3896, 5236],
};

/** 折线图示例数据 */
const lineData: ChartData = {
  ...barData,
  chart_type: 'line',
};

/** 饼图示例数据 */
const pieData: ChartData = {
  ...barData,
  chart_type: 'pie',
};

/** 无图片URL的图表数据 */
const noImageData: ChartData = {
  ...barData,
  image_url: undefined,
};

describe('ChartContainer', () => {
  describe('基础渲染', () => {
    it('应该渲染 ECharts 容器', () => {
      render(<ChartContainer data={barData} />);
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });

    it('应该传递正确的 height', () => {
      render(<ChartContainer data={barData} height={500} />);
      const el = screen.getByTestId('echarts');
      expect(el.style.height).toBe('500px');
    });

    it('默认 height 为 360px', () => {
      render(<ChartContainer data={barData} />);
      const el = screen.getByTestId('echarts');
      expect(el.style.height).toBe('360px');
    });
  });

  describe('图表类型切换', () => {
    it('柱状图 series type 为 bar', () => {
      render(<ChartContainer data={barData} />);
      const option = getOption();
      expect(option.series).toBeDefined();
      const series = (option.series as Record<string, unknown>[])[0];
      expect(series.type).toBe('bar');
    });

    it('折线图 series type 为 line', () => {
      render(<ChartContainer data={lineData} />);
      const option = getOption();
      const series = (option.series as Record<string, unknown>[])[0];
      expect(series.type).toBe('line');
    });

    it('饼图 series type 为 pie', () => {
      render(<ChartContainer data={pieData} />);
      const option = getOption();
      const series = (option.series as Record<string, unknown>[])[0];
      expect(series.type).toBe('pie');
    });
  });

  describe('颜色覆盖修复验证', () => {
    it('series 顶层不应该有 itemStyle.color 覆盖data数组中的颜色', () => {
      render(<ChartContainer data={barData} />);
      const option = getOption();
      const series = (option.series as Record<string, unknown>[])[0];
      expect((series.itemStyle as Record<string, unknown> | undefined)?.color).toBeUndefined();
    });

    it('每个 data 条目应该有独立的 itemStyle.color', () => {
      render(<ChartContainer data={barData} />);
      const option = getOption();
      const series = (option.series as Record<string, unknown>[])[0];
      const dataArr = series.data as Array<Record<string, unknown>>;
      expect(dataArr).toHaveLength(3);
      dataArr.forEach(item => {
        expect(item.itemStyle).toBeDefined();
        expect((item.itemStyle as Record<string, unknown>).color).toBeDefined();
      });
    });

    it('不同数据点的颜色应该不同', () => {
      render(<ChartContainer data={barData} />);
      const option = getOption();
      const series = (option.series as Record<string, unknown>[])[0];
      const dataArr = series.data as Array<Record<string, unknown>>;
      const colors = new Set(
        dataArr.map(d => (d.itemStyle as Record<string, unknown>).color)
      );
      expect(colors.size).toBeGreaterThanOrEqual(2);
    });

    it('折线图的 lineStyle 颜色应该在 series 顶层设置', () => {
      render(<ChartContainer data={lineData} />);
      const option = getOption();
      const series = (option.series as Record<string, unknown>[])[0];
      expect(series.lineStyle).toBeDefined();
      expect((series.lineStyle as Record<string, unknown>).color).toBe('#B8A9C9');
      const dataArr = series.data as Array<Record<string, unknown>>;
      dataArr.forEach(item => {
        expect((item.itemStyle as Record<string, unknown>).color).toBeDefined();
      });
    });
  });

  describe('工具提示', () => {
    it('柱状图 tooltip trigger 为 axis', () => {
      render(<ChartContainer data={barData} />);
      const option = getOption();
      expect((option.tooltip as Record<string, unknown>).trigger).toBe('axis');
    });

    it('饼图 tooltip trigger 为 item', () => {
      render(<ChartContainer data={pieData} />);
      const option = getOption();
      expect((option.tooltip as Record<string, unknown>).trigger).toBe('item');
    });
  });

  describe('图片 URL 链接', () => {
    it('有 image_url 时显示查看图片版本链接', () => {
      render(<ChartContainer data={{ ...barData, image_url: '/api/charts/test.png' }} />);
      const link = screen.getByText('查看图片版本');
      expect(link).toBeInTheDocument();
      expect(link.getAttribute('href')).toBe('/api/charts/test.png');
    });

    it('无 image_url 时不显示图片链接', () => {
      render(<ChartContainer data={noImageData} />);
      const link = screen.queryByText('查看图片版本');
      expect(link).toBeNull();
    });
  });

  describe('标题和图例', () => {
    it('应该设置正确的标题', () => {
      render(<ChartContainer data={barData} />);
      const option = getOption();
      expect((option.title as Record<string, unknown>).text).toBe('2024年营收对比');
    });

    it('非饼图应该显示图例', () => {
      render(<ChartContainer data={barData} />);
      const option = getOption();
      expect((option.legend as Record<string, unknown>).show).toBe(true);
    });

    it('饼图不应该显示图例', () => {
      render(<ChartContainer data={pieData} />);
      const option = getOption();
      expect((option.legend as Record<string, unknown>).show).toBe(false);
    });
  });

  describe('边缘情况: 空数据与长度不一致', () => {
    it('空 labels 和空 values 时不崩溃并显示暂无数据', () => {
      const emptyData: ChartData = {
        chart_type: 'bar',
        title: '空数据测试',
        labels: [],
        values: [],
      };
      render(<ChartContainer data={emptyData} />);
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });

    it('labels 和 values 长度不一致时截断到最小长度', () => {
      const mismatchData: ChartData = {
        chart_type: 'bar',
        title: '长度不一致',
        labels: ['A', 'B', 'C', 'D'],
        values: [100, 200],
      };
      render(<ChartContainer data={mismatchData} />);
      const option = getOption();
      const series = (option.series as Record<string, unknown>[])[0];
      const dataArr = series.data as Array<Record<string, unknown>>;
      expect(dataArr).toHaveLength(2);
    });

    it('空数据时 option 应包含 graphic 暂无数据提示', () => {
      const emptyData: ChartData = {
        chart_type: 'bar',
        title: '',
        labels: [],
        values: [],
      };
      render(<ChartContainer data={emptyData} />);
      const option = getOption();
      expect((option.title as Record<string, unknown>).text).toBe('暂无数据');
      expect((option.graphic as Record<string, unknown>)?.type).toBe('text');
    });
  });

  describe('边缘情况: tooltip formatter', () => {
    it('axis trigger 时 formatter 是函数且正确处理数组参数', () => {
      render(<ChartContainer data={barData} />);
      const option = getOption();
      const formatter = (option.tooltip as Record<string, unknown>).formatter as Function;

      // 验证 formatter 存在且是函数
      expect(typeof formatter).toBe('function');

      // 调用 formatter 验证 axis trigger (数组)
      const result = formatter([{ name: '移动', value: 10408 }]);
      expect(result).toContain('移动');
      expect(result).toContain('10408');
    });

    it('item trigger 时 formatter 正确处理单对象参数(饼图含百分比)', () => {
      render(<ChartContainer data={pieData} />);
      const option = getOption();
      const formatter = (option.tooltip as Record<string, unknown>).formatter as Function;

      expect(typeof formatter).toBe('function');

      // 调用 formatter 验证 item trigger (单对象)
      const result = formatter({ name: '移动', value: 10408, percent: 55 });
      expect(result).toContain('移动');
      expect(result).toContain('10408');
      expect(result).toContain('55%');
    });
  });
});
