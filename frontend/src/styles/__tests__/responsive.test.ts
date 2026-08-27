// -*- coding: utf-8 -*-
/** 响应式断点回归测试。 */
import { describe, expect, it } from 'vitest';
import '../responsive.css';

/** 从样式表中查找指定条件的媒体规则 */
function findMediaRule(conditionText: string): CSSMediaRule {
  const rule = Array.from(document.styleSheets)
    .flatMap((sheet) => Array.from(sheet.cssRules))
    .find((rule) => rule instanceof CSSMediaRule && rule.conditionText === conditionText) as CSSMediaRule;
  expect(rule, `应存在媒体规则 ${conditionText}`).toBeTruthy();
  return rule;
}

describe('窄屏顶栏压缩', () => {
  it('CP-R17: 768px 以下隐藏长研究摘要，保留研究范围入口', () => {
    const mobileRule = findMediaRule('(max-width: 768px)');
    const compactRule = Array.from(mobileRule.cssRules)
      .find((rule) => rule instanceof CSSStyleRule && rule.cssText.includes('.header-research-context')) as CSSStyleRule;

    expect(compactRule.selectorText).toContain('.header-research-context');
    expect(compactRule.style.display).toBe('none');
  });
});

describe('中窄屏会话列表收起', () => {
  it('CP-R67: 1199px 及以下收起会话列表并显示移动会话触发器', () => {
    // 对应 design 断点表：768–1199px 会话侧栏默认收起，
    // 由 ChatContainer 既有的移动会话抽屉与触发器承担打开职责，
    // 避免主导航叠加常驻会话列表挤压主画布产生横向滚动。
    const mediumRule = findMediaRule('(max-width: 1199px)');
    const sidebarRule = Array.from(mediumRule.cssRules)
      .find((rule) => rule instanceof CSSStyleRule && rule.cssText.includes('.chat-session-sidebar')) as CSSStyleRule;
    const triggerRule = Array.from(mediumRule.cssRules)
      .find((rule) => rule instanceof CSSStyleRule && rule.cssText.includes('.chat-mobile-session-trigger')) as CSSStyleRule;

    expect(sidebarRule, '中窄屏应存在会话列表隐藏规则').toBeTruthy();
    expect(sidebarRule.style.display).toBe('none');
    expect(triggerRule, '中窄屏应存在移动会话触发器显示规则').toBeTruthy();
    expect(triggerRule.style.display).toBe('inline-flex');
  });

  it('CP-R67: 769px 及以上不再依赖 768px 块重复声明会话列表显隐', () => {
    // 显隐职责统一上收到 1199px 断点后，768px 块内不应残留同类声明，避免双处维护漂移。
    const mobileRule = findMediaRule('(max-width: 768px)');
    const duplicated = Array.from(mobileRule.cssRules)
      .filter((rule) => rule instanceof CSSStyleRule)
      .map((rule) => (rule as CSSStyleRule).selectorText)
      .filter((selector) => selector.includes('.chat-session-sidebar') || selector.includes('.chat-mobile-session-trigger'));

    expect(duplicated).toEqual([]);
  });
});
