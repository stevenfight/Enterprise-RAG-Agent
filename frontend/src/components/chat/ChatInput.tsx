// -*- coding: utf-8 -*-
/**
 * 输入区域组件 - 马卡龙玻璃拟态风格
 * 文本框 + 发送按钮，支持 Enter 发送 / Shift+Enter 换行
 */

import { useState, useEffect } from 'react';
import { Input, Button } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { useTheme } from '@/hooks/useTheme';
import { colors, gradients } from '@/styles/theme';
import { createLogger } from '@/utils/logger';

const logger = createLogger('ChatInput');
const { TextArea } = Input;

interface ChatInputProps {
  /** 发送消息回调 */
  onSend: (content: string) => void;
  /** 是否禁用（正在等待响应） */
  disabled?: boolean;
  /** 外部设置输入框文本（示例问题点击时填入） */
  fillText?: string;
  /** fillText 使用后回调，通知父组件清除 fillText */
  onFillTextConsumed?: () => void;
}

export default function ChatInput({ onSend, disabled = false, fillText, onFillTextConsumed }: ChatInputProps) {
  const [value, setValue] = useState('');
  const { isDark } = useTheme();

  // 当外部传入 fillText 时填入输入框
  useEffect(() => {
    if (fillText) {
      setValue(fillText);
      onFillTextConsumed?.();
    }
  }, [fillText, onFillTextConsumed]);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) {
      logger.debug('发送被阻止:', { empty: !trimmed, disabled });
      return;
    }
    logger.info('发送消息:', { contentLen: trimmed.length, preview: trimmed.slice(0, 30) });
    onSend(trimmed);
    setValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const borderColor = isDark ? '#3A3550' : '#E8E3EF';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-end',
        gap: 12,
        padding: '10px 14px',
        background: isDark
          ? 'rgba(37, 34, 54, 0.65)'
          : 'rgba(255, 255, 255, 0.65)',
        backdropFilter: 'blur(12px)',
        borderRadius: 14,
        border: `1px solid ${borderColor}`,
        boxShadow: `0 2px 16px ${isDark ? 'rgba(0,0,0,0.25)' : 'rgba(184, 169, 201, 0.1)'}`,
      }}
    >
      <TextArea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="请输入您的问题... (Enter 发送, Shift+Enter 换行)"
        autoSize={{ minRows: 1, maxRows: 4 }}
        disabled={disabled}
        style={{
          flex: 1,
          fontSize: 14,
          background: 'transparent',
          border: 'none',
          resize: 'none',
        }}
        variant="borderless"
      />
      <Button
        type="primary"
        icon={<SendOutlined />}
        onClick={handleSend}
        disabled={disabled || !value.trim()}
        style={{
          height: 40,
          width: 40,
          borderRadius: 10,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: disabled ? undefined : gradients.hero,
          border: 'none',
          boxShadow: disabled ? 'none' : '0 2px 10px rgba(184, 169, 201, 0.4)',
        }}
      />
    </div>
  );
}
