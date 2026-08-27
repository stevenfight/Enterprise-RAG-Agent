// -*- coding: utf-8 -*-
/** 研究工作台的只读研究摘要条。 */
import type { ReactNode } from 'react';
import { Button, Typography } from 'antd';
import { AimOutlined, FileSearchOutlined } from '@ant-design/icons';
import { useTheme } from '@/hooks/useTheme';
import { colors } from '@/styles/theme';

const { Text } = Typography;

interface ResearchContextBarProps {
  companyName?: string;
  mode: 'rag' | 'agent';
  configuration?: ReactNode;
  onOpenEvidence?: () => void;
}

export default function ResearchContextBar({ companyName, configuration, onOpenEvidence }: ResearchContextBarProps) {
  const { isDark } = useTheme();
  const surface = isDark ? colors.bgDarkCard : colors.bgCard;
  const border = isDark ? colors.borderDark : colors.border;
  const secondaryText = isDark ? colors.textSecondaryDark : colors.textSecondary;
  const scopeSummary = (
    <>
      <span
        className="research-context-bar__scope-icon"
        style={{
          background: isDark
            ? 'color-mix(in srgb, var(--color-primary) 18%, transparent)'
            : 'color-mix(in srgb, var(--color-primary) 8%, transparent)',
        }}
      >
        <AimOutlined style={{ color: 'var(--color-primary)', fontSize: 15 }} />
      </span>
      <span className="research-context-bar__scope-copy">
        <Text strong style={{ display: 'block', fontSize: 14 }}>
          研究工作台
        </Text>
        <Text style={{ display: 'block', fontSize: 12, color: secondaryText }}>
          下次提问：{companyName ?? '全部公司'}
        </Text>
      </span>
    </>
  );

  return (
    <section
      aria-label="研究摘要"
      className="research-context-bar"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 16,
        padding: '12px 20px',
        background: surface,
        borderBottom: `1px solid ${border}`,
        flexWrap: 'wrap',
      }}
    >
      <span className="research-context-bar__scope-summary">{scopeSummary}</span>

      <div className="research-context-bar__actions">
        {configuration}
        {onOpenEvidence && (
          <Button className="research-context-bar__action" type="text" size="small" icon={<FileSearchOutlined />} aria-label="查看证据" onClick={onOpenEvidence}>
            <span className="research-context-bar__action-label">查看证据</span>
          </Button>
        )}
      </div>
    </section>
  );
}
