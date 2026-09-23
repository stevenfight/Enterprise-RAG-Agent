// -*- coding: utf-8 -*-
/** E1.3 研究任务页的 RED→GREEN 契约。 */
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const listResearchTasks = vi.hoisted(() => vi.fn());
const getResearchTaskReport = vi.hoisted(() => vi.fn());
const listResearchTaskConflicts = vi.hoisted(() => vi.fn());
const getResearchTaskConflictReviews = vi.hoisted(() => vi.fn());
const grantResearchTaskConflictApproval = vi.hoisted(() => vi.fn());
const resolveResearchTaskConflict = vi.hoisted(() => vi.fn());
const getResearchTaskReportSignoff = vi.hoisted(() => vi.fn());
const grantResearchTaskReportSignoffApproval = vi.hoisted(() => vi.fn());
const signoffResearchTaskReport = vi.hoisted(() => vi.fn());
const createResearchTask = vi.hoisted(() => vi.fn());
const approveResearchTaskSubmission = vi.hoisted(() => vi.fn());
const rejectResearchTaskSubmission = vi.hoisted(() => vi.fn());
const getResearchTaskExecutionSummary = vi.hoisted(() => vi.fn());
const retryFailedResearchTask = vi.hoisted(() => vi.fn());
const disposeLegacyRunningResearchTask = vi.hoisted(() => vi.fn());
const getCurrentResearchIdentity = vi.hoisted(() => vi.fn());
vi.mock('@/services/researchTaskService', () => ({ listResearchTasks, getResearchTaskReport, listResearchTaskConflicts, getResearchTaskConflictReviews, grantResearchTaskConflictApproval, resolveResearchTaskConflict, getResearchTaskReportSignoff, grantResearchTaskReportSignoffApproval, signoffResearchTaskReport, createResearchTask, approveResearchTaskSubmission, rejectResearchTaskSubmission, getResearchTaskExecutionSummary, retryFailedResearchTask, disposeLegacyRunningResearchTask }));
vi.mock('@/services/researchAuthService', () => ({ getCurrentResearchIdentity, RESEARCH_IDENTITY_CHANGED_EVENT: 'research-identity-changed' }));
vi.mock('@/components/dag/DagFlow', () => ({ default: () => <div data-testid="research-task-dag">DAG 空态</div> }));
vi.mock('@/components/chat/EvidenceContent', () => ({ default: () => <div data-testid="research-task-evidence">证据空态</div> }));
vi.mock('@/components/charts/ChartContainer', () => ({ default: () => <div data-testid="research-task-chart">图表空态</div> }));

import ResearchTasksPage from '@/pages/ResearchTasksPage';

