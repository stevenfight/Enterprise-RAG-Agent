// -*- coding: utf-8 -*-
/**
 * TDD 测试: 财务格式化工具
 * 对应 tdd: openspec/changes/financial-cards-beautify/specs/tdd-financial-cards.md
 */

import { describe, it, expect } from 'vitest';
import { extractFinancialKPIs, isNumericCell, formatMarkdown } from '@/utils/financialFormat';

// ============================================================
// 模块 A: extractFinancialKPIs
// ============================================================

describe('extractFinancialKPIs', () => {
  it('KPI-01: 提取营收', () => {
    const text = '2024年营收1,234.5亿元';
    const kpis = extractFinancialKPIs(text);
    expect(kpis).toHaveLength(1);
    expect(kpis[0]).toMatchObject({
      name: '营业收入',
      value: '1,234.5',
      unit: '亿元',
      type: 'revenue',
    });
  });

  it('KPI-02: 提取净利润', () => {
    const text = '净利润567.8亿元';
    const kpis = extractFinancialKPIs(text);
    expect(kpis).toHaveLength(1);
    expect(kpis[0]).toMatchObject({
      name: '净利润',
      value: '567.8',
      unit: '亿元',
      type: 'profit',
    });
  });

  it('KPI-03: 提取同比增长', () => {
    const text = '同比增长5.6%';
    const kpis = extractFinancialKPIs(text);
    expect(kpis).toHaveLength(1);
    expect(kpis[0]).toMatchObject({
      name: '同比增长',
      value: '+5.6',
      unit: '%',
      type: 'growth',
      isPositive: true,
    });
  });

  it('KPI-04: 提取负增长', () => {
    const text = '同比下降3.2%';
    const kpis = extractFinancialKPIs(text);
    expect(kpis).toHaveLength(1);
    expect(kpis[0]).toMatchObject({
      name: '同比下降',
      value: '-3.2',
      unit: '%',
      type: 'growth',
      isPositive: false,
    });
  });

  it('KPI-05: 多指标混合', () => {
    const text = '营收1,234.5亿元，净利润567.8亿元，同比增长5.6%';
    const kpis = extractFinancialKPIs(text);
    expect(kpis).toHaveLength(3);
  });

  it('KPI-06: 无匹配内容', () => {
    const text = '你好，请问今天天气如何？';
    const kpis = extractFinancialKPIs(text);
    expect(kpis).toHaveLength(0);
  });

  it('KPI-07: 提取 ROE', () => {
    const text = 'ROE: 12.5%';
    const kpis = extractFinancialKPIs(text);
    expect(kpis).toHaveLength(1);
    expect(kpis[0]).toMatchObject({
      name: 'ROE',
      value: '12.5',
      unit: '%',
      type: 'roe',
    });
  });

  it('KPI-08: 提取毛利率', () => {
    const text = '毛利率：35.2%';
    const kpis = extractFinancialKPIs(text);
    expect(kpis).toHaveLength(1);
    expect(kpis[0]).toMatchObject({
      name: '毛利率',
      value: '35.2',
      unit: '%',
      type: 'margin',
    });
  });
});

// ============================================================
// 模块 B: isNumericCell
// ============================================================

describe('isNumericCell', () => {
  it('识别纯数字', () => {
    expect(isNumericCell('1,234.5')).toBe(true);
  });

  it('识别百分比', () => {
    expect(isNumericCell('5.6%')).toBe(true);
  });

  it('识别货币符号', () => {
    expect(isNumericCell('¥1,234')).toBe(true);
  });

  it('拒绝纯文本', () => {
    expect(isNumericCell('中国移动')).toBe(false);
  });
});

// ============================================================
// 模块 C: formatMarkdown 表格美化
// ============================================================

describe('formatMarkdown table beautification', () => {
  const mdTable = `| 公司 | 营收(亿元) | 同比增长 |
|---|---|---|
| 中国移动 | 1,023.4 | 5.6% |
| 中国电信 | 567.8 | 3.2% |`;

  it('TB-01: 表格包含表头渐变', () => {
    const html = formatMarkdown(mdTable, false);
    expect(html).toContain('linear-gradient');
  });

  it('TB-02: 斑马纹行', () => {
    const html = formatMarkdown(mdTable, false);
    // 偶数行应有特殊背景色
    expect(html).toMatch(/#FAF8FC|#FFFFFF/);
  });

  it('TB-03: 数字列右对齐', () => {
    const html = formatMarkdown(mdTable, false);
    expect(html).toContain('text-align:right');
  });

  it('TB-04: 表格圆角外框', () => {
    const html = formatMarkdown(mdTable, false);
    expect(html).toContain('border-radius:12px');
  });

  it('TB-05: 表格阴影', () => {
    const html = formatMarkdown(mdTable, false);
    expect(html).toContain('box-shadow');
  });

  it('TB-06: 等宽数字字体', () => {
    const html = formatMarkdown(mdTable, false);
    expect(html).toContain('font-family');
  });

  it('TB-07: 非表格内容不受影响', () => {
    const text = '`code` **bold**';
    const html = formatMarkdown(text, false);
    expect(html).toContain('<code');
    expect(html).toContain('<strong>bold</strong>');
  });
});
