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
import { colors, lightTheme, darkTheme } from '@/styles/theme';
import { useTheme } from '@/hooks/useTheme';
import '@/styles/global.css';
import { createLogger } from '@/utils/logger';
import { checkHealth } from '@/services/chatService';

const logger = createLogger('AppLayout');
const { Content } = Layout;

export default function AppLayout() {
  const { themeMode, isDark } = useTheme();
  const [systemOnline, setSystemOnline] = useState(false);
  const location = useLocation();
  // 聊天首页铺满内容区，其余页面保留标准内边距
  const isChatRoute = location.pathname === '/';

  logger.renderStart({ themeMode, systemOnline, path: location.pathname });

  // 定期检查系统健康状态
  useEffect(() => {
    const runHealthCheck = async () => {
      try {
        logger.debug('健康检查请求: GET /api/health');
        const data = await checkHealth();
        const online = data.status === 'ok';
        setSystemOnline(online);
        logger.info('健康检查结果:', { status: data.status, online });
      } catch (err) {
        setSystemOnline(false);
        logger.warn('健康检查失败:', err);
      }
    };

    runHealthCheck();
    const timer = setInterval(runHealthCheck, 30000); // 每 30 秒检查一次
    return () => clearInterval(timer);
  }, []);

  const currentTheme = isDark ? darkTheme : lightTheme;
  const pageThemeStyle = {
    '--page-primary': colors.primary,
    '--page-text-primary': isDark ? colors.textPrimaryDark : colors.textPrimary,
    '--page-text-secondary': isDark ? colors.textSecondaryDark : colors.textSecondary,
    '--page-border': isDark ? colors.borderDark : colors.border,
    '--page-card-bg': isDark ? colors.bgDarkCard : colors.bgCard,
  } as CSSProperties;
  logger.renderEnd(`主题=${themeMode}, 在线=${systemOnline}`);

  return (
    <ConfigProvider theme={currentTheme}>
      <AntApp>
        <ConfigProvider
          theme={{
            algorithm: isDark
              ? antdTheme.darkAlgorithm
              : antdTheme.defaultAlgorithm,
          }}
        >
          <Layout style={{ height: '100vh', overflow: 'hidden' }}>
            {/* 左侧导航 */}
            <Sidebar />

            {/* 右侧主区域 */}
            <Layout>
              {/* 顶部栏 */}
              <HeaderBar systemOnline={systemOnline} />

              {/* 内容区域 */}
              <Content
                style={{
                  ...pageThemeStyle,
                  overflow: isChatRoute ? 'hidden' : 'auto',
                  padding: isChatRoute ? 0 : 24,
                  background: isDark ? '#141414' : colors.bgLight,
                }}
              >
                <Outlet />
              </Content>
            </Layout>
          </Layout>
        </ConfigProvider>
      </AntApp>
    </ConfigProvider>
  );
}
