// -*- coding: utf-8 -*-
/** 回答级来源的只读聚合，供证据侧栏改善阅读层级。 */
import type { SourceInfo } from '@/types/chat';

export interface EvidenceBundle {
  companyName: string;
  sourceFile: string;
  pages: number[];
  evidenceKind: 'retrieval' | 'answer';
  sources: SourceInfo[];
}

/** 按公司与报告分组，不修改消息内原始来源的顺序或字段。 */
export function buildEvidenceBundles(sources: SourceInfo[]): EvidenceBundle[] {
  const bundles = new Map<string, EvidenceBundle>();

  for (const source of sources) {
    const key = `${source.company_name}\u0000${source.source_file}`;
    const existing = bundles.get(key);
    if (existing) {
      existing.sources.push(source);
      existing.pages = Array.from(new Set([...existing.pages, ...source.pages])).sort((a, b) => a - b);
      if (typeof source.scores?.hybrid === 'number') existing.evidenceKind = 'retrieval';
      continue;
    }

    bundles.set(key, {
      companyName: source.company_name,
      sourceFile: source.source_file,
      pages: Array.from(new Set(source.pages)).sort((a, b) => a - b),
      evidenceKind: typeof source.scores?.hybrid === 'number' ? 'retrieval' : 'answer',
      sources: [source],
    });
  }

  return Array.from(bundles.values());
}
