// -*- coding: utf-8 -*-
/** 高级视觉统一的 TDD 验收测试。 */
import { describe, expect, it } from 'vitest';
import { colors, createThemeConfig } from '@/styles/theme';
import '../global.css';
import '../responsive.css';

describe('高级视觉主题 token', () => {
  it('RED-01 导出页面层级表面色', () => {
    expect(colors).toHaveProperty('pageBackgroundDark');
    expect(colors).toHaveProperty('pageSurfaceDark');
    expect(colors).toHaveProperty('pageInputDark');
  });

  it('RED-02 暗色输入表面不是纯白', () => {
    const darkToken = createThemeConfig('dark', 'financialTeal').token as Record<string, string>;
    expect(darkToken.colorBgContainer).not.toBe('#FFFFFF');
  });
});

describe('高级视觉样式规则', () => {
  it('RED-03 存在统一表面和输入框规则', () => {
    const cssText = Array.from(document.styleSheets)
      .flatMap((sheet) => Array.from(sheet.cssRules))
      .map((rule) => rule.cssText)
      .join('\n');

    expect(cssText).toContain('.research-surface');
    expect(cssText).toContain('.ant-sender');
    expect(cssText).toContain('var(--page-input-bg');
  });

  it('RED-04 辅助页摘要网格具备自适应列规则', () => {
    const cssText = Array.from(document.styleSheets)
      .flatMap((sheet) => Array.from(sheet.cssRules))
      .map((rule) => rule.cssText)
      .join('\n');

    expect(cssText).toContain('.research-output-strip');
    expect(cssText).toContain('minmax(180px, 1fr)');
  });
});
