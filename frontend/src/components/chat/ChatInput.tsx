// -*- coding: utf-8 -*-
/**
 * 输入区域组件 - 基于 @ant-design/x Sender
 * 支持 Enter 发送 / Shift+Enter 换行，自动适应高度
 */

import { useState, useEffect } from 'react';
import { Sender } from '@ant-design/x';
import { useTheme } from '@/hooks/useTheme';
import { createLogger } from '@/utils/logger';

const logger = createLogger('ChatInput');

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

  // Sender 提交回调：去空格后发送，并清空输入框
  const handleSubmit = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || disabled) {
      logger.debug('发送被阻止:', { empty: !trimmed, disabled });
      return;
    }
    logger.info('发送消息:', { contentLen: trimmed.length, preview: trimmed.slice(0, 30) });
    onSend(trimmed);
    setValue('');
  };

  const borderColor = isDark ? '#2a2a3a' : '#e8e8e8';

  return (
    <Sender
      value={value}
      onChange={(v) => setValue(v)}
      onSubmit={handleSubmit}
      loading={disabled}
      disabled={disabled}
      placeholder="请输入您的问题，Enter 发送 / Shift+Enter 换行"
      autoSize={{ minRows: 1, maxRows: 4 }}
      suffix={(_, { components: { LoadingButton, SendButton } }) => (
        disabled
          ? <LoadingButton aria-label="停止生成" title="停止生成" />
          : <SendButton aria-label="发送研究问题" title="发送研究问题" />
      )}
      className="chat-sender chat-sender--research"
      style={{
        background: isDark
          ? 'rgba(30, 28, 45, 0.9)'
          : '#ffffff',
        borderRadius: 18,
        border: `1px solid ${borderColor}`,
        boxShadow: isDark
          ? '0 2px 8px rgba(0,0,0,0.2)'
          : '0 2px 8px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03)',
        transition: 'border-color 0.2s, box-shadow 0.2s',
      }}
    />
  );
}
