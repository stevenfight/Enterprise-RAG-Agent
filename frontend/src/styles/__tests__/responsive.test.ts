// -*- coding: utf-8 -*-
/** 375px 顶栏压缩回归测试。 */
import { describe, expect, it } from 'vitest';
import '../responsive.css';

describe('窄屏顶栏压缩', () => {
  it('CP-R17: 768px 以下隐藏长研究摘要，保留研究范围入口', () => {
    const mobileRule = Array.from(document.styleSheets)
      .flatMap((sheet) => Array.from(sheet.cssRules))
      .find((rule) => rule instanceof CSSMediaRule && rule.conditionText === '(max-width: 768px)') as CSSMediaRule;
    const compactRule = Array.from(mobileRule.cssRules)
      .find((rule) => rule instanceof CSSStyleRule && rule.cssText.includes('.header-research-context')) as CSSStyleRule;

    expect(compactRule.selectorText).toContain('.header-research-context');
    expect(compactRule.style.display).toBe('none');
  });
});