describe('ResearchTasksPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    vi.resetAllMocks();
    getResearchTaskReport.mockRejectedValue({ response: { status: 404 } });
    listResearchTaskConflicts.mockResolvedValue([]);
    getResearchTaskConflictReviews.mockResolvedValue([]);
    getCurrentResearchIdentity.mockRejectedValue({ response: { status: 401 } });
    grantResearchTaskConflictApproval.mockReset();
    resolveResearchTaskConflict.mockReset();
    getResearchTaskReportSignoff.mockRejectedValue({ response: { status: 404 } });
    grantResearchTaskReportSignoffApproval.mockReset();
    signoffResearchTaskReport.mockReset();
    createResearchTask.mockReset();
    approveResearchTaskSubmission.mockReset();
    rejectResearchTaskSubmission.mockReset();
    getResearchTaskExecutionSummary.mockResolvedValue({ completed_step_ids: [], current_step_id: null, completed_at: null, failure_reason: null });
  });

  it('E-T12: 展示任务列表、只读详情和既有可视化组件的空态', async () => {
    listResearchTasks.mockResolvedValue([
      { task_id: 'task-a', run_id: 'research:task-a', status: 'running', revision: 2, dag_step_ids: [] },
      { task_id: 'task-b', run_id: 'research:task-b', status: 'paused', revision: 4, dag_step_ids: [] },
    ]);

    render(<ResearchTasksPage />);

    expect(await screen.findByRole('heading', { name: '研究任务' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /task-b/ }));

    expect(screen.getByText('research:task-b')).toBeInTheDocument();
    expect(screen.getAllByText('已暂停')).toHaveLength(2);
    expect(screen.getByTestId('research-task-dag')).toBeInTheDocument();
    expect(screen.getByTestId('research-task-evidence')).toBeInTheDocument();
    expect(screen.getByTestId('research-task-chart')).toBeInTheDocument();
  });

  it('E-T12: 无任务时不伪造研究详情', async () => {
    listResearchTasks.mockResolvedValue([]);

    render(<ResearchTasksPage />);

    expect(await screen.findByText('当前没有可查看的研究任务')).toBeInTheDocument();
    expect(screen.getByText('任务详情')).toBeInTheDocument();
    expect(screen.queryByText('任务 ID')).not.toBeInTheDocument();
    expect(screen.queryByText('报告详情')).not.toBeInTheDocument();
  });

  it('RTW-T01/T02: 以真实数量展示任务导航，并将当前任务放入详情区域', async () => {
    listResearchTasks.mockResolvedValue([
      { task_id: 'task-a', run_id: 'research:task-a', status: 'running', revision: 2, dag_step_ids: [] },
      { task_id: 'task-b', run_id: 'research:task-b', status: 'paused', revision: 4, dag_step_ids: [] },
    ]);

    render(<ResearchTasksPage />);

    expect(await screen.findByText('任务列表（2）')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: '任务导航' })).toHaveClass('research-task-list-panel');
    fireEvent.click(screen.getByRole('button', { name: /task-b/ }));
    expect(screen.getByRole('region', { name: '任务详情' })).toHaveClass('research-task-details');
  });

  it('RTW-T04: 报告证据和图表只说明服务端持久化内容', async () => {
    listResearchTasks.mockResolvedValue([
      { task_id: 'task-empty-report', run_id: 'research:task-empty-report', status: 'completed', revision: 3, dag_step_ids: [] },
    ]);

    render(<ResearchTasksPage />);

    expect(await screen.findByText('仅展示服务端已持久化的证据内容。')).toBeInTheDocument();
    expect(screen.getByText('仅展示服务端已持久化的图表内容。')).toBeInTheDocument();
  });

  it('E-T42: approver 只能为失败任务创建新的待审批重试任务', async () => {
    getCurrentResearchIdentity.mockResolvedValue({ username: 'approver', roles: ['approver'] });
    listResearchTasks.mockResolvedValue([{ task_id: 'task-failed', run_id: 'research:task-failed', status: 'failed', revision: 5, dag_step_ids: [] }]);
    retryFailedResearchTask.mockResolvedValue({ task_id: 'task-failed-retry-1', run_id: 'research:task-failed-retry-1', status: 'pending', revision: 0, dag_step_ids: [] });
    render(<ResearchTasksPage />);
    await userEvent.click(await screen.findByRole('button', { name: '创建重试任务' }));
    expect(retryFailedResearchTask).toHaveBeenCalledWith('task-failed', expect.objectContaining({ expected_revision: 5 }));
    expect(await screen.findByText('research:task-failed-retry-1')).toBeInTheDocument();
  });

  it('E-T43: approver 必须携带原因处置遗留 running 任务', async () => {
    getCurrentResearchIdentity.mockResolvedValue({ username: 'approver', roles: ['approver'] });
    listResearchTasks.mockResolvedValue([{ task_id: 'legacy-running', run_id: 'research:legacy-running', status: 'running', revision: 1, dag_step_ids: [] }]);
    disposeLegacyRunningResearchTask.mockResolvedValue({ task_id: 'legacy-running', run_id: 'research:legacy-running', status: 'failed', revision: 2, dag_step_ids: [] });
    render(<ResearchTasksPage />);
    await userEvent.click(await screen.findByRole('button', { name: '标记为失败并保留审计' }));
    expect(disposeLegacyRunningResearchTask).toHaveBeenCalledWith('legacy-running', expect.objectContaining({ expected_revision: 1, reason: expect.any(String) }));
  });

  it('E-T14: 展示任务的持久化报告版本和声明依据', async () => {
    listResearchTasks.mockResolvedValue([
      { task_id: 'task-report', run_id: 'research:task-report', status: 'completed', revision: 3, dag_step_ids: [] },
    ]);
    getResearchTaskReport.mockResolvedValue({
      report_id: 'report-1', task_id: 'task-report', plan_id: 'plan-1', report_version: 2,
      data_version: 'publication-1', review_status: 'pending_review',
      claims: [{ claim_id: 'claim-1', text: '营业收入增长。', support_kind: 'fact', fact_ids: ['fact-1'], calculation_ids: [], source_ids: ['source-1'], analysis_label: null }],
    });

    render(<ResearchTasksPage />);

    expect(await screen.findByText(/报告版本 2/)).toBeInTheDocument();
    expect(screen.getByText('营业收入增长。')).toBeInTheDocument();
    expect(screen.getByText('事实：fact-1')).toBeInTheDocument();
    expect(getResearchTaskReport).toHaveBeenCalledWith('task-report');
  });

  it('E-T35: 按服务端执行摘要展示 DAG 步骤、完成时间与失败原因', async () => {
    listResearchTasks.mockResolvedValue([
      { task_id: 'task-progress', run_id: 'research:task-progress', status: 'completed', revision: 2, dag_step_ids: ['plan', 'retrieve'] },
    ]);
    getResearchTaskExecutionSummary.mockResolvedValue({
      completed_step_ids: ['plan', 'retrieve'], current_step_id: null,
      completed_at: '2026-09-01 01:00:00', failure_reason: null,
    });

    render(<ResearchTasksPage />);

    expect(await screen.findByText('执行进度')).toBeInTheDocument();
    expect(await screen.findByText('已完成步骤：plan、retrieve')).toBeInTheDocument();
    expect(await screen.findByText('完成时间：2026-09-01 01:00:00')).toBeInTheDocument();
    expect(getResearchTaskExecutionSummary).toHaveBeenCalledWith('task-progress');
  });

  it('E-T35: 运行中任务每 5 秒刷新任务状态和执行摘要', async () => {
    vi.useFakeTimers();
    listResearchTasks.mockResolvedValue([{ task_id: 'task-live', run_id: 'research:task-live', status: 'running', revision: 1, dag_step_ids: ['plan'] }]);
    getResearchTaskExecutionSummary.mockResolvedValue({ completed_step_ids: [], current_step_id: 'plan', completed_at: null, failure_reason: null });

    render(<ResearchTasksPage />);
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(listResearchTasks).toHaveBeenCalledTimes(1);
    expect(getResearchTaskExecutionSummary).toHaveBeenCalledTimes(1);

    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });

    expect(listResearchTasks).toHaveBeenCalledTimes(2);
    expect(getResearchTaskExecutionSummary).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

  it('E-T39: 展示服务端持久化的 Agent、工具和脱敏结果轨迹', async () => {
    listResearchTasks.mockResolvedValue([
      { task_id: 'task-trace', run_id: 'research:task-trace', status: 'completed', revision: 2, dag_step_ids: ['retrieve'] },
    ]);
    getResearchTaskExecutionSummary.mockResolvedValue({
      completed_step_ids: ['retrieve'], current_step_id: null, completed_at: null, failure_reason: null,
      step_traces: [{ step_id: 'retrieve', agent_name: 'DataAgent', tool_names: ['retrieve'], status: 'succeeded', result_summary: { source_count: 1, answer_present: true } }],
    });

    render(<ResearchTasksPage />);

    expect(await screen.findByText('Agent / 工具结果轨迹')).toBeInTheDocument();
    expect(screen.getByText('DataAgent')).toBeInTheDocument();
    expect(screen.getByText('工具：retrieve')).toBeInTheDocument();
    expect(screen.getByText('结果：source_count=1，answer_present=true')).toBeInTheDocument();
  });

  it('E-T14: 无持久化报告时展示明确空态', async () => {
    listResearchTasks.mockResolvedValue([
      { task_id: 'task-empty-report', run_id: 'research:task-empty-report', status: 'completed', revision: 3, dag_step_ids: [] },
    ]);
    getResearchTaskReport.mockRejectedValue({ response: { status: 404 } });

    render(<ResearchTasksPage />);

    expect(await screen.findByText('该任务尚未生成可查看的持久化报告')).toBeInTheDocument();
  });

  it('FWC-T06: 没有选中任务时详情区域说明下一步', async () => {
    listResearchTasks.mockResolvedValue([]);

    render(<ResearchTasksPage />);

    expect(await screen.findByText('任务详情将在加载或选择任务后显示')).toBeInTheDocument();
  });

  it('E-RRD-2: 默认选中首个有报告任务并标记报告版本', async () => {
    listResearchTasks.mockResolvedValue([
      { task_id: 'task-without-report', run_id: 'research:task-without-report', status: 'failed', revision: 2, dag_step_ids: [] },
      { task_id: 'task-with-report', run_id: 'research:task-with-report', status: 'completed', revision: 3, dag_step_ids: [], report: { report_version: 1, review_status: 'pending_review' } },
    ]);
    getResearchTaskReport.mockResolvedValue({
      report_id: 'report-rrd', task_id: 'task-with-report', plan_id: 'plan-rrd', report_version: 1,
      data_version: 'facts-rrd', review_status: 'pending_review', claims: [],
    });

    render(<ResearchTasksPage />);

    expect(await screen.findByText(/报告版本 1/)).toBeInTheDocument();
    expect(screen.getByText('有报告 v1')).toBeInTheDocument();
    expect(getResearchTaskReport).toHaveBeenCalledWith('task-with-report');
  });

  it('E-T19: 展示任务范围内冲突和无冲突明确空态', async () => {
    listResearchTasks.mockResolvedValue([{ task_id: 'task-conflict', run_id: 'research:task-conflict', status: 'completed', revision: 3, dag_step_ids: [] }]);
    listResearchTaskConflicts.mockResolvedValue([{ conflict_id: 'conflict-1', status: 'pending_review', conflict_type: 'VALUE_CONFLICT', fact_ids: ['fact-a', 'fact-b'], context_version: 1 }]);
    getResearchTaskConflictReviews.mockResolvedValue([{ review_id: 'review-1', action: 'keep_pending', selected_fact_id: null, fact_ids: ['fact-a', 'fact-b'], actor: 'governance-operator', approval_id: null }]);
    render(<ResearchTasksPage />);
    expect(await screen.findByText('conflict-1')).toBeInTheDocument();
    expect(screen.getByText('事实：fact-a、fact-b')).toBeInTheDocument();
    expect(screen.getByText('保持未决')).toBeInTheDocument();
  });

  it('E-T23: approver 先取得服务端审批再提交批准裁决', async () => {
    listResearchTasks.mockResolvedValue([{ task_id: 'task-approve', run_id: 'research:task-approve', status: 'completed', revision: 3, dag_step_ids: [] }]);
    listResearchTaskConflicts.mockResolvedValue([{ conflict_id: 'conflict-approve', status: 'pending_review', conflict_type: 'VALUE_CONFLICT', fact_ids: ['fact-a', 'fact-b'], context_version: 1 }]);
    getCurrentResearchIdentity.mockResolvedValueOnce({ user_id: 'user-1', username: 'alice', roles: ['approver'] });
    grantResearchTaskConflictApproval.mockResolvedValueOnce({ approval_id: 'approval-1' });
    resolveResearchTaskConflict.mockResolvedValueOnce({ review_id: 'review-2', action: 'approve', selected_fact_id: 'fact-a', fact_ids: ['fact-a', 'fact-b'], actor: 'alice', approval_id: 'approval-1' });

    render(<ResearchTasksPage />);
    fireEvent.click(await screen.findByRole('button', { name: '批准 conflict-approve' }));

    expect(await screen.findByText('批准')).toBeInTheDocument();
    expect(grantResearchTaskConflictApproval).toHaveBeenCalledWith('task-approve', 'conflict-approve', { action: 'approve', selected_fact_id: 'fact-a', expires_in_seconds: 3600 });
    expect(resolveResearchTaskConflict).toHaveBeenCalledWith('task-approve', 'conflict-approve', { action: 'approve', selected_fact_id: 'fact-a', approval_id: 'approval-1' });
  });

  it('E-T32: researcher 可以提交任务，approver 可批准并启动待审批任务', async () => {
    const user = userEvent.setup();
    listResearchTasks.mockResolvedValue([{ task_id: 'task-submitted', run_id: 'research:task-submitted', status: 'pending', revision: 0, dag_step_ids: [], submission: { status: 'submitted', requester: 'alice', reviewer: null } }]);
    getCurrentResearchIdentity.mockResolvedValueOnce({ user_id: 'user-1', username: 'alice', roles: ['researcher', 'approver'] });
    createResearchTask.mockResolvedValueOnce({ task_id: 'task-new', run_id: 'research:task-new', status: 'pending', revision: 0, dag_step_ids: ['plan', 'retrieve', 'review', 'report'], submission: { status: 'submitted', requester: 'alice', reviewer: null } });
    approveResearchTaskSubmission.mockResolvedValueOnce({ task_id: 'task-submitted', run_id: 'research:task-submitted', status: 'running', revision: 1, dag_step_ids: [], submission: { status: 'approved', requester: 'alice', reviewer: 'alice' } });

    render(<ResearchTasksPage />);
    await user.type(await screen.findByRole('textbox', { name: '研究目标' }), '核对收入变化');
    await user.type(screen.getByRole('textbox', { name: '研究范围' }), '营业收入，净利润');
    await user.type(screen.getByRole('textbox', { name: '预算' }), '1.00');
    await user.click(screen.getByRole('button', { name: '提交研究任务' }));
    expect(createResearchTask).toHaveBeenCalledWith(expect.objectContaining({ objective: '核对收入变化', scope: ['营业收入', '净利润'], estimated_cost: '1.00', dag_step_ids: ['plan', 'retrieve', 'review', 'report'] }));

    await user.click(screen.getByRole('button', { name: /task-submitted/ }));
    await user.click(screen.getByRole('button', { name: '批准并执行' }));
    expect(approveResearchTaskSubmission).toHaveBeenCalledWith('task-submitted', expect.objectContaining({ expected_revision: 0 }));
  }, 15000);

  it('RTH-T01: 公共 HTTP 环境缺少 crypto.randomUUID 时仍可提交任务', async () => {
    const user = userEvent.setup();
    vi.stubGlobal('crypto', {});
    listResearchTasks.mockResolvedValue([]);
    getCurrentResearchIdentity.mockResolvedValueOnce({ user_id: 'user-1', username: 'alice', roles: ['researcher'] });
    createResearchTask.mockResolvedValueOnce({ task_id: 'task-http', run_id: 'research:task-http', status: 'pending', revision: 0, dag_step_ids: ['plan', 'retrieve', 'review', 'report'] });

    render(<ResearchTasksPage />);
    await user.type(await screen.findByRole('textbox', { name: '研究目标' }), '核对收入变化');
    await user.type(screen.getByRole('textbox', { name: '研究范围' }), '营业收入');
    await user.type(screen.getByRole('textbox', { name: '预算' }), '1.00');
    await user.click(screen.getByRole('button', { name: '提交研究任务' }));

    expect(createResearchTask).toHaveBeenCalledWith(expect.objectContaining({ task_id: expect.stringMatching(/^research-task-/) }));
  });

  it('RTH-T02: 展示服务端返回的任务提交失败原因', async () => {
    const user = userEvent.setup();
    listResearchTasks.mockResolvedValue([]);
    getCurrentResearchIdentity.mockResolvedValueOnce({ user_id: 'user-1', username: 'alice', roles: ['researcher'] });
    createResearchTask.mockRejectedValueOnce({ response: { data: { detail: { message: '计划必须同时提供 objective、scope 和 estimated_cost' } } } });

    render(<ResearchTasksPage />);
    await user.type(await screen.findByRole('textbox', { name: '研究目标' }), '核对收入变化');
    await user.type(screen.getByRole('textbox', { name: '研究范围' }), '营业收入');
    await user.type(screen.getByRole('textbox', { name: '预算' }), '1.00');
    await user.click(screen.getByRole('button', { name: '提交研究任务' }));

    expect(await screen.findByText('任务未提交：计划必须同时提供 objective、scope 和 estimated_cost')).toBeInTheDocument();
  });

  it('E-T23.1: approver 驳回冲突时不提交事实选择', async () => {
    listResearchTasks.mockResolvedValue([{ task_id: 'task-reject', run_id: 'research:task-reject', status: 'completed', revision: 3, dag_step_ids: [] }]);
    listResearchTaskConflicts.mockResolvedValue([{ conflict_id: 'conflict-reject', status: 'pending_review', conflict_type: 'VALUE_CONFLICT', fact_ids: ['fact-a', 'fact-b'], context_version: 1 }]);
    getCurrentResearchIdentity.mockResolvedValueOnce({ user_id: 'user-1', username: 'alice', roles: ['approver'] });
    grantResearchTaskConflictApproval.mockResolvedValueOnce({ approval_id: 'approval-reject-1' });
    resolveResearchTaskConflict.mockResolvedValueOnce({ review_id: 'review-reject-1', action: 'reject', selected_fact_id: null, fact_ids: ['fact-a', 'fact-b'], actor: 'alice', approval_id: 'approval-reject-1' });

    render(<ResearchTasksPage />);
    fireEvent.click(await screen.findByRole('button', { name: '驳回 conflict-reject' }));

    expect(await screen.findByText('驳回')).toBeInTheDocument();
    expect(grantResearchTaskConflictApproval).toHaveBeenCalledWith('task-reject', 'conflict-reject', { action: 'reject', selected_fact_id: null, expires_in_seconds: 3600 });
    expect(resolveResearchTaskConflict).toHaveBeenCalledWith('task-reject', 'conflict-reject', { action: 'reject', selected_fact_id: null, approval_id: 'approval-reject-1' });
  });

  it('E-T23: 普通用户没有裁决按钮', async () => {
    listResearchTasks.mockResolvedValue([{ task_id: 'task-view', run_id: 'research:task-view', status: 'completed', revision: 3, dag_step_ids: [] }]);
    listResearchTaskConflicts.mockResolvedValue([{ conflict_id: 'conflict-view', status: 'pending_review', conflict_type: 'VALUE_CONFLICT', fact_ids: ['fact-a', 'fact-b'], context_version: 1 }]);
    getCurrentResearchIdentity.mockResolvedValueOnce({ user_id: 'user-2', username: 'bob', roles: ['viewer'] });

    render(<ResearchTasksPage />);

    expect(await screen.findByText('conflict-view')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '批准 conflict-view' })).not.toBeInTheDocument();
    expect(screen.getByText('仅审批人可提交裁决。')).toBeInTheDocument();
  });

  it('E-T25: approver 先取得签发审批再正式签发，并显示服务端返回的状态', async () => {
    listResearchTasks.mockResolvedValue([{ task_id: 'task-sign', run_id: 'research:task-sign', status: 'completed', revision: 3, dag_step_ids: [] }]);
    getResearchTaskReport.mockResolvedValue({ report_id: 'report-sign', task_id: 'task-sign', plan_id: 'plan-1', report_version: 1, data_version: 'facts-1', review_status: 'pending_review', claims: [] });
    getCurrentResearchIdentity.mockResolvedValueOnce({ user_id: 'user-1', username: 'alice', roles: ['approver'] });
    grantResearchTaskReportSignoffApproval.mockResolvedValueOnce({ approval_id: 'signoff-approval-1' });
    signoffResearchTaskReport.mockResolvedValueOnce({ signoff_id: 'signoff-1', report_id: 'report-sign', approval_id: 'signoff-approval-1', actor: 'alice', signed_at: '2026-08-31T12:00:00+00:00' });

    render(<ResearchTasksPage />);
    fireEvent.click(await screen.findByRole('button', { name: '正式签发报告' }));

    expect(await screen.findByText('已正式签发')).toBeInTheDocument();
    expect(grantResearchTaskReportSignoffApproval).toHaveBeenCalledWith('task-sign', { expires_in_seconds: 3600 });
    expect(signoffResearchTaskReport).toHaveBeenCalledWith('task-sign', { approval_id: 'signoff-approval-1' });
  });

  it('E-T25: 普通用户不能看到报告签发入口', async () => {
    listResearchTasks.mockResolvedValue([{ task_id: 'task-sign-view', run_id: 'research:task-sign-view', status: 'completed', revision: 3, dag_step_ids: [] }]);
    getResearchTaskReport.mockResolvedValue({ report_id: 'report-view', task_id: 'task-sign-view', plan_id: 'plan-1', report_version: 1, data_version: 'facts-1', review_status: 'pending_review', claims: [] });
    getCurrentResearchIdentity.mockResolvedValueOnce({ user_id: 'user-2', username: 'bob', roles: ['viewer'] });

    render(<ResearchTasksPage />);

    expect(await screen.findByText(/报告版本 1/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '正式签发报告' })).not.toBeInTheDocument();
  });

  it('E-T28.1: 登录完成后无需刷新页面即可同步审批人签发入口', async () => {
    listResearchTasks.mockResolvedValue([{ task_id: 'task-login-sync', run_id: 'research:task-login-sync', status: 'completed', revision: 3, dag_step_ids: [] }]);
    getResearchTaskReport.mockResolvedValue({ report_id: 'report-login-sync', task_id: 'task-login-sync', plan_id: 'plan-1', report_version: 1, data_version: 'facts-1', review_status: 'pending_review', claims: [] });
    getCurrentResearchIdentity.mockRejectedValueOnce({ response: { status: 401 } });

    render(<ResearchTasksPage />);
    expect(await screen.findByText(/报告版本 1/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '正式签发报告' })).not.toBeInTheDocument();

    getCurrentResearchIdentity.mockResolvedValueOnce({ user_id: 'user-1', username: 'alice', roles: ['approver'] });
    window.dispatchEvent(new Event('research-identity-changed'));

    expect(await screen.findByRole('button', { name: '正式签发报告' })).toBeInTheDocument();
  });

  it('E-T26: 审批人可用键盘触发签发，失败信息会被辅助技术明确通知', async () => {
    const user = userEvent.setup();
    listResearchTasks.mockResolvedValue([{ task_id: 'task-sign-error', run_id: 'research:task-sign-error', status: 'completed', revision: 3, dag_step_ids: [] }]);
    getResearchTaskReport.mockResolvedValue({ report_id: 'report-sign-error', task_id: 'task-sign-error', plan_id: 'plan-1', report_version: 1, data_version: 'facts-1', review_status: 'pending_review', claims: [] });
    getCurrentResearchIdentity.mockResolvedValueOnce({ user_id: 'user-1', username: 'alice', roles: ['approver'] });
    grantResearchTaskReportSignoffApproval.mockRejectedValueOnce(new Error('approval failed'));

    render(<ResearchTasksPage />);
    const signoffButton = await screen.findByRole('button', { name: '正式签发报告' });
    signoffButton.focus();
    await user.keyboard('{Enter}');

    expect(await screen.findByRole('alert')).toHaveTextContent('报告未正式签发，请确认当前会话角色、冲突裁决和服务端审批状态。');
    expect(grantResearchTaskReportSignoffApproval).toHaveBeenCalledWith('task-sign-error', { expires_in_seconds: 3600 });
  });
});
