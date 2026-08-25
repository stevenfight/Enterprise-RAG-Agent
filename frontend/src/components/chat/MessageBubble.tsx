// -*- coding: utf-8 -*-
/**
 * 消息气泡组件 - 基于 @ant-design/x Bubble
 * 用户消息右对齐填充式，AI 消息左对齐描边式，系统消息居中
 */

import { useState } from 'react';
import { Typography, Space, Tag, Button } from 'antd';
import { Bubble } from '@ant-design/x';
import {
  UserOutlined,
  RobotOutlined,
  WarningOutlined,
  BulbOutlined,
  CaretDownOutlined,
  CopyOutlined,
  RedoOutlined,
  CheckOutlined,
} from '@ant-design/icons';
import type { Message, AnalysisTraceStep } from '@/types/chat';
import { useTheme } from '@/hooks/useTheme';
import { colors, gradients } from '@/styles/theme';
import { formatMarkdown, extractFinancialKPIs } from '@/utils/financialFormat';
import FinancialKPICards from './FinancialKPICards';
import VerifiedComparisonCard from './VerifiedComparisonCard';
import { createLogger } from '@/utils/logger';

const logger = createLogger('MessageBubble');
const { Text } = Typography;

interface MessageBubbleProps {
  message: Message;
  onViewReasoning?: (steps: AnalysisTraceStep[]) => void;
  /** 是否处于流式输出状态（AI 消息正在接收 SSE 数据时显示打字机光标） */
  isStreaming?: boolean;
  /** 重新生成回调 */
  onRegenerate?: (messageId: string) => void;
  /** 打开该回答的完整证据面板 */
  onViewEvidence?: (messageId: string) => void;
}

