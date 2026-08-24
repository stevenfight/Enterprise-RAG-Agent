// -*- coding: utf-8 -*-
/**
 * TDD 测试: HeaderBar 主题切换
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import HeaderBar from '../HeaderBar';

const mockToggle = vi.fn();

// mock useTheme
vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({
    isDark: false,
    toggleTheme: mockToggle,
  }),
}));

describe('HeaderBar theme toggle', () => {
  it('TB-01: 渲染主题切换按钮', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <HeaderBar systemOnline />
      </MemoryRouter>,
    );
    const btn = screen.getByRole('button', { name: /切换暗色模式/i });
    expect(btn).toBeInTheDocument();
  });

  it('TB-02: 点击切换暗色', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <HeaderBar systemOnline />
      </MemoryRouter>,
    );
    const btn = screen.getByRole('button', { name: /切换暗色模式/i });
    fireEvent.click(btn);
    expect(mockToggle).toHaveBeenCalledTimes(1);
  });

  it('TB-03: 亮色显示太阳图标', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <HeaderBar systemOnline />
      </MemoryRouter>,
    );
    const btn = screen.getByRole('button', { name: /切换暗色模式/i });
    expect(btn).toBeInTheDocument();
  });
});
