import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  FileTextOutlined,
  PercentageOutlined,
} from '@ant-design/icons';
import type { KnowledgeDocument } from '@/types/chat';
import StatusOverview, { type StatusOverviewItem } from '@/components/common/StatusOverview';

interface KnowledgeOverviewProps {
  documents: KnowledgeDocument[];
}

export default function KnowledgeOverview({ documents }: KnowledgeOverviewProps) {
  const total = documents.length;
  const indexed = documents.filter((document) => document.indexed).length;
  const pending = total - indexed;
  const completionRate = total === 0 ? 0 : Math.round((indexed / total) * 100);

  const items: StatusOverviewItem[] = [
    { key: 'total', label: '文档总数', value: `${total}`, detail: '知识库文档', icon: <FileTextOutlined />, state: 'neutral' },
    { key: 'indexed', label: '已索引', value: `${indexed}`, detail: '可用于检索', icon: <CheckCircleOutlined />, state: 'success' },
    { key: 'pending', label: '待索引', value: `${pending}`, detail: pending ? '等待处理' : '全部完成', icon: <ClockCircleOutlined />, state: pending ? 'warning' : 'success' },
    { key: 'rate', label: '索引完成率', value: `${completionRate}%`, detail: total ? `${indexed} / ${total} 篇` : '暂无文档', icon: <PercentageOutlined />, state: completionRate === 100 ? 'success' : 'neutral' },
  ];

  return <StatusOverview items={items} ariaLabel="知识库概览" />;
}
