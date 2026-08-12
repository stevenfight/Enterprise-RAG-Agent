// -*- coding: utf-8 -*-
/**
 * 对话相关 TypeScript 类型定义
 * 与后端 FastAPI Pydantic 模型一一对应
 */

/** 来源信息 (对应后端 SourceInfo) */
export interface SourceInfo {
  index: number;
  source_file: string;
  pages: number[];
  company_name: string;
  scores: Record<string, number>;
}

/** RAG 问答请求 (对应后端 QueryRequest) */
export interface QueryRequest {
  query: string;
  company_name?: string | null;
  top_n?: number;
  conversation_id?: string | null;
  enable_rewrite?: boolean;
}

/** RAG 问答响应 (对应后端 QueryResponse) */
export interface QueryResponse {
  answer: string;
  sources: SourceInfo[];
  query: string;
  company_name: string | null;
  retrieved_count: number;
  context_used_count?: number | null;
  processing_time: number;
  conversation_id?: string | null;
}

/** 仅检索请求 (对应后端 RetrieveRequest) */
export interface RetrieveRequest {
  query: string;
  company_name?: string | null;
  top_n?: number;
}

/** 单条检索结果 (对应后端 RetrieveResultItem) */
export interface RetrieveResultItem {
  parent_text: string;
  source_file: string;
  pages: number[];
  company_name: string;
  child_id?: string | null;
  parent_key?: string | null;
  scores: Record<string, number>;
}

/** 仅检索响应 (对应后端 RetrieveResponse) */
export interface RetrieveResponse {
  results: RetrieveResultItem[];
  query: string;
  company_name: string | null;
  total_count: number;
}

/** 公司信息 (对应后端 CompanyInfo) */
export interface CompanyInfo {
  name: string;
  display_name: string;
}

/** 公司列表响应 (对应后端 CompaniesResponse) */
export interface CompaniesResponse {
  companies: CompanyInfo[];
  total_count: number;
}

/** 健康检查响应 (对应后端 HealthResponse) */
export interface HealthResponse {
  status: string;
  vector_db_dir: string;
  rag_generator_loaded: boolean;
  agent_loaded: boolean;
}

/** Agent 单步推理信息 (对应后端 AgentStepInfo) */
export interface AgentStepInfo {
  step_number: number;
  thought: string;
  action?: string | null;
  action_input?: Record<string, unknown> | null;
  observation?: string | null;
  elapsed_ms: number;
}

/** Agent 查询请求 (对应后端 AgentQueryRequest) */
export interface AgentQueryRequest {
  query: string;
  max_steps?: number;
  temperature?: number;
  conversation_id?: string | null;
}

/** Agent 查询响应 (对应后端 AgentQueryResponse) */
export interface AgentQueryResponse {
  answer: string;
  success: boolean;
  reasoning_chain: AgentStepInfo[];
  total_steps: number;
  total_elapsed_ms: number;
  forced_stop: boolean;
  reflection?: Record<string, unknown> | null;
  error?: string | null;
}

/** 前端对话消息 */
export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  sources?: SourceInfo[];
  reasoningChain?: AgentStepInfo[];
  error?: string;
}

/** 前端会话 */
export interface Session {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: Message[];
}

/** Agent 推理步骤（Phase 2 思维链抽屉使用） */
export interface ReasoningStep {
  step_number: number;
  thought: string;
  action?: string | null;
  action_input?: Record<string, unknown> | null;
  observation?: string | null;
  elapsed_ms: number;
}

/** SSE 流式事件类型 (Phase 2) */
export type SSEEventType = 'connected' | 'thought' | 'action' | 'observation' | 'answer' | 'error' | 'done';

/** SSE 流式事件 (Phase 2) */
export interface SSEEvent {
  type: SSEEventType;
  step?: number;
  content?: string;
  action_input?: Record<string, unknown> | null;
  timestamp?: number;
  total_steps?: number;
  total_elapsed_ms?: number;
  /** 是否因达到步数上限而强制终止 */
  forced_stop?: boolean;
}

/** 知识库文档 (对应后端 KnowledgeDocument) */
export interface KnowledgeDocument {
  filename: string;
  size: number;
  size_mb: number;
  upload_time: string;
  indexed: boolean;
}

/** 系统状态数据 (对应后端 SystemStatusResponse) */
export interface SystemStatusData {
  model: {
    name: string;
    status: string;
    temperature: number;
    max_steps: number;
  };
  vector_db: {
    path: string;
    status: string;
    company_count: number;
  };
  memory: {
    long_term_enabled: boolean;
    working_memory_limit: number;
  };
  monitoring: {
    langsmith_available: boolean;
    langsmith_project: string;
    langsmith_endpoint: string;
  };
  tools: Record<string, boolean>;
}
