// -*- coding: utf-8 -*-
/**
 * 外观偏好持久化
 * 仅保存已定义的主题模式与主体色，避免不受支持的值进入界面状态。
 */

import type { AccentTheme } from '@/styles/theme';
import type { ThemeMode } from '@/stores/appStore';

const THEME_STORAGE_KEY = 'app-theme';
const ACCENT_STORAGE_KEY = 'app-accent-theme';

export const DEFAULT_ACCENT_THEME: AccentTheme = 'financialTeal';

export interface AppearancePreference {
  themeMode: ThemeMode;
  accentTheme: AccentTheme;
}

/** 读取已保存的外观偏好 */
export function getStoredAppearance(): AppearancePreference {
  try {
    const storedTheme = localStorage.getItem(THEME_STORAGE_KEY);
    const storedAccent = localStorage.getItem(ACCENT_STORAGE_KEY);

    return {
      themeMode: storedTheme === 'dark' || storedTheme === 'light' ? storedTheme : 'light',
      accentTheme:
        storedAccent === 'deepBlue' || storedAccent === 'financialTeal'
          ? storedAccent
          : DEFAULT_ACCENT_THEME,
    };
  } catch {
    // localStorage 不可用时使用默认外观
    return { themeMode: 'light', accentTheme: DEFAULT_ACCENT_THEME };
  }
}

/** 保存主题与主体色偏好 */
export function saveAppearance(preference: AppearancePreference) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, preference.themeMode);
    localStorage.setItem(ACCENT_STORAGE_KEY, preference.accentTheme);
  } catch {
    // localStorage 不可用时忽略保存操作
  }
}
