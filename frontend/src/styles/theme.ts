// -*- coding: utf-8 -*-
/**
 * Ant Design 主题 token 定义
 * 马卡龙配色方案 - 柔和粉彩 + 玻璃拟态，高端企业级财务分析界面
 */

import type { ThemeConfig } from 'antd';

// ============================================================
// 马卡龙色板 - 低饱和度高明度粉彩色系
// ============================================================

// 主色调: 马卡龙紫 (柔和薰衣草)
const MACARON_PURPLE = '#B8A9C9';
const MACARON_PURPLE_LIGHT = '#D4C5E9';
const MACARON_PURPLE_DARK = '#9B8EC4';

// 辅助马卡龙色
const MACARON_MINT = '#98D8C8';       // 薄荷绿
const MACARON_ROSE = '#F4B8C8';       // 玫瑰粉
const MACARON_PEACH = '#FAD4B8';      // 蜜桃橙
const MACARON_BLUE = '#A8D8EA';       // 天空蓝
const MACARON_YELLOW = '#FFF1C1';     // 柠檬黄

// 亮色主题背景
const LIGHT_BG = '#FBF7F2';           // 暖奶油底色
const LIGHT_CARD = '#FFFFFF';         // 纯白卡片
const LIGHT_SIDEBAR = '#FFF9F5';      // 侧边栏暖白

// 暗色主题背景
const DARK_BG = '#1A1826';            // 深紫黑底
const DARK_CARD = '#252236';          // 暗紫卡片
const DARK_SIDEBAR = '#1F1D2B';       // 侧边栏深紫

// 文字色
const TEXT_PRIMARY_LIGHT = '#3D3554';
const TEXT_SECONDARY_LIGHT = '#9B95A9';
const TEXT_PRIMARY_DARK = '#E8E0F0';
const TEXT_SECONDARY_DARK = '#8B85A0';

// 渐变预设
export const gradients = {
  // 主渐变: 紫→粉
  hero: `linear-gradient(135deg, ${MACARON_PURPLE} 0%, ${MACARON_ROSE} 100%)`,
  // 柔和渐变: 蓝→薄荷
  soft: `linear-gradient(135deg, ${MACARON_BLUE} 0%, ${MACARON_MINT} 100%)`,
  // 暖色渐变: 桃→黄
  warm: `linear-gradient(135deg, ${MACARON_PEACH} 0%, ${MACARON_YELLOW} 100%)`,
  // 梦幻渐变: 紫→蓝
  dream: `linear-gradient(135deg, ${MACARON_PURPLE} 0%, ${MACARON_BLUE} 100%)`,
  // 暗色渐变
  darkHero: `linear-gradient(135deg, #2D2640 0%, #3D2E4A 100%)`,
  // 消息气泡-用户
  bubbleUser: `linear-gradient(135deg, ${MACARON_PURPLE} 0%, ${MACARON_PURPLE_DARK} 100%)`,
};

// 玻璃拟态预设
export const glass = {
  light: {
    background: 'rgba(255, 255, 255, 0.6)',
    backdropFilter: 'blur(12px)',
    border: '1px solid rgba(255, 255, 255, 0.8)',
    boxShadow: '0 4px 24px rgba(184, 169, 201, 0.12)',
  },
  dark: {
    background: 'rgba(37, 34, 54, 0.6)',
    backdropFilter: 'blur(12px)',
    border: '1px solid rgba(255, 255, 255, 0.06)',
    boxShadow: '0 4px 24px rgba(0, 0, 0, 0.3)',
  },
};

export const colors = {
  // 马卡龙主色
  primary: MACARON_PURPLE,
  primaryLight: MACARON_PURPLE_LIGHT,
  primaryDark: MACARON_PURPLE_DARK,

  // 强调色: 薄荷绿
  accent: MACARON_MINT,
  accentLight: '#B8E8DC',
  accentDark: '#78C0A8',

  // 辅助马卡龙色
  rose: MACARON_ROSE,
  peach: MACARON_PEACH,
  blue: MACARON_BLUE,
  yellow: MACARON_YELLOW,

  // 语义色 - 适配马卡龙风格
  success: '#7ECB9A',
  warning: '#F0C07E',
  error: '#E88B8B',
  info: '#8BB8E0',

  // 文字色
  textPrimary: TEXT_PRIMARY_LIGHT,
  textSecondary: TEXT_SECONDARY_LIGHT,
  textPrimaryDark: TEXT_PRIMARY_DARK,
  textSecondaryDark: TEXT_SECONDARY_DARK,

  // 边框/分割线
  border: '#E8E3EF',
  divider: '#F0EBF5',

  // 背景色
  bgLight: LIGHT_BG,
  bgCard: LIGHT_CARD,
  bgSidebar: LIGHT_SIDEBAR,
  bgDark: DARK_BG,
  bgDarkCard: DARK_CARD,
  bgDarkSidebar: DARK_SIDEBAR,
};

