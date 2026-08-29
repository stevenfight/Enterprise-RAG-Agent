// -*- coding: utf-8 -*-
/** 回答级已核验比较卡片，仅展示后端登记并随回答返回的事实。 */
import { Button, Card, Typography } from 'antd';
import type { SourceInfo, VerifiedComparison } from '@/types/chat';
import ClaimEvidenceDetails from './ClaimEvidenceDetails';
import { useTheme } from '@/hooks/useTheme';
import { colors } from '@/styles/theme';

const { Text } = Typography;

interface VerifiedComparisonCardProps {
  comparison?: VerifiedComparison | null;
  /** 仅使用当前回答中实际返回的来源定位证据。 */
  sources?: SourceInfo[];
  onViewEvidence?: (sourceIndex: number) => void;
  /** 从已核验比较携带真实维度进入成果浏览，不声明图表归属关系。 */
  onViewCharts?: (criteria: Pick<VerifiedComparison, 'metric_key' | 'fiscal_year' | 'unit'>) => void;
}

const metricLabels: Record<string, string> = { operating_revenue: '营业收入' };

/** 将页码转换为简洁、可核验的来源定位。 */
function formatSource(sourceFile: string, pages: number[]): string {
  return `${sourceFile} · P${pages.join('、P')}`;
}

export default function VerifiedComparisonCard({ comparison, sources, onViewEvidence, onViewCharts }: VerifiedComparisonCardProps) {
  const { isDark } = useTheme();
  if (!comparison?.available || comparison.items.length === 0) return null;
  const metricLabel = metricLabels[comparison.metric_key] ?? comparison.metric_key;
  const rankedItems = [...comparison.items].sort((left, right) => right.value - left.value);
  const leader = rankedItems[0];
  const runnerUp = rankedItems[1];
  const canVisualize = comparison.items.length >= 2 && leader.value > 0;
  const leadValue = canVisualize && runnerUp ? leader.value - runnerUp.value : 0;

  return (
    <section aria-label="已核验对比" style={{ marginBottom: 14 }}>
      <Card className="verified-comparison-card verified-comparison-card--financial" size="small" style={{ borderRadius: 12, border: `1px solid ${isDark ? 'rgba(152, 216, 200, 0.28)' : 'rgba(61, 139, 122, 0.24)'}`, background: isDark ? 'rgba(152, 216, 200, 0.06)' : 'linear-gradient(135deg, #F7FCFA 0%, #FFFFFF 100%)' }} styles={{ body: { padding: '12px 14px' } }}>
        <div className="verified-comparison-card__header">
          <Text strong style={{ color: isDark ? '#C8F0E4' : '#28695C' }}>已核验对比</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>{comparison.fiscal_year} · {metricLabel}（{comparison.unit}）</Text>
        </div>
        {canVisualize && runnerUp && (
          <div className="verified-comparison-card__summary" aria-label={`${metricLabel}对比摘要`}>
            <div>
              <Text type="secondary">最高{metricLabel}</Text>
              <Text strong>{leader.company_name} {leader.value.toLocaleString('zh-CN')}{comparison.unit}</Text>
            </div>
            <Text type="secondary">领先第二名 {leadValue.toLocaleString('zh-CN')}{comparison.unit}</Text>
          </div>
        )}
        <div role={canVisualize ? 'list' : 'table'} aria-label={canVisualize ? `${metricLabel}对比图` : `${comparison.fiscal_year}年${metricLabel}已核验比较`}>
          {comparison.items.map((item, index) => {
            const percentage = canVisualize ? Math.round((item.value / leader.value) * 100) : 0;
            const matchingSource = onViewEvidence
              ? sources?.find((source) => (
                source.company_name === item.company_name
                && source.source_file === item.source_file
                && item.pages.some((page) => source.pages.includes(page))
              ))
              : undefined;

            return (
              <div role={canVisualize ? 'listitem' : 'row'} aria-label={canVisualize ? `${item.company_name} ${item.value.toLocaleString('zh-CN')}${comparison.unit}，占最高值 ${percentage}%` : undefined} className="verified-comparison-card__row" key={`${item.company_name}-${item.source_file}`} style={{ padding: index === 0 ? '0 0 9px' : '9px 0', borderTop: index === 0 ? 'none' : `1px solid ${isDark ? colors.borderDark : colors.border}` }}>
                {matchingSource ? (
                  <button type="button" className="verified-comparison-card__evidence-link" onClick={() => onViewEvidence?.(matchingSource.index)} aria-label={`查看${item.company_name}的证据`}>
                    <Text strong>{item.company_name}</Text>
                    <span>{formatSource(item.source_file, item.pages)}</span>
                  </button>
                ) : (
                  <div>
                    <Text strong>{item.company_name}</Text>
                    <div style={{ marginTop: 2 }}><Text type="secondary" style={{ fontSize: 11 }}>{formatSource(item.source_file, item.pages)}</Text></div>
                  </div>
                )}
                {canVisualize && (
                  <div className="verified-comparison-card__bar-item">
                    <div className="verified-comparison-card__bar-track" aria-hidden="true">
                      <span className="verified-comparison-card__bar-fill" style={{ width: `${percentage}%` }} />
                    </div>
                  </div>
                )}
                <Text strong className="verified-comparison-card__value" style={{ color: isDark ? '#98D8C8' : '#28695C' }}>{item.value.toLocaleString('zh-CN')}</Text>
              </div>
            );
          })}
        </div>
        {/* B2.6：携带声明级可选载荷时追加原始值、归一值、公式与冲突原因明细，旧载荷不渲染。 */}
        <ClaimEvidenceDetails comparison={comparison} />
        {onViewCharts && (
          <Button type="link" size="small" className="verified-comparison-card__output-link" onClick={() => onViewCharts({
            metric_key: comparison.metric_key,
            fiscal_year: comparison.fiscal_year,
            unit: comparison.unit,
          })}>
            查看分析成果
          </Button>
        )}
      </Card>
    </section>
  );
}
