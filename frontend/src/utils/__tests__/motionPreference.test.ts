// -*- coding: utf-8 -*-
/**
 * TDD 测试: 动效偏好工具
 * 覆盖: prefers-reduced-motion 下滚动行为降级为 auto(CP-R12)
 */

import { describe, it, expect, afterEach } from 'vitest';
import { getPreferredScrollBehavior } from '../motionPreference';

/** 构造可受控的 matchMedia 桩 */
function stubMatchMedia(reduceMotion: boolean) {
  window.matchMedia = ((query: string) => ({
    matches: reduceMotion && query.includes('prefers-reduced-motion'),
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

describe('motionPreference 工具', () => {
  const originalMatchMedia = window.matchMedia;

  afterEach(() => {
    window.matchMedia = originalMatchMedia;
  });

  it('CP-R12-01: 系统偏好减少动画时滚动行为为 auto', () => {
    stubMatchMedia(true);
    expect(getPreferredScrollBehavior()).toBe('auto');
  });

  it('CP-R12-02: 未声明减少动画时滚动行为为 smooth', () => {
    stubMatchMedia(false);
    expect(getPreferredScrollBehavior()).toBe('smooth');
  });
});
