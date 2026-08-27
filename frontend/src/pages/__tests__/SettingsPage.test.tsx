// -*- coding: utf-8 -*-
/** 系统状态页分组与只读边界回归测试。 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const getSystemStatus = vi.hoisted(() => vi.fn());
vi.mock('@/services/systemService', () => ({ getSystemStatus }));

import SettingsPage from '@/pages/SettingsPage';

describe('SettingsPage', () => {
  it('AP-R04-01: 以研究可用性、模型与检索工具、运行配置分组展示只读状态', async () => {
    getSystemStatus.mockResolvedValue({
      model: { name: '模型A', status: 'loaded', temperature: 0.2, max_steps: 5 },
      vector_db: { path: '忽略', status: 'available', company_count: 3 },
      memory: { long_term_enabled: true, working_memory_limit: 10 },
      monitoring: { langsmith_available: false, langsmith_project: '', langsmith_endpoint: '' },
      tools: { retrieve: true },
    });
    render(<SettingsPage />);

    expect(await screen.findByText('研究可用性')).toBeInTheDocument();
    expect(screen.getByText('模型与检索工具')).toBeInTheDocument();
    expect(screen.getByText('运行配置')).toBeInTheDocument();
    expect(screen.queryByText('忽略')).toBeNull();
  });

  it('CP-R63: 系统状态以真实研究可用性摘要作为首要信息，保留只读分组', async () => {
    getSystemStatus.mockResolvedValue({
      model: { name: '模型A', status: 'loaded', temperature: 0.2, max_steps: 5 },
      vector_db: { path: '忽略', status: 'available', company_count: 3 },
      memory: { long_term_enabled: true, working_memory_limit: 10 },
      monitoring: { langsmith_available: false, langsmith_project: '', langsmith_endpoint: '' },
      tools: { retrieve: true },
    });
    const { container } = render(<SettingsPage />);

    expect(await screen.findByText('研究服务可用')).toBeInTheDocument();
    expect(container.querySelector('.settings-availability-brief')).toBeInTheDocument();
    expect(screen.getByText('研究可用性')).toBeInTheDocument();
  });
});
