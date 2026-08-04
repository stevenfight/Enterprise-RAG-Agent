// -*- coding: utf-8 -*-
/**
 * 主题切换 Hook
 * 支持亮色/暗色切换，localStorage 持久化
 */

import { useCallback, useEffect } from 'react';
import { appStore } from '@/stores/appStore';

const STORAGE_KEY = 'app-theme';

export type ThemeMode = 'light' | 'dark';

/** 从 localStorage 读取初始主题 */
function getStoredTheme(): ThemeMode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'dark' || stored === 'light') {
      return stored;
    }
  } catch {
    // localStorage 不可用时忽略
  }
  return 'light';
}

/** 保存主题到 localStorage */
function saveTheme(mode: ThemeMode) {
  try {
    localStorage.setItem(STORAGE_KEY, mode);
  } catch {
    // localStorage 不可用时忽略
  }
}

/** 主题切换 Hook */
export function useTheme() {
  const themeMode = appStore((s) => s.themeMode);
  const setThemeMode = appStore((s) => s.setThemeMode);

  // 初始化: 从 localStorage 恢复主题
  useEffect(() => {
    const stored = getStoredTheme();
    if (stored !== themeMode) {
      setThemeMode(stored);
    }
    // 仅挂载时执行一次
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 切换主题
  const toggleTheme = useCallback(() => {
    const next: ThemeMode = themeMode === 'light' ? 'dark' : 'light';
    setThemeMode(next);
    saveTheme(next);
  }, [themeMode, setThemeMode]);

  // 设置指定主题
  const setTheme = useCallback(
    (mode: ThemeMode) => {
      setThemeMode(mode);
      saveTheme(mode);
    },
    [setThemeMode],
  );

  const isDark = themeMode === 'dark';

  return {
    themeMode,
    isDark,
    toggleTheme,
    setTheme,
  };
}
