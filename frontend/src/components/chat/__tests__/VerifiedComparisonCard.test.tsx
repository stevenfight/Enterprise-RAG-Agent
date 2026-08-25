// -*- coding: utf-8 -*-
/** 已核验比较卡片的回答级展示契约。 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import VerifiedComparisonCard from '../VerifiedComparisonCard';

vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({ isDark: false }),
}));

const comparison = {
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
};

describe('VerifiedComparisonCard', () => {
  it('CP-R23-01 回答携带已核验事实时展示数值与出处', () => {
    render(<VerifiedComparisonCard comparison={comparison} />);

    expect(screen.getByRole('region', { name: '已核验对比' })).toBeInTheDocument();
    expect(screen.getByText('中国移动')).toBeInTheDocument();
    expect(screen.getByText('10,408')).toBeInTheDocument();
    expect(screen.getByText('移动2024年度报告.pdf · P3')).toBeInTheDocument();
  });

  it('CP-R23-02 没有已核验比较事实时不渲染卡片', () => {
    const { container } = render(<VerifiedComparisonCard comparison={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});
