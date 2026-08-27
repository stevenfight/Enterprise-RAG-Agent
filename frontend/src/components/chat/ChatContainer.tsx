// -*- coding: utf-8 -*-
/**
 * 对话容器组件 - 基于 @ant-design/x Conversations + Welcome
 * 会话列表 + 消息列表 + 输入框
 */

import { useRef, useEffect, useState } from 'react';
import { Conversations } from '@ant-design/x';
import { Button, Drawer } from 'antd';
import {
  PlusOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons';
import { chatStore, selectCurrentMessages } from '@/stores/chatStore';
import { useTheme } from '@/hooks/useTheme';
import { colors } from '@/styles/theme';
import type { AnalysisTraceStep, VerifiedComparison } from '@/types/chat';
import MessageBubble from './MessageBubble';
import ChatInput from './ChatInput';
import ResearchWelcome from './ResearchWelcome';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import { createLogger } from '@/utils/logger';
import { getPreferredScrollBehavior } from '@/utils/motionPreference';

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
  onViewReasoning?: (steps: AnalysisTraceStep[]) => void;
  /** 查看指定回答的完整证据 */
  onViewEvidence?: (messageId: string, sourceIndex?: number) => void;
  /** 基于已核验比较打开成果浏览。 */
  onViewCharts?: (criteria: Pick<VerifiedComparison, 'metric_key' | 'fiscal_year' | 'unit'>) => void;
  /** 欢迎页快捷指令（点击直接发送） */
  quickCommands?: string[];
  /** 当前运行期研究范围，仅用于空会话启动页展示 */
  companyName?: string;
  /** 当前运行期研究模式，仅用于空会话启动页展示 */
  researchMode?: 'rag' | 'agent';
  /** 由页面统一控制的窄屏会话抽屉状态 */
  mobileSessionsOpen?: boolean;
  /** 由页面统一切换窄屏会话抽屉 */
  onMobileSessionsOpenChange?: (open: boolean) => void;
}

export default function ChatContainer({ onSend, isLoading = false, isAgentMode = false, fillInputText, onFillInputTextConsumed, onViewReasoning, onViewEvidence, onViewCharts, quickCommands, companyName, researchMode, mobileSessionsOpen, onMobileSessionsOpenChange }: ChatContainerProps) {
  const { isDark } = useTheme();
  const [localMobileSessionsOpen, setLocalMobileSessionsOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const sessions = chatStore((s) => s.sessions);
  const currentSessionId = chatStore((s) => s.currentSessionId);
  const currentMessages = chatStore(selectCurrentMessages);
  const createNewSession = chatStore((s) => s.createNewSession);
  const switchSession = chatStore((s) => s.switchSession);
  const deleteSession = chatStore((s) => s.deleteSession);
  const isMobileSessionsOpen = mobileSessionsOpen ?? localMobileSessionsOpen;
  const setMobileSessionsOpen = onMobileSessionsOpenChange ?? setLocalMobileSessionsOpen;

  logger.renderStart({
    isLoading,
    sessionsCount: sessions.length,
    currentSessionId,
    messagesCount: currentMessages.length,
  });

  // 自动滚动到最新消息
  // 减少动画偏好下降级为即时滚动(CP-R12)
  useEffect(() => {
    if (currentMessages.length === 0 && !isLoading) return;
    logger.debug('自动滚动到最新消息, messagesCount=' + currentMessages.length);
    messagesEndRef.current?.scrollIntoView({ behavior: getPreferredScrollBehavior() });
  }, [currentMessages.length, isLoading]);

  const renderConversations = (onSelected?: () => void) => (
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
      onActiveChange={(key) => {
        if (isLoading) return;
        switchSession(key as string);
        onSelected?.();
      }}
      menu={(item) => ({
        items: [{ key: 'delete', label: '删除对话', danger: true }],
        onClick: ({ key }) => {
          if (key === 'delete' && !isLoading) {
            deleteSession(item.key);
          }
        },
      })}
      creation={{
        label: '新建对话',
        icon: <PlusOutlined />,
        onClick: () => {
          if (isLoading) return;
          createNewSession();
          onSelected?.();
        },
      }}
    />
  );

  return (
    <div className="chat-container" style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* 左侧: 会话列表 - LobeChat 风格 */}
      <div
        className="chat-session-sidebar"
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
          <div aria-disabled={isLoading} style={isLoading ? { pointerEvents: 'none', opacity: 0.55 } : undefined}>
            {renderConversations()}
          </div>
        </div>
      </div>

      {/* 右侧: 消息区域 + 输入框 */}
      <div className="chat-main-canvas chat-main-canvas--research" style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: isDark ? colors.chatAreaDark : colors.chatAreaLight }}>
        <Button
          className="chat-mobile-session-trigger"
          type="text"
          icon={<UnorderedListOutlined />}
          aria-label="打开会话列表"
          disabled={isLoading}
          onClick={() => setMobileSessionsOpen(true)}
        >
          会话
        </Button>
        {/* 消息列表 */}
        <div
          className="chat-scroll-area chat-scroll-area--refined"
          style={{ flex: 1, overflow: 'auto', padding: '24px 0' }}
        >
          {currentMessages.length === 0 && !isLoading && (
            <ResearchWelcome quickCommands={quickCommands} companyName={companyName} mode={researchMode} onSend={onSend} />
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
                onViewEvidence={onViewEvidence}
                onViewCharts={onViewCharts}
                isStreaming={isStreaming}
              />
            );
          })}

          {isLoading && !isAgentMode && <LoadingSpinner text="正在思考中..." />}

          <div ref={messagesEndRef} style={{ height: 8 }} />
        </div>

        {/* 输入区域 */}
        <div className="chat-input-area" style={{ padding: '0 20px 20px', flexShrink: 0 }}>
          <ChatInput onSend={onSend} disabled={isLoading} fillText={fillInputText} onFillTextConsumed={onFillInputTextConsumed} />
        </div>
      </div>

      <Drawer
        title="会话列表"
        placement="left"
        size={300}
        open={isMobileSessionsOpen}
        onClose={() => setMobileSessionsOpen(false)}
      >
        {renderConversations(() => setMobileSessionsOpen(false))}
      </Drawer>
    </div>
  );
}
