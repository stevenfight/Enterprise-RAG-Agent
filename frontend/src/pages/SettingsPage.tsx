// -*- coding: utf-8 -*-
/**
 * 系统设置页面（只读监控面板）
 * Phase 3 实现: 展示服务端运行状态，不做本地修改
 */

import { useState, useEffect } from 'react';
import {
  Typography, Card, Tag, Descriptions, Space, Spin,
} from 'antd';
import {
  CheckCircleOutlined, CloseCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { getSystemStatus } from '@/services/systemService';
import type { SystemStatusData } from '@/types/chat';

const { Title, Text } = Typography;

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
      <div style={{
        display: 'flex', justifyContent: 'center',
        alignItems: 'center', minHeight: 300,
      }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <Title level={3}>系统设置</Title>
        <Card>
          <Text type="danger">
            <ExclamationCircleOutlined style={{ marginRight: 8 }} />
            {error}
          </Text>
        </Card>
      </div>
    );
  }

  if (!status) return null;

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>系统设置</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        当前运行状态（只读监控，修改配置请编辑 config/agent_config.json）
      </Text>

      <Space direction="vertical"
             style={{ width: '100%' }} size="middle">

        {/* ===== Agent 当前配置 ===== */}
        <Card title="Agent 当前配置">
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

        {/* ===== 系统健康 ===== */}
        <Card title="系统健康">
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="模型状态">
              <Tag color={
                  status.model.status === 'loaded' ? 'green' : 'red'}>
                {status.model.status === 'loaded'
                    ? <CheckCircleOutlined />
                    : <CloseCircleOutlined />}
                {' '}{status.model.status === 'loaded'
                    ? '已加载' : '未加载'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="向量数据库">
              <Tag color={
                  status.vector_db.status === 'available'
                      ? 'green' : 'red'}>
                {status.vector_db.status === 'available'
                    ? <CheckCircleOutlined />
                    : <CloseCircleOutlined />}
                {' '}{status.vector_db.status === 'available'
                    ? `可用 (${status.vector_db.company_count} 家公司)`
                    : '不可用'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="长期记忆">
              <Tag color={
                  status.memory.long_term_enabled ? 'green' : 'default'}>
                {status.memory.long_term_enabled
                    ? '已启用' : '未启用'}
              </Tag>
              {status.memory.long_term_enabled && (
                <Text type="secondary" style={{ marginLeft: 8 }}>
                  容量: {status.memory.working_memory_limit} 条
                </Text>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="LangSmith">
              <Tag color={
                  status.monitoring.langsmith_available
                      ? 'green' : 'default'}>
                {status.monitoring.langsmith_available
                    ? '已启用' : '未启用'}
              </Tag>
              {status.monitoring.langsmith_available && (
                <Text type="secondary" style={{ marginLeft: 8 }}>
                  {status.monitoring.langsmith_project}
                </Text>
              )}
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {/* ===== 已注册工具 ===== */}
        <Card title="已注册工具">
          <Descriptions column={1} bordered size="small">
            {Object.entries(TOOL_LABELS).map(([key, label]) => (
              <Descriptions.Item key={key} label={label}>
                <Tag color={status.tools[key] ? 'green' : 'red'}>
                  {status.tools[key] ? '已启用' : '已禁用'}
                </Tag>
                <Text type="secondary" style={{ marginLeft: 8 }}>
                  ({key})
                </Text>
              </Descriptions.Item>
            ))}
          </Descriptions>
        </Card>
      </Space>
    </div>
  );
}
