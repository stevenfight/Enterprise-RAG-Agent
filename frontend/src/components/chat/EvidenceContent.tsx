// -*- coding: utf-8 -*-
/** 可复用于桌面侧栏与移动抽屉的回答级证据内容。 */
import { useEffect, useState } from 'react';
import { Empty, Typography } from 'antd';
import type { SourceInfo } from '@/types/chat';
import SourceCard from './SourceCard';
import { buildEvidenceBundles } from './evidenceBundle';
import { getPreferredScrollBehavior } from '@/utils/motionPreference';

const { Text } = Typography;

interface EvidenceContentProps {
  sources: SourceInfo[];
  /** 当前由正文引用定位的来源原始编号。 */
  highlightedSourceIndex?: number;
}

export default function EvidenceContent({ sources, highlightedSourceIndex }: EvidenceContentProps) {
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());
  const bundles = buildEvidenceBundles(sources);

  useEffect(() => {
    if (highlightedSourceIndex === undefined) return;
    const bundle = bundles.find((item) => item.sources.some((source) => source.index === highlightedSourceIndex));
    if (!bundle) return;
    const bundleKey = `${bundle.companyName}\u0000${bundle.sourceFile}`;
    setExpandedKeys((keys) => keys.has(bundleKey) ? keys : new Set([...keys, bundleKey]));
  }, [bundles, highlightedSourceIndex]);

  useEffect(() => {
    if (highlightedSourceIndex === undefined) return;
    document.querySelector<HTMLElement>(`[data-testid="source-card-${highlightedSourceIndex}"]`)
      ?.scrollIntoView?.({ block: 'nearest', behavior: getPreferredScrollBehavior() });
  }, [expandedKeys, highlightedSourceIndex]);

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <Text strong style={{ display: 'block', marginBottom: 4 }}>回答级证据</Text>
        <Text type="secondary" style={{ fontSize: 12, lineHeight: 1.6 }}>
          以下来源用于支撑当前回答；检索匹配度反映来源与问题的匹配程度，不表示单项 KPI 的确定性。
        </Text>
      </div>

      {bundles.length > 0 ? (
        <div className="evidence-bundle-list">
          {bundles.map((bundle) => {
            const bundleKey = `${bundle.companyName}\u0000${bundle.sourceFile}`;
            const expanded = expandedKeys.has(bundleKey);
            const pageLabel = bundle.pages.length > 0 ? ` · P${bundle.pages.join('、P')}` : '';
            const evidenceLabel = bundle.evidenceKind === 'retrieval' ? '检索证据' : '回答证据';
            return (
              <section className="evidence-bundle" key={bundleKey} aria-label={`${bundle.companyName} ${bundle.sourceFile}`}>
                <button
                  type="button"
                  className="evidence-bundle__trigger"
                  aria-expanded={expanded}
                  onClick={() => {
                    setExpandedKeys((keys) => {
                      const next = new Set(keys);
                      if (next.has(bundleKey)) next.delete(bundleKey);
                      else next.add(bundleKey);
                      return next;
                    });
                  }}
                >
                  <span>
                    <strong>{bundle.companyName}</strong>
                    <span className="evidence-bundle__file"><span>{bundle.sourceFile}</span>{pageLabel}</span>
                  </span>
                  <span className="evidence-bundle__meta"><span>{evidenceLabel}</span> · {bundle.sources.length} 条</span>
                </button>
                {expanded && (
                  <div className="evidence-bundle__items">
                    {bundle.sources.map((source) => (
                      <SourceCard
                        key={source.index}
                        source={source}
                        showScoreStatus={bundle.evidenceKind === 'retrieval'}
                        highlighted={source.index === highlightedSourceIndex}
                      />
                    ))}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前回答暂无引用来源" />
      )}
    </>
  );
}
