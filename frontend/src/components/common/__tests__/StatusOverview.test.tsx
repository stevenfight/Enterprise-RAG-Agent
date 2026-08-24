// -*- coding: utf-8 -*-
/**
 * StatusOverview 通用状态概览组件测试
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import StatusOverview, { type StatusOverviewItem } from '../StatusOverview';
import { FileTextOutlined } from '@ant-design/icons';

const items: StatusOverviewItem[] = [
  { key: 'a', label: '总数', value: '10', detail: '示例明细', state: 'neutral', icon: <FileTextOutlined /> },
  { key: 'b', label: '已完成', value: '8', detail: '全部完成', state: 'success', icon: <FileTextOutlined /> },
  { key: 'c', label: '待处理', value: '2', detail: '等待处理', state: 'warning', icon: <FileTextOutlined /> },
  { key: 'd', label: '故障', value: '1', detail: '不可用', state: 'error', icon: <FileTextOutlined /> },
];

describe('StatusOverview', () => {
  it('渲染所有状态卡片和无障碍标签', () => {
    render(<StatusOverview items={items} ariaLabel="测试概览" />);

    expect(screen.getByRole('region', { name: '测试概览' })).toBeInTheDocument();
    expect(screen.getByText('总数')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText('示例明细')).toBeInTheDocument();
  });

  it('应用 neutral/success/warning/error 状态样式类', () => {
    render(<StatusOverview items={items} ariaLabel="测试概览" />);

    expect(document.querySelectorAll('.status-overview-card--neutral')).toHaveLength(1);
    expect(document.querySelectorAll('.status-overview-card--success')).toHaveLength(1);
    expect(document.querySelectorAll('.status-overview-card--warning')).toHaveLength(1);
    expect(document.querySelectorAll('.status-overview-card--error')).toHaveLength(1);
  });

  it('columns=5 时应用 cols-5 网格类', () => {
    render(<StatusOverview items={items} ariaLabel="测试概览" columns={5} />);
    expect(document.querySelector('.status-overview-grid--cols-5')).toBeInTheDocument();
  });

  it('compact 模式应用紧凑卡片类', () => {
    render(<StatusOverview items={items} ariaLabel="测试概览" compact />);
    expect(document.querySelector('.status-overview-card--compact')).toBeInTheDocument();
  });
});
