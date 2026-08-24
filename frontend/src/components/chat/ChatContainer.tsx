// -*- coding: utf-8 -*-
/**
 * 对话容器组件 - 基于 @ant-design/x Conversations + Welcome
 * 会话列表 + 消息列表 + 输入框
 */

import { useRef, useEffect } from 'react';
import { Conversations, Welcome } from '@ant-design/x';
import {
  PlusOutlined,
  MessageOutlined,
  BulbOutlined,
} from '@ant-design/icons';
import { chatStore, selectCurrentMessages } from '@/stores/chatStore';
import { useTheme } from '@/hooks/useTheme';
import { colors, gradients } from '@/styles/theme';
import type { ReasoningStep } from '@/types/chat';
import MessageBubble from './MessageBubble';
import ChatInput from './ChatInput';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import { createLogger } from '@/utils/logger';

const logger = createLogger('ChatContainer');

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
  /** 欢迎页快捷指令（点击直接发送） */
  quickCommands?: string[];
}

export default function ChatContainer({ onSend, isLoading = false, isAgentMode = false, fillInputText, onFillInputTextConsumed, onViewReasoning, quickCommands }: ChatContainerProps) {
  const { isDark } = useTheme();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const sessions = chatStore((s) => s.sessions);
  const currentSessionId = chatStore((s) => s.currentSessionId);
  const currentMessages = chatStore(selectCurrentMessages);
  const createNewSession = chatStore((s) => s.createNewSession);
  const switchSession = chatStore((s) => s.switchSession);
  const deleteSession = chatStore((s) => s.deleteSession);

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

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* 左侧: 会话列表 - LobeChat 风格 */}
      <div
        style={{
          width: 260,
          borderRight: isDark ? `1px solid ${colors.borderDark}` : `1px solid ${colors.border}`,
          display: 'flex',
          flexDirection: 'column',
          background: isDark ? colors.bgDarkSidebar : colors.bgCard,
          flexShrink: 0,
        }}
      >
        {/* 会话列表（含新建对话入口） */}
        <div style={{ flex: 1, overflow: 'auto', padding: '12px 8px' }}>
          <Conversations
            items={sessions.map((session) => ({
              key: session.id,
              label: (
                <span style={{ fontSize: 13, fontWeight: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}>
                  {session.title}
                </span>
              ),
            }))}
            activeKey={currentSessionId}
            onActiveChange={(key) => switchSession(key as string)}
            menu={(item) => ({
              items: [{ key: 'delete', label: '删除对话', danger: true }],
              onClick: ({ key }) => {
                if (key === 'delete') {
                  deleteSession(item.key);
                }
              },
            })}
            creation={{ label: '新建对话', icon: <PlusOutlined />, onClick: createNewSession }}
          />
        </div>
      </div>

      {/* 右侧: 消息区域 + 输入框 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: isDark ? colors.chatAreaDark : colors.chatAreaLight }}>
        {/* 消息列表 */}
        <div
          className="chat-scroll-area"
          style={{ flex: 1, overflow: 'auto', padding: '24px 0' }}
        >
          {currentMessages.length === 0 && !isLoading && (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                gap: 28,
                padding: '0 24px',
              }}
            >
              <Welcome
                variant="borderless"
                icon={
                  <div
                    style={{
                      width: 80,
                      height: 80,
                      borderRadius: 24,
                      background: gradients.hero,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      boxShadow: '0 8px 32px rgba(184, 169, 201, 0.25)',
                    }}
                  >
                    <MessageOutlined style={{ fontSize: 36, color: '#ffffff' }} />
                  </div>
                }
                title="您好，我是企业财务年报分析助手"
                description="请输入您的问题，或点击下方示例快速开始"
              />

              {/* 快捷指令区：点击直接发送问题 */}
              {quickCommands && quickCommands.length > 0 && (
                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 10,
                    justifyContent: 'center',
                    maxWidth: 560,
                  }}
                >
                  {quickCommands.map((command) => (
                    <button
                      key={command}
                      type="button"
                      className="quick-command-chip"
                      onClick={() => onSend(command)}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        padding: '8px 14px',
                        borderRadius: 999,
                        fontSize: 13,
                        lineHeight: 1.4,
                        cursor: 'pointer',
                        border: `1px solid ${isDark ? 'rgba(184,169,201,0.5)' : 'rgba(184,169,201,0.6)'}`,
                        background: isDark ? 'rgba(184,169,201,0.12)' : 'rgba(184,169,201,0.08)',
                        color: isDark ? '#e8e8e8' : '#3d3554',
                        transition: 'transform 0.2s, box-shadow 0.2s, background 0.2s',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.transform = 'translateY(-2px)';
                        e.currentTarget.style.boxShadow = '0 4px 12px rgba(184,169,201,0.35)';
                        e.currentTarget.style.background = isDark ? 'rgba(184,169,201,0.2)' : 'rgba(184,169,201,0.16)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.transform = 'translateY(0)';
                        e.currentTarget.style.boxShadow = 'none';
                        e.currentTarget.style.background = isDark ? 'rgba(184,169,201,0.12)' : 'rgba(184,169,201,0.08)';
                      }}
                    >
                      <BulbOutlined style={{ fontSize: 12, color: '#B8A9C9' }} />
                      <span>{command}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {currentMessages.map((msg, idx) => {
            const isLast = idx === currentMessages.length - 1;
            // Agent SSE 流式模式下，最后一条 assistant 消息正在接收数据时显示打字机光标
            const isStreaming = isAgentMode && isLoading && isLast && msg.role === 'assistant';
            return (
              <MessageBubble
                key={msg.id}
                message={msg}
                onViewReasoning={onViewReasoning}
                isStreaming={isStreaming}
              />
            );
          })}

          {isLoading && !isAgentMode && <LoadingSpinner text="正在思考中..." />}

          <div ref={messagesEndRef} style={{ height: 8 }} />
        </div>

        {/* 输入区域 */}
        <div style={{ padding: '0 20px 20px', flexShrink: 0 }}>
          <ChatInput onSend={onSend} disabled={isLoading} fillText={fillInputText} onFillTextConsumed={onFillInputTextConsumed} />
        </div>
      </div>
    </div>
  );
}
