// -*- coding: utf-8 -*-
/**
 * 引用来源卡片 - 马卡龙风格
 * 展示 AI 回答引用的文档来源信息
 */

import { useState } from 'react';
import { Card, Typography, Space, Tag } from 'antd';
import {
  FileTextOutlined,
  BookOutlined,
  CaretDownOutlined,
} from '@ant-design/icons';
import type { SourceInfo, SourceScoreValue } from '@/types/chat';
import { useTheme } from '@/hooks/useTheme';
import { colors } from '@/styles/theme';
import { createLogger } from '@/utils/logger';

const logger = createLogger('SourceCard');
const { Text } = Typography;

interface SourceCardProps {
  source: SourceInfo;
  /** Agent 来源没有检索分数时，分组标题已说明为回答证据，不重复显示空分数。 */
  showScoreStatus?: boolean;
  /** 由正文来源编号定位时，短暂强调当前来源。 */
  highlighted?: boolean;
}

/** 计算检索匹配度百分比
 * scores 包含多个不同量纲的字段:
 *   hybrid:  0.0~1.0  (加权融合分, 始终存在)  → 作为置信度主指标
 *   rerank:  0.0~10.0 (重排序分)
 *   vector:  ~0.0~1.0 (向量相似度)
 *   bm25:    >0 无上界 (BM25 分)
 * 仅使用 hybrid 分数作为可比较的检索匹配度百分比。
 */
function calcScorePercent(scores: Record<string, SourceScoreValue>): number | null {
  // hybrid 为 0~1 的融合分，可安全转换为百分比。
  if (typeof scores.hybrid === 'number') {
    return Math.round(Math.min(100, Math.max(0, scores.hybrid * 100)));
  }
  return null;
}

export default function SourceCard({ source, showScoreStatus = true, highlighted = false }: SourceCardProps) {
  logger.renderStart({ sourceFile: source.source_file, company: source.company_name, pages: source.pages });
  const [expanded, setExpanded] = useState(false);
  const [showScores, setShowScores] = useState(false);
  const { isDark } = useTheme();

  const scorePercent = calcScorePercent(source.scores || {});

  const borderColor = isDark ? '#3A3550' : '#E8E3EF';
  const iconColor = isDark ? colors.accent : colors.primary;

  return (
    <Card
      size="small"
      className={`card-hover source-card${highlighted ? ' source-card--highlighted' : ''}`}
      data-testid={`source-card-${source.index}`}
      style={{
        marginBottom: 8,
        borderRadius: 10,
        border: `1px solid ${borderColor}`,
        cursor: 'pointer',
        background: isDark
          ? 'rgba(37, 34, 54, 0.5)'
          : 'rgba(255, 255, 255, 0.6)',
        backdropFilter: 'blur(6px)',
      }}
      onClick={() => setExpanded(!expanded)}
    >
      <Space size={8} align="center" style={{ width: '100%' }}>
        <div
          style={{
            width: 26,
            height: 26,
            borderRadius: 8,
            // 浅色分支使用主体色语义变量（A3 品牌硬编码迁移），暗色分支为既有可读性对照色
            background: isDark
              ? 'rgba(152, 216, 200, 0.15)'
              : 'color-mix(in srgb, var(--page-primary, #0F766E) 12%, transparent)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <FileTextOutlined style={{ fontSize: 14, color: iconColor }} />
        </div>
        <Text
          strong
          ellipsis
          style={{ maxWidth: 180, fontSize: 13 }}
        >
          {source.source_file}
        </Text>
        {scorePercent !== null ? (
          <Tag
            color={scorePercent >= 80 ? 'success' : scorePercent >= 50 ? 'processing' : 'default'}
            style={{ fontSize: 12, margin: 0, borderRadius: 6 }}
          >
            {scorePercent}%
          </Tag>
        ) : showScoreStatus ? (
          <Text type="secondary" style={{ fontSize: 11 }}>
            匹配度未提供
          </Text>
        ) : null}
      </Space>

      <div style={{ marginTop: 6, marginLeft: 34 }}>
        <Space size={8}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            <BookOutlined /> {source.company_name}
          </Text>
          {source.pages.length > 0 && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              P{source.pages.join(', P')}
            </Text>
          )}
        </Space>
      </div>

      {expanded && (
        <div style={{ marginTop: 8, paddingTop: 8, borderTop: `1px solid ${borderColor}` }}>
          {source.excerpt && (
            <div style={{ marginBottom: 8 }}>
              <Text strong style={{ display: 'block', fontSize: 12, marginBottom: 4 }}>命中文本摘要</Text>
              <Text type="secondary" style={{ fontSize: 12, lineHeight: 1.6 }}>{source.excerpt}</Text>
            </div>
          )}
          {/* 评分详情 - 独立的可点击标题，不再使用 Collapse 避免事件冲突 */}
          <div
            onClick={(e) => {
              e.stopPropagation(); // 阻止冒泡到 Card 的 onClick
              setShowScores(!showScores);
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              cursor: 'pointer',
              padding: '4px 0',
              userSelect: 'none',
            }}
          >
            <Text style={{ fontSize: 12, color: isDark ? '#8c8c8c' : '#595959' }}>
              评分详情
            </Text>
            <CaretDownOutlined
              style={{
                fontSize: 10,
                color: isDark ? '#8c8c8c' : '#595959',
                transform: showScores ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 0.2s',
              }}
            />
          </div>
          {showScores && (
            <Space orientation="vertical" size={2} style={{ marginTop: 4 }}>
              {Object.entries(source.scores || {}).map(([key, value]) => (
                <Text key={key} style={{ fontSize: 11, color: isDark ? '#a0a0a0' : '#666' }}>
                  {key}: {typeof value === 'number' ? value.toFixed(4) : String(value)}
                </Text>
              ))}
            </Space>
          )}
        </div>
      )}
    </Card>
  );
}
