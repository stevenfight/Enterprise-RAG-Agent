// -*- coding: utf-8 -*-
/**
 * 服务层请求统一 apiClient 测试
 * 覆盖: chartService / dagService / chatService.checkHealth
 */
import { describe, expect, it, vi } from 'vitest';

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import apiClient from '@/services/api';
import { getCharts } from '@/services/chartService';
import { getAgentPlan } from '@/services/dagService';
import { checkHealth } from '@/services/chatService';

const mockGet = apiClient.get as ReturnType<typeof vi.fn>;

describe('服务层统一 apiClient', () => {
  it('getCharts 通过 apiClient 请求 /api/charts/list', async () => {
    mockGet.mockResolvedValueOnce({ data: { charts: [{ chart_type: 'bar' }] } });
    const charts = await getCharts();
    expect(mockGet).toHaveBeenCalledWith('/api/charts/list');
    expect(charts).toHaveLength(1);
  });

  it('getAgentPlan 通过 apiClient 请求 /api/agent/plan 并携带 query 参数', async () => {
    mockGet.mockResolvedValueOnce({ data: { nodes: [], edges: [], execution_order: [], category: '', message: '' } });
    await getAgentPlan('营收对比');
    expect(mockGet).toHaveBeenCalledWith('/api/agent/plan', { params: { query: '营收对比' } });
  });

  it('checkHealth 通过 apiClient 请求 /api/health', async () => {
    mockGet.mockResolvedValueOnce({ data: { status: 'ok' } });
    const health = await checkHealth();
    expect(mockGet).toHaveBeenCalledWith('/api/health');
    expect(health.status).toBe('ok');
  });
});
