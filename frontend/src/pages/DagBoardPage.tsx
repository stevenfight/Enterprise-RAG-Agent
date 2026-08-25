// -*- coding: utf-8 -*-
/**
 * DAG 任务规划看板页面
 * Phase 2 - 使用 @antv/g6 渲染 Agent 任务规划的有向无环图
 *
 * 后端 /api/agent/plan?query=xxx 返回子任务节点和依赖边，
 * 前端用 DagFlow 组件渲染交互式 DAG（支持缩放、拖拽、节点点击）
 */

import { useState, useCallback } from 'react';
import {
  Button,
  Card,
  Input,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd';
import { SearchOutlined, NodeIndexOutlined } from '@ant-design/icons';
import DagFlow from '@/components/dag/DagFlow';
import DagTaskSummary from '@/components/dag/DagTaskSummary';
import DagExecutionTimeline from '@/components/dag/DagExecutionTimeline';
import { PageHeader, PageShell } from '@/components/common/PageShell';
import { TYPE_COLORS, TYPE_NAMES, type DagNodeType } from '../constants/dag';
import { getAgentPlan, type PlanData } from '@/services/dagService';

const { Text } = Typography;

export default function DagBoardPage() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [planData, setPlanData] = useState<PlanData | null>(null);
  const [error, setError] = useState('');

  const fetchPlan = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    try {
      const data = await getAgentPlan(query);
      setPlanData(data);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : '请求失败';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [query]);

  return (
    <PageShell>
      <PageHeader
        eyebrow="任务规划"
        title="高级分析流程"
        icon={<NodeIndexOutlined />}
        description="查看 Agent 如何组织任务、依赖关系与执行批次；不替代最终研究结论"
      />

      {/* 查询输入 */}
      <Card size="small" className="page-card page-toolbar" style={{ marginBottom: 24 }}>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="输入查询语句，查看 Agent 的任务拆解 DAG..."
            onPressEnter={fetchPlan}
            allowClear
            style={{ borderRadius: '8px 0 0 8px' }}
          />
          <Button
            type="primary"
            icon={<SearchOutlined />}
            onClick={fetchPlan}
            loading={loading}
            style={{ borderRadius: '0 8px 8px 0' }}
          >
            分析
          </Button>
        </Space.Compact>
        {error && <Text type="danger" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>{error}</Text>}
      </Card>

      {/* 加载状态 */}
      {loading && (
        <div className="page-state" style={{ textAlign: 'center', padding: 60 }}>
          <Spin size="large" />
          <div style={{ marginTop: 12, color: 'var(--page-text-secondary)' }}>Agent 正在规划任务...</div>
        </div>
      )}

      {/* DAG 图 */}
      {!loading && planData && (
        <>
          <DagTaskSummary
            category={planData.category}
            nodeCount={planData.nodes.length}
            edgeCount={planData.edges.length}
            batchCount={planData.execution_order.length}
            status={planData.message}
          />

          <div className="dag-flow-panel">
            <DagFlow
              nodes={planData.nodes}
              edges={planData.edges}
              height={420}
            />
          </div>

          <DagExecutionTimeline
            batches={planData.execution_order}
            nodeLabels={Object.fromEntries(planData.nodes.map((node) => [node.id, node.label]))}
          />

          {/* 图例 */}
          <Card size="small" className="page-card" style={{ marginTop: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
              <Text style={{ fontSize: 12, color: '#888', fontWeight: 600 }}>图例:</Text>
              {Object.entries(TYPE_COLORS).map(([type, color]) => (
                <Tag key={type} color={color} style={{ margin: 0 }}>
                  {TYPE_NAMES[type as DagNodeType] || type}
                </Tag>
              ))}
            </div>
            {planData.execution_order.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Text style={{ fontSize: 12, color: '#888', fontWeight: 600 }}>执行批次:</Text>
                {planData.execution_order.map((batch, idx) => (
                  <Tag key={idx} style={{ margin: '0 4px', fontSize: 11 }}>
                    第{idx + 1}批: {batch.join(', ')}
                  </Tag>
                ))}
              </div>
            )}
            {planData.message && (
              <Text style={{ fontSize: 12, color: '#999', display: 'block', marginTop: 8 }}>
                {planData.message}
              </Text>
            )}
          </Card>
        </>
      )}

      {/* 空状态 */}
      {!loading && !planData && !error && (
        <div className="page-state" style={{
          textAlign: 'center',
          padding: 80,
          color: 'var(--page-text-secondary)',
        }}>
          <NodeIndexOutlined style={{ fontSize: 48, opacity: 0.3, marginBottom: 16 }} />
          <div style={{ fontSize: 14 }}>输入查询语句，查看 Agent 如何拆解任务</div>
          <div style={{ fontSize: 12, marginTop: 4 }}>
            支持: 营收对比、趋势分析、复合计算等
          </div>
        </div>
      )}
    </PageShell>
  );
}
