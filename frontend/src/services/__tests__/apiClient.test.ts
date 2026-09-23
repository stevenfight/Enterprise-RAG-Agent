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
import { getVisualArtifactImage } from '@/services/visualArtifactService';
import { getResearchTaskReport } from '@/services/researchTaskService';

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

  it('M1.7: 页图读取复用 apiClient 鉴权链并只传制品标识', async () => {
    const image = new Blob(['page-image']);
    mockGet.mockResolvedValueOnce({ data: image });

    const result = await getVisualArtifactImage({
      manifest_id: 'manifest-1',
      page_artifact_id: 'artifact-1',
      visual_region_id: 'region-1',
      normalized_bbox: [0.1, 0.2, 0.8, 0.9],
      artifact_status: 'complete',
    });

    expect(mockGet).toHaveBeenCalledWith(
      '/api/artifacts/manifests/manifest-1/pages/artifact-1/image',
      { responseType: 'blob' },
    );
    expect(result).toBe(image);
  });

  it('E-T14: 报告详情通过 apiClient 请求任务最新报告', async () => {
    mockGet.mockResolvedValueOnce({ data: { report_id: 'report-a', claims: [] } });

    const report = await getResearchTaskReport('task-a');

    expect(mockGet).toHaveBeenCalledWith('/api/research/tasks/task-a/report');
    expect(report.report_id).toBe('report-a');
  });
});
