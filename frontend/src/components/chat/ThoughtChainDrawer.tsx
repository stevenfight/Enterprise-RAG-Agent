// -*- coding: utf-8 -*-
/**
 * Agent 思维链侧边抽屉组件
 * Phase 2 - 右侧抽屉展示完整推理过程时间线
 *
 * 与 MessageBubble 内嵌的折叠推理步骤配合：
 *   - 消息气泡内: 快速预览（折叠/展开 + 步骤摘要）
 *   - 本组件: 侧边抽屉展示完整细节（不受 60px 高度限制）
 */

import { useState } from 'react';
import { Drawer, Tag, Typography, Space } from 'antd';
import {
  BulbOutlined,
  ToolOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import type { ReasoningStep } from '@/types/chat';
import { useTheme } from '@/hooks/useTheme';

const { Text } = Typography;

interface ThoughtChainDrawerProps {
  open: boolean;
  onClose: () => void;
  steps: ReasoningStep[];
}

/** 时间线节点颜色轮转 */
const NODE_COLORS = ['#B8A9C9', '#98D8C8', '#A8D8EA', '#F4B8C8', '#FAD4B8'];

export default function ThoughtChainDrawer({ open, onClose, steps }: ThoughtChainDrawerProps) {
  const { isDark } = useTheme();
  const [expandedObs, setExpandedObs] = useState<number[]>([]);

  const toggleExpand = (idx: number) => {
    setExpandedObs(prev =>
      prev.includes(idx) ? prev.filter(i => i !== idx) : [...prev, idx]
    );
  };

  return (
    <Drawer
      title={
        <Space>
          <BulbOutlined style={{ color: '#B8A9C9' }} />
          <span>推理过程 ({steps.length} 步)</span>
        </Space>
      }
      placement="right"
      size="large"
      open={open}
      onClose={onClose}
      styles={{
        body: {
          padding: '16px',
          background: isDark ? '#141414' : '#f9f7fc',
        },
        header: {
          background: isDark ? '#1f1f1f' : '#f0ebf7',
          borderBottom: `1px solid ${isDark ? '#303030' : '#e8e3ef'}`,
        },
      }}
    >
      {/* 时间线 */}
      <div style={{ position: 'relative', paddingLeft: 28 }}>
        {/* 时间线竖线 */}
        <div
          style={{
            position: 'absolute',
            left: 11,
            top: 0,
            bottom: 0,
            width: 2,
            background: isDark ? '#303030' : '#e8e3ef',
          }}
        />

        {steps.map((step, idx) => (
          <div
            key={idx}
            style={{
              position: 'relative',
              marginBottom: idx < steps.length - 1 ? 20 : 0,
            }}
          >
            {/* 时间线节点 */}
            <div
              style={{
                position: 'absolute',
                left: -23,
                top: 16,
                width: 12,
                height: 12,
                borderRadius: '50%',
                background: NODE_COLORS[idx % NODE_COLORS.length],
                border: `2px solid ${isDark ? '#141414' : '#f9f7fc'}`,
                zIndex: 1,
              }}
            />

            {/* 步骤卡片 */}
            <div
              style={{
                padding: '12px 14px',
                borderRadius: 10,
                background: isDark ? '#1f1f1f' : '#ffffff',
                border: `1px solid ${isDark ? '#303030' : '#e8e3ef'}`,
                boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
              }}
            >
              {/* 步骤编号 */}
              <Tag
                color="purple"
                style={{ fontSize: 10, margin: '0 0 8px 0', borderRadius: 4 }}
              >
                步骤 {step.step_number}
              </Tag>

              {/* Thought */}
              {step.thought && (
                <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 8 }}>
                  <BulbOutlined style={{
                    fontSize: 13,
                    color: '#B8A9C9',
                    marginTop: 2,
                    marginRight: 8,
                    flexShrink: 0,
                  }} />
                  <Text style={{
                    fontSize: 13,
                    color: isDark ? '#bbb' : '#555',
                    lineHeight: 1.7,
                  }}>
                    {step.thought}
                  </Text>
                </div>
              )}

              {/* Action */}
              {step.action && (
                <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 8 }}>
                  <ToolOutlined style={{
                    fontSize: 13,
                    color: '#52c41a',
                    marginTop: 2,
                    marginRight: 8,
                    flexShrink: 0,
                  }} />
                  <div>
                    <Tag color="green" style={{ fontSize: 10, lineHeight: '16px', borderRadius: 4 }}>
                      调用工具: {step.action}
                    </Tag>
                    {step.action_input && (
                      <div style={{
                        marginTop: 4,
                        padding: '6px 10px',
                        borderRadius: 6,
                        background: isDark ? 'rgba(82, 196, 26, 0.06)' : 'rgba(82, 196, 26, 0.04)',
                        fontSize: 11,
                        fontFamily: "'Courier New', monospace",
                        color: isDark ? '#aaa' : '#666',
                        maxHeight: 80,
                        overflow: 'auto',
                      }}>
                        {typeof step.action_input === 'string'
                          ? step.action_input
                          : JSON.stringify(step.action_input, null, 2)}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Observation */}
              {step.observation && (
                <div style={{ display: 'flex', alignItems: 'flex-start' }}>
                  <EyeOutlined style={{
                    fontSize: 13,
                    color: '#1890ff',
                    marginTop: 2,
                    marginRight: 8,
                    flexShrink: 0,
                  }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Text
                      onClick={() => toggleExpand(idx)}
                      style={{
                        fontSize: 12,
                        color: isDark ? '#999' : '#888',
                        cursor: 'pointer',
                        display: 'block',
                        maxHeight: expandedObs.includes(idx) ? 'none' : 40,
                        overflow: 'hidden',
                        whiteSpace: expandedObs.includes(idx) ? 'pre-wrap' : 'normal',
                        lineHeight: 1.5,
                      }}
                    >
                      {step.observation}
                    </Text>
                    {step.observation.length > 80 && !expandedObs.includes(idx) && (
                      <Text
                        style={{ fontSize: 11, color: '#1890ff', cursor: 'pointer' }}
                        onClick={() => toggleExpand(idx)}
                      >
                        展开全部
                      </Text>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </Drawer>
  );
}
