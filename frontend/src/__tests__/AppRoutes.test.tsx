// -*- coding: utf-8 -*-
/** 研究工作台接入后，根聊天路由与研究路由的兼容契约。 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

vi.mock('@/components/common/ErrorBoundary', () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/layout/AppLayout', async () => {
  const { Outlet } = await import('react-router-dom');
  return { default: () => <Outlet /> };
});

vi.mock('@/pages/ChatPage', () => ({
  default: () => <main data-testid="chat-page">聊天工作台</main>,
}));

vi.mock('@/pages/ResearchTasksPage', () => ({
  default: () => <main data-testid="research-page">研究任务工作台</main>,
}));

import App from '@/App';

afterEach(() => {
  cleanup();
  window.history.replaceState({}, '', '/');
});

describe('App 路由兼容', () => {
  it('E-T09：接入研究工作台后根路由仍渲染既有聊天页', async () => {
    window.history.replaceState({}, '', '/');

    render(<App />);

    expect(await screen.findByTestId('chat-page')).toHaveTextContent('聊天工作台');
    expect(screen.queryByTestId('research-page')).not.toBeInTheDocument();
  });

  it('E-T09：研究任务页只在 /research 路由渲染', async () => {
    window.history.replaceState({}, '', '/research');

    render(<App />);

    expect(await screen.findByTestId('research-page')).toHaveTextContent('研究任务工作台');
    expect(screen.queryByTestId('chat-page')).not.toBeInTheDocument();
  });
});
