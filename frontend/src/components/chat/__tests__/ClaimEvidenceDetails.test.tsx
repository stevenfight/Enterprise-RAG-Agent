// -*- coding: utf-8 -*-
/** 声明级证据明细组件的展示契约：原始值、归一值、公式与冲突原因。 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ClaimEvidenceDetails from '../ClaimEvidenceDetails';
import type { VerifiedComparison } from '@/types/chat';

vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({ isDark: false }),
}));

const claimComparison: VerifiedComparison = {
  available: true,
  metric_key: 'operating_revenue',
  fiscal_year: 2024,
  unit: '亿元',
  fact_ids: ['operating-revenue-2024-中国移动', 'operating-revenue-2024-中国电信'],
  items: [
    {
      company_name: '中国移动',
      value: 10408,
      source_file: '移动2024年度报告.pdf',
      pages: [3],
      excerpt: '2024 年，营业收入达到人民币 10,408 亿元。',
      raw_value: '10408',
      raw_unit: '亿元',
      normalized_value: '1040800000000',
      normalized_unit: '元',
    },
    {
      company_name: '中国电信',
      value: 5236,
      source_file: '电信2024年度报告.pdf',
      pages: [18],
      excerpt: '2024 年营业收入为人民币 5,236 亿元。',
      raw_value: '5236',
      raw_unit: '亿元',
      normalized_value: '523600000000',
      normalized_unit: '元',
    },
  ],
  calculations: [
    {
      calculation_id: 'calc-revenue-yoy-2024',
      operation: 'yoy_growth',
      formula_version: 'calculator-yoy-v1',
      input_fact_ids: ['operating-revenue-2024-中国移动', 'operating-revenue-2023-中国移动'],
      details: { growth_rate: 0.1 },
    },
  ],
  conflicts: [
    {
      conflict_id: 'conflict-revenue-2024',
      status: 'pending_review',
      conflict_type: 'VALUE_CONFLICT',
      fact_ids: ['operating-revenue-2024-中国移动', 'operating-revenue-2024-中国电信'],
      relative_difference: '0.06',
      preferred_fact_id: 'operating-revenue-2024-中国移动',
    },
  ],
};

describe('ClaimEvidenceDetails', () => {
  it('B-T25-01 展示每个事实的原始值与归一值', () => {
    render(<ClaimEvidenceDetails comparison={claimComparison} />);

    expect(screen.getByRole('region', { name: '声明级证据明细' })).toBeInTheDocument();
    expect(screen.getByText('中国移动')).toBeInTheDocument();
    expect(screen.getByText('原始值 10408亿元')).toBeInTheDocument();
    expect(screen.getByText('归一值 1040800000000元')).toBeInTheDocument();
    expect(screen.getByText('原始值 5236亿元')).toBeInTheDocument();
    expect(screen.getByText('归一值 523600000000元')).toBeInTheDocument();
  });

  it('B-T25-02 展示关联公式与冲突原因', () => {
    render(<ClaimEvidenceDetails comparison={claimComparison} />);

    expect(screen.getByText(/yoy_growth/)).toBeInTheDocument();
    expect(screen.getByText(/calculator-yoy-v1/)).toBeInTheDocument();
    expect(screen.getByText(/VALUE_CONFLICT/)).toBeInTheDocument();
    expect(screen.getByText(/相对差异 0\.06/)).toBeInTheDocument();
    expect(screen.getByText(/待人工复核/)).toBeInTheDocument();
  });

  it('B-T25-03 旧比较载荷不含声明级字段时不渲染明细', () => {
    const legacyComparison = {
      available: true,
      metric_key: 'operating_revenue',
      fiscal_year: 2024,
      unit: '亿元',
      fact_ids: ['operating-revenue-2024-中国移动'],
      items: [
        {
          company_name: '中国移动',
          value: 10408,
          source_file: '移动2024年度报告.pdf',
          pages: [3],
          excerpt: '2024 年，营业收入达到人民币 10,408 亿元。',
        },
      ],
    } as VerifiedComparison;

    const { container } = render(<ClaimEvidenceDetails comparison={legacyComparison} />);
    expect(container).toBeEmptyDOMElement();
  });
});
