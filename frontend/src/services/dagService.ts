// -*- coding: utf-8 -*-
/**
 * DAG 任务规划 API 封装
 */

import apiClient from './api';
import type { DagNodeType } from '../constants/dag';

export interface PlanData {
  nodes: Array<{
    id: string;
    label: string;
    type: DagNodeType;
    description: string;
    tool_name: string;
    status: string;
  }>;
  edges: Array<{ source: string; target: string }>;
  execution_order: string[][];
  category: string;
  message: string;
}

export async function getAgentPlan(query: string): Promise<PlanData> {
  const res = await apiClient.get<PlanData>('/api/agent/plan', { params: { query } });
  return res.data;
}
