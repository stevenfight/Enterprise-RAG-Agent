// -*- coding: utf-8 -*-
/**
 * 顶部栏
 * 包含: 折叠按钮 + 页面标题 + 系统状态指示灯
 */

import { Button, Space, Typography, Badge, Tooltip } from 'antd';
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons';
import { useLocation } from 'react-router-dom';
import { appStore } from '@/stores/appStore';
import { useTheme } from '@/hooks/useTheme';
import { colors } from '@/styles/theme';

const { Text } = Typography;

/** 路由到页面标题的映射 */
const pageTitleMap: Record<string, string> = {
  '/': '智能问答',
  '/dag': 'DAG 任务看板',
  '/charts': '数据图表',
  '/knowledge': '知识库管理',
  '/settings': '系统设置',
};

interface HeaderBarProps {
  /** 系统是否在线 */
  systemOnline?: boolean;
}

export default function HeaderBar({ systemOnline = false }: HeaderBarProps) {
  const location = useLocation();
  const siderCollapsed = appStore((s) => s.siderCollapsed);
  const toggleSider = appStore((s) => s.toggleSider);
  const { isDark } = useTheme();

  const title = pageTitleMap[location.pathname] || '企业知识库';

  return (
    <div
      style={{
        height: 56,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        borderBottom: `1px solid ${isDark ? '#303030' : '#f0f0f0'}`,
        background: isDark ? '#1f1f1f' : '#ffffff',
      }}
    >
      {/* 左侧: 折叠按钮 + 标题 */}
      <Space size={12}>
        <Button
          type="text"
          icon={siderCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          onClick={toggleSider}
          style={{ fontSize: 16 }}
        />
        <Text
          strong
          style={{ fontSize: 16, color: isDark ? '#e8e8e8' : '#262626' }}
        >
          {title}
        </Text>
      </Space>

      {/* 右侧: 系统状态 */}
      <Space size={8}>
        <Tooltip title={systemOnline ? '系统已就绪' : '系统离线'}>
          <Badge
            status={systemOnline ? 'success' : 'error'}
            text={
              <Text
                style={{
                  fontSize: 13,
                  color: isDark ? '#8c8c8c' : '#595959',
                }}
              >
                {systemOnline ? '已就绪' : '离线'}
              </Text>
            }
          />
        </Tooltip>
      </Space>
    </div>
  );
}
