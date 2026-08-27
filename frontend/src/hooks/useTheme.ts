// -*- coding: utf-8 -*-
/**
 * 主题切换 Hook
 * 支持亮色/暗色与主体色切换，localStorage 持久化
 */

import { useCallback } from 'react';
import { appStore, type ThemeMode } from '@/stores/appStore';
import type { AccentTheme } from '@/styles/theme';
import { saveAppearance } from '@/utils/appearancePreference';

export type { ThemeMode } from '@/stores/appStore';

/** 主题切换 Hook */
export function useTheme() {
  const themeMode = appStore((s) => s.themeMode);
  const setThemeMode = appStore((s) => s.setThemeMode);
  const accentTheme = appStore((s) => s.accentTheme);
  const setAccentThemeState = appStore((s) => s.setAccentTheme);

  // 切换主题
  // 说明: 一律从 appStore.getState() 读取最新外观, 避免事件批次内闭包值过期
  // 导致 saveAppearance 将旧主题覆盖回 localStorage(CP-R68)
  const toggleTheme = useCallback(() => {
    const { themeMode: currentMode, accentTheme: currentAccent } = appStore.getState();
    const next: ThemeMode = currentMode === 'light' ? 'dark' : 'light';
    setThemeMode(next);
    saveAppearance({ themeMode: next, accentTheme: currentAccent });
  }, [setThemeMode]);

  // 设置指定主题
  const setTheme = useCallback(
    (mode: ThemeMode) => {
      const { accentTheme: currentAccent } = appStore.getState();
      setThemeMode(mode);
      saveAppearance({ themeMode: mode, accentTheme: currentAccent });
    },
    [setThemeMode],
  );

  // 设置指定主体色
  const setAccentTheme = useCallback(
    (theme: AccentTheme) => {
      const { themeMode: currentMode } = appStore.getState();
      setAccentThemeState(theme);
      saveAppearance({ themeMode: currentMode, accentTheme: theme });
    },
    [setAccentThemeState],
  );

  const isDark = themeMode === 'dark';

  return {
    themeMode,
    accentTheme,
    isDark,
    toggleTheme,
    setTheme,
    setAccentTheme,
  };
}
