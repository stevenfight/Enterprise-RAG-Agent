// -*- coding: utf-8 -*-
/**
 * 消息气泡组件 - 马卡龙渐变风格
 * 用户消息右对齐紫粉渐变，AI 消息左对齐玻璃拟态，系统消息居中
 */

import { useState } from 'react';
import { Typography, Space, Tag } from 'antd';
import {
  UserOutlined,
  RobotOutlined,
  WarningOutlined,
  BulbOutlined,
  ToolOutlined,
  EyeOutlined,
  CaretDownOutlined,
} from '@ant-design/icons';
import type { Message } from '@/types/chat';
import SourceCard from './SourceCard';
import { useTheme } from '@/hooks/useTheme';
import { colors, gradients, monoFont } from '@/styles/theme';
import { createLogger } from '@/utils/logger';

const logger = createLogger('MessageBubble');
const { Text } = Typography;

interface MessageBubbleProps {
  message: Message;
  onViewReasoning?: (steps: Message['reasoningChain']) => void;
}

export default function MessageBubble({ message, onViewReasoning }: MessageBubbleProps) {
  logger.renderStart({ role: message.role, id: message.id, contentLen: message.content.length, sourcesCount: message.sources?.length });
  const { isDark } = useTheme();
  const [showReasoning, setShowReasoning] = useState(false); // Agent 推理链路展开/收起
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

  return (
    <div
      className="fade-in-up"
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        margin: '10px 0',
        padding: '0 16px',
      }}
    >
      {/* AI 头像 (左侧) */}
      {!isUser && (
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 12,
            background: isDark
              ? 'rgba(152, 216, 200, 0.15)'
              : 'rgba(152, 216, 200, 0.2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginRight: 12,
            flexShrink: 0,
          }}
        >
          <RobotOutlined style={{ fontSize: 18, color: isDark ? colors.accent : '#5BAA98' }} />
        </div>
      )}

      {/* 消息内容 */}
      <div
        style={{
          maxWidth: '70%',
          background: isUser
            ? gradients.bubbleUser
            : (isDark
              ? 'rgba(37, 34, 54, 0.7)'
              : 'rgba(255, 255, 255, 0.7)'),
          backdropFilter: isUser ? 'none' : 'blur(8px)',
          color: isUser ? '#ffffff' : (isDark ? colors.textPrimaryDark : colors.textPrimary),
          borderRadius: isUser ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
          padding: '12px 16px',
          boxShadow: isUser
            ? '0 3px 12px rgba(184, 169, 201, 0.3)'
            : `0 2px 12px ${isDark ? 'rgba(0,0,0,0.2)' : 'rgba(184, 169, 201, 0.1)'}`,
          border: isUser ? 'none' : `1px solid ${isDark ? '#3A3550' : '#E8E3EF'}`,
          wordBreak: 'break-word',
        }}
      >
        {/* 消息文本 */}
        <div
          style={{
            fontSize: 14,
            lineHeight: 1.7,
            fontFamily: 'inherit',
          }}
          className="markdown-body"
          dangerouslySetInnerHTML={{
            __html: isUser
              ? message.content
              : formatMarkdown(message.content),
          }}
        />

        {/* Agent 推理链路 (Phase 2 SSE) */}
        {!isUser && message.reasoningChain && message.reasoningChain.length > 0 && (
          <div style={{
            marginTop: 10,
            paddingTop: 8,
            borderTop: `1px solid ${isDark ? '#3A3550' : '#E8E3EF'}`,
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
                    推理过程 ({message.reasoningChain.length} 步)
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
                onClick={() => {
                  if (message.reasoningChain) {
                    onViewReasoning?.(message.reasoningChain);
                  }
                }}
              >
                展开详情
              </Text>
            </div>
            {showReasoning && (
              <div style={{ marginTop: 8 }}>
                {message.reasoningChain.map((step, idx) => (
                  <div
                    key={idx}
                    style={{
                      marginBottom: idx < message.reasoningChain!.length - 1 ? 8 : 0,
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
                      步骤 {step.step_number}
                    </Tag>

                    {/* Thought */}
                    <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 2 }}>
                      <BulbOutlined style={{
                        fontSize: 11,
                        color: '#B8A9C9',
                        marginTop: 2,
                        marginRight: 6,
                        flexShrink: 0,
                      }} />
                      <Text style={{ fontSize: 12, color: isDark ? '#bbb' : '#555', lineHeight: 1.6 }}>
                        {step.thought}
                      </Text>
                    </div>

                    {/* Action */}
                    {step.action && (
                      <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 2 }}>
                        <ToolOutlined style={{
                          fontSize: 11,
                          color: '#52c41a',
                          marginTop: 2,
                          marginRight: 6,
                          flexShrink: 0,
                        }} />
                        <Text style={{ fontSize: 12, color: isDark ? '#98D8C8' : '#389e0d', lineHeight: 1.6 }}>
                          调用工具: {step.action}
                        </Text>
                      </div>
                    )}

                    {/* Observation */}
                    {step.observation && (
                      <div style={{ display: 'flex', alignItems: 'flex-start' }}>
                        <EyeOutlined style={{
                          fontSize: 11,
                          color: '#1890ff',
                          marginTop: 2,
                          marginRight: 6,
                          flexShrink: 0,
                        }} />
                        <Text style={{
                          fontSize: 11,
                          color: isDark ? '#a0a0a0' : '#888',
                          lineHeight: 1.5,
                          maxHeight: 60,
                          overflow: 'hidden',
                        }}>
                          {step.observation.length > 200
                            ? step.observation.slice(0, 200) + '...'
                            : step.observation}
                        </Text>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 多 Agent 运行状态 (Phase 10) */}
        {!isUser && message.agentRun?.isMultiAgent && (
          <div style={{
            marginTop: 10,
            paddingTop: 8,
            borderTop: `1px solid ${isDark ? '#3A3550' : '#E8E3EF'}`,
          }}>
            <Space size={6} style={{ marginBottom: 8 }}>
              <RobotOutlined style={{ fontSize: 13, color: '#B8A9C9' }} />
              <Tag color="geekblue" style={{ fontSize: 11, margin: 0, lineHeight: '16px', borderRadius: 4 }}>
                多 Agent
              </Tag>
              <Text style={{ fontSize: 12, color: '#B8A9C9' }}>
                已注册 {message.agentRun.registeredAgents.length} 个 Worker
              </Text>
            </Space>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {message.agentRun.workers.map((worker, idx) => (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '6px 10px',
                    borderRadius: 8,
                    background: isDark
                      ? 'rgba(184, 169, 201, 0.08)'
                      : 'rgba(184, 169, 201, 0.06)',
                  }}
                >
                  <Space size={6}>
                    <Text style={{ fontSize: 12, color: isDark ? '#ddd' : '#444' }}>{worker.agent}</Text>
                    <Tag
                      color={worker.done ? (worker.success === false ? 'red' : 'green') : 'processing'}
                      style={{ fontSize: 10, margin: 0, lineHeight: '14px', borderRadius: 4 }}
                    >
                      {worker.done ? (worker.success === false ? '失败' : '完成') : '运行中'}
                    </Tag>
                  </Space>
                  <Text style={{ fontSize: 11, color: '#B8A9C9' }}>
                    {worker.steps.length} 步{worker.elapsed_ms != null ? ` · ${(worker.elapsed_ms / 1000).toFixed(1)}s` : ''}
                  </Text>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 引用来源 */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div style={{
            marginTop: 12,
            paddingTop: 8,
            borderTop: `1px solid ${isDark ? '#3A3550' : '#E8E3EF'}`,
          }}>
            <Text style={{
              fontSize: 12,
              color: isDark ? colors.textSecondaryDark : colors.textSecondary,
              marginBottom: 4,
              display: 'block',
            }}>
              引用来源
            </Text>
            {message.sources.map((source) => (
              <SourceCard key={source.index} source={source} />
            ))}
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

      {/* 用户头像 (右侧) */}
      {isUser && (
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 12,
            background: gradients.hero,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginLeft: 12,
            flexShrink: 0,
            boxShadow: '0 2px 8px rgba(184, 169, 201, 0.35)',
          }}
        >
          <UserOutlined style={{ fontSize: 18, color: '#ffffff' }} />
        </div>
      )}
    </div>
  );
}

/** 格式化时间戳 */
function formatTime(ts: number): string {
  const d = new Date(ts);
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
}

/** Markdown -> HTML 转换 (Phase 2 增强版，支持图片、链接、标题、列表、表格) */
function formatMarkdown(text: string): string {
  const lines = text.split('\n');
  const result: string[] = [];
  let inTable = false;
  let tableRows: string[] = [];
  let isHeader = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // 检测表格行：以 | 开头和结尾
    if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
      if (!inTable) {
        inTable = true;
        tableRows = [];
        isHeader = true;
      }
      const cells = line.trim().split('|').filter(c => c.trim() !== '');
      // 跳过分隔行（如 |---|---| ）
      if (cells.every(c => /^[-:]+$/.test(c.trim()))) {
        isHeader = false;
        continue;
      }
      if (isHeader) {
        tableRows.push(`<thead><tr>${cells.map(c => `<th style="padding:6px 12px;border:1px solid #ddd;background:#f5f3f9;text-align:left;font-size:13px">${processInline(c.trim())}</th>`).join('')}</tr></thead>`);
      } else {
        tableRows.push(`<tr>${cells.map(c => `<td style="padding:6px 12px;border:1px solid #ddd;font-size:13px">${processInline(c.trim())}</td>`).join('')}</tr>`);
      }
      continue;
    }

    // 表格结束，输出表格 HTML
    if (inTable && tableRows.length > 0) {
      const bodyRows = tableRows.slice(1).join('');
      result.push(`<table style="border-collapse:collapse;width:100%;margin:8px 0;border:1px solid #ddd;border-radius:6px;overflow:hidden">${tableRows[0]}<tbody>${bodyRows}</tbody></table>`);
      inTable = false;
      tableRows = [];
      isHeader = false;
    }

    if (line.trim() === '') {
      result.push('<br/>');
      continue;
    }

    result.push(processLine(line));
  }

  // 结尾处理未关闭的表格
  if (inTable && tableRows.length > 0) {
    const bodyRows = tableRows.slice(1).join('');
    result.push(`<table style="border-collapse:collapse;width:100%;margin:8px 0;border:1px solid #ddd;border-radius:6px;overflow:hidden">${tableRows[0]}<tbody>${bodyRows}</tbody></table>`);
  }

  return result.join('\n');
}

/** 处理单行（非表格行） */
function processLine(line: string): string {
  let html = line;

  // 图片语法 ![alt](url) -- 必须在链接之前处理
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
    return `<img src="${url}" alt="${alt}" style="max-width:100%;border-radius:8px;margin:8px 0;" />`;
  });

  // 链接语法 [text](url)
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, text, url) => {
    if (match.includes('<img')) return match;
    return `<a href="${url}" target="_blank" rel="noopener noreferrer" style="color:#5BAA98;text-decoration:underline;">${text}</a>`;
  });

  // 标题语法 ### / ## / #
  html = html.replace(/^### (.+)$/gm, '<h4 style="margin:8px 0 4px;font-size:14px;font-weight:600;">$1</h4>');
  html = html.replace(/^## (.+)$/gm, '<h3 style="margin:10px 0 6px;font-size:15px;font-weight:700;">$1</h3>');
  html = html.replace(/^# (.+)$/gm, '<h2 style="margin:12px 0 8px;font-size:16px;font-weight:700;">$1</h2>');

  html = processInline(html);

  return html;
}

/** 处理行内格式：粗体、斜体、代码 */
function processInline(html: string): string {
  // 粗体 **text**
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // 斜体 *text*
  html = html.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');
  // 行内代码 `code`
  html = html.replace(/`(.+?)`/g, `<code style="background:rgba(0,0,0,0.06);padding:2px 6px;border-radius:3px;font-family:${monoFont};font-size:13px">$1</code>`);
  return html;
}
