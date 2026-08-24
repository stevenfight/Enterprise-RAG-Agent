// -*- coding: utf-8 -*-
/**
 * theme.ts 语义色测试
 * 覆盖: 聊天区/暗色边框语义色的存在与取值
 */
import { describe, it, expect } from 'vitest';
import { colors } from '@/styles/theme';

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
