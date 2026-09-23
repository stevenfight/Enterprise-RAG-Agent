// -*- coding: utf-8 -*-
/** 复用既有图表组件展示可定位的高置信视觉图表证据。 */
import { Alert, Typography } from 'antd';
import ChartContainer from '@/components/charts/ChartContainer';
import type { SourceInfo } from '@/types/chat';

const { Text } = Typography;
const NUMERIC_CONFIDENCE_THRESHOLD = 0.85;

interface VisualChartEvidenceProps {
  source: SourceInfo;
  dark?: boolean;
}

export default function VisualChartEvidence({ source, dark = false }: VisualChartEvidenceProps) {
  const chart = source.visual_chart;
  if (!chart) return null;

  const validNumbers = chart.values.every((value) => Number.isFinite(value));
  const canRender = Boolean(
    source.visual_locator
    && chart.numeric_confidence >= NUMERIC_CONFIDENCE_THRESHOLD
    && chart.labels.length > 0
    && chart.labels.length === chart.values.length
    && validNumbers,
  );

  return (
    <section style={{ marginTop: 8 }} aria-label="识别图表证据">
      <Text strong style={{ display: 'block', fontSize: 12, marginBottom: 4 }}>识别图表系列</Text>
      {canRender ? (
        <>
          <ChartContainer
            data={{
              chart_type: chart.chart_type,
              title: chart.title,
              xlabel: chart.xlabel,
              ylabel: chart.ylabel,
              labels: chart.labels,
              values: chart.values,
            }}
            height={240}
            dark={dark}
          />
          <Text type="secondary" style={{ fontSize: 12 }}>原始图表证据由本卡页图高亮定位。</Text>
        </>
      ) : (
        <>
          <Alert
            type="warning"
            showIcon
            message="图表数值置信度不足或缺少已确认定位，未展示数值图形。"
          />
          {chart.trends && chart.trends.length > 0 && (
            <ul aria-label="图表趋势候选" style={{ margin: '8px 0 0', paddingLeft: 20 }}>
              {chart.trends.map((trend) => <li key={trend}>{trend}</li>)}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
