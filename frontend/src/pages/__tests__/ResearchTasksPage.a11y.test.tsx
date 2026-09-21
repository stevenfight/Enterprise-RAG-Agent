// -*- coding: utf-8 -*-
/** E1.10 研究任务工作台的可访问性语义契约。 */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

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

vi.mock('@/services/researchTaskService', () => ({
  listResearchTasks,
  getResearchTaskReport,
  listResearchTaskConflicts,
  getResearchTaskConflictReviews,
  grantResearchTaskConflictApproval,
  resolveResearchTaskConflict,
  getResearchTaskReportSignoff,
  grantResearchTaskReportSignoffApproval,
  signoffResearchTaskReport,
  createResearchTask,
  approveResearchTaskSubmission,
  rejectResearchTaskSubmission,
  getResearchTaskExecutionSummary,
  retryFailedResearchTask,
  disposeLegacyRunningResearchTask,
}));
vi.mock('@/services/researchAuthService', () => ({
  getCurrentResearchIdentity,
  RESEARCH_IDENTITY_CHANGED_EVENT: 'research-identity-changed',
}));
vi.mock('@/components/dag/DagFlow', () => ({ default: () => <div data-testid="research-task-dag" /> }));
vi.mock('@/components/chat/EvidenceContent', () => ({ default: () => <div data-testid="research-task-evidence" /> }));
vi.mock('@/components/charts/ChartContainer', () => ({ default: () => <div data-testid="research-task-chart" /> }));

import ResearchTasksPage from '@/pages/ResearchTasksPage';

describe('ResearchTasksPage a11y', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    listResearchTasks.mockResolvedValue([]);
    getResearchTaskReport.mockRejectedValue({ response: { status: 404 } });
    listResearchTaskConflicts.mockResolvedValue([]);
    getResearchTaskConflictReviews.mockResolvedValue([]);
    getResearchTaskExecutionSummary.mockResolvedValue({ completed_step_ids: [], current_step_id: null, completed_at: null, failure_reason: null });
    getResearchTaskReportSignoff.mockRejectedValue({ response: { status: 404 } });
    getCurrentResearchIdentity.mockRejectedValue({ response: { status: 401 } });
  });

  it('E1.10: 暴露带名称的主地标、工作台区域和刷新操作', async () => {
    render(<ResearchTasksPage />);

    const main = await screen.findByRole('main', { name: '研究任务' });
    expect(main).toContainElement(screen.getByRole('region', { name: '研究任务工作台' }));
    expect(screen.getByRole('button', { name: '刷新' })).toBeInTheDocument();
    expect(screen.getByText('当前没有可查看的研究任务')).toBeInTheDocument();
  });

  it('E1.10: 提交任务进入加载态时仍保持稳定的操作名称', async () => {
    const user = userEvent.setup();
    getCurrentResearchIdentity.mockResolvedValue({ username: 'alice', roles: ['researcher'] });
    createResearchTask.mockImplementation(() => new Promise(() => {}));

    render(<ResearchTasksPage />);

    await user.type(await screen.findByRole('textbox', { name: '研究目标' }), '核对收入变化');
    await user.type(screen.getByRole('textbox', { name: '研究范围' }), '营业收入');
    await user.type(screen.getByRole('textbox', { name: '预算' }), '1.00');
    await user.click(screen.getByRole('button', { name: '提交研究任务' }));

    expect(screen.getByRole('button', { name: '提交研究任务' })).toBeInTheDocument();
  });

  it('E1.10: 审批任务进入加载态时仍保持稳定的操作名称', async () => {
    const user = userEvent.setup();
    getCurrentResearchIdentity.mockResolvedValue({ username: 'alice', roles: ['approver'] });
    listResearchTasks.mockResolvedValue([{ task_id: 'submitted-task', run_id: 'research:submitted-task', status: 'pending', revision: 0, dag_step_ids: [], submission: { status: 'submitted', requester: 'bob', reviewer: null } }]);
    approveResearchTaskSubmission.mockImplementation(() => new Promise(() => {}));

    render(<ResearchTasksPage />);

    await user.click(await screen.findByRole('button', { name: '批准并执行' }));

    expect(screen.getByRole('button', { name: '批准并执行' })).toBeInTheDocument();
  });

  it('E1.10: 重试任务进入加载态时仍保持稳定的操作名称', async () => {
    const user = userEvent.setup();
    getCurrentResearchIdentity.mockResolvedValue({ username: 'alice', roles: ['approver'] });
    listResearchTasks.mockResolvedValue([{ task_id: 'failed-task', run_id: 'research:failed-task', status: 'failed', revision: 2, dag_step_ids: [] }]);
    retryFailedResearchTask.mockImplementation(() => new Promise(() => {}));

    render(<ResearchTasksPage />);

    await user.click(await screen.findByRole('button', { name: '创建重试任务' }));

    expect(screen.getByRole('button', { name: '创建重试任务' })).toBeInTheDocument();
  });

  it('E1.10: 遗留任务处置进入加载态时仍保持稳定的操作名称', async () => {
    const user = userEvent.setup();
    getCurrentResearchIdentity.mockResolvedValue({ username: 'alice', roles: ['approver'] });
    listResearchTasks.mockResolvedValue([{ task_id: 'legacy-task', run_id: 'research:legacy-task', status: 'running', revision: 1, dag_step_ids: [] }]);
    disposeLegacyRunningResearchTask.mockImplementation(() => new Promise(() => {}));

    render(<ResearchTasksPage />);

    await user.click(await screen.findByRole('button', { name: '标记为失败并保留审计' }));

    expect(screen.getByRole('button', { name: '标记为失败并保留审计' })).toBeInTheDocument();
  });

  it('E1.10: 报告签发进入加载态时仍保持稳定的操作名称', async () => {
    const user = userEvent.setup();
    getCurrentResearchIdentity.mockResolvedValue({ username: 'alice', roles: ['approver'] });
    listResearchTasks.mockResolvedValue([{ task_id: 'report-task', run_id: 'research:report-task', status: 'completed', revision: 3, dag_step_ids: [] }]);
    getResearchTaskReport.mockResolvedValue({ report_id: 'report-1', task_id: 'report-task', plan_id: 'plan-1', report_version: 1, data_version: 'facts-1', review_status: 'pending_review', claims: [] });
    grantResearchTaskReportSignoffApproval.mockImplementation(() => new Promise(() => {}));

    render(<ResearchTasksPage />);

    await user.click(await screen.findByRole('button', { name: '正式签发报告' }));

    expect(screen.getByRole('button', { name: '正式签发报告' })).toBeInTheDocument();
  });
});
