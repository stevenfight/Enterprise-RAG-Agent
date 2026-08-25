// -*- coding: utf-8 -*-
/** 桌面侧栏复用的安全分析过程内容。 */
import { Empty, Tag, Typography } from 'antd';
import { EyeOutlined, ToolOutlined } from '@ant-design/icons';
import type { AnalysisTraceStep } from '@/types/chat';
import { useTheme } from '@/hooks/useTheme';

const { Text } = Typography;

interface AnalysisTraceContentProps {
  steps: AnalysisTraceStep[];
}

export default function AnalysisTraceContent({ steps }: AnalysisTraceContentProps) {
  const { isDark } = useTheme();

  if (steps.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前回答暂无分析过程" />;
  }

  return (
    <div style={{ display: 'grid', gap: 10 }}>
      {steps.map((step) => (
        <section
          key={`${step.stepNumber}-${step.toolLabel}`}
          aria-label={`步骤 ${step.stepNumber}`}
          style={{
            padding: 12,
            borderRadius: 10,
            background: isDark ? '#1f1f1f' : '#ffffff',
            border: `1px solid ${isDark ? '#303030' : '#e8e3ef'}`,
          }}
        >
          <Tag color="blue" style={{ fontSize: 10, margin: '0 0 8px 0' }}>
            步骤 {step.stepNumber} · {step.status === 'completed' ? '已完成' : step.status === 'failed' ? '未完成' : '进行中'}
          </Tag>
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
            <ToolOutlined style={{ color: '#52c41a', marginTop: 3 }} />
            <div>
              <Text strong style={{ fontSize: 12 }}>{step.toolLabel}</Text>
              {step.inputSummary && <Text type="secondary" style={{ display: 'block', fontSize: 12 }}>{step.inputSummary}</Text>}
            </div>
          </div>
          {step.observationSummary && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginTop: 8 }}>
              <EyeOutlined style={{ color: '#1890ff', marginTop: 3 }} />
              <Text type="secondary" style={{ fontSize: 12, lineHeight: 1.5 }}>{step.observationSummary}</Text>
            </div>
          )}
        </section>
      ))}
    </div>
  );
}
