// -*- coding: utf-8 -*-
/**
 * 系统设置页面（只读监控面板）
 * Phase 3 实现: 展示服务端运行状态，不做本地修改
 */

import { useState, useEffect } from 'react';
import {
  Card, Descriptions, Space, Spin, Tag, Typography,
} from 'antd';
import {
  CheckCircleOutlined, CloseCircleOutlined, ExclamationCircleOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { getSystemStatus } from '@/services/systemService';
import type { SystemStatusData } from '@/types/chat';
import { PageHeader, PageShell } from '@/components/common/PageShell';
import SettingsOverview from '@/components/settings/SettingsOverview';

const TOOL_LABELS: Record<string, string> = {
  retrieve: '检索',
  calculator: '计算',
  compare: '对比',
  chart: '图表',
  verify: '验证',
  delegate: '委派',
};

export default function SettingsPage() {
  const [status, setStatus] = useState<SystemStatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await getSystemStatus();
        setStatus(data);
      } catch {
        setError('无法连接后端服务');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <PageShell>
        <PageHeader
          eyebrow="运行监控"
          title="系统状态"
          icon={<SettingOutlined />}
          description="查看研究服务、模型、检索与运行配置的当前状态"
        />
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
          <Spin size="large" />
        </div>
      </PageShell>
    );
  }

  if (error) {
    return (
      <PageShell>
        <PageHeader
          eyebrow="运行监控"
          title="系统状态"
          icon={<SettingOutlined />}
          description="查看当前 Agent、知识库和工具运行状态"
        />
        <Card className="page-card">
          <Typography.Text type="danger">
            <ExclamationCircleOutlined style={{ marginRight: 8 }} />
            {error}
          </Typography.Text>
        </Card>
      </PageShell>
    );
  }

  if (!status) return null;
  const researchAvailable = status.model.status === 'loaded' && status.vector_db.status === 'available';

  return (
    <PageShell>
      <PageHeader
        eyebrow="运行监控"
        title="系统状态"
        icon={<SettingOutlined />}
        description="当前运行状态（只读监控，修改配置请编辑 config/agent_config.json）"
      />

      <Space orientation="vertical" className="page-stack"
             style={{ width: '100%' }}>
        <section className={`settings-availability-brief settings-availability-brief--${researchAvailable ? 'ready' : 'attention'}`} aria-label="研究服务可用性摘要">
          {researchAvailable ? <CheckCircleOutlined aria-hidden="true" /> : <ExclamationCircleOutlined aria-hidden="true" />}
          <div>
            <strong>{researchAvailable ? '研究服务可用' : '研究服务需关注'}</strong>
            <span>
              模型{status.model.status === 'loaded' ? '已加载' : '未加载'} · 向量数据库{status.vector_db.status === 'available' ? '可用' : '不可用'}
            </span>
          </div>
        </section>
        <SettingsOverview status={status} />

        {/* ===== 研究可用性 ===== */}
        <Card title="研究可用性" className="page-card">
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="模型状态">
              <Tag color={status.model.status === 'loaded' ? 'green' : 'red'}>
                {status.model.status === 'loaded' ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                {' '}{status.model.status === 'loaded' ? '已加载' : '未加载'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="向量数据库">
              <Tag color={status.vector_db.status === 'available' ? 'green' : 'red'}>
                {status.vector_db.status === 'available' ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                {' '}{status.vector_db.status === 'available' ? `可用 (${status.vector_db.company_count} 家公司)` : '不可用'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="长期记忆">
              <Tag color={status.memory.long_term_enabled ? 'green' : 'default'}>{status.memory.long_term_enabled ? '已启用' : '未启用'}</Tag>
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {/* ===== 模型与检索工具 ===== */}
        <Card title="模型与检索工具" className="page-card">
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="模型"><Tag color="blue">{status.model.name}</Tag></Descriptions.Item>
            {Object.entries(TOOL_LABELS).map(([key, label]) => (
              <Descriptions.Item key={key} label={label}>
                <Tag color={status.tools[key] ? 'green' : 'red'}>{status.tools[key] ? '已启用' : '已禁用'}</Tag>
              </Descriptions.Item>
            ))}
          </Descriptions>
        </Card>

        {/* ===== 运行配置 ===== */}
        <Card title="运行配置" className="page-card">
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="模型">
              <Tag color="blue">{status.model.name}</Tag>
              <Tag color={
                  status.model.status === 'loaded' ? 'green' : 'red'}
                   style={{ marginLeft: 8 }}>
                {status.model.status === 'loaded'
                    ? '已加载' : '未加载'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Temperature">
              {status.model.temperature}
            </Descriptions.Item>
            <Descriptions.Item label="Max Steps">
              {status.model.max_steps} 步
            </Descriptions.Item>
          </Descriptions>
        </Card>

      </Space>
    </PageShell>
  );
}
