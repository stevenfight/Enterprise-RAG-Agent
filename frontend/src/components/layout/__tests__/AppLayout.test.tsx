// -*- coding: utf-8 -*-
/**
 * AppLayout 聊天区铺满测试
 * 覆盖: 聊天路由去内边距/overflow hidden，其他路由保持标准内边距
 */
import { render } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockPathname = vi.hoisted(() => ({ value: '/' }));

vi.mock('react-router-dom', () => ({
  useLocation: () => ({ pathname: mockPathname.value }),
  Outlet: () => <div data-testid="outlet" />,
}));

vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({ isDark: false, themeMode: 'light' }),
}));

vi.mock('@/components/layout/Sidebar', () => ({
  default: () => <div data-testid="sidebar" />,
}));

vi.mock('@/components/layout/HeaderBar', () => ({
  default: () => <div data-testid="header" />,
}));

import AppLayout from '@/components/layout/AppLayout';

describe('AppLayout 聊天区铺满', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        json: () => Promise.resolve({ status: 'ok' }),
      }),
    );
  });

  it('TC-UI-001-02 聊天路由时 Content overflow 为 hidden（铺满）', () => {
    mockPathname.value = '/';
    const { container } = render(<AppLayout />);
    const content = container.querySelector('.ant-layout-content');
    expect(content?.getAttribute('style')).toContain('overflow: hidden');
  });

  it('TC-UI-001-03 非聊天路由时 Content overflow 为 auto（标准内边距）', () => {
    mockPathname.value = '/dag';
    const { container } = render(<AppLayout />);
    const content = container.querySelector('.ant-layout-content');
    expect(content?.getAttribute('style')).toContain('overflow: auto');
  });
});
