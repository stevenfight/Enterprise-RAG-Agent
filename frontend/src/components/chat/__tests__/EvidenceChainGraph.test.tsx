// -*- coding: utf-8 -*-
/** 回答级证据链的 TDD 验收测试。 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import type { SourceInfo } from '@/types/chat';
import EvidenceChainGraph from '@/components/chat/EvidenceChainGraph';
import { buildEvidenceChain } from '@/components/chat/evidenceChain';

const sources: SourceInfo[] = [
  { index: 1, source_file: '中国移动2024年度报告.pdf', pages: [17], company_name: '中国移动', scores: {}, excerpt: '营业收入达到人民币 10,408 亿元' },
  { index: 2, source_file: '中国电信2024年度报告.pdf', pages: [18], company_name: '中国电信', scores: {}, excerpt: '营业收入为人民币 5,236 亿元' },
];

describe('EvidenceChainGraph', () => {
  it('RED-01 只标记正文真实引用且存在于当前来源的节点', () => {
    const chain = buildEvidenceChain('结论内容[来源1]，另有[来源9]。', sources);
    expect(chain.citedIndexes).toEqual([1]);
    expect(chain.nodes.map((node) => [node.index, node.cited])).toEqual([[1, true], [2, false]]);
  });

  it('RED-02 展示回答节点、来源节点和引用状态', () => {
    render(<EvidenceChainGraph answer="结论内容[来源1]" sources={sources} onViewEvidence={vi.fn()} />);
    expect(screen.getByRole('region', { name: '回答级证据链' })).toBeInTheDocument();
    expect(screen.getByText('研究结论')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /中国移动2024年度报告/ })).toHaveTextContent('已引用');
    expect(screen.getByRole('button', { name: /中国电信2024年度报告/ })).toHaveTextContent('未在正文标记');
  });

  it('RED-03 点击来源节点定位当前回答的证据', () => {
    const onViewEvidence = vi.fn();
    render(<EvidenceChainGraph answer="结论内容[来源1]" sources={sources} onViewEvidence={onViewEvidence} />);
    fireEvent.click(screen.getByRole('button', { name: /中国移动2024年度报告/ }));
    expect(onViewEvidence).toHaveBeenCalledWith(1);
  });

  it('M4.2: 视觉来源展示证据类型与未完成制品警告', () => {
    const visualSources: SourceInfo[] = [{
      index: 3,
      source_file: '扫描年报.pdf',
      pages: [21],
      company_name: '示例公司',
      scores: {},
      visual_preview_status: 'incomplete',
    }];

    render(<EvidenceChainGraph answer="结论[来源3]" sources={visualSources} onViewEvidence={vi.fn()} />);

    expect(screen.getByText('视觉证据')).toBeInTheDocument();
    expect(screen.getByText('视觉制品未完成')).toBeInTheDocument();
  });
});
