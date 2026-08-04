// -*- coding: utf-8 -*-
/**
 * 左侧导航菜单 - 马卡龙风格
 * 包含: 项目 Logo + 导航菜单 + 主题切换 (玻璃拟态效果)
 */

import { useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Switch, Typography, Space } from 'antd';
import {
  MessageOutlined,
  ApartmentOutlined,
  BarChartOutlined,
  DatabaseOutlined,
  SettingOutlined,
  BulbOutlined,
  BulbFilled,
} from '@ant-design/icons';
import { appStore } from '@/stores/appStore';
import { useTheme } from '@/hooks/useTheme';
import { colors, gradients } from '@/styles/theme';

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
  const { isDark, toggleTheme } = useTheme();

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
          ? colors.bgDarkSidebar
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
          background: isDark
            ? 'rgba(184, 169, 201, 0.06)'
            : 'rgba(184, 169, 201, 0.08)',
        }}
      >
        <Space size={8}>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 10,
              background: gradients.hero,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 8px rgba(184, 169, 201, 0.35)',
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
                  : `linear-gradient(135deg, ${colors.primaryDark}, ${colors.primary})`,
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

      {/* 底部: 主题切换 - 玻璃拟态 */}
      <div
        style={{
          position: 'absolute',
          bottom: 8,
          left: 8,
          right: 8,
          width: 'auto',
          padding: siderCollapsed ? '10px' : '10px 14px',
          borderTop: `1px solid ${borderColor}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: siderCollapsed ? 'center' : 'space-between',
          background: isDark
            ? 'rgba(37, 34, 54, 0.6)'
            : 'rgba(255, 255, 255, 0.6)',
          backdropFilter: 'blur(12px)',
          borderRadius: 12,
        }}
      >
        {!siderCollapsed && (
          <Text
            style={{ fontSize: 12, color: isDark ? colors.textSecondaryDark : colors.textSecondary }}
          >
            {isDark ? '暗色模式' : '亮色模式'}
          </Text>
        )}
        <Switch
          checked={isDark}
          onChange={toggleTheme}
          checkedChildren={<BulbFilled />}
          unCheckedChildren={<BulbOutlined />}
          size="small"
        />
      </div>
    </Sider>
  );
}
