// -*- coding: utf-8 -*-
/**
 * 问答相关 API 封装
 * 对接 FastAPI 后端接口
 */

import apiClient from './api';
import type {
  QueryRequest,
  QueryResponse,
  RetrieveRequest,
  RetrieveResponse,
  CompaniesResponse,
  HealthResponse,
  AgentQueryRequest,
  AgentQueryResponse,
  SSEEvent,
} from '@/types/chat';
import { createLogger } from '@/utils/logger';

const logger = createLogger('chatService');

/** RAG 管道问答 */
export async function queryQuestion(params: QueryRequest): Promise<QueryResponse> {
  logger.info('POST /api/query:', { query: params.query.slice(0, 30), company: params.company_name, topN: params.top_n });
  const startTime = Date.now();
  const res = await apiClient.post<QueryResponse>('/api/query', params);
  logger.info('/api/query 响应:', { elapsed: Date.now() - startTime + 'ms', answerLen: res.data.answer?.length, sourcesCount: res.data.sources?.length });
  return res.data;
}

/** 仅检索（不生成） */
export async function retrieveDocuments(params: RetrieveRequest): Promise<RetrieveResponse> {
  logger.info('POST /api/retrieve:', { query: params.query.slice(0, 30) });
  const res = await apiClient.post<RetrieveResponse>('/api/retrieve', params);
  logger.info('/api/retrieve 响应:', { totalCount: res.data.total_count });
  return res.data;
}

/** 获取可用公司列表 */
export async function getCompanies(): Promise<CompaniesResponse> {
  logger.info('GET /api/companies');
  const res = await apiClient.get<CompaniesResponse>('/api/companies');
  logger.info('/api/companies 响应:', { count: res.data.total_count, companies: res.data.companies.map(c => c.name) });
  return res.data;
}

/** 健康检查 */
export async function checkHealth(): Promise<HealthResponse> {
  logger.debug('GET /api/health');
  const res = await apiClient.get<HealthResponse>('/api/health');
  return res.data;
}

/** Agent 模式问答 */
export async function agentQuery(params: AgentQueryRequest): Promise<AgentQueryResponse> {
  logger.info('POST /api/agent/query:', { query: params.query.slice(0, 30), maxSteps: params.max_steps });
  const startTime = Date.now();
  const res = await apiClient.post<AgentQueryResponse>('/api/agent/query', params);
  logger.info('/api/agent/query 响应:', { elapsed: Date.now() - startTime + 'ms', success: res.data.success, steps: res.data.total_steps });
  return res.data;
}

/** Agent SSE 流式推理 (Phase 2)
 *
 * 使用 EventSource API 接收 SSE 事件流，通过 onEvent 回调逐条推送
 *
 * 日志追踪点:
 *   [streamAgentQuery] CONNECT  - 建立 EventSource 连接
 *   [streamAgentQuery] OPEN     - 连接成功打开
 *   [streamAgentQuery] EVENT    - 收到事件（raw + parsed）
 *   [streamAgentQuery] ERROR    - 连接错误
 *   [streamAgentQuery] CLOSE    - 主动关闭连接
 *
 * @param query - 查询文本
 * @param options - 可选参数 (company_name, max_steps, temperature, conversation_id)
 * @param onEvent - 每收到一个事件时调用的回调
 * @returns 返回 EventSource 实例，调用方可通过 .close() 主动断开
 */
