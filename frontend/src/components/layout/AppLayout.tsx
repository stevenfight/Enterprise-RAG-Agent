// -*- coding: utf-8 -*-
/**
 * 全局布局组件
 * 结构: 左侧导航 (Sidebar) + 右侧主区域 (HeaderBar + Content)
 */

import { useState, useEffect } from 'react';
import { Layout, ConfigProvider, theme as antdTheme, App as AntApp } from 'antd';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import HeaderBar from './HeaderBar';
import { lightTheme, darkTheme, colors } from '@/styles/theme';
import { useTheme } from '@/hooks/useTheme';
import '@/styles/global.css';
import { createLogger } from '@/utils/logger';

const logger = createLogger('AppLayout');
const { Content } = Layout;

export default function AppLayout() {
  const { themeMode, isDark } = useTheme();
  const [systemOnline, setSystemOnline] = useState(false);

  logger.renderStart({ themeMode, systemOnline });

  // 定期检查系统健康状态
  useEffect(() => {
    const checkHealth = async () => {
      try {
        logger.debug('健康检查请求: GET /api/health');
        const res = await fetch('/api/health');
        const data = await res.json();
        const online = data.status === 'ok';
        setSystemOnline(online);
        logger.info('健康检查结果:', { status: data.status, online });
      } catch (err) {
        setSystemOnline(false);
        logger.warn('健康检查失败:', err);
      }
    };

    checkHealth();
    const timer = setInterval(checkHealth, 30000); // 每 30 秒检查一次
    return () => clearInterval(timer);
  }, []);

  const currentTheme = isDark ? darkTheme : lightTheme;
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
                  overflow: 'auto',
                  padding: 24,
                  background: isDark ? '#141414' : '#f5f5f5',
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
