// -*- coding: utf-8 -*-
/**
 * TDD 测试: useTheme 外观偏好持久化
 * 覆盖: 同一批次内连续调用切换回调时, saveAppearance 必须写入最新外观组合
 */

import { beforeEach, describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useTheme } from '../useTheme';
import { appStore } from '@/stores/appStore';

describe('useTheme 外观持久化', () => {
  beforeEach(() => {
    window.localStorage.clear();
    // 重置为主题初始默认值(暗色 + 金融青绿)
    appStore.setState({ themeMode: 'dark', accentTheme: 'financialTeal' });
  });

  it('CP-R68-01: 先选亮色再选主体色时, localStorage 必须保留亮色模式', () => {
    const { result } = renderHook(() => useTheme());

    act(() => {
      result.current.setTheme('light');
      result.current.setAccentTheme('deepBlue');
    });

    expect(window.localStorage.getItem('app-theme')).toBe('light');
    expect(window.localStorage.getItem('app-accent-theme')).toBe('deepBlue');
    // store 内部状态同步一致
    expect(appStore.getState().themeMode).toBe('light');
    expect(appStore.getState().accentTheme).toBe('deepBlue');
  });

  it('CP-R68-02: 先选主体色再切亮色时, localStorage 必须保留新主体色', () => {
    const { result, rerender } = renderHook(() => useTheme());
    // 从深蓝主体色出发
    appStore.setState({ themeMode: 'dark', accentTheme: 'deepBlue' });
    act(() => {
      rerender();
    });

    act(() => {
      result.current.setAccentTheme('financialTeal');
      result.current.setTheme('light');
    });

    expect(window.localStorage.getItem('app-theme')).toBe('light');
    expect(window.localStorage.getItem('app-accent-theme')).toBe('financialTeal');
    expect(appStore.getState().accentTheme).toBe('financialTeal');
    expect(appStore.getState().themeMode).toBe('light');
  });

  it('CP-R68-03: toggleTheme 在同一批次与主体色切换连用时互不覆盖', () => {
    const { result } = renderHook(() => useTheme());

    act(() => {
      result.current.toggleTheme();
      result.current.setAccentTheme('deepBlue');
    });

    expect(window.localStorage.getItem('app-theme')).toBe('light');
    expect(window.localStorage.getItem('app-accent-theme')).toBe('deepBlue');
  });
});
