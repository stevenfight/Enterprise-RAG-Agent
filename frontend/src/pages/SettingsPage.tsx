// -*- coding: utf-8 -*-
/**
 * 系统设置与监控页面 (占位)
 * Phase 3 实现
 */

import { SettingOutlined } from '@ant-design/icons';
import PlaceholderPage from '@/components/common/PlaceholderPage';

export default function SettingsPage() {
  return (
    <PlaceholderPage
      title="系统设置"
      description="Agent 参数调节、工具开关、系统健康状态监控面板"
      icon={<SettingOutlined style={{ fontSize: 72, color: '#1a3a5c' }} />}
      phase="Phase 3"
    />
  );
}
