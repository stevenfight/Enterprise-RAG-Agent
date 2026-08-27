// -*- coding: utf-8 -*-
/**
 * 左侧导航菜单 - 马卡龙风格
 * 包含: 项目 Logo + 导航菜单
 */

import { useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Typography, Space } from 'antd';
import {
  MessageOutlined,
  ApartmentOutlined,
  BarChartOutlined,
  DatabaseOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { appStore } from '@/stores/appStore';
import { useTheme } from '@/hooks/useTheme';
import { colors } from '@/styles/theme';

const { Sider } = Layout;
const { Text } = Typography;

/** 导航菜单项 */
const menuItems = [
  {
    key: '/',
    icon: <MessageOutlined />,
    label: '智能问答',
  },
  {
    key: '/dag',
    icon: <ApartmentOutlined />,
    label: 'DAG 看板',
  },
  {
    key: '/charts',
    icon: <BarChartOutlined />,
    label: '数据图表',
  },
  {
    key: '/knowledge',
    icon: <DatabaseOutlined />,
    label: '知识库管理',
  },
  {
    key: '/settings',
    icon: <SettingOutlined />,
    label: '系统设置',
  },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const siderCollapsed = appStore((s) => s.siderCollapsed);
  const toggleSider = appStore((s) => s.toggleSider);
  const { isDark } = useTheme();

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  const borderColor = isDark ? '#3A3550' : '#E8E3EF';

  return (
    <Sider
      collapsible
      collapsed={siderCollapsed}
      onCollapse={toggleSider}
      width={220}
      collapsedWidth={64}
      trigger={null}
      className="sider-transition"
      style={{
        borderRight: `1px solid ${borderColor}`,
        overflow: 'auto',
        height: '100vh',
        position: 'sticky',
        top: 0,
        left: 0,
        background: isDark
          ? colors.pageSidebarDark
          : 'linear-gradient(180deg, #FFF9F5 0%, #F8F4FA 50%, #F5F8FA 100%)',
      }}
    >
      {/* Logo 区域 - 马卡龙渐变 */}
      <div
        style={{
          height: 56,
          display: 'flex',
          alignItems: 'center',
          justifyContent: siderCollapsed ? 'center' : 'flex-start',
          padding: siderCollapsed ? '0' : '0 20px',
          borderBottom: `1px solid ${borderColor}`,
          background: 'color-mix(in srgb, var(--page-primary) 8%, transparent)',
        }}
      >
        <Space size={8}>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 10,
              background: 'var(--page-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 8px color-mix(in srgb, var(--page-primary) 35%, transparent)',
            }}
          >
            <ApartmentOutlined
              style={{ fontSize: 18, color: '#ffffff' }}
            />
          </div>
          {!siderCollapsed && (
            <Text
              strong
              style={{
                fontSize: 15,
                color: isDark ? colors.textPrimaryDark : colors.textPrimary,
                whiteSpace: 'nowrap',
                background: isDark
                  ? 'none'
                  : 'linear-gradient(135deg, var(--page-primary), var(--page-primary))',
                WebkitBackgroundClip: isDark ? 'none' : 'text',
                WebkitTextFillColor: isDark ? 'inherit' : 'transparent',
              }}
            >
              企业知识库
            </Text>
          )}
        </Space>
      </div>

      {/* 导航菜单 */}
      <Menu
        mode="inline"
        selectedKeys={[location.pathname]}
        items={menuItems}
        onClick={handleMenuClick}
        style={{
          border: 'none',
          marginTop: 8,
          background: 'transparent',
        }}
      />
    </Sider>
  );
}
