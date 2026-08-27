// -*- coding: utf-8 -*-
/**
 * 动效偏好工具
 * 读取系统 prefers-reduced-motion 偏好, 为自动滚动提供行为参数
 */

/** 系统偏好减少动画时返回 auto, 否则返回 smooth */
export function getPreferredScrollBehavior(): ScrollBehavior {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
}
