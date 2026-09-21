// -*- coding: utf-8 -*-
/** E1.3 研究任务列表的只读 API 封装。 */
import apiClient from './api';

export interface ResearchTaskSnapshot {
  task_id: string;
  run_id: string;
  status: string;
  revision: number;
  dag_step_ids: string[];
  submission?: {
    status: 'submitted' | 'approved' | 'rejected';
    requester: string;
    reviewer: string | null;
  };
  report?: {
    report_version: number;
    review_status: string;
  };
}

export interface ResearchTaskExecutionSummary {
  completed_step_ids: string[];
  current_step_id: string | null;
  completed_at: string | null;
  failure_reason: string | null;
  step_traces?: ResearchTaskStepTrace[];
}

export interface ResearchTaskStepTrace {
  step_id: string;
  agent_name: string;
  tool_names: string[];
  status: string;
  result_summary: Record<string, string | number | boolean>;
}

interface ResearchTaskListResponse {
  items: ResearchTaskSnapshot[];
}

export interface ResearchReportClaim {
  claim_id: string;
  text: string;
  support_kind: string;
  fact_ids: string[];
  calculation_ids: string[];
  source_ids: string[];
  analysis_label: string | null;
}

export interface ResearchTaskReport {
  report_id: string;
  task_id: string;
  plan_id: string;
  report_version: number;
  data_version: string;
  review_status: string;
  claims: ResearchReportClaim[];
}

export interface ResearchTaskConflict {
  conflict_id: string;
  status: string;
  conflict_type: string;
  fact_ids: string[];
  context_version: number;
}

export interface ResearchTaskConflictReview {
  review_id: string;
  action: string;
  selected_fact_id: string | null;
  fact_ids: string[];
  actor: string;
  approval_id: string | null;
}

export type ResearchTaskConflictAction = 'approve' | 'reject' | 'keep_pending';

export interface ResearchTaskConflictApproval {
  approval_id: string;
  status?: string;
}

export interface ResearchTaskReportSignoff {
  signoff_id: string;
  report_id: string;
  approval_id: string;
  actor: string;
  signed_at: string;
}

/** 读取 E1.2 列表端点，不在浏览器侧推测或写入任务状态。 */
export async function listResearchTasks(): Promise<ResearchTaskSnapshot[]> {
  const response = await apiClient.get<ResearchTaskListResponse>('/api/research/tasks');
  return response.data.items;
}

/** 研究员提交任务；任务需经审批后才能进入运行状态。 */
export async function createResearchTask(input: {
  task_id: string;
  dag_step_ids: string[];
  objective: string;
  scope: string[];
  estimated_cost: string;
  step_bindings?: Record<string, { agent_name: string; tool_names: string[] }>;
}): Promise<ResearchTaskSnapshot> {
  const response = await apiClient.post<ResearchTaskSnapshot>('/api/research/tasks', input);
  return response.data;
}

/** 审批人批准已提交任务，并由服务端启动其既有执行状态机。 */
export async function approveResearchTaskSubmission(
  taskId: string,
  input: { expected_revision: number; command_id: string },
): Promise<ResearchTaskSnapshot> {
  const response = await apiClient.post<ResearchTaskSnapshot>(`/api/research/tasks/${encodeURIComponent(taskId)}/submission/approve`, input);
  return response.data;
}

/** 审批人驳回已提交任务；任务保留待开始状态以便审计查询。 */
export async function rejectResearchTaskSubmission(
  taskId: string,
  input: { expected_revision: number; command_id: string },
): Promise<ResearchTaskSnapshot> {
  const response = await apiClient.post<ResearchTaskSnapshot>(`/api/research/tasks/${encodeURIComponent(taskId)}/submission/reject`, input);
  return response.data;
}

/** 仅 approver 可从失败任务复制计划，创建新的待审批重试任务。 */
export async function retryFailedResearchTask(
  taskId: string,
  input: { expected_revision: number; command_id: string },
): Promise<ResearchTaskSnapshot> {
  const response = await apiClient.post<ResearchTaskSnapshot>(`/api/research/tasks/${encodeURIComponent(taskId)}/retry`, input);
  return response.data;
}

