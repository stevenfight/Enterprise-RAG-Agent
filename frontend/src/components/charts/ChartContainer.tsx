// -*- coding: utf-8 -*-
/**
 * ECharts 交互式图表容器
 * Phase 2 - 支持柱状图/折线图/饼图切换、图例交互、Tooltip
 *
 * 后端 chart_tool 生成 PNG 的同时输出 JSON 结构化数据，
 * 本组件接收 JSON 数据后用 ECharts 渲染交互式图表。
 */

import { useMemo, useEffect } from 'react';
import ReactEChartsCore from 'echarts-for-react/esm/core';
import * as echarts from 'echarts/core';
import { BarChart, LineChart, PieChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  TitleComponent,
  LegendComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

// 按需注册 ECharts 组件（减小打包体积）
echarts.use([
  BarChart, LineChart, PieChart,
  GridComponent, TooltipComponent, TitleComponent, LegendComponent,
  CanvasRenderer,
]);

export interface ChartData {
  chart_type: string;
  title: string;
  xlabel?: string;
  ylabel?: string;
  labels: string[];
  values: number[];
  image_url?: string;
}

interface ChartContainerProps {
  data: ChartData;
  height?: number;
}

/** 图表主题色 */
const CHART_COLORS = ['#B8A9C9', '#98D8C8', '#A8D8EA', '#F4B8C8', '#FAD4B8', '#C8B8D8'];

// ========== 日志工具 ==========

let _mountId = 0;

function logger(fnName: string, msg: string, extra?: Record<string, unknown>) {
  const payload = extra ? ` ${JSON.stringify(extra)}` : '';
  console.debug(`[ChartContainer][${fnName}] ${msg}${payload}`);
}

// ========== 组件 ==========

export default function ChartContainer({ data, height = 360 }: ChartContainerProps) {
  const mountId = useMemo(() => { _mountId += 1; return _mountId; }, []);

  // ---- 挂载 / 数据变更日志 ----
  useEffect(() => {
    logger(`mount#${mountId}`, `chart_type=${data.chart_type} title="${data.title}" labels=${data.labels.length} values=${data.values.length} height=${height}`);
  }, [data, height, mountId]);

  // ---- option 计算 ----
  const option = useMemo(() => {
    const { chart_type, title, xlabel, ylabel, labels, values } = data;

    // 防御: 空数据或 labels/values 长度不一致时，截断到最小长度
    const safeLength = Math.min(labels.length, values.length);

    logger('option', `labels=${labels.length} values=${values.length} safeLength=${safeLength} chart_type=${chart_type}`);

    if (safeLength === 0) {
      logger('option', '空数据，返回暂无数据占位option', { title: title || '暂无数据' });
      return {
        title: {
          text: title || '暂无数据',
          left: 'center',
          textStyle: { fontSize: 15, color: '#3D3554', fontWeight: 600 },
        },
        graphic: {
          type: 'text',
          left: 'center',
          top: 'middle',
          style: { text: '暂无可用数据', fontSize: 14, fill: '#bbb' },
        },
      };
    }

    if (labels.length !== values.length) {
      logger('option', `labels/values长度不一致，截断到 ${safeLength}`, {
        labelsLen: labels.length,
        valuesLen: values.length,
      });
    }

    const safeLabels = labels.slice(0, safeLength);
    const safeValues = values.slice(0, safeLength);

    const baseOption: Record<string, unknown> = {
      title: {
        text: title,
        left: 'center',
        textStyle: { fontSize: 15, color: '#3D3554', fontWeight: 600 },
      },
      tooltip: {
        trigger: chart_type === 'pie' ? 'item' : 'axis',
        formatter: (params: unknown) => {
          // axis trigger 时 params 是数组，item trigger 时是单个对象
          if (Array.isArray(params)) {
            const first = params[0] as Record<string, unknown>;
            const text = `${first.name}: ${first.value} ${ylabel || ''}`;
            logger('tooltip', `axis模式, name=${first.name} value=${first.value}`, { result: text });
            return text;
          }
          const p = params as Record<string, unknown>;
          if (chart_type === 'pie') {
            const text = `${p.name}: ${p.value} ${ylabel || ''} (${p.percent}%)`;
            logger('tooltip', `item模式(pie), name=${p.name} value=${p.value} percent=${p.percent}`, { result: text });
            return text;
          }
          const text = `${p.name}: ${p.value} ${ylabel || ''}`;
          logger('tooltip', `item模式, name=${p.name} value=${p.value}`, { result: text });
          return text;
        },
      },
      legend: {
        show: chart_type !== 'pie',
        bottom: 0,
        textStyle: { fontSize: 12, color: '#888' },
      },
      grid: {
        left: 50,
        right: 30,
        top: 50,
        bottom: 40,
      },
    };

    if (chart_type === 'pie') {
      logger('option', `渲染饼图, dataPoints=${safeLength}`);
      return {
        ...baseOption,
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          center: ['50%', '55%'],
          data: safeLabels.map((name, i) => ({
            name,
            value: safeValues[i],
          })),
          itemStyle: {
            color: (params: { dataIndex: number }) =>
              CHART_COLORS[params.dataIndex % CHART_COLORS.length],
            borderRadius: 4,
            borderColor: '#fff',
            borderWidth: 2,
          },
          label: {
            formatter: '{b}: {d}%',
            fontSize: 12,
          },
          emphasis: {
            label: { fontSize: 16, fontWeight: 'bold' },
            itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.1)' },
          },
        }],
      };
    }

    // hbar: 横向柱状图，x轴和y轴互换
    if (chart_type === 'hbar') {
      logger('option', `渲染横向柱状图, dataPoints=${safeLength} label种数=${new Set(safeLabels).size}`);
      return {
        ...baseOption,
        grid: {
          left: 80,
          right: 30,
          top: 50,
          bottom: 40,
        },
        xAxis: {
          type: 'value',
          name: ylabel || '',
          axisLabel: { fontSize: 12, color: '#888' },
        },
        yAxis: {
          type: 'category',
          data: safeLabels,
          name: xlabel || '',
          axisLabel: { fontSize: 12, color: '#888' },
          axisTick: { alignWithLabel: true },
        },
        series: [{
          type: 'bar',
          data: safeValues.map((v, i) => ({
            value: v,
            itemStyle: { color: CHART_COLORS[i % CHART_COLORS.length], borderRadius: [0, 6, 6, 0] },
          })),
          barWidth: '50%',
          label: { show: true, position: 'right', fontSize: 11, color: '#888', formatter: '{c}' },
        }],
      };
    }

    logger('option', `渲染${chart_type}图, dataPoints=${safeLength} label种数=${new Set(safeLabels).size}`);
    return {
      ...baseOption,
      xAxis: {
        type: 'category',
        data: safeLabels,
        name: xlabel || '',
        axisLabel: { fontSize: 12, color: '#888' },
        axisTick: { alignWithLabel: true },
      },
      yAxis: {
        type: 'value',
        name: ylabel || '',
        axisLabel: { fontSize: 12, color: '#888' },
      },
      series: [chart_type === 'line' ? {
        type: 'line',
        data: safeValues.map((v, i) => ({
          value: v,
          itemStyle: { color: CHART_COLORS[i % CHART_COLORS.length], borderRadius: 0 },
        })),
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { width: 3, color: '#B8A9C9' },
        label: { show: true, position: 'top', fontSize: 11, color: '#888', formatter: '{c}' },
      } : {
        type: 'bar',
        data: safeValues.map((v, i) => ({
          value: v,
          itemStyle: { color: CHART_COLORS[i % CHART_COLORS.length], borderRadius: [6, 6, 0, 0] },
        })),
        barWidth: '50%',
        label: { show: true, position: 'top', fontSize: 11, color: '#888', formatter: '{c}' },
      }],
    };
  }, [data]);

  // ---- 渲染 ----

  return (
    <div style={{
      borderRadius: 12,
      padding: '16px 12px 8px',
      background: '#ffffff',
      border: '1px solid #e8e3ef',
      boxShadow: '0 2px 8px rgba(184, 169, 201, 0.1)',
      marginBottom: 16,
    }}>
      <ReactEChartsCore
        echarts={echarts}
        option={option}
        style={{ height, width: '100%' }}
        notMerge
        lazyUpdate
        onChartReady={() => {
          logger(`mount#${mountId}`, 'ECharts 实例就绪');
        }}
      />
      {data.image_url && (
        <div style={{ textAlign: 'center', marginTop: 8 }}>
          <a
            href={data.image_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 11, color: '#B8A9C9' }}
          >
            查看图片版本
          </a>
        </div>
      )}
    </div>
  );
}
