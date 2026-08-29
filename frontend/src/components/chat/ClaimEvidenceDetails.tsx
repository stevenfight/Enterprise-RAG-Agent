// -*- coding: utf-8 -*-
/** 声明级证据明细：展示比较事实的原始值、归一值、关联公式与冲突原因。 */
import { Typography } from 'antd';
import type { VerifiedComparison } from '@/types/chat';
import { useTheme } from '@/hooks/useTheme';
import { colors } from '@/styles/theme';

const { Text } = Typography;

interface ClaimEvidenceDetailsProps {
  comparison: VerifiedComparison;
}

export default function ClaimEvidenceDetails({ comparison }: ClaimEvidenceDetailsProps) {
  const { isDark } = useTheme();
  // 旧比较响应不携带声明级字段，此时不渲染任何明细。
  const factDetails = comparison.items.filter((item) => item.raw_value !== undefined);
  const calculations = comparison.calculations ?? [];
  const conflicts = comparison.conflicts ?? [];
  if (factDetails.length === 0 && calculations.length === 0 && conflicts.length === 0) return null;

  return (
    <section
      aria-label="声明级证据明细"
      style={{ marginTop: 10, paddingTop: 8, borderTop: `1px dashed ${isDark ? colors.borderDark : colors.border}` }}
    >
      <Text type="secondary" style={{ display: 'block', fontSize: 11, marginBottom: 4 }}>声明级证据明细</Text>
      {factDetails.map((item) => (
        <div key={item.company_name} style={{ display: 'flex', gap: 8, alignItems: 'baseline', flexWrap: 'wrap' }}>
          <Text strong style={{ fontSize: 12 }}>{item.company_name}</Text>
          <Text type="secondary" style={{ fontSize: 11 }}>原始值 {item.raw_value}{item.raw_unit}</Text>
          <Text type="secondary" style={{ fontSize: 11 }}>归一值 {item.normalized_value}{item.normalized_unit}</Text>
        </div>
      ))}
      {calculations.map((calculation) => (
        <div key={calculation.calculation_id}>
          <Text type="secondary" style={{ fontSize: 11 }}>公式 {calculation.operation}（{calculation.formula_version}）</Text>
        </div>
      ))}
      {conflicts.map((conflict) => (
        <div key={conflict.conflict_id}>
          <Text type="secondary" style={{ fontSize: 11 }}>
            冲突{conflict.conflict_type ? ` ${conflict.conflict_type}` : ''} · 相对差异 {conflict.relative_difference} · {conflict.status === 'pending_review' ? '待人工复核' : conflict.status}
          </Text>
        </div>
      ))}
    </section>
  );
}