/** 仅 approver 可处置无执行证据的遗留运行任务；服务端保留失败原因与审计记录。 */
export async function disposeLegacyRunningResearchTask(
  taskId: string,
  input: { expected_revision: number; command_id: string; reason: string },
): Promise<ResearchTaskSnapshot> {
  const response = await apiClient.post<ResearchTaskSnapshot>(`/api/research/tasks/${encodeURIComponent(taskId)}/legacy-disposition`, input);
  return response.data;
}

/** 读取任务最新持久化报告；后端 404 明确表示该任务当前尚无报告。 */
export async function getResearchTaskReport(taskId: string): Promise<ResearchTaskReport> {
  const response = await apiClient.get<ResearchTaskReport>(`/api/research/tasks/${encodeURIComponent(taskId)}/report`);
  return response.data;
}

/** 读取服务端从 C0 审计记录汇总的执行进度，不在浏览器侧推测步骤结果。 */
export async function getResearchTaskExecutionSummary(taskId: string): Promise<ResearchTaskExecutionSummary> {
  const response = await apiClient.get<ResearchTaskExecutionSummary>(`/api/research/tasks/${encodeURIComponent(taskId)}/execution`);
  return response.data;
}

/** 读取当前报告的持久化签发状态；404 明确表示尚未签发。 */
export async function getResearchTaskReportSignoff(taskId: string): Promise<ResearchTaskReportSignoff> {
  const response = await apiClient.get<ResearchTaskReportSignoff>(`/api/research/tasks/${encodeURIComponent(taskId)}/report/signoff`);
  return response.data;
}

/** 由服务端按当前会话、报告与任务快照授予一次性正式签发审批。 */
export async function grantResearchTaskReportSignoffApproval(
  taskId: string,
  input: { expires_in_seconds: number },
): Promise<{ approval_id: string }> {
  const response = await apiClient.post<{ approval_id: string }>(`/api/research/tasks/${encodeURIComponent(taskId)}/report/signoff/approvals`, input);
  return response.data;
}

/** 消费刚刚取得的绑定审批，将当前不可变报告正式签发。 */
export async function signoffResearchTaskReport(
  taskId: string,
  input: { approval_id: string },
): Promise<ResearchTaskReportSignoff> {
  const response = await apiClient.post<ResearchTaskReportSignoff>(`/api/research/tasks/${encodeURIComponent(taskId)}/report/signoff`, input);
  return response.data;
}

/** 仅读取当前任务可信上下文内的冲突，不在浏览器侧尝试裁决。 */
export async function listResearchTaskConflicts(taskId: string): Promise<ResearchTaskConflict[]> {
  const response = await apiClient.get<{ items: ResearchTaskConflict[] }>(`/api/research/tasks/${encodeURIComponent(taskId)}/conflicts`);
  return response.data.items;
}

/** 读取单个冲突的只追加裁决历史。 */
export async function getResearchTaskConflictReviews(taskId: string, conflictId: string): Promise<ResearchTaskConflictReview[]> {
  const response = await apiClient.get<{ items: ResearchTaskConflictReview[] }>(`/api/research/tasks/${encodeURIComponent(taskId)}/conflicts/${encodeURIComponent(conflictId)}/reviews`);
  return response.data.items;
}

/** 由服务端以当前会话身份、任务与冲突上下文生成一次性审批。 */
export async function grantResearchTaskConflictApproval(
  taskId: string,
  conflictId: string,
  input: { action: Exclude<ResearchTaskConflictAction, 'keep_pending'>; selected_fact_id: string | null; expires_in_seconds: number },
): Promise<ResearchTaskConflictApproval> {
  const response = await apiClient.post<ResearchTaskConflictApproval>(`/api/research/tasks/${encodeURIComponent(taskId)}/conflicts/${encodeURIComponent(conflictId)}/approvals`, input);
  return response.data;
}

/** 提交冲突裁决；审批 ID 只能来自刚刚由服务端授予的审批响应。 */
export async function resolveResearchTaskConflict(
  taskId: string,
  conflictId: string,
  input: { action: ResearchTaskConflictAction; selected_fact_id?: string | null; approval_id?: string },
): Promise<ResearchTaskConflictReview> {
  const response = await apiClient.post<ResearchTaskConflictReview>(`/api/research/tasks/${encodeURIComponent(taskId)}/conflicts/${encodeURIComponent(conflictId)}/reviews`, input);
  return response.data;
}
