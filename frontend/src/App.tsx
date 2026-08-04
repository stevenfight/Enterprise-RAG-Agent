// -*- coding: utf-8 -*-
/**
 * 根组件 - 路由配置
 * 5 个页面路由 + 404 兜底
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Result, Button } from 'antd';
import AppLayout from '@/components/layout/AppLayout';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import ChatPage from '@/pages/ChatPage';
import DagBoardPage from '@/pages/DagBoardPage';
import ChartsPage from '@/pages/ChartsPage';
import KnowledgePage from '@/pages/KnowledgePage';
import SettingsPage from '@/pages/SettingsPage';

/** 404 页面 */
function NotFoundPage() {
  return (
    <Result
      status="404"
      title="404"
      subTitle="抱歉，您访问的页面不存在"
      extra={
        <Button type="primary" href="/">
          返回首页
        </Button>
      }
    />
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<ChatPage />} />
            <Route path="/dag" element={<DagBoardPage />} />
            <Route path="/charts" element={<ChartsPage />} />
            <Route path="/knowledge" element={<KnowledgePage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
