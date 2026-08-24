import {
  DatabaseOutlined,
  ExperimentOutlined,
  LineChartOutlined,
  RobotOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import type { SystemStatusData } from '@/types/chat';
import StatusOverview, { type StatusOverviewItem } from '@/components/common/StatusOverview';

interface SettingsOverviewProps {
  status: SystemStatusData;
}

function getState(status: boolean, unavailableIsError = false): StatusOverviewItem['state'] {
  if (status) return 'success';
  return unavailableIsError ? 'error' : 'warning';
}

export default function SettingsOverview({ status }: SettingsOverviewProps) {
  const enabledTools = Object.values(status.tools).filter(Boolean).length;
  const totalTools = Object.keys(status.tools).length;
  const items: StatusOverviewItem[] = [
    {
      key: 'agent',
      label: 'Agent 状态',
      value: status.model.name,
      detail: status.model.status === 'loaded' ? '模型已加载' : '模型未加载',
      state: getState(status.model.status === 'loaded', true),
      icon: <RobotOutlined />,
    },
    {
      key: 'vector-db',
      label: '向量数据库',
      value: `${status.vector_db.company_count} 家公司`,
      detail: status.vector_db.status === 'available' ? '服务可用' : '服务不可用',
      state: getState(status.vector_db.status === 'available', true),
      icon: <DatabaseOutlined />,
    },
    {
      key: 'memory',
      label: '长期记忆',
      value: status.memory.long_term_enabled ? '已启用' : '未启用',
      detail: status.memory.long_term_enabled
        ? `工作记忆容量 ${status.memory.working_memory_limit} 条`
        : '当前未启用长期记忆',
      state: getState(status.memory.long_term_enabled),
      icon: <ExperimentOutlined />,
    },
    {
      key: 'langsmith',
      label: 'LangSmith 追踪',
      value: status.monitoring.langsmith_available ? '已启用' : '未启用',
      detail: status.monitoring.langsmith_available
        ? status.monitoring.langsmith_project
        : '当前未启用追踪',
      state: getState(status.monitoring.langsmith_available),
      icon: <LineChartOutlined />,
    },
    {
      key: 'tools',
      label: '工具注册',
      value: `${enabledTools} / ${totalTools}`,
      detail: enabledTools === totalTools ? '全部工具已启用' : '部分工具已启用',
      state: enabledTools === totalTools ? 'success' : 'warning',
      icon: <ToolOutlined />,
    },
  ];

  return <StatusOverview items={items} ariaLabel="系统状态概览" columns={5} compact />;
}
