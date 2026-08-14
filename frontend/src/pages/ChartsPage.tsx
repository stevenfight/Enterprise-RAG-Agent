// -*- coding: utf-8 -*-
/**
 * 交互式图表中心页面
 * Phase 2 - 使用 ECharts 渲染后端 chart_tool 生成的结构化图表数据
 */

import { useState, useEffect } from 'react';
import { Card, Radio, Empty, Spin, Typography, message, Table, Segmented } from 'antd';
import { BarChartOutlined, LineChartOutlined, PieChartOutlined, AlignLeftOutlined, TableOutlined } from '@ant-design/icons';
import ChartContainer, { type ChartData } from '@/components/charts/ChartContainer';

const { Title } = Typography;

type ViewMode = 'chart' | 'table';

export default function ChartsPage() {
  const [charts, setCharts] = useState<ChartData[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeType, setActiveType] = useState<string>('all');
  const [viewMode, setViewMode] = useState<ViewMode>('chart');

  useEffect(() => {
    const fetchCharts = async () => {
      try {
        const res = await fetch('/api/charts/list');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setCharts(data.charts || []);
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
    <div style={{ padding: '24px 32px', maxWidth: 960, margin: '0 auto' }}>
      <Title level={4} style={{ color: '#3D3554', marginBottom: 20, fontWeight: 600 }}>
        <BarChartOutlined style={{ marginRight: 8, color: '#B8A9C9' }} />
        数据图表中心
      </Title>

      {/* 图表类型筛选 + 视图切换 */}
      <Card size="small" style={{ marginBottom: 20, borderRadius: 10 }}>
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
          <div style={{ marginTop: 16, color: '#bbb' }}>加载图表数据...</div>
        </div>
      ) : filtered.length === 0 ? (
        <Empty
          description="暂无图表数据"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          style={{ marginTop: 60 }}
        >
          {charts.length === 0 && (
            <div style={{ fontSize: 13, color: '#bbb', marginTop: 8 }}>
              发送图表相关查询后，生成的图表将在此展示
            </div>
          )}
        </Empty>
      ) : viewMode === 'table' ? (
        filtered.map((chart, idx) => (
          <Card
            key={idx}
            size="small"
            title={chart.title}
            style={{ marginBottom: 16, borderRadius: 12 }}
            extra={
              <span style={{ fontSize: 12, color: '#B8A9C9' }}>
                {chart.chart_type === 'bar' ? '柱状图' :
                 chart.chart_type === 'hbar' ? '横向柱状图' :
                 chart.chart_type === 'line' ? '折线图' :
                 chart.chart_type === 'table' ? '表格' : '饼图'}
              </span>
            }
          >
            <Table
              dataSource={chart.labels.map((label, i) => ({
                key: i,
                label,
                value: chart.values[i] ?? '-',
              }))}
              columns={[
                { title: chart.xlabel || '类别', dataIndex: 'label', key: 'label' },
                { title: chart.ylabel || '数值', dataIndex: 'value', key: 'value', align: 'right' as const },
              ]}
              pagination={false}
              size="small"
              bordered
              style={{ borderRadius: 8 }}
            />
          </Card>
        ))
      ) : (
        filtered.map((chart, idx) => (
          <ChartContainer key={idx} data={chart} height={360} />
        ))
      )}
    </div>
  );
}
