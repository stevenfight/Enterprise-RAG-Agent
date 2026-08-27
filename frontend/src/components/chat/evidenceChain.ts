// -*- coding: utf-8 -*-
/** 回答级证据链数据映射。 */
import type { SourceInfo } from '@/types/chat';

export interface EvidenceChainNode {
  index: number;
  source: SourceInfo;
  cited: boolean;
}

export interface EvidenceChain {
  citedIndexes: number[];
  nodes: EvidenceChainNode[];
}

/** 将正文来源标记与当前消息来源做严格映射，不从其他消息或历史数据补造关系。 */
export function buildEvidenceChain(answer: string, sources: SourceInfo[]): EvidenceChain {
  const citedIndexes = Array.from(new Set(
    Array.from(answer.matchAll(/\[来源(\d+)\]/g), (match) => Number(match[1]))
      .filter((index) => sources.some((source) => source.index === index)),
  )).sort((a, b) => a - b);
  const citedSet = new Set(citedIndexes);

  return {
    citedIndexes,
    nodes: sources.map((source) => ({
      index: source.index,
      source,
      cited: citedSet.has(source.index),
    })),
  };
}
