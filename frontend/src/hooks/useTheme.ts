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
  const toggleTheme = useCallback(() => {
    const next: ThemeMode = themeMode === 'light' ? 'dark' : 'light';
    setThemeMode(next);
    saveAppearance({ themeMode: next, accentTheme });
  }, [accentTheme, themeMode, setThemeMode]);

  // 设置指定主题
  const setTheme = useCallback(
    (mode: ThemeMode) => {
      setThemeMode(mode);
      saveAppearance({ themeMode: mode, accentTheme });
    },
    [accentTheme, setThemeMode],
  );

  // 设置指定主体色
  const setAccentTheme = useCallback(
    (theme: AccentTheme) => {
      setAccentThemeState(theme);
      saveAppearance({ themeMode, accentTheme: theme });
    },
    [setAccentThemeState, themeMode],
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
