// -*- coding: utf-8 -*-
/**
 * Vitest 全局测试环境初始化
 * 补充 jsdom 缺失的浏览器 API（antd / @ant-design/x 组件依赖）
 */

import '@testing-library/jest-dom';

/** ResizeObserver 桩实现（antd TextArea autoSize / Card 依赖） */
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof globalThis.ResizeObserver === 'undefined') {
  (globalThis as unknown as { ResizeObserver: typeof ResizeObserver }).ResizeObserver = ResizeObserverMock;
}

/** scrollIntoView 桩实现（jsdom 未实现） */
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}

/** matchMedia 桩实现（antd 响应式 / @ant-design/x useMobile 依赖） */
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = (query: string): MediaQueryList => {
    return {
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    } as unknown as MediaQueryList;
  };
}
