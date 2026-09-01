// -*- coding: utf-8 -*-
/** E1.3 研究任务工作台：只读查看已持久化的任务快照与交付空态。 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Descriptions, Empty, Form, Input, List, Space, Spin, Tag, Typography } from 'antd';
import { ExperimentOutlined, ReloadOutlined } from '@ant-design/icons';

import { PageHeader, PageShell } from '@/components/common/PageShell';
import DagFlow, { type DagNode } from '@/components/dag/DagFlow';
import EvidenceContent from '@/components/chat/EvidenceContent';
import ChartContainer from '@/components/charts/ChartContainer';
import type { ChartData } from '@/types/chart';
import {
  getResearchTaskReport,
  getResearchTaskExecutionSummary,
  approveResearchTaskSubmission,
  createResearchTask,
  getResearchTaskReportSignoff,
  getResearchTaskConflictReviews,
  grantResearchTaskConflictApproval,
  grantResearchTaskReportSignoffApproval,
  listResearchTaskConflicts,
  resolveResearchTaskConflict,
  signoffResearchTaskReport,
  type ResearchTaskConflictAction,
  type ResearchTaskConflict,
  type ResearchTaskConflictReview,
  listResearchTasks,
  rejectResearchTaskSubmission,
  retryFailedResearchTask,
  disposeLegacyRunningResearchTask,
  type ResearchTaskReport,
  type ResearchTaskReportSignoff,
  type ResearchTaskSnapshot,
  type ResearchTaskExecutionSummary,
} from '@/services/researchTaskService';
import { getCurrentResearchIdentity, RESEARCH_IDENTITY_CHANGED_EVENT, type ResearchCurrentIdentity } from '@/services/researchAuthService';

const { Text } = Typography;

const STATUS_META: Record<string, { label: string; color: string }> = {
  pending: { label: '等待开始', color: 'blue' },
  running: { label: '运行中', color: 'processing' },
  waiting_approval: { label: '等待审批', color: 'gold' },
  paused: { label: '已暂停', color: 'orange' },
  failed: { label: '失败', color: 'error' },
  cancelled: { label: '已取消', color: 'default' },
  completed: { label: '已完成', color: 'success' },
};

const EMPTY_REPORT_CHART: ChartData = {
  chart_type: 'bar',
  title: '暂无可审计报告图表',
  labels: [],
  values: [],
};

function statusTag(status: string) {
  const meta = STATUS_META[status] ?? { label: '状态未知', color: 'default' };
  return <Tag color={meta.color}>{meta.label}</Tag>;
}

function submissionTag(status: 'submitted' | 'approved' | 'rejected') {
  const meta = {
    submitted: { label: '待领导审批', color: 'gold' },
    approved: { label: '已批准执行', color: 'success' },
    rejected: { label: '已驳回', color: 'error' },
  }[status];
  return <Tag color={meta.color}>{meta.label}</Tag>;
}

function taskNodes(task: ResearchTaskSnapshot | undefined, execution: ResearchTaskExecutionSummary | undefined): DagNode[] {
  return (task?.dag_step_ids ?? []).map((stepId) => ({
    id: stepId,
    label: stepId,
    type: 'report',
    description: '研究任务步骤',
    tool_name: '未记录',
    status: execution?.completed_step_ids.includes(stepId)
      ? 'completed'
      : execution?.current_step_id === stepId
        ? 'running'
        : task?.status === 'failed'
          ? 'failed'
          : 'pending',
  }));
}

function traceSummaryText(summary: Record<string, string | number | boolean>): string {
  return Object.entries(summary).map(([key, value]) => `${key}=${String(value)}`).join('，');
}

export default function ResearchTasksPage() {
  const [form] = Form.useForm<{ objective: string; scope: string; estimated_cost: string }>();
  const [tasks, setTasks] = useState<ResearchTaskSnapshot[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [report, setReport] = useState<ResearchTaskReport>();
  const [execution, setExecution] = useState<ResearchTaskExecutionSummary>();
  const [executionLoading, setExecutionLoading] = useState(false);
  const [executionError, setExecutionError] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportMissing, setReportMissing] = useState(false);
  const [reportSignoff, setReportSignoff] = useState<ResearchTaskReportSignoff>();
  const [reportSignoffLoading, setReportSignoffLoading] = useState(false);
  const [signingReport, setSigningReport] = useState(false);
  const [reportSignoffError, setReportSignoffError] = useState('');
  const [conflicts, setConflicts] = useState<ResearchTaskConflict[]>([]);
  const [reviews, setReviews] = useState<Record<string, ResearchTaskConflictReview[]>>({});
  const [identity, setIdentity] = useState<ResearchCurrentIdentity | null>(null);
  const [resolvingConflictId, setResolvingConflictId] = useState<string>();
  const [conflictActionError, setConflictActionError] = useState('');
  const [submittingTask, setSubmittingTask] = useState(false);
  const [submissionError, setSubmissionError] = useState('');
  const [decidingSubmission, setDecidingSubmission] = useState(false);
  const [retryingTask, setRetryingTask] = useState(false);
  const [disposingLegacy, setDisposingLegacy] = useState(false);
  const [legacyReason, setLegacyReason] = useState('未发现步骤尝试、租约、调用或检查点，按审计流程处置。');

  useEffect(() => {
    let active = true;
    const refreshIdentity = () => {
      void getCurrentResearchIdentity().then((current) => {
        if (active) setIdentity(current);
      }).catch(() => {
        if (active) setIdentity(null);
      });
    };
    refreshIdentity();
    window.addEventListener(RESEARCH_IDENTITY_CHANGED_EVENT, refreshIdentity);
    return () => {
      active = false;
      window.removeEventListener(RESEARCH_IDENTITY_CHANGED_EVENT, refreshIdentity);
    };
  }, []);

  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const items = await listResearchTasks();
      setTasks(items);
      setSelectedTaskId((current) => current && items.some((item) => item.task_id === current)
        ? current
        : items[0]?.task_id);
    } catch {
      setError('无法加载研究任务，请确认后端服务已启动。');
      setTasks([]);
      setSelectedTaskId(undefined);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  const selectedTask = useMemo(
    () => tasks.find((task) => task.task_id === selectedTaskId),
    [selectedTaskId, tasks],
  );

  useEffect(() => {
    if (!selectedTaskId) {
      setReport(undefined);
      setReportLoading(false);
      setReportMissing(false);
      return;
    }
    let active = true;
    setReport(undefined);
    setReportLoading(true);
    setReportMissing(false);
    void getResearchTaskReport(selectedTaskId)
      .then((item) => {
        if (active) setReport(item);
      })
      .catch((requestError: { response?: { status?: number } }) => {
        if (active && requestError.response?.status === 404) setReportMissing(true);
      })
      .finally(() => {
        if (active) setReportLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedTaskId]);

  useEffect(() => {
    if (!selectedTaskId) {
      setExecution(undefined);
      setExecutionLoading(false);
      setExecutionError(false);
      return;
    }
    let active = true;
    setExecution(undefined);
    setExecutionLoading(true);
    setExecutionError(false);
    void getResearchTaskExecutionSummary(selectedTaskId)
      .then((item) => { if (active) setExecution(item); })
      .catch(() => { if (active) setExecutionError(true); })
      .finally(() => { if (active) setExecutionLoading(false); });
    return () => { active = false; };
  }, [selectedTaskId]);

  useEffect(() => {
    if (!selectedTaskId || !report) {
      setReportSignoff(undefined);
      setReportSignoffLoading(false);
      return;
    }
    let active = true;
    setReportSignoff(undefined);
    setReportSignoffLoading(true);
    void getResearchTaskReportSignoff(selectedTaskId)
      .then((item) => { if (active) setReportSignoff(item); })
      .catch(() => { if (active) setReportSignoff(undefined); })
      .finally(() => { if (active) setReportSignoffLoading(false); });
    return () => { active = false; };
  }, [selectedTaskId, report]);

  const canResolveConflicts = identity?.roles.includes('approver') ?? false;
  const canSignoffReport = identity?.roles.includes('approver') ?? false;
  const canSubmitTask = identity?.roles.includes('researcher') ?? false;
  const canDecideSubmission = (identity?.roles.includes('approver') ?? false) && selectedTask?.submission?.status === 'submitted';

  const submitTask = async (values: { objective: string; scope: string; estimated_cost: string }) => {
    setSubmittingTask(true);
    setSubmissionError('');
    try {
      const scope = values.scope.split(/[，,]/).map((item) => item.trim()).filter(Boolean);
      const created = await createResearchTask({
        task_id: `research-task-${crypto.randomUUID()}`,
        dag_step_ids: ['plan', 'retrieve', 'review', 'report'],
        objective: values.objective.trim(),
        scope,
        estimated_cost: values.estimated_cost.trim(),
        step_bindings: {
          plan: { agent_name: 'DataAgent', tool_names: [] },
          retrieve: { agent_name: 'DataAgent', tool_names: ['retrieve'] },
          review: { agent_name: 'VerifyAgent', tool_names: ['verify'] },
          report: { agent_name: 'VerifyAgent', tool_names: [] },
        },
      });
      form.resetFields();
      await loadTasks();
      setSelectedTaskId(created.task_id);
    } catch {
      setSubmissionError('任务未提交，请确认当前会话、研究范围和预算。');
    } finally {
      setSubmittingTask(false);
    }
  };

  const decideSubmission = async (action: 'approve' | 'reject') => {
    if (!selectedTask || !canDecideSubmission) return;
    setDecidingSubmission(true);
    setSubmissionError('');
    try {
      const input = {
        expected_revision: selectedTask.revision,
        command_id: `submission-${action}-${crypto.randomUUID()}`,
      };
      const updated = action === 'approve'
        ? await approveResearchTaskSubmission(selectedTask.task_id, input)
        : await rejectResearchTaskSubmission(selectedTask.task_id, input);
      setTasks((current) => current.map((item) => item.task_id === updated.task_id ? updated : item));
    } catch {
      setSubmissionError('任务审批未提交，请确认当前会话角色和任务状态。');
    } finally {
      setDecidingSubmission(false);
    }
  };
  const retryFailedTask = async () => {
    if (!selectedTask || !(identity?.roles.includes('approver')) || selectedTask.status !== 'failed') return;
    setRetryingTask(true);
    setSubmissionError('');
    try {
      const created = await retryFailedResearchTask(selectedTask.task_id, {
        expected_revision: selectedTask.revision,
        command_id: `retry-${crypto.randomUUID()}`,
      });
      setTasks((current) => [...current, created]);
      setSelectedTaskId(created.task_id);
    } catch {
      setSubmissionError('重试任务未创建，请确认当前会话角色和任务修订版本。');
    } finally {
      setRetryingTask(false);
    }
  };
  const disposeLegacyTask = async () => {
    if (!selectedTask || !(identity?.roles.includes('approver')) || selectedTask.status !== 'running' || !legacyReason.trim()) return;
    setDisposingLegacy(true);
    setSubmissionError('');
    try {
      const updated = await disposeLegacyRunningResearchTask(selectedTask.task_id, { expected_revision: selectedTask.revision, command_id: `legacy-disposition-${crypto.randomUUID()}`, reason: legacyReason.trim() });
      setTasks((current) => current.map((item) => item.task_id === updated.task_id ? updated : item));
    } catch {
      setSubmissionError('遗留任务未处置；仅无执行证据的 running 任务可由审批人处置。');
    } finally {
      setDisposingLegacy(false);
    }
  };
  const resolveConflict = async (conflict: ResearchTaskConflict, action: ResearchTaskConflictAction) => {
    if (!selectedTaskId || !canResolveConflicts) return;
    setResolvingConflictId(conflict.conflict_id);
    setConflictActionError('');
    try {
      const selectedFactId = action === 'approve' ? conflict.fact_ids[0] : null;
      let review: ResearchTaskConflictReview;
      if (action === 'keep_pending') {
        review = await resolveResearchTaskConflict(selectedTaskId, conflict.conflict_id, { action });
      } else {
        const approval = await grantResearchTaskConflictApproval(selectedTaskId, conflict.conflict_id, {
          action,
          selected_fact_id: selectedFactId,
          expires_in_seconds: 3600,
        });
        review = await resolveResearchTaskConflict(selectedTaskId, conflict.conflict_id, {
          action,
          selected_fact_id: selectedFactId,
          approval_id: approval.approval_id,
        });
      }
      setReviews((current) => ({ ...current, [conflict.conflict_id]: [...(current[conflict.conflict_id] ?? []), review] }));
    } catch {
      setConflictActionError('裁决未提交，请确认当前会话角色和服务端审批状态。');
    } finally {
      setResolvingConflictId(undefined);
    }
  };

  const signoffReport = async () => {
    if (!selectedTaskId || !report || !canSignoffReport) return;
    setSigningReport(true);
    setReportSignoffError('');
    try {
      const approval = await grantResearchTaskReportSignoffApproval(selectedTaskId, { expires_in_seconds: 3600 });
      const result = await signoffResearchTaskReport(selectedTaskId, { approval_id: approval.approval_id });
      setReportSignoff(result);
    } catch {
      setReportSignoffError('报告未正式签发，请确认当前会话角色、冲突裁决和服务端审批状态。');
    } finally {
      setSigningReport(false);
    }
  };

  useEffect(() => {
    if (!selectedTaskId) { setConflicts([]); setReviews({}); return; }
    let active = true;
    void listResearchTaskConflicts(selectedTaskId).then(async (items) => {
      const histories = await Promise.all(items.map(async (item) => [item.conflict_id, await getResearchTaskConflictReviews(selectedTaskId, item.conflict_id)] as const));
      if (active) { setConflicts(items); setReviews(Object.fromEntries(histories)); }
    }).catch(() => { if (active) { setConflicts([]); setReviews({}); } });
    return () => { active = false; };
  }, [selectedTaskId]);

  return (
    <PageShell>
      <main aria-label="研究任务">
        <PageHeader
          eyebrow="研究交付"
          title="研究任务"
          icon={<ExperimentOutlined />}
          description="查看可恢复研究任务的当前状态与已持久化交付信息；未生成的报告内容不会被推测。"
        />

      <div className="page-stack" role="region" aria-label="研究任务工作台">
        <Card
          className="page-card page-toolbar"
          size="small"
          title="任务列表"
          extra={<Button icon={<ReloadOutlined />} aria-label="刷新" onClick={() => void loadTasks()} loading={loading}>刷新</Button>}
        >
          {error ? <Alert type="warning" showIcon message={error} /> : null}
          {canSubmitTask ? <Form form={form} layout="vertical" onFinish={(values) => void submitTask(values)} style={{ marginBottom: 16 }}>
            <Form.Item label="研究目标" name="objective" rules={[{ required: true, message: '请填写研究目标' }]}><Input aria-label="研究目标" placeholder="例如：核对 2024 年营业收入变化" /></Form.Item>
            <Form.Item label="研究范围" name="scope" rules={[{ required: true, message: '请填写研究范围' }]}><Input aria-label="研究范围" placeholder="例如：营业收入，净利润" /></Form.Item>
            <Form.Item label="预算" name="estimated_cost" rules={[{ required: true, message: '请填写预算' }]}><Input aria-label="预算" placeholder="例如：1.00" /></Form.Item>
            <Button type="primary" htmlType="submit" aria-label="提交研究任务" loading={submittingTask}>提交研究任务</Button>
          </Form> : <Text type="secondary">仅研究员可提交研究任务。</Text>}
          {submissionError ? <Alert type="error" showIcon message={submissionError} style={{ marginBottom: 12 }} /> : null}
          {loading ? (
            <div className="page-state"><Spin tip="加载研究任务..." /></div>
          ) : tasks.length === 0 ? (
            <div className="page-state"><Empty description="当前没有可查看的研究任务" /></div>
          ) : (
            <List
              dataSource={tasks}
              renderItem={(task) => (
                <List.Item>
                  <Button
                    type="text"
                    onClick={() => setSelectedTaskId(task.task_id)}
                    aria-pressed={selectedTaskId === task.task_id}
                    style={{ width: '100%', height: 'auto', padding: '8px 4px', textAlign: 'left' }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, width: '100%', flexWrap: 'wrap' }}>
                      <span className="mono">{task.task_id}</span>
                      <span>{statusTag(task.status)} {task.submission ? submissionTag(task.submission.status) : null} <Text type="secondary">revision {task.revision}</Text></span>
                    </div>
                  </Button>
                </List.Item>
              )}
            />
          )}
        </Card>

        {selectedTask ? (
          <>
            <Card className="page-card" title="任务详情">
              <Descriptions column={{ xs: 1, sm: 2 }} size="small">
                <Descriptions.Item label="任务 ID"><span className="mono">{selectedTask.task_id}</span></Descriptions.Item>
                <Descriptions.Item label="运行状态">{statusTag(selectedTask.status)}</Descriptions.Item>
                <Descriptions.Item label="运行 ID"><span className="mono">{selectedTask.run_id}</span></Descriptions.Item>
                <Descriptions.Item label="修订版本">{selectedTask.revision}</Descriptions.Item>
                <Descriptions.Item label="提交状态">{selectedTask.submission ? submissionTag(selectedTask.submission.status) : '历史任务未登记提交审批'}</Descriptions.Item>
                {selectedTask.submission ? <Descriptions.Item label="提交人">{selectedTask.submission.requester}</Descriptions.Item> : null}
                {selectedTask.submission?.reviewer ? <Descriptions.Item label="审批人">{selectedTask.submission.reviewer}</Descriptions.Item> : null}
              </Descriptions>
              {canDecideSubmission ? <Space style={{ marginTop: 12 }}><Button type="primary" aria-label="批准并执行" loading={decidingSubmission} onClick={() => void decideSubmission('approve')}>批准并执行</Button><Button danger disabled={decidingSubmission} onClick={() => void decideSubmission('reject')}>驳回任务</Button></Space> : null}
              {selectedTask.status === 'failed' && identity?.roles.includes('approver') ? <Space style={{ marginTop: 12 }}><Button aria-label="创建重试任务" loading={retryingTask} onClick={() => void retryFailedTask()}>创建重试任务</Button><Text type="secondary">将复制计划并重新提交审批；原失败任务不会改写或自动恢复。</Text></Space> : null}
              {selectedTask.status === 'running' && identity?.roles.includes('approver') ? <Space direction="vertical" style={{ marginTop: 12, width: '100%' }}><Text strong>遗留运行任务处置</Text><Input.TextArea aria-label="遗留任务处置原因" value={legacyReason} onChange={(event) => setLegacyReason(event.target.value)} maxLength={500} /><Space><Button danger aria-label="标记为失败并保留审计" loading={disposingLegacy} onClick={() => void disposeLegacyTask()} disabled={!legacyReason.trim()}>标记为失败并保留审计</Button><Text type="secondary">仅适用于无执行证据的遗留任务；不会删除、重启或直接改写执行记录。</Text></Space></Space> : null}
            </Card>

            <Card className="page-card" title="执行 DAG" aria-label="执行 DAG">
              <DagFlow nodes={taskNodes(selectedTask, execution)} edges={[]} height={280} />
            </Card>
            <Card className="page-card" title="执行进度" aria-label="执行进度">
              {executionLoading ? <Spin tip="加载执行进度..." /> : null}
              {execution ? <Space direction="vertical" size={4}>
                <Text>已完成步骤：{execution.completed_step_ids.length > 0 ? execution.completed_step_ids.join('、') : '暂无'}</Text>
                {execution.current_step_id ? <Text>当前步骤：{execution.current_step_id}</Text> : null}
                {execution.completed_at ? <Text>完成时间：{execution.completed_at}</Text> : null}
                {execution.failure_reason ? <Alert type="error" showIcon message={`失败原因：${execution.failure_reason}`} /> : null}
                {execution.step_traces && execution.step_traces.length > 0 ? (
                  <List
                    size="small"
                    header={<Text strong>Agent / 工具结果轨迹</Text>}
                    dataSource={execution.step_traces}
                    renderItem={(trace) => (
                      <List.Item>
                        <Space wrap>
                          <Text strong>{trace.step_id}</Text>
                          <Tag>{trace.agent_name}</Tag>
                          <Text type="secondary">工具：{trace.tool_names.length > 0 ? trace.tool_names.join('、') : '无'}</Text>
                          <Text type="secondary">结果：{traceSummaryText(trace.result_summary)}</Text>
                        </Space>
                      </List.Item>
                    )}
                  />
                ) : null}
              </Space> : null}
              {executionError ? <Alert type="warning" showIcon message="无法读取执行进度，请刷新后重试。" /> : null}
            </Card>
            <Card className="page-card" title="报告详情" aria-label="报告详情">
              {reportLoading ? <Spin tip="加载持久化报告..." /> : null}
              {report ? (
                <List
                  header={<Text type="secondary">报告版本 {report.report_version} · 审核状态 {report.review_status}</Text>}
                  dataSource={report.claims}
                  locale={{ emptyText: '该报告未包含可展示的声明' }}
                  renderItem={(claim) => (
                    <List.Item>
                      <div>
                        <Text strong>{claim.text}</Text>
                        <div><Text type="secondary">声明 ID：{claim.claim_id}</Text></div>
                        {claim.fact_ids.map((factId) => <div key={factId}><Text type="secondary">事实：{factId}</Text></div>)}
                        {claim.calculation_ids.map((calculationId) => <div key={calculationId}><Text type="secondary">计算：{calculationId}</Text></div>)}
                        {claim.source_ids.map((sourceId) => <div key={sourceId}><Text type="secondary">来源：{sourceId}</Text></div>)}
                        {claim.analysis_label ? <div><Text type="secondary">分析判断：{claim.analysis_label}</Text></div> : null}
                      </div>
                    </List.Item>
                  )}
                />
              ) : null}
              {reportMissing ? <Empty description="该任务尚未生成可查看的持久化报告" /> : null}
              {report ? <div style={{ marginTop: 12 }}>
                {reportSignoffLoading ? <Spin size="small" /> : null}
                {reportSignoff ? <Space wrap><Tag color="success">已正式签发</Tag><Text type="secondary">签发人：{reportSignoff.actor} · {reportSignoff.signed_at}</Text></Space> : null}
                {!reportSignoff && !reportSignoffLoading && canSignoffReport ? <Button type="primary" aria-label="正式签发报告" loading={signingReport} onClick={() => void signoffReport()}>正式签发报告</Button> : null}
                {!reportSignoff && !reportSignoffLoading && !canSignoffReport ? <Text type="secondary">正式签发仅对审批人开放。</Text> : null}
                {reportSignoffError ? <Alert type="error" showIcon message={reportSignoffError} style={{ marginTop: 12 }} /> : null}
              </div> : null}
            </Card>
            <Card className="page-card" title="关键冲突" aria-label="关键冲突">
              {conflictActionError ? <Alert type="error" showIcon message={conflictActionError} style={{ marginBottom: 12 }} /> : null}
              {conflicts.length === 0 ? <Empty description="该任务当前没有可信上下文登记的关键冲突" /> : <List dataSource={conflicts} renderItem={(conflict) => (
                <List.Item><div><Text strong>{conflict.conflict_id}</Text><div><Text type="secondary">事实：{conflict.fact_ids.join('、')}</Text></div><div><Text type="secondary">冲突类型：{conflict.conflict_type}</Text></div>{(reviews[conflict.conflict_id] ?? []).map((review) => <div key={review.review_id}><Text type="secondary">{review.action === 'approve' ? '批准' : review.action === 'reject' ? '驳回' : '保持未决'}</Text></div>)}{canResolveConflicts ? <Space size={8} style={{ marginTop: 8 }}><Button size="small" type="primary" aria-label={`批准 ${conflict.conflict_id}`} loading={resolvingConflictId === conflict.conflict_id} onClick={() => void resolveConflict(conflict, 'approve')}>批准</Button><Button size="small" danger aria-label={`驳回 ${conflict.conflict_id}`} disabled={Boolean(resolvingConflictId)} onClick={() => void resolveConflict(conflict, 'reject')}>驳回</Button><Button size="small" aria-label={`保持未决 ${conflict.conflict_id}`} disabled={Boolean(resolvingConflictId)} onClick={() => void resolveConflict(conflict, 'keep_pending')}>保持未决</Button></Space> : null}</div></List.Item>
              )} />}
              <Text type="secondary">{canResolveConflicts ? '裁决授权、依赖绑定和审批消费均由服务端当前会话处理。' : '仅审批人可提交裁决。'}</Text>
            </Card>
            <Card className="page-card" title="报告证据" aria-label="报告证据">
              <EvidenceContent sources={[]} />
            </Card>
            <Card className="page-card" title="报告图表" aria-label="报告图表">
              <ChartContainer data={EMPTY_REPORT_CHART} height={260} />
            </Card>
          </>
        ) : null}
      </div>
      </main>
    </PageShell>
  );
}
