// -*- coding: utf-8 -*-
/** 视觉与文本来源共用的证据类型、完整性语义。 */
import type { SourceInfo } from '@/types/chat';

export type EvidenceKind = 'retrieval' | 'answer' | 'visual';
export type EvidenceIntegrityStatus = 'complete' | 'incomplete' | 'text_only';

export function getSourceEvidenceKind(source: SourceInfo): EvidenceKind {
  if (source.visual_locator || source.visual_preview_status === 'incomplete' || source.visual_chart) return 'visual';
  return typeof source.scores?.hybrid === 'number' ? 'retrieval' : 'answer';
}

export function getSourceIntegrityStatus(source: SourceInfo): EvidenceIntegrityStatus {
  if (source.visual_preview_status === 'incomplete') return 'incomplete';
  if (source.visual_chart && !source.visual_locator) return 'incomplete';
  if (source.visual_locator) return 'complete';
  return 'text_only';
}

export function getEvidenceKindLabel(kind: EvidenceKind): string {
  return kind === 'visual' ? '视觉证据' : kind === 'retrieval' ? '检索证据' : '回答证据';
}
