// -*- coding: utf-8 -*-
/**
 * 全局应用状态 (Zustand)
 * 管理主题、侧边栏折叠等全局状态
 */

import { create } from 'zustand';

export type ThemeMode = 'light' | 'dark';

interface AppState {
  /** 当前主题模式 */
  themeMode: ThemeMode;
  /** 设置主题模式 */
  setThemeMode: (mode: ThemeMode) => void;

  /** 侧边栏是否折叠 */
  siderCollapsed: boolean;
  /** 切换侧边栏折叠状态 */
  toggleSider: () => void;
  /** 设置侧边栏折叠状态 */
  setSiderCollapsed: (collapsed: boolean) => void;
}

export const appStore = create<AppState>((set) => ({
  // 主题
  themeMode: 'light',
  setThemeMode: (mode) => set({ themeMode: mode }),

  // 侧边栏
  siderCollapsed: false,
  toggleSider: () => set((s) => ({ siderCollapsed: !s.siderCollapsed })),
  setSiderCollapsed: (collapsed) => set({ siderCollapsed: collapsed }),
}));
