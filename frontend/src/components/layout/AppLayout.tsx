// -*- coding: utf-8 -*-
/**
 * 全局布局组件
 * 结构: 左侧导航 (Sidebar) + 右侧主区域 (HeaderBar + Content)
 */

import { useState, useEffect } from 'react';
import type { CSSProperties } from 'react';
import { Layout, ConfigProvider, theme as antdTheme, App as AntApp } from 'antd';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import HeaderBar from './HeaderBar';
import type { SystemStatus } from './HeaderBar';
import { accentThemes, colors, createThemeConfig } from '@/styles/theme';
import { useTheme } from '@/hooks/useTheme';
import '@/styles/global.css';
import { createLogger } from '@/utils/logger';
import { checkHealth } from '@/services/chatService';

const logger = createLogger('AppLayout');
const { Content } = Layout;

export default function AppLayout() {
  const { themeMode, isDark, accentTheme } = useTheme();
  const [systemStatus, setSystemStatus] = useState<SystemStatus>('checking');
  const location = useLocation();
  // 聊天首页铺满内容区，其余页面保留标准内边距
  const isChatRoute = location.pathname === '/';

  logger.renderStart({ themeMode, systemStatus, path: location.pathname });

  // 定期检查系统健康状态
  useEffect(() => {
    const runHealthCheck = async () => {
      try {
        logger.debug('健康检查请求: GET /api/health');
        const data = await checkHealth();
        const nextStatus: SystemStatus = data.status === 'ok' ? 'ready' : 'unavailable';
        setSystemStatus(nextStatus);
        logger.info('健康检查结果:', { status: data.status, systemStatus: nextStatus });
      } catch (err) {
        setSystemStatus('unavailable');
        logger.warn('健康检查失败:', err);
      }
    };

    runHealthCheck();
    const timer = setInterval(runHealthCheck, 30000); // 每 30 秒检查一次
    return () => clearInterval(timer);
  }, []);

  const currentTheme = {
    ...createThemeConfig(themeMode, accentTheme),
    algorithm: isDark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
  };
  const pagePrimary = accentThemes[accentTheme][themeMode];
  const pageThemeStyle = {
    '--page-primary': pagePrimary,
    '--page-text-primary': isDark ? colors.textPrimaryDark : colors.textPrimary,
    '--page-text-secondary': isDark ? colors.textSecondaryDark : colors.textSecondary,
    '--page-border': isDark ? colors.pageBorderDark : colors.pageBorderLight,
    '--page-card-bg': isDark ? colors.bgDarkCard : colors.bgCard,
    '--page-background': isDark ? colors.pageBackgroundDark : colors.pageBackgroundLight,
    '--page-surface': isDark ? colors.pageSurfaceDark : colors.pageSurfaceLight,
    '--page-raised': isDark ? colors.pageRaisedDark : colors.pageSurfaceLight,
    '--page-input-bg': isDark ? colors.pageInputDark : colors.pageInputLight,
    '--page-sidebar-bg': isDark ? colors.pageSidebarDark : colors.pageSidebarLight,
  } as CSSProperties;
  logger.renderEnd(`主题=${themeMode}, 健康状态=${systemStatus}`);

  return (
    <ConfigProvider theme={currentTheme}>
      <AntApp>
        <Layout
          style={{
            ...pageThemeStyle,
            height: '100vh',
            overflow: 'hidden',
          }}
        >
          {/* 左侧导航 */}
          <Sidebar />

          {/* 右侧主区域 */}
          <Layout>
            {/* 顶部栏 */}
            <HeaderBar systemStatus={systemStatus} />

            {/* 内容区域 */}
            <Content
              className="app-workspace-content"
              style={{
                overflow: isChatRoute ? 'hidden' : 'auto',
                // 页面级留白统一由辅助页面的 PageShell 管理，避免与外层内容区叠加。
                padding: 0,
                background: isDark ? colors.pageBackgroundDark : colors.pageBackgroundLight,
              }}
            >
              <Outlet />
            </Content>
          </Layout>
        </Layout>
      </AntApp>
    </ConfigProvider>
  );
}
