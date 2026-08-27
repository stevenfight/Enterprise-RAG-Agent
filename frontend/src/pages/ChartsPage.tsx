// -*- coding: utf-8 -*-
/**
 * 交互式图表中心页面
 * Phase 2 - 使用 ECharts 渲染后端 chart_tool 生成的结构化图表数据
 */

import { useState, useEffect } from 'react';
import { Card, Radio, Empty, Spin, message, Segmented, Statistic } from 'antd';
import { BarChartOutlined, LineChartOutlined, PieChartOutlined, AlignLeftOutlined, TableOutlined } from '@ant-design/icons';
import ChartContainer from '@/components/charts/ChartContainer';
import type { ChartData } from '../types/chart';
import ChartMeta from '@/components/charts/ChartMeta';
import { PageHeader, PageShell } from '@/components/common/PageShell';
import { useTheme } from '@/hooks/useTheme';
import { getCharts } from '@/services/chartService';
import ChartTable from '@/components/charts/ChartTable';

type ViewMode = 'chart' | 'table';

const CHART_TYPE_LABELS: Record<string, string> = {
  bar: '柱状图',
  hbar: '横向柱状图',
  line: '折线图',
  pie: '饼图',
  table: '表格',
};

const RESEARCH_METRIC_BROWSE_CONFIG: Record<string, { label: string; titleTerms: string[] }> = {
  operating_revenue: { label: '营业收入', titleTerms: ['营业收入', '营收'] },
};

export default function ChartsPage() {
  const { isDark } = useTheme();
  const [charts, setCharts] = useState<ChartData[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeType, setActiveType] = useState<string>('all');
  const [viewMode, setViewMode] = useState<ViewMode>('chart');
  const searchParams = new URLSearchParams(window.location.search);
  const metricKey = searchParams.get('metric') ?? '';
  const fiscalYear = searchParams.get('year') ?? '';
  const unit = searchParams.get('unit') ?? '';
  const researchMetric = RESEARCH_METRIC_BROWSE_CONFIG[metricKey];
  const researchCriteria = researchMetric && fiscalYear && unit
    ? { label: researchMetric.label, fiscalYear, unit }
    : undefined;

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

  const researchCandidates = researchCriteria
    ? charts.filter((chart) => researchMetric.titleTerms.some((term) => chart.title.includes(term)))
    : [];
  const browseCharts = researchCriteria && researchCandidates.length > 0 ? researchCandidates : charts;
  const filtered = activeType === 'all'
    ? browseCharts
    : browseCharts.filter(c => c.chart_type === activeType);
  const chartTypeCounts = charts.reduce<Record<string, number>>((counts, chart) => {
    counts[chart.chart_type] = (counts[chart.chart_type] ?? 0) + 1;
    return counts;
  }, {});

  return (
    <PageShell>
      <PageHeader
        eyebrow="研究成果"
        title="分析成果"
        icon={<BarChartOutlined />}
        description="浏览由财务分析生成的图表与数据表格；仅展示当前可用成果"
      />

      <section className="charts-workbench" aria-label="分析成果工作区">
      {researchCriteria && (
        <section className="charts-research-entry" aria-label="研究成果浏览条件">
          <div>
            <span>来自已核验比较</span>
            <strong>{researchCriteria.fiscalYear} · {researchCriteria.label}（{researchCriteria.unit}）</strong>
          </div>
          <p>{researchCandidates.length > 0
            ? `已按图表标题中的指标关键词筛选 ${researchCandidates.length} 项候选成果。`
            : '未在图表标题中找到可核验的指标候选，以下展示全部可用成果。'}</p>
        </section>
      )}
      {!loading && (
        <section className="status-overview-grid status-overview-grid--cols-5 research-output-strip" aria-label="成果摘要">
          <Card className="status-overview-card status-overview-card--compact">
            <Statistic title="成果总数" value={charts.length} />
          </Card>
          {Object.entries(chartTypeCounts).map(([type, count]) => (
            <Card key={type} className="status-overview-card status-overview-card--compact">
              <Statistic title={CHART_TYPE_LABELS[type] ?? '其他类型'} value={count} suffix="项" />
            </Card>
          ))}
        </section>
      )}

      {/* 图表类型筛选 + 视图切换 */}
      <Card size="small" className="page-card page-toolbar" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          <Radio.Group
            value={activeType}
            onChange={e => setActiveType(e.target.value)}
            size="small"
          >
            <Radio.Button value="all">全部 ({browseCharts.length})</Radio.Button>
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
        <div className="page-state" style={{ textAlign: 'center', padding: 80 }}>
          <Spin size="large" />
          <div style={{ marginTop: 16, color: 'var(--page-text-secondary)' }}>加载图表数据...</div>
        </div>
      ) : filtered.length === 0 ? (
        <div className="page-state">
          <Empty
            description="暂无图表数据"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            <div className="charts-empty-hint">
              {charts.length === 0 ? '发送图表相关查询后，生成的图表将在此展示' : '可以切换图表类型筛选，或选择图表 / 表格视图'}
            </div>
          </Empty>
        </div>
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
              <span style={{ fontSize: 12, color: 'var(--page-text-secondary)' }}>
                {CHART_TYPE_LABELS[chart.chart_type] ?? '其他类型'}
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
      </section>
    </PageShell>
  );
}
