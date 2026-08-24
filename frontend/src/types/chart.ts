// -*- coding: utf-8 -*-
/**
 * 图表数据类型定义
 */

export interface ChartData {
  chart_type: string;
  title: string;
  xlabel?: string;
  ylabel?: string;
  labels?: string[];
  values?: number[];
  image_url?: string;
  file_name?: string;
  generated_at?: string;
  columns?: string[];
  rows?: string[][];
}