export function streamAgentQuery(
  query: string,
  options: {
    company_name?: string;
    max_steps?: number;
    temperature?: number;
    conversation_id?: string;
  },
  onEvent: (event: SSEEvent) => void,
  onError?: (error: Event) => void,
): EventSource {
  const connectStartTime = Date.now();
  let eventCount = 0;
  let streamCompleted = false; // 标记流是否正常完成（避免 onerror 误判）

  const params = new URLSearchParams();
  params.set('query', query);
  if (options.company_name) params.set('company_name', options.company_name);
  if (options.max_steps) params.set('max_steps', String(options.max_steps));
  if (options.temperature) params.set('temperature', String(options.temperature));
  if (options.conversation_id) params.set('conversation_id', options.conversation_id);

  const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
  const url = `${baseUrl}/api/agent/stream?${params.toString()}`;

  logger.info('建立 SSE EventSource 连接', { url, query: query.slice(0, 80), params: Object.fromEntries(params) });

  const es = new EventSource(url);

  // [streamAgentQuery] OPEN - 连接成功打开
  es.onopen = () => {
    const elapsed = Date.now() - connectStartTime;
    logger.info('SSE 连接已建立', { readyState: es.readyState, elapsedMs: elapsed });
  };

  // [streamAgentQuery] EVENT - 收到事件
  es.onmessage = (event: MessageEvent) => {
    eventCount++;
    const receiveTime = Date.now();

    logger.debug('SSE 消息到达', {
      eventCount,
      data: event.data,
      dataLength: event.data.length,
      readyState: es.readyState,
      elapsedMs: receiveTime - connectStartTime,
    });

    try {
      const data = JSON.parse(event.data) as SSEEvent;

      logger.debug('SSE 事件解析结果', {
        type: data.type,
        step: data.step,
        content: data.content ? data.content.slice(0, 120) : '(empty)',
        contentLength: data.content?.length ?? 0,
        action_input: data.action_input,
        timestamp: data.timestamp,
        total_steps: data.total_steps,
        total_elapsed_ms: data.total_elapsed_ms,
      });

      const typeColors: Record<string, string> = {
        thought: '#9B8EC4',
        action: '#52c41a',
        observation: '#1890ff',
        answer: '#faad14',
        error: '#ff4d4f',
        done: '#722ed1',
      };
      const color = typeColors[data.type] || '#666';
      console.log(
        `%c[${data.type.toUpperCase()}]%c step=${data.step}, content=${(data.content || '').slice(0, 60)}...`,
        `color: ${color}; font-weight: bold;`,
        'color: #666;',
      );

      // 标记流正常完成（answer 或 done 事件到达即为正常结束）
      if (data.type === 'answer' || data.type === 'done') {
        streamCompleted = true;
      }

      logger.debug('SSE 事件:', {
        type: data.type,
        step: data.step,
        contentLen: data.content?.length ?? 0,
        eventCount,
      });

      onEvent(data);
    } catch (e) {
      logger.error('SSE 解析失败:', e, event.data);
    }
  };

  // [streamAgentQuery] ERROR - 连接错误
  es.onerror = (error: Event) => {
    const elapsed = Date.now() - connectStartTime;

    // 如果流已正常完成，onerror 只是服务端关闭连接的正常行为，不报错
    if (streamCompleted) {
    logger.debug('SSE 流已正常完成，忽略 onerror', { eventCount, elapsedMs: elapsed });
      es.close();
      return;
    }

    logger.warn('SSE 连接错误', {
      readyState: es.readyState,
      eventCount,
      elapsedMs: elapsed,
    });

    onError?.(error);

    // EventSource 会自动尝试重连，closing 状态说明连接已结束
    if (es.readyState === EventSource.CLOSED) {
    logger.debug('EventSource 已关闭 (CLOSED state)', { eventCount, elapsedMs: elapsed });
      es.close();
    }
  };

  // 包装原始 close 方法以追踪主动关闭
  const originalClose = es.close.bind(es);
  es.close = () => {
    const elapsed = Date.now() - connectStartTime;
    logger.debug('主动关闭 EventSource', { eventCount, totalElapsedMs: elapsed });
    originalClose();
  };

  return es;
}

/** 将 EventSource readyState 转换为可读文本 */
function EventSourceReadyStateText(state: number): string {
  switch (state) {
    case EventSource.CONNECTING: return 'CONNECTING (0)';
    case EventSource.OPEN: return 'OPEN (1)';
    case EventSource.CLOSED: return 'CLOSED (2)';
    default: return `UNKNOWN (${state})`;
  }
}
