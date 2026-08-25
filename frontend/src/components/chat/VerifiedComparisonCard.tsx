// -*- coding: utf-8 -*-
/** 回答级已核验比较卡片，仅展示后端登记并随回答返回的事实。 */
import { Card, Typography } from 'antd';
import type { VerifiedComparison } from '@/types/chat';
import { useTheme } from '@/hooks/useTheme';
import { colors } from '@/styles/theme';

const { Text } = Typography;

interface VerifiedComparisonCardProps {
  comparison?: VerifiedComparison | null;
}

const metricLabels: Record<string, string> = { operating_revenue: '营业收入' };

/** 将页码转换为简洁、可核验的来源定位。 */
function formatSource(sourceFile: string, pages: number[]): string {
  return `${sourceFile} · P${pages.join('、P')}`;
}

export default function VerifiedComparisonCard({ comparison }: VerifiedComparisonCardProps) {
  const { isDark } = useTheme();
  if (!comparison?.available || comparison.items.length === 0) return null;
  const metricLabel = metricLabels[comparison.metric_key] ?? comparison.metric_key;

  return (
    <section aria-label="已核验对比" style={{ marginBottom: 14 }}>
      <Card size="small" style={{ borderRadius: 12, border: `1px solid ${isDark ? 'rgba(152, 216, 200, 0.28)' : 'rgba(61, 139, 122, 0.24)'}`, background: isDark ? 'rgba(152, 216, 200, 0.06)' : 'linear-gradient(135deg, #F7FCFA 0%, #FFFFFF 100%)' }} styles={{ body: { padding: '12px 14px' } }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 10 }}>
          <Text strong style={{ color: isDark ? '#C8F0E4' : '#28695C' }}>已核验对比</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>{comparison.fiscal_year} · {metricLabel}（{comparison.unit}）</Text>
        </div>
        <div role="table" aria-label={`${comparison.fiscal_year}年${metricLabel}已核验比较`}>
          {comparison.items.map((item, index) => (
            <div role="row" key={`${item.company_name}-${item.source_file}`} style={{ display: 'grid', gridTemplateColumns: 'minmax(84px, 1fr) auto', gap: 12, alignItems: 'center', padding: index === 0 ? '0 0 9px' : '9px 0', borderTop: index === 0 ? 'none' : `1px solid ${isDark ? colors.borderDark : colors.border}` }}>
              <div>
                <Text strong>{item.company_name}</Text>
                <div style={{ marginTop: 2 }}><Text type="secondary" style={{ fontSize: 11 }}>{formatSource(item.source_file, item.pages)}</Text></div>
              </div>
              <Text strong style={{ color: isDark ? '#98D8C8' : '#28695C', fontSize: 18 }}>{item.value.toLocaleString('zh-CN')}</Text>
            </div>
          ))}
        </div>
      </Card>
    </section>
  );
}
