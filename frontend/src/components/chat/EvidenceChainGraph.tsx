// -*- coding: utf-8 -*-
/** 回答级证据链：仅展示当前回答正文与当前来源数组的严格交集。 */
import { Button, Tag } from 'antd';
import { ArrowRightOutlined, FileSearchOutlined } from '@ant-design/icons';
import type { SourceInfo } from '@/types/chat';
import { buildEvidenceChain } from './evidenceChain';
import { getEvidenceKindLabel } from './evidenceSemantics';

interface EvidenceChainGraphProps {
  answer: string;
  sources: SourceInfo[];
  onViewEvidence: (sourceIndex: number) => void;
}

export default function EvidenceChainGraph({ answer, sources, onViewEvidence }: EvidenceChainGraphProps) {
  const chain = buildEvidenceChain(answer, sources);

  return (
    <section className="evidence-chain-graph" aria-label="回答级证据链">
      <div className="evidence-chain-graph__node evidence-chain-graph__node--answer">
        <span className="evidence-chain-graph__eyebrow">回答节点</span>
        <strong>研究结论</strong>
        <span>{chain.citedIndexes.length} 条正文引用</span>
      </div>
      <div className="evidence-chain-graph__connector" aria-hidden="true">
        <ArrowRightOutlined />
        <span>由来源支撑</span>
      </div>
      <div className="evidence-chain-graph__sources" aria-label="回答来源节点">
        {chain.nodes.map(({ index, source, cited, evidenceKind, integrityStatus }) => (
          <Button
            key={index}
            type="text"
            className="evidence-chain-graph__node evidence-chain-graph__node--source"
            aria-label={`${source.source_file}，第${source.pages.join('、')}页`}
            onClick={() => onViewEvidence(index)}
          >
            <span className="evidence-chain-graph__source-icon" aria-hidden="true"><FileSearchOutlined /></span>
            <span className="evidence-chain-graph__source-copy">
              <strong>{source.source_file}</strong>
              <span>{source.company_name} · 第 {source.pages.join('、')} 页</span>
            </span>
            <Tag color={evidenceKind === 'visual' ? 'gold' : 'blue'}>{getEvidenceKindLabel(evidenceKind)}</Tag>
            {integrityStatus === 'incomplete' && <Tag color="warning">视觉制品未完成</Tag>}
            <Tag color={cited ? 'success' : 'default'}>{cited ? '已引用' : '未在正文标记'}</Tag>
          </Button>
        ))}
      </div>
    </section>
  );
}
