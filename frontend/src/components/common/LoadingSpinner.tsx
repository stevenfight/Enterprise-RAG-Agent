// -*- coding: utf-8 -*-
/**
 * 加载动画组件
 * 用于 AI 响应等待状态
 */

import { Space, Spin, Typography } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';
import { useTheme } from '@/hooks/useTheme';

const { Text } = Typography;

interface LoadingSpinnerProps {
  /** 提示文本 */
  text?: string;
}

export default function LoadingSpinner({ text = '正在思考中...' }: LoadingSpinnerProps) {
  const { isDark } = useTheme();

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'flex-start',
        margin: '12px 0',
        padding: '0 16px',
      }}
    >
      <div
        style={{
          maxWidth: '70%',
          background: isDark ? '#2a2a2a' : '#ffffff',
          borderRadius: 12,
          padding: '16px 20px',
          boxShadow: `0 1px 4px ${isDark ? 'rgba(0,0,0,0.3)' : 'rgba(0,0,0,0.08)'}`,
        }}
      >
        <Space size={8}>
          <Spin
            indicator={<LoadingOutlined style={{ fontSize: 18, color: isDark ? '#c9a96e' : '#1a3a5c' }} />}
          />
          <Text
            style={{
              fontSize: 14,
              color: isDark ? '#8c8c8c' : '#595959',
            }}
          >
            {text}
          </Text>
        </Space>
      </div>
    </div>
  );
}