// 亮色主题配置
export const lightTheme: ThemeConfig = {
  token: {
    colorPrimary: colors.primary,
    colorInfo: colors.info,
    colorSuccess: colors.success,
    colorWarning: colors.warning,
    colorError: colors.error,
    colorBgBase: LIGHT_BG,
    colorBgContainer: LIGHT_CARD,
    colorBgElevated: LIGHT_CARD,
    colorTextBase: TEXT_PRIMARY_LIGHT,
    colorTextSecondary: TEXT_SECONDARY_LIGHT,
    borderRadius: 12,
    borderRadiusSM: 8,
    borderRadiusLG: 16,
    fontFamily: `'Source Han Sans CN', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`,
    fontSize: 14,
    colorBorder: colors.border,
    colorBorderSecondary: colors.divider,
  },
  components: {
    Layout: {
      siderBg: LIGHT_SIDEBAR,
      headerBg: LIGHT_CARD,
    },
    Menu: {
      itemBg: 'transparent',
      itemSelectedBg: `${MACARON_PURPLE}18`,
      itemSelectedColor: MACARON_PURPLE,
      itemHoverBg: `${MACARON_PURPLE}0A`,
      borderRadius: 12,
      itemMarginInline: 8,
      itemHeight: 42,
    },
    Button: {
      primaryShadow: '0 2px 8px rgba(184, 169, 201, 0.35)',
      borderRadius: 10,
      controlHeight: 38,
    },
    Card: {
      borderRadius: 14,
    },
    Input: {
      borderRadius: 10,
      controlHeight: 38,
    },
    Select: {
      borderRadius: 10,
      controlHeight: 38,
    },
    Slider: {
      trackBg: MACARON_PURPLE,
      trackHoverBg: MACARON_PURPLE_DARK,
      handleColor: MACARON_PURPLE,
      handleActiveColor: MACARON_PURPLE_DARK,
    },
    Switch: {
      trackHeight: 22,
      handleSize: 18,
    },
    Collapse: {
      borderRadius: 12,
    },
  },
};

// 暗色主题配置
export const darkTheme: ThemeConfig = {
  token: {
    colorPrimary: MACARON_PURPLE_LIGHT,
    colorInfo: '#8BB8E0',
    colorSuccess: '#7ECB9A',
    colorWarning: '#F0C07E',
    colorError: '#E88B8B',
    colorBgBase: DARK_BG,
    colorBgContainer: DARK_CARD,
    colorBgElevated: '#2D2A3A',
    colorTextBase: TEXT_PRIMARY_DARK,
    colorTextSecondary: TEXT_SECONDARY_DARK,
    borderRadius: 12,
    borderRadiusSM: 8,
    borderRadiusLG: 16,
    fontFamily: `'Source Han Sans CN', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`,
    fontSize: 14,
    colorBorder: '#3A3550',
    colorBorderSecondary: '#2E2A40',
  },
  components: {
    Layout: {
      siderBg: DARK_SIDEBAR,
      headerBg: DARK_SIDEBAR,
    },
    Menu: {
      itemBg: 'transparent',
      itemSelectedBg: `${MACARON_PURPLE_LIGHT}18`,
      itemSelectedColor: MACARON_PURPLE_LIGHT,
      itemHoverBg: `${MACARON_PURPLE_LIGHT}0A`,
      borderRadius: 12,
      itemMarginInline: 8,
      itemHeight: 42,
    },
    Button: {
      primaryShadow: '0 2px 12px rgba(184, 169, 201, 0.3)',
      borderRadius: 10,
      controlHeight: 38,
    },
    Card: {
      borderRadius: 14,
    },
    Input: {
      borderRadius: 10,
      controlHeight: 38,
    },
    Select: {
      borderRadius: 10,
      controlHeight: 38,
    },
    Slider: {
      trackBg: MACARON_PURPLE_LIGHT,
      trackHoverBg: MACARON_PURPLE,
      handleColor: MACARON_PURPLE_LIGHT,
      handleActiveColor: MACARON_PURPLE,
    },
    Switch: {
      trackHeight: 22,
      handleSize: 18,
    },
    Collapse: {
      borderRadius: 12,
    },
  },
};

// 等宽字体 (用于财务数字展示)
export const monoFont = `'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace`;
