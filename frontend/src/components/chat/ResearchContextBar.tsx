// -*- coding: utf-8 -*-
/** 研究工作台的只读研究摘要条。 */
import { Button, Space, Tag, Typography } from 'antd';
import { AimOutlined, FileSearchOutlined, RobotOutlined, SearchOutlined, SettingOutlined } from '@ant-design/icons';
import { useTheme } from '@/hooks/useTheme';
import { colors } from '@/styles/theme';

const { Text, Title } = Typography;

interface ResearchContextBarProps {
  companyName?: string;
  mode: 'rag' | 'agent';
  onOpenEvidence?: () => void;
  onOpenConfig?: () => void;
}

export default function ResearchContextBar({ companyName, mode, onOpenEvidence, onOpenConfig }: ResearchContextBarProps) {
  const { isDark } = useTheme();
  const surface = isDark ? colors.bgDarkCard : colors.bgCard;
  const border = isDark ? colors.borderDark : colors.border;
  const secondaryText = isDark ? colors.textSecondaryDark : colors.textSecondary;

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
      <Space size={10} wrap>
        <div
          style={{
            width: 30,
            height: 30,
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: isDark
              ? 'color-mix(in srgb, var(--color-primary) 18%, transparent)'
              : 'color-mix(in srgb, var(--color-primary) 8%, transparent)',
          }}
        >
          <AimOutlined style={{ color: 'var(--color-primary)', fontSize: 15 }} />
        </div>
        <div>
          <Title level={5} style={{ margin: 0, fontSize: 14 }}>
            研究工作台
          </Title>
          <Text style={{ fontSize: 12, color: secondaryText }}>
            下次提问：{companyName ?? '全部公司'}
          </Text>
        </div>
      </Space>

      <Space className="research-context-bar__actions" size={8} wrap>
        <Tag
          className="research-context-bar__mode"
          icon={mode === 'agent' ? <RobotOutlined /> : <SearchOutlined />}
          style={{
            margin: 0,
            borderRadius: 999,
            padding: '2px 9px',
            color: 'var(--color-primary)',
            borderColor: 'var(--color-primary)',
            background: 'transparent',
          }}
        >
          {mode === 'agent' ? 'Agent 深度分析' : 'RAG 问答'}
        </Tag>
        {onOpenConfig && (
          <Button
            className="research-context-bar__action"
            type="text"
            size="small"
            icon={<SettingOutlined />}
            aria-label="打开研究配置"
            onClick={onOpenConfig}
          >
            <span className="research-context-bar__action-label">研究配置</span>
          </Button>
        )}
        {onOpenEvidence && (
          <Button className="research-context-bar__action" type="text" size="small" icon={<FileSearchOutlined />} aria-label="查看证据" onClick={onOpenEvidence}>
            <span className="research-context-bar__action-label">查看证据</span>
          </Button>
        )}
      </Space>
    </section>
  );
}
