// -*- coding: utf-8 -*-
/**
 * 财务 KPI 卡片组件
 * 在 AI 回答顶部展示关键财务指标摘要
 */

import { Space } from 'antd';
import {
  DollarOutlined,
  RiseOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  FundOutlined,
  PieChartOutlined,
} from '@ant-design/icons';
import type { KPIItem } from '@/utils/financialFormat';
import { colors, monoFont } from '@/styles/theme';

interface FinancialKPICardsProps {
  kpis: KPIItem[];
  isDark?: boolean;
}

/** 图标映射 */
const iconMap: Record<string, React.ReactNode> = {
  revenue: <DollarOutlined />,
  profit: <RiseOutlined />,
  growth: <ArrowUpOutlined />,
  roe: <FundOutlined />,
  margin: <PieChartOutlined />,
  other: <FundOutlined />,
};

/** 颜色映射 */
const colorMap: Record<string, string> = {
  revenue: '#B8A9C9',
  profit: '#98D8C8',
  growth: '#A8D8EA',
  roe: '#F4B8C8',
  margin: '#FAD4B8',
  other: '#B8A9C9',
};

export default function FinancialKPICards({ kpis, isDark = false }: FinancialKPICardsProps) {
  if (!kpis || kpis.length === 0) return null;

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 12,
        marginBottom: 16,
        padding: '2px',
      }}
    >
      {kpis.map((kpi, idx) => {
        const icon = iconMap[kpi.type] || iconMap.other;
        const iconColor = colorMap[kpi.type] || colorMap.other;
        const isGrowthNegative = kpi.type === 'growth' && kpi.isPositive === false;
        const valueColor = isGrowthNegative
          ? (isDark ? '#E88B8B' : '#CF4A4A')
          : (isDark ? '#7ECB9A' : '#2E9A5E');

        return (
          <div
            key={idx}
            style={{
              flex: '1 1 140px',
              maxWidth: 200,
              minWidth: 140,
              padding: '14px 18px',
              borderRadius: 12,
              background: isDark ? colors.bgDarkCard : '#FFFFFF',
              boxShadow: isDark
                ? '0 2px 8px rgba(0,0,0,0.2)'
                : '0 2px 8px rgba(0,0,0,0.06)',
              border: isDark ? `1px solid ${colors.borderDark}` : '1px solid #F0EBF5',
              transition: 'transform 0.2s, box-shadow 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-2px)';
              e.currentTarget.style.boxShadow = isDark
                ? '0 4px 16px rgba(0,0,0,0.3)'
                : '0 4px 16px rgba(0,0,0,0.1)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = isDark
                ? '0 2px 8px rgba(0,0,0,0.2)'
                : '0 2px 8px rgba(0,0,0,0.06)';
            }}
          >
            <Space size={6} style={{ marginBottom: 6 }}>
              <span style={{ fontSize: 14, color: iconColor }}>{icon}</span>
              <span
                style={{
                  fontSize: 12,
                  color: isDark ? colors.textSecondaryDark : colors.textSecondary,
                  fontWeight: 500,
                }}
              >
                {kpi.name}
              </span>
            </Space>

            <div
              style={{
                fontSize: 24,
                fontWeight: 700,
                fontFamily: monoFont,
                color: isGrowthNegative ? valueColor : (isDark ? colors.textPrimaryDark : colors.textPrimary),
                lineHeight: 1.2,
                letterSpacing: '-0.5px',
              }}
            >
              {kpi.value}
            </div>

            <div
              style={{
                fontSize: 12,
                color: isDark ? colors.textSecondaryDark : '#9B95A9',
                marginTop: 2,
              }}
            >
              {kpi.unit}
              {kpi.type === 'growth' && (
                <span style={{ marginLeft: 6, color: valueColor }}>
                  {kpi.isPositive ? (
                    <ArrowUpOutlined style={{ fontSize: 10 }} />
                  ) : (
                    <ArrowDownOutlined style={{ fontSize: 10 }} />
                  )}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
