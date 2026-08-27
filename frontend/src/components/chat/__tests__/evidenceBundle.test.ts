// -*- coding: utf-8 -*-
/** C9 回答证据分组的纯数据契约测试。 */
import { describe, expect, it } from 'vitest';
import { buildEvidenceBundles } from '@/components/chat/evidenceBundle';

describe('buildEvidenceBundles', () => {
  it('CP-R31: 按公司与报告聚合，保留来源顺序、序号、摘要和单条分数', () => {
    const bundles = buildEvidenceBundles([
      { index: 3, source_file: '移动2024年度报告.pdf', pages: [18, 17], company_name: '中国移动', excerpt: '第一条摘要', scores: { hybrid: 0.91 } },
      { index: 7, source_file: '移动2024年度报告.pdf', pages: [17, 19], company_name: '中国移动', excerpt: '第二条摘要', scores: { hybrid: 0.73 } },
      { index: 8, source_file: '电信2024年度报告.pdf', pages: [18], company_name: '中国电信', scores: {} },
    ]);

    expect(bundles).toHaveLength(2);
    expect(bundles[0]).toMatchObject({
      companyName: '中国移动',
      sourceFile: '移动2024年度报告.pdf',
      pages: [17, 18, 19],
      evidenceKind: 'retrieval',
    });
    expect(bundles[0].sources.map((source) => source.index)).toEqual([3, 7]);
    expect(bundles[0].sources.map((source) => source.excerpt)).toEqual(['第一条摘要', '第二条摘要']);
    expect(bundles[0].sources.map((source) => source.scores.hybrid)).toEqual([0.91, 0.73]);
    expect(bundles[1].evidenceKind).toBe('answer');
  });
});
