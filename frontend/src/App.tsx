// -*- coding: utf-8 -*-
/**
 * 根组件 - 路由配置
 * 5 个页面路由 + 404 兜底
 * Phase 3: 非首页路由 React.lazy 懒加载
 */

import React, { Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Spin, Result, Button } from 'antd';
import AppLayout from '@/components/layout/AppLayout';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import ChatPage from '@/pages/ChatPage';

// 非首页路由懒加载 (Phase 3)
const DagBoardPage = React.lazy(() => import('@/pages/DagBoardPage'));
const ChartsPage = React.lazy(() => import('@/pages/ChartsPage'));
const KnowledgePage = React.lazy(() => import('@/pages/KnowledgePage'));
const SettingsPage = React.lazy(() => import('@/pages/SettingsPage'));

/** Suspense fallback 组件 */
function LazyFallback() {
  return (
    <div style={{
      display: 'flex', justifyContent: 'center',
      alignItems: 'center', minHeight: 300,
    }}>
      <Spin size="large" />
    </div>
  );
}

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
            <Route path="/dag" element={
              <Suspense fallback={<LazyFallback />}>
                <DagBoardPage />
              </Suspense>} />
            <Route path="/charts" element={
              <Suspense fallback={<LazyFallback />}>
                <ChartsPage />
              </Suspense>} />
            <Route path="/knowledge" element={
              <Suspense fallback={<LazyFallback />}>
                <KnowledgePage />
              </Suspense>} />
            <Route path="/settings" element={
              <Suspense fallback={<LazyFallback />}>
                <SettingsPage />
              </Suspense>} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
