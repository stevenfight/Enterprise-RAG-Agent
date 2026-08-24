// -*- coding: utf-8 -*-
/**
 * ChartTable 通用图表表格组件测试
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ChartTable from '../ChartTable';
import type { ChartData } from '../../../types/chart';

const tableData: ChartData = {
  chart_type: 'table',
  title: '营收表',
  columns: ['公司', '营收'],
  rows: [
    ['移动', '10408'],
    ['联通', '3896'],
  ],
};

const labelValueData: ChartData = {
  chart_type: 'bar',
  title: '营收对比',
  xlabel: '公司',
  ylabel: '亿元',
  labels: ['移动', '联通'],
  values: [10408, 3896],
};

describe('ChartTable', () => {
  it('转换 table 类型数据为表格行', () => {
    render(<ChartTable data={tableData} />);

    expect(screen.getByText('公司')).toBeInTheDocument();
    expect(screen.getByText('营收')).toBeInTheDocument();
    expect(screen.getByText('10408')).toBeInTheDocument();
    expect(screen.getByText('3896')).toBeInTheDocument();
  });

  it('table 类型空单元格使用占位符', () => {
    render(<ChartTable data={{ ...tableData, rows: [['移动']] }} />);
    expect(screen.getAllByText('-').length).toBeGreaterThan(0);
  });

  it('转换 labels/values 数据为两列表格', () => {
    render(<ChartTable data={labelValueData} />);

    expect(screen.getByText('公司')).toBeInTheDocument();
    expect(screen.getByText('亿元')).toBeInTheDocument();
    expect(screen.getByText('10408')).toBeInTheDocument();
    expect(screen.getByText('3896')).toBeInTheDocument();
  });

  it('pagination=true 且行数超过阈值时启用分页', () => {
    const rows = Array.from({ length: 20 }, (_, i) => [`行${i}`, `${i}`]);
    render(<ChartTable data={{ ...tableData, rows }} pagination />);
    expect(screen.getByTitle('2')).toBeInTheDocument();
  });
});
