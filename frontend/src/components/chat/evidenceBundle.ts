// -*- coding: utf-8 -*-
/** 回答级来源的只读聚合，供证据侧栏改善阅读层级。 */
import type { SourceInfo } from '@/types/chat';
import { getSourceEvidenceKind, getSourceIntegrityStatus, type EvidenceIntegrityStatus, type EvidenceKind } from './evidenceSemantics';

export interface EvidenceBundle {
  companyName: string;
  sourceFile: string;
  pages: number[];
  evidenceKind: EvidenceKind;
  integrityStatus: EvidenceIntegrityStatus;
  visualLocatorCount: number;
  visualChartCount: number;
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
      continue;
    }

    bundles.set(key, {
      companyName: source.company_name,
      sourceFile: source.source_file,
      pages: Array.from(new Set(source.pages)).sort((a, b) => a - b),
      evidenceKind: getSourceEvidenceKind(source),
      integrityStatus: getSourceIntegrityStatus(source),
      visualLocatorCount: source.visual_locator ? 1 : 0,
      visualChartCount: source.visual_chart ? 1 : 0,
      sources: [source],
    });
  }

  return Array.from(bundles.values()).map((bundle) => {
    const evidenceKind = bundle.sources.some((source) => getSourceEvidenceKind(source) === 'visual')
      ? 'visual'
      : bundle.sources.some((source) => getSourceEvidenceKind(source) === 'retrieval')
        ? 'retrieval'
        : 'answer';
    const integrityStatus = bundle.sources.some((source) => getSourceIntegrityStatus(source) === 'incomplete')
      ? 'incomplete'
      : bundle.sources.some((source) => getSourceIntegrityStatus(source) === 'complete')
        ? 'complete'
        : 'text_only';
    return {
      ...bundle,
      evidenceKind,
      integrityStatus,
      visualLocatorCount: bundle.sources.filter((source) => source.visual_locator).length,
      visualChartCount: bundle.sources.filter((source) => source.visual_chart).length,
    };
  });
}
