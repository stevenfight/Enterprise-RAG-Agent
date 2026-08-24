// -*- coding: utf-8 -*-
/**
 * 图表中心 API 封装
 */

import apiClient from './api';
import type { ChartData } from '../types/chart';

interface ChartsResponse {
  charts?: ChartData[];
}

export async function getCharts(): Promise<ChartData[]> {
  const res = await apiClient.get<ChartsResponse>('/api/charts/list');
  return res.data.charts || [];
}