export default function MessageBubble({ message, onViewReasoning, isStreaming = false, onRegenerate, onViewEvidence }: MessageBubbleProps) {
  logger.renderStart({ role: message.role, id: message.id, contentLen: message.content.length, sourcesCount: message.sources?.length });
  const { isDark } = useTheme();
  const [showReasoning, setShowReasoning] = useState(false); // Agent 推理链路展开/收起
  const [hovered, setHovered] = useState(false); // 气泡 hover 状态
  const [copied, setCopied] = useState(false); // 复制成功状态
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  // 系统消息: 居中灰色
  if (isSystem) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', margin: '8px 0' }}>
        <Space size={6}>
          <WarningOutlined style={{ color: '#ff4d4f', fontSize: 14 }} />
          <Text type="secondary" style={{ fontSize: 13 }}>
            {message.content}
          </Text>
        </Space>
      </div>
    );
  }

  // 消息文本内容（用户纯文本，AI 走 Markdown 渲染）
  // 流式输出时在内容末尾追加打字机光标
  const rawHtml = isUser ? message.content : formatMarkdown(message.content, isDark);
  const cursorHtml = isStreaming && !isUser ? '<span class="typing-cursor"></span>' : '';

  // AI 消息自动提取财务 KPI 并展示卡片
  const kpis = !isUser ? extractFinancialKPIs(message.content) : [];

  const messageContent = (
    <div style={{ fontSize: 14, lineHeight: 1.7, fontFamily: 'inherit' }}>
      {!isUser && kpis.length > 0 && (
        <FinancialKPICards kpis={kpis} isDark={isDark} />
      )}
      {!isUser && <VerifiedComparisonCard comparison={message.comparison} />}
      <div
        className="markdown-body"
        dangerouslySetInnerHTML={{
          __html: rawHtml + cursorHtml,
        }}
      />
    </div>
  );

  // 气泡底部插槽: 推理链 + 多 Agent 状态 + 引用来源 + 时间戳
  const footer = (
    <div style={{ marginTop: 6 }}>
      {/* Hover 操作按钮: 复制 + 重新生成 */}
      {!isUser && hovered && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 4,
            marginBottom: 6,
            opacity: hovered ? 1 : 0,
            transition: 'opacity 0.2s',
          }}
        >
          <Button
            type="text"
            size="small"
            icon={copied ? <CheckOutlined style={{ color: '#52c41a' }} /> : <CopyOutlined />}
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(message.content);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              } catch {
                // 剪贴板写入失败时静默处理
              }
            }}
            style={{
              fontSize: 12,
              color: isDark ? '#a0a0a0' : '#8c8c8c',
              padding: '0 6px',
              height: 24,
            }}
          >
            {copied ? '已复制' : '复制'}
          </Button>
          {onRegenerate && (
            <Button
              type="text"
              size="small"
              icon={<RedoOutlined />}
              onClick={() => onRegenerate(message.id)}
              style={{
                fontSize: 12,
                color: isDark ? '#a0a0a0' : '#8c8c8c',
                padding: '0 6px',
                height: 24,
              }}
            >
              重新生成
            </Button>
          )}
        </div>
      )}

      {/* 安全分析过程摘要 */}
      {!isUser && message.analysisTrace && message.analysisTrace.length > 0 && (
        <div style={{
          marginTop: 10,
          paddingTop: 8,
          borderTop: `1px solid ${isDark ? colors.borderDark : colors.border}`,
        }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              userSelect: 'none',
            }}
          >
            <div
              onClick={() => setShowReasoning(!showReasoning)}
              style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', flex: 1 }}
            >
              <Space size={6}>
                <BulbOutlined style={{ fontSize: 13, color: '#B8A9C9' }} />
                <Text style={{ fontSize: 12, color: '#B8A9C9' }}>
                  分析过程 ({message.analysisTrace.length} 步)
                </Text>
              </Space>
              <CaretDownOutlined
                style={{
                  fontSize: 10,
                  color: '#B8A9C9',
                  marginLeft: 6,
                  transform: showReasoning ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: 'transform 0.2s',
                }}
              />
            </div>
            {/* Phase 2: 侧边抽屉入口 */}
            <Text
              style={{ fontSize: 11, color: '#B8A9C9', cursor: 'pointer', textDecoration: 'underline' }}
              onClick={() => onViewReasoning?.(message.analysisTrace ?? [])}
            >
              展开详情
            </Text>
          </div>
          {showReasoning && (
            <div style={{ marginTop: 8 }}>
              {message.analysisTrace.map((step, idx) => (
                <div
                  key={idx}
                  style={{
                    marginBottom: idx < message.analysisTrace!.length - 1 ? 8 : 0,
                    padding: '8px 10px',
                    borderRadius: 8,
                    background: isDark
                      ? 'rgba(184, 169, 201, 0.08)'
                      : 'rgba(184, 169, 201, 0.06)',
                    borderLeft: `2px solid ${['#B8A9C9', '#98D8C8', '#A8D8EA', '#F4B8C8', '#FAD4B8'][idx % 5]}`,
                  }}
                >
                  {/* Step 标签 */}
                  <Tag
                    color="purple"
                    style={{ fontSize: 10, margin: '0 0 4px 0', lineHeight: '16px', borderRadius: 4 }}
                  >
                    步骤 {step.stepNumber} · {step.status === 'completed' ? '已完成' : step.status === 'failed' ? '未完成' : '进行中'}
                  </Tag>

                  {step.inputSummary && (
                    <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 2 }}>
                      <Text style={{ fontSize: 12, color: isDark ? '#98D8C8' : '#389e0d', lineHeight: 1.6 }}>
                        {step.toolLabel}：{step.inputSummary}
                      </Text>
                    </div>
                  )}

                  {step.observationSummary && (
                    <div style={{ display: 'flex', alignItems: 'flex-start' }}>
                      <Text style={{
                        fontSize: 11,
                        color: isDark ? '#a0a0a0' : '#888',
                        lineHeight: 1.5,
                        maxHeight: 60,
                        overflow: 'hidden',
                      }}>
                        {step.observationSummary}
                      </Text>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 引用来源仅保留入口，完整卡片统一在证据面板展示。 */}
      {!isUser && message.sources && message.sources.length > 0 && (
        <div style={{
          marginTop: 12,
          paddingTop: 8,
          borderTop: `1px solid ${isDark ? colors.borderDark : colors.border}`,
        }}>
          <Button
            type="link"
            size="small"
            style={{ padding: 0 }}
            onClick={() => onViewEvidence?.(message.id)}
          >
            查看 {message.sources.length} 条证据
          </Button>
        </div>
      )}

      {/* 时间戳 */}
      <div style={{ marginTop: 6, textAlign: isUser ? 'right' : 'left' }}>
        <Text
          style={{
            fontSize: 11,
            color: isUser
              ? 'rgba(255,255,255,0.6)'
              : (isDark ? colors.textSecondaryDark : '#B0AABF'),
          }}
        >
          {formatTime(message.timestamp)}
        </Text>
      </div>
    </div>
  );

  return (
    <div
      style={{ position: 'relative' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <Bubble
        placement={isUser ? 'end' : 'start'}
        variant={isUser ? 'filled' : 'outlined'}
        shape="corner"
        avatar={
          isUser ? (
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 14,
                background: gradients.hero,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 2px 8px rgba(184, 169, 201, 0.3)',
              }}
            >
              <UserOutlined style={{ fontSize: 20, color: '#ffffff' }} />
            </div>
          ) : (
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 14,
                background: isDark
                  ? 'rgba(152, 216, 200, 0.12)'
                  : 'rgba(152, 216, 200, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <RobotOutlined style={{ fontSize: 20, color: isDark ? colors.accent : '#3D8B7A' }} />
            </div>
          )
        }
        content={messageContent}
        footer={footer}
        rootClassName="fade-in-up-smooth"
        styles={{
          content: {
            maxWidth: '70%',
            borderRadius: 20,
            padding: '12px 18px',
            background: isUser
              ? 'linear-gradient(135deg, #C4B5E0 0%, #B8A9C9 100%)'
              : (isDark
                ? colors.bgDarkCard
                : colors.bgCard),
            color: isUser ? '#ffffff' : (isDark ? colors.textPrimaryDark : colors.textPrimary),
            boxShadow: isUser
              ? '0 2px 8px rgba(184, 169, 201, 0.25)'
              : (isDark
                ? '0 1px 3px rgba(0,0,0,0.3)'
                : '0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)'),
            border: isUser ? 'none' : (isDark ? `1px solid ${colors.borderDark}` : `1px solid ${colors.border}`),
          },
        }}
      />
    </div>
  );
}

/** 格式化时间戳 */
function formatTime(ts: number): string {
  const d = new Date(ts);
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
}
