// -*- coding: utf-8 -*-
/**
 * 对话容器组件 - 马卡龙风格
 * 消息列表 + 输入框 + 会话列表
 */

import { useRef, useEffect } from 'react';
import { Typography, Button, Popconfirm } from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  ClearOutlined,
  MessageOutlined,
} from '@ant-design/icons';
import { chatStore, selectCurrentMessages } from '@/stores/chatStore';
import { useTheme } from '@/hooks/useTheme';
import { colors, gradients } from '@/styles/theme';
import type { ReasoningStep } from '@/types/chat';
import MessageBubble from './MessageBubble';
import ChatInput from './ChatInput';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import dayjs from 'dayjs';
import { createLogger } from '@/utils/logger';

const logger = createLogger('ChatContainer');
const { Text } = Typography;

interface ChatContainerProps {
  /** 发送消息回调 */
  onSend: (content: string) => void;
  /** 是否正在加载 */
  isLoading?: boolean;
  /** Agent 模式（Phase 2: 实时推理消息替代加载气泡） */
  isAgentMode?: boolean;
  /** 外部填入输入框的文本（示例问题点击时） */
  fillInputText?: string;
  /** fillInputText 使用后回调 */
  onFillInputTextConsumed?: () => void;
  /** Phase 2: 查看推理详情回调 */
  onViewReasoning?: (steps: ReasoningStep[]) => void;
}

export default function ChatContainer({ onSend, isLoading = false, isAgentMode = false, fillInputText, onFillInputTextConsumed, onViewReasoning }: ChatContainerProps) {
  const { isDark } = useTheme();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const sessions = chatStore((s) => s.sessions);
  const currentSessionId = chatStore((s) => s.currentSessionId);
  const currentMessages = chatStore(selectCurrentMessages);
  const createNewSession = chatStore((s) => s.createNewSession);
  const switchSession = chatStore((s) => s.switchSession);
  const deleteSession = chatStore((s) => s.deleteSession);
  const clearCurrentMessages = chatStore((s) => s.clearCurrentMessages);

  logger.renderStart({
    isLoading,
    sessionsCount: sessions.length,
    currentSessionId,
    messagesCount: currentMessages.length,
  });

  // 自动滚动到最新消息
  useEffect(() => {
    logger.debug('自动滚动到最新消息, messagesCount=' + currentMessages.length);
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentMessages.length, isLoading]);

  const borderColor = isDark ? '#3A3550' : '#E8E3EF';
  const sessionActiveBg = isDark ? 'rgba(184, 169, 201, 0.12)' : 'rgba(184, 169, 201, 0.1)';
  const sessionActiveBorder = isDark ? colors.primaryLight : colors.primary;
  const sessionActiveText = isDark ? colors.primaryLight : colors.primary;
  const sessionNormalText = isDark ? colors.textSecondaryDark : colors.textSecondary;

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* 左侧: 会话列表 */}
      <div
        style={{
          width: 240,
          borderRight: `1px solid ${borderColor}`,
          display: 'flex',
          flexDirection: 'column',
          background: isDark ? colors.bgDarkSidebar : colors.bgSidebar,
          flexShrink: 0,
        }}
      >
        {/* 新建会话按钮 */}
        <div style={{ padding: '12px 12px 8px' }}>
          <Button
            type="primary"
            ghost
            icon={<PlusOutlined />}
            block
            onClick={createNewSession}
            style={{
              borderRadius: 10,
              height: 38,
            }}
          >
            新建对话
          </Button>
        </div>

        {/* 会话列表 */}
        <div style={{ flex: 1, overflow: 'auto', padding: '0 8px' }}>
          {sessions.map((session) => (
            <div
              key={session.id}
              onClick={() => switchSession(session.id)}
              className="card-hover"
              style={{
                padding: '10px 12px',
                borderRadius: 10,
                marginBottom: 4,
                cursor: 'pointer',
                background:
                  session.id === currentSessionId
                    ? sessionActiveBg
                    : 'transparent',
                borderLeft:
                  session.id === currentSessionId
                    ? `3px solid ${sessionActiveBorder}`
                    : '3px solid transparent',
                transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text
                  ellipsis
                  style={{
                    fontSize: 13,
                    flex: 1,
                    color:
                      session.id === currentSessionId
                        ? sessionActiveText
                        : sessionNormalText,
                    fontWeight: session.id === currentSessionId ? 600 : 400,
                  }}
                >
                  <MessageOutlined style={{ marginRight: 6 }} />
                  {session.title}
                </Text>
                <Popconfirm
                  title="删除此对话？"
                  onConfirm={(e) => {
                    e?.stopPropagation();
                    deleteSession(session.id);
                  }}
                  okText="删除"
                  cancelText="取消"
                >
                  <DeleteOutlined
                    style={{ fontSize: 12, color: colors.textSecondary, marginLeft: 4 }}
                    onClick={(e) => e.stopPropagation()}
                  />
                </Popconfirm>
              </div>
              <Text
                type="secondary"
                style={{ fontSize: 11, marginLeft: 20 }}
              >
                {dayjs(session.updatedAt).format('HH:mm')}
              </Text>
            </div>
          ))}
        </div>

        {/* 底部: 清空对话 */}
        {currentMessages.length > 0 && (
          <div
            style={{
              padding: '8px 12px',
              borderTop: `1px solid ${borderColor}`,
              background: isDark
                ? 'rgba(37, 34, 54, 0.6)'
                : 'rgba(255, 255, 255, 0.6)',
              backdropFilter: 'blur(8px)',
            }}
          >
            <Popconfirm
              title="清空当前对话的所有消息？"
              onConfirm={clearCurrentMessages}
              okText="清空"
              cancelText="取消"
            >
              <Button
                type="text"
                icon={<ClearOutlined />}
                danger
                size="small"
                block
              >
                清空对话
              </Button>
            </Popconfirm>
          </div>
        )}
      </div>

      {/* 右侧: 消息区域 + 输入框 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* 消息列表 */}
        <div
          className="chat-scroll-area"
          style={{ flex: 1, overflow: 'auto', padding: '16px 0' }}
        >
          {currentMessages.length === 0 && !isLoading && (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                opacity: 0.7,
              }}
            >
              <div
                style={{
                  width: 72,
                  height: 72,
                  borderRadius: 20,
                  background: gradients.hero,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: 20,
                  boxShadow: '0 4px 16px rgba(184, 169, 201, 0.3)',
                }}
              >
                <MessageOutlined style={{ fontSize: 32, color: '#ffffff' }} />
              </div>
              <Text style={{ fontSize: 16, color: isDark ? colors.textPrimaryDark : colors.textPrimary }}>
                您好，我是企业财务年报分析助手
              </Text>
              <Text style={{ fontSize: 14, color: isDark ? colors.textSecondaryDark : colors.textSecondary, marginTop: 8 }}>
                请输入您的问题，或点击下方示例快速开始
              </Text>
            </div>
          )}

          {currentMessages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} onViewReasoning={onViewReasoning} />
          ))}

          {/* Agent 模式下用实时推理消息替代加载气泡 */}
          {isLoading && !isAgentMode && <LoadingSpinner text="正在思考中..." />}

          <div ref={messagesEndRef} />
        </div>

        {/* 输入区域 */}
        <div style={{ padding: '0 16px 16px', flexShrink: 0 }}>
          <ChatInput onSend={onSend} disabled={isLoading} fillText={fillInputText} onFillTextConsumed={onFillInputTextConsumed} />
        </div>
      </div>
    </div>
  );
}
