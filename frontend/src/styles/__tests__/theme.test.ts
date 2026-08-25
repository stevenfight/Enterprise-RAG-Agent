// -*- coding: utf-8 -*-
/**
 * theme.ts 语义色测试
 * 覆盖: 聊天区/暗色边框语义色的存在与取值
 */
import { describe, it, expect } from 'vitest';
import { accentThemes, colors, createThemeConfig } from '@/styles/theme';

describe('theme colors 语义色', () => {
  it('TC-UI-001-01 导出 chatAreaLight / chatAreaDark / borderDark', () => {
    expect(colors).toHaveProperty('chatAreaLight');
    expect(colors).toHaveProperty('chatAreaDark');
    expect(colors).toHaveProperty('borderDark');
  });

  it('TC-UI-002-01 chatAreaDark 等于主题暗色背景 #1A1826', () => {
    expect(colors.chatAreaDark).toBe('#1A1826');
  });

  it('TC-UI-002-02 borderDark 等于 #3A3550', () => {
    expect(colors.borderDark).toBe('#3A3550');
  });

  it('TC-UI-001-01 chatAreaLight 为浅色聊天区背景', () => {
    expect(colors.chatAreaLight).toBe('#FAFAFA');
  });
});

describe('主体色主题工厂', () => {
  it('DS-R05-01 金融青绿和深蓝主体色均已注册', () => {
    expect(accentThemes.financialTeal.light).toBe('#0F766E');
    expect(accentThemes.financialTeal.dark).toBe('#2DD4BF');
    expect(accentThemes.deepBlue.light).toBe('#1D4ED8');
    expect(accentThemes.deepBlue.dark).toBe('#60A5FA');
  });

  it('DS-R05-02 工厂根据模式和主体色返回对应 Ant Design 主色', () => {
    expect(createThemeConfig('light', 'financialTeal').token?.colorPrimary).toBe('#0F766E');
    expect(createThemeConfig('dark', 'deepBlue').token?.colorPrimary).toBe('#60A5FA');
  });

  it('DS-R07-01 主题工厂不将主体色用作成功语义色', () => {
    const tealTheme = createThemeConfig('light', 'financialTeal');
    const blueTheme = createThemeConfig('light', 'deepBlue');

    expect(tealTheme.token?.colorSuccess).toBe(blueTheme.token?.colorSuccess);
    expect(tealTheme.token?.colorSuccess).not.toBe(tealTheme.token?.colorPrimary);
  });

  it('DS-R07-02 品牌相关组件 token 跟随当前主体色', () => {
    const blueTheme = createThemeConfig('light', 'deepBlue');
    const menuToken = blueTheme.components?.Menu as { itemSelectedColor?: string };
    const sliderToken = blueTheme.components?.Slider as { trackBg?: string; handleColor?: string };

    expect(menuToken.itemSelectedColor).toBe('#1D4ED8');
    expect(sliderToken.trackBg).toBe('#1D4ED8');
    expect(sliderToken.handleColor).toBe('#1D4ED8');
  });
});
