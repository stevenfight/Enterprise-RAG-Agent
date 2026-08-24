import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import DagTaskSummary from '../DagTaskSummary';
import DagExecutionTimeline from '../DagExecutionTimeline';

describe('DAG 看板视觉增强组件', () => {
  it('显示任务摘要统计', () => {
    render(
      <DagTaskSummary
        category="横向对比"
        nodeCount={4}
        edgeCount={3}
        batchCount={2}
        status="已生成任务计划"
      />,
    );

    expect(screen.getByRole('region', { name: '任务摘要' })).toBeInTheDocument();
    expect(screen.getByText('横向对比')).toBeInTheDocument();
    expect(screen.getByText('4 个')).toBeInTheDocument();
    expect(screen.getByText('3 条')).toBeInTheDocument();
    expect(screen.getByText('2 批')).toBeInTheDocument();
  });

  it('显示执行批次时间线和节点名称', () => {
    render(
      <DagExecutionTimeline
        batches={[['a'], ['b', 'c']]}
        nodeLabels={{ a: '检索年报', b: '计算营收', c: '生成结论' }}
      />,
    );

    expect(screen.getByRole('region', { name: '执行批次时间线' })).toBeInTheDocument();
    expect(screen.getByText('2 个阶段')).toBeInTheDocument();
    expect(screen.getByText('检索年报')).toBeInTheDocument();
    expect(screen.getByText('计算营收')).toBeInTheDocument();
    expect(screen.getByText('生成结论')).toBeInTheDocument();
  });

  it('没有执行批次时不渲染时间线', () => {
    const { container } = render(<DagExecutionTimeline batches={[]} nodeLabels={{}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
