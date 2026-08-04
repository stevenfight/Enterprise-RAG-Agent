// -*- coding: utf-8 -*-
/**
 * 对话状态管理 (Zustand)
 * 管理会话列表、消息、加载状态，支持 localStorage 持久化
 *
 * 注意: 不提供 getCurrentSession/getCurrentMessages 方法,
 * 因为作为 Zustand selector 使用时会每次返回新引用导致无限 re-render。
 * 组件中应使用 selectCurrentMessages selector 直接派生。
 */

import { create } from 'zustand';
import type { Message, Session, SourceInfo, AgentStepInfo } from '@/types/chat';
import { createLogger } from '@/utils/logger';

const logger = createLogger('chatStore');
const STORAGE_KEY = 'chat-sessions';

/** 生成唯一 ID */
function genId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

/** 创建空会话 */
function createSession(title = '新对话'): Session {
  return {
    id: genId(),
    title,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [],
  };
}

/** 从 localStorage 恢复会话 */
function loadSessions(): Session[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Session[];
      if (Array.isArray(parsed) && parsed.length > 0) {
        logger.info('从 localStorage 恢复会话:', { count: parsed.length });
        return parsed;
      }
    }
  } catch (err) {
    logger.warn('localStorage 解析失败:', err);
  }
  logger.info('创建默认会话');
  return [createSession()];
}

/** 保存会话到 localStorage */
function saveSessions(sessions: Session[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch {
    // localStorage 不可用时忽略
  }
}

interface ChatState {
  /** 会话列表 */
  sessions: Session[];
  /** 当前会话 ID */
  currentSessionId: string;
  /** 是否正在等待 AI 响应 */
  isLoading: boolean;

  /** 新建会话 */
  createNewSession: () => void;
  /** 切换会话 */
  switchSession: (sessionId: string) => void;
  /** 删除会话 */
  deleteSession: (sessionId: string) => void;
  /** 清空当前会话消息 */
  clearCurrentMessages: () => void;

  /** 添加用户消息 */
  addUserMessage: (content: string) => void;
  /** 添加 AI 消息 */
  addAssistantMessage: (content: string, sources?: SourceInfo[], reasoningChain?: AgentStepInfo[]) => void;
  /** 更新最后一条 AI 消息（Phase 2: SSE 流式推理实时追加 reasoningChain） */
  updateLastAssistantMessage: (partial: { content?: string; reasoningChain?: AgentStepInfo[] }) => void;
  /** 添加错误消息 */
  addErrorMessage: (error: string) => void;
  /** 设置加载状态 */
  setLoading: (loading: boolean) => void;
}

const _initialSessions = loadSessions();

export const chatStore = create<ChatState>((set) => ({
  sessions: _initialSessions,
  currentSessionId: _initialSessions[0]?.id || '',
  isLoading: false,

  createNewSession: () => {
    const newSession = createSession();
    set((state) => {
      const sessions = [newSession, ...state.sessions];
      saveSessions(sessions);
      return { sessions, currentSessionId: newSession.id };
    });
  },

  switchSession: (sessionId) => {
    set({ currentSessionId: sessionId });
  },

  deleteSession: (sessionId) => {
    set((state) => {
      const sessions = state.sessions.filter((s) => s.id !== sessionId);
      if (sessions.length === 0) {
        const newSession = createSession();
        saveSessions([newSession]);
        return { sessions: [newSession], currentSessionId: newSession.id };
      }
      saveSessions(sessions);
      const currentSessionId =
        state.currentSessionId === sessionId ? sessions[0].id : state.currentSessionId;
      return { sessions, currentSessionId };
    });
  },

  clearCurrentMessages: () => {
    set((state) => {
      const sessions = state.sessions.map((s) =>
        s.id === state.currentSessionId
          ? { ...s, messages: [], updatedAt: Date.now() }
          : s,
      );
      saveSessions(sessions);
      return { sessions };
    });
  },

  addUserMessage: (content) => {
    const message: Message = {
      id: genId(),
      role: 'user',
      content,
      timestamp: Date.now(),
    };
    set((state) => {
      const sessions = state.sessions.map((s) => {
        if (s.id !== state.currentSessionId) return s;
        const title =
          s.messages.length === 0
            ? content.slice(0, 30) + (content.length > 30 ? '...' : '')
            : s.title;
        return {
          ...s,
          title,
          messages: [...s.messages, message],
          updatedAt: Date.now(),
        };
      });
      saveSessions(sessions);
      return { sessions };
    });
  },

  addAssistantMessage: (content, sources, reasoningChain) => {
    const message: Message = {
      id: genId(),
      role: 'assistant',
      content,
      timestamp: Date.now(),
      sources,
      reasoningChain,
    };
    set((state) => {
      const sessions = state.sessions.map((s) =>
        s.id === state.currentSessionId
          ? { ...s, messages: [...s.messages, message], updatedAt: Date.now() }
          : s,
      );
      saveSessions(sessions);
      return { sessions };
    });
  },

  addErrorMessage: (error) => {
    const message: Message = {
      id: genId(),
      role: 'system',
      content: error,
      timestamp: Date.now(),
      error,
    };
    set((state) => {
      const sessions = state.sessions.map((s) =>
        s.id === state.currentSessionId
          ? { ...s, messages: [...s.messages, message], updatedAt: Date.now() }
          : s,
      );
      saveSessions(sessions);
      return { sessions };
    });
  },

  updateLastAssistantMessage: (partial) => {
    set((state) => {
      const sessions = state.sessions.map((s) => {
        if (s.id !== state.currentSessionId) return s;
        const messages = [...s.messages];
        // 从后往前找最后一条 assistant 消息
        for (let i = messages.length - 1; i >= 0; i--) {
          if (messages[i].role === 'assistant') {
            messages[i] = {
              ...messages[i],
              ...(partial.content !== undefined ? { content: partial.content } : {}),
              ...(partial.reasoningChain !== undefined ? { reasoningChain: partial.reasoningChain } : {}),
            };
            break;
          }
        }
        return { ...s, messages, updatedAt: Date.now() };
      });
      saveSessions(sessions);
      return { sessions };
    });
  },

  setLoading: (loading) => {
    set({ isLoading: loading });
  },
}));

/**
 * 稳定的 selector: 从 sessions 中派生当前会话的消息
 * 使用 shallow 比较避免无限 re-render
 */
export function selectCurrentMessages(state: ChatState): Message[] {
  const session = state.sessions.find((s) => s.id === state.currentSessionId);
  return session?.messages || [];
}
