// -*- coding: utf-8 -*-
/**
 * 全局应用状态 (Zustand)
 * 管理主题、侧边栏折叠等全局状态
 */

import { create } from 'zustand';
import type { AccentTheme } from '@/styles/theme';
import { getStoredAppearance } from '@/utils/appearancePreference';

export type ThemeMode = 'light' | 'dark';

/** 当前运行期研究范围，不进入浏览器持久化 */
export interface ResearchContext {
  /** 下次提问限定的公司名称 */
  companyName?: string;
  /** 下次提问使用的模式 */
  mode?: 'rag' | 'agent';
}

interface AppState {
  /** 当前主题模式 */
  themeMode: ThemeMode;
  /** 设置主题模式 */
  setThemeMode: (mode: ThemeMode) => void;
  /** 当前主体色方案 */
  accentTheme: AccentTheme;
  /** 设置主体色方案 */
  setAccentTheme: (theme: AccentTheme) => void;

  /** 当前运行期研究范围 */
  researchContext: ResearchContext;
  /** 合并更新当前运行期研究范围 */
  setResearchContext: (context: Partial<ResearchContext>) => void;

  /** 侧边栏是否折叠 */
  siderCollapsed: boolean;
  /** 切换侧边栏折叠状态 */
  toggleSider: () => void;
  /** 设置侧边栏折叠状态 */
  setSiderCollapsed: (collapsed: boolean) => void;
}

const initialAppearance = getStoredAppearance();

function getInitialResearchMode(): ResearchContext['mode'] {
  try {
    return localStorage.getItem('agent-mode') === 'true' ? 'agent' : 'rag';
  } catch {
    return 'rag';
  }
}

export const appStore = create<AppState>((set) => ({
  // 主题
  themeMode: initialAppearance.themeMode,
  setThemeMode: (mode) => set({ themeMode: mode }),
  accentTheme: initialAppearance.accentTheme,
  setAccentTheme: (theme) => set({ accentTheme: theme }),
  researchContext: { mode: getInitialResearchMode() },
  setResearchContext: (context) => set((state) => {
    const researchContext = { ...state.researchContext, ...context };
    Object.entries(context).forEach(([key, value]) => {
      if (value === undefined) {
        delete researchContext[key as keyof ResearchContext];
      }
    });
    return { researchContext };
  }),

  // 侧边栏
  siderCollapsed: false,
  toggleSider: () => set((s) => ({ siderCollapsed: !s.siderCollapsed })),
  setSiderCollapsed: (collapsed) => set({ siderCollapsed: collapsed }),
}));
