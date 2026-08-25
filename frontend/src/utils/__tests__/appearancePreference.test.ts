// -*- coding: utf-8 -*-
/**
 * 外观偏好持久化测试
 * 覆盖受限主体色读取、默认值和保存行为。
 */

import { beforeEach, describe, expect, it } from 'vitest';
import {
  DEFAULT_ACCENT_THEME,
  getStoredAppearance,
  saveAppearance,
} from '@/utils/appearancePreference';

describe('外观偏好持久化', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('DS-R06-01 读取有效的深蓝与暗色偏好', () => {
    localStorage.setItem('app-theme', 'dark');
    localStorage.setItem('app-accent-theme', 'deepBlue');

    expect(getStoredAppearance()).toEqual({
      themeMode: 'dark',
      accentTheme: 'deepBlue',
    });
  });

  it('DS-R06-02 无效主体色回到金融青绿默认值', () => {
    localStorage.setItem('app-accent-theme', 'purple');

    expect(getStoredAppearance().accentTheme).toBe(DEFAULT_ACCENT_THEME);
  });

  it('DS-R06-03 保存主题与主体色偏好', () => {
    saveAppearance({ themeMode: 'light', accentTheme: 'financialTeal' });

    expect(localStorage.getItem('app-theme')).toBe('light');
    expect(localStorage.getItem('app-accent-theme')).toBe('financialTeal');
  });
});
