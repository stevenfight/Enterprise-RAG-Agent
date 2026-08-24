// -*- coding: utf-8 -*-
/**
 * 通用状态概览组件
 */

import type { ReactNode } from 'react';

export type OverviewState = 'success' | 'warning' | 'error' | 'neutral';

export interface StatusOverviewItem {
  key: string;
  label: string;
  value: string;
  detail: string;
  state: OverviewState;
  icon: ReactNode;
}

interface StatusOverviewProps {
  items: StatusOverviewItem[];
  ariaLabel: string;
  /** 列数（默认 4 列） */
  columns?: number;
  /** 紧凑模式（适用于长文本数值，如模型名） */
  compact?: boolean;
}

export default function StatusOverview({ items, ariaLabel, columns = 4, compact = false }: StatusOverviewProps) {
  const gridClass = columns === 5 ? 'status-overview-grid status-overview-grid--cols-5' : 'status-overview-grid';

  return (
    <section className={gridClass} aria-label={ariaLabel}>
      {items.map((item) => (
        <article key={item.key} className={`status-overview-card status-overview-card--${item.state}${compact ? ' status-overview-card--compact' : ''}`}>
          <div className="status-overview-card__icon">{item.icon}</div>
          <div className="status-overview-card__content">
            <span className="status-overview-card__label">{item.label}</span>
            <strong className="status-overview-card__value">{item.value}</strong>
            <span className="status-overview-card__detail">{item.detail}</span>
          </div>
        </article>
      ))}
    </section>
  );
}
