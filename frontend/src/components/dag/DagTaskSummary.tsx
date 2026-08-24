import {
  ApartmentOutlined,
  CheckCircleOutlined,
  NodeIndexOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';

interface DagTaskSummaryProps {
  category: string;
  nodeCount: number;
  edgeCount: number;
  batchCount: number;
  status: string;
}

export default function DagTaskSummary({
  category,
  nodeCount,
  edgeCount,
  batchCount,
  status,
}: DagTaskSummaryProps) {
  const items = [
    { key: 'category', label: '任务类型', value: category || '未分类', icon: <ThunderboltOutlined /> },
    { key: 'nodes', label: '任务节点', value: `${nodeCount} 个`, icon: <NodeIndexOutlined /> },
    { key: 'edges', label: '依赖连线', value: `${edgeCount} 条`, icon: <ApartmentOutlined /> },
    { key: 'batches', label: '执行批次', value: `${batchCount} 批`, icon: <CheckCircleOutlined /> },
  ];

  return (
    <section className="dag-task-summary" aria-label="任务摘要">
      <div className="dag-task-summary__status">
        <span className="dag-task-summary__status-dot" />
        <span>{status || '已生成任务计划'}</span>
      </div>
      <div className="dag-task-summary__grid">
        {items.map((item) => (
          <article key={item.key} className="dag-task-summary__item">
            <span className="dag-task-summary__icon">{item.icon}</span>
            <span className="dag-task-summary__label">{item.label}</span>
            <strong className="dag-task-summary__value">{item.value}</strong>
          </article>
        ))}
      </div>
    </section>
  );
}
