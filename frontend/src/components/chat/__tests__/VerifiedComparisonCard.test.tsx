// -*- coding: utf-8 -*-
/** 已核验比较卡片的回答级展示契约。 */
import { fireEvent, render, screen } from '@testing-library/react';
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

const multiCompanyComparison = {
  ...comparison,
  items: [
    comparison.items[0],
    {
      company_name: '中国电信',
      value: 5236,
      source_file: '电信2024年度报告.pdf',
      pages: [18],
      excerpt: '2024 年营业收入为人民币 5,236 亿元。',
    },
    {
      company_name: '中国联通',
      value: 3896,
      source_file: '联通2024年度报告.pdf',
      pages: [9],
      excerpt: '2024 年营业收入为人民币 3,896 亿元。',
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

  it('CP-R41 多公司事实展示可核验摘要与横向量级条，单公司不展示比较视觉', () => {
    const { rerender } = render(<VerifiedComparisonCard comparison={multiCompanyComparison} />);

    expect(screen.getByText('最高营业收入')).toBeInTheDocument();
    expect(screen.getByText('中国移动 10,408亿元')).toBeInTheDocument();
    expect(screen.getByText('领先第二名 5,172亿元')).toBeInTheDocument();
    expect(screen.getByRole('list', { name: '营业收入对比图' })).toBeInTheDocument();
    expect(screen.getByRole('listitem', { name: '中国联通 3,896亿元，占最高值 37%' })).toBeInTheDocument();

    rerender(<VerifiedComparisonCard comparison={comparison} />);
    expect(screen.queryByRole('list', { name: '营业收入对比图' })).not.toBeInTheDocument();
  });

  it('CP-R43 仅对当前回答精确匹配的来源提供一跳证据定位', () => {
    const onViewEvidence = vi.fn();
    render(<VerifiedComparisonCard comparison={comparison} sources={[
      { index: 7, company_name: '中国移动', source_file: '移动2024年度报告.pdf', pages: [3], scores: {} },
      { index: 8, company_name: '中国移动', source_file: '移动2024年度报告.pdf', pages: [4], scores: {} },
    ]} onViewEvidence={onViewEvidence} />);

    fireEvent.click(screen.getByRole('button', { name: '查看中国移动的证据' }));
    expect(onViewEvidence).toHaveBeenCalledWith(7);
    expect(screen.getAllByRole('button', { name: '查看中国移动的证据' })).toHaveLength(1);
  });

  it('CP-R58: 已核验比较使用统一财务主题钩子，不影响精确事实展示', () => {
    const { container } = render(<VerifiedComparisonCard comparison={multiCompanyComparison} />);
    expect(container.querySelector('.verified-comparison-card--financial')).toBeInTheDocument();
    expect(screen.getByText('10,408')).toBeInTheDocument();
  });
});
