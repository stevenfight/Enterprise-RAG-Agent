// -*- coding: utf-8 -*-
/**
 * C2.8 研究任务状态标签组件。
 * 从 researchTaskStore 读取按 revision 合并后的状态，展示运行、
 * 暂停、等待审批、失败、取消、恢复等中文标签。
 */
import { Tag } from 'antd';

import type { ResearchTaskStatus } from '@/services/researchTaskState';
import { researchTaskStore } from '@/stores/researchTaskStore';

/** 状态到中文标签与 antd 颜色的映射 */
const STATUS_LABELS: Record<ResearchTaskStatus, { label: string; color: string }> = {
  unknown: { label: '未开始', color: 'default' },
  pending: { label: '等待开始', color: 'blue' },
  running: { label: '运行中', color: 'processing' },
  waiting_approval: { label: '等待审批', color: 'gold' },
  paused: { label: '已暂停', color: 'orange' },
  failed: { label: '失败', color: 'error' },
  cancelled: { label: '已取消', color: 'default' },
  completed: { label: '已完成', color: 'success' },
};

export default function ResearchTaskStatusTag({ taskId }: { taskId: string }) {
  const task = researchTaskStore((state) => state.tasks[taskId]);
  const meta = STATUS_LABELS[task?.status ?? 'unknown'];

  return (
    <span className="research-task-status-tag">
      <Tag color={meta.color}>{meta.label}</Tag>
      {task?.resumed ? <Tag color="green">已恢复</Tag> : null}
    </span>
  );
}
