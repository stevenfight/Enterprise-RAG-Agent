// -*- coding: utf-8 -*-
/**
 * 交互式图表中心页面
 * Phase 2 - 使用 ECharts 渲染后端 chart_tool 生成的结构化图表数据
 */

import { useState, useEffect } from 'react';
import { Card, Radio, Empty, Spin, message, Segmented } from 'antd';
import { BarChartOutlined, LineChartOutlined, PieChartOutlined, AlignLeftOutlined, TableOutlined } from '@ant-design/icons';
import ChartContainer from '@/components/charts/ChartContainer';
import type { ChartData } from '../types/chart';
import ChartMeta from '@/components/charts/ChartMeta';
import { PageHeader, PageShell } from '@/components/common/PageShell';
import { useTheme } from '@/hooks/useTheme';
import { getCharts } from '@/services/chartService';
import ChartTable from '@/components/charts/ChartTable';

type ViewMode = 'chart' | 'table';

export default function ChartsPage() {
  const { isDark } = useTheme();
  const [charts, setCharts] = useState<ChartData[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeType, setActiveType] = useState<string>('all');
  const [viewMode, setViewMode] = useState<ViewMode>('chart');

  useEffect(() => {
    const fetchCharts = async () => {
      try {
        setCharts(await getCharts());
      } catch {
        message.warning('无法加载图表列表，请确认后端服务已启动');
      } finally {
        setLoading(false);
      }
    };
    fetchCharts();
  }, []);

  const filtered = activeType === 'all'
    ? charts
    : charts.filter(c => c.chart_type === activeType);

  return (
    <PageShell>
      <PageHeader
        title="数据图表中心"
        icon={<BarChartOutlined />}
        description="浏览由财务分析生成的交互式图表与数据表格"
      />

      {/* 图表类型筛选 + 视图切换 */}
      <Card size="small" className="page-card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          <Radio.Group
            value={activeType}
            onChange={e => setActiveType(e.target.value)}
            size="small"
          >
            <Radio.Button value="all">全部 ({charts.length})</Radio.Button>
            <Radio.Button value="bar"><BarChartOutlined /> 柱状图</Radio.Button>
            <Radio.Button value="hbar"><AlignLeftOutlined /> 横向柱状图</Radio.Button>
            <Radio.Button value="line"><LineChartOutlined /> 折线图</Radio.Button>
            <Radio.Button value="pie"><PieChartOutlined /> 饼图</Radio.Button>
            <Radio.Button value="table"><TableOutlined /> 表格</Radio.Button>
          </Radio.Group>
          <Segmented
            options={[
              { label: '图表', value: 'chart', icon: <BarChartOutlined /> },
              { label: '表格', value: 'table', icon: <TableOutlined /> },
            ]}
            value={viewMode}
            onChange={v => setViewMode(v as ViewMode)}
          />
        </div>
      </Card>

      {/* 图表/表格列表 */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 80 }}>
          <Spin size="large" />
          <div style={{ marginTop: 16, color: isDark ? '#6b6b6b' : '#bbb' }}>加载图表数据...</div>
        </div>
      ) : filtered.length === 0 ? (
        <Empty
          description="暂无图表数据"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          style={{ marginTop: 60 }}
        >
          <div className="charts-empty-hint">
            {charts.length === 0 ? '发送图表相关查询后，生成的图表将在此展示' : '可以切换图表类型筛选，或选择图表 / 表格视图'}
          </div>
        </Empty>
      ) : viewMode === 'table' ? (
        <div className="charts-table-list">
        {filtered.map((chart, idx) => (
          <Card
            key={idx}
            size="small"
            title={chart.title}
            className="page-card"
            style={{ marginBottom: 16 }}
            extra={
              <span style={{ fontSize: 12, color: '#B8A9C9' }}>
                {chart.chart_type === 'bar' ? '柱状图' :
                 chart.chart_type === 'hbar' ? '横向柱状图' :
                 chart.chart_type === 'line' ? '折线图' :
                 chart.chart_type === 'table' ? '表格' : '饼图'}
              </span>
            }
          >
            <ChartMeta data={chart} />
            <ChartTable data={chart} />
          </Card>
        ))}
        </div>
      ) : (
        <div className="charts-grid">
          {filtered.map((chart, idx) => (
            <div key={idx} className="charts-grid__item">
              <ChartMeta data={chart} />
              <ChartContainer data={chart} height={360} dark={isDark} />
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
}
