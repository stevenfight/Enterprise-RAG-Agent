import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import SettingsOverview from '../SettingsOverview';
import type { SystemStatusData } from '@/types/chat';

const status: SystemStatusData = {
  model: { name: '财务分析模型', status: 'loaded', temperature: 0.2, max_steps: 8 },
  vector_db: { path: '/data/vector', status: 'available', company_count: 12 },
  memory: { long_term_enabled: true, working_memory_limit: 50 },
  monitoring: {
    langsmith_available: true,
    langsmith_project: 'financial-agent',
    langsmith_endpoint: 'https://example.com',
  },
  tools: { retrieve: true, calculator: true, compare: false },
};

describe('SettingsOverview', () => {
  it('展示系统状态 KPI 概览', () => {
    render(<SettingsOverview status={status} />);

    expect(screen.getByRole('region', { name: '系统状态概览' })).toBeInTheDocument();
    expect(screen.getByText('财务分析模型')).toBeInTheDocument();
    expect(screen.getByText('12 家公司')).toBeInTheDocument();
    expect(screen.getByText('工作记忆容量 50 条')).toBeInTheDocument();
    expect(screen.getByText('financial-agent')).toBeInTheDocument();
    expect(screen.getByText('2 / 3')).toBeInTheDocument();
  });

  it('未启用或不可用状态使用告警状态样式', () => {
    render(
      <SettingsOverview
        status={{
          ...status,
          model: { ...status.model, status: 'unloaded' },
          vector_db: { ...status.vector_db, status: 'unavailable' },
          memory: { ...status.memory, long_term_enabled: false },
          monitoring: { ...status.monitoring, langsmith_available: false },
          tools: { retrieve: false, calculator: false, compare: false },
        }}
      />,
    );

    expect(document.querySelectorAll('.status-overview-card--error')).toHaveLength(2);
    expect(document.querySelectorAll('.status-overview-card--warning')).toHaveLength(3);
  });
});
