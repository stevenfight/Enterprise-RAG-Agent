// -*- coding: utf-8 -*-
/** 当前回答的引用证据面板。 */
import { Drawer, Space } from 'antd';
import { FileSearchOutlined } from '@ant-design/icons';
import type { SourceInfo } from '@/types/chat';
import { useTheme } from '@/hooks/useTheme';
import EvidenceContent from './EvidenceContent';

interface EvidencePanelProps {
  open: boolean;
  onClose: () => void;
  sources: SourceInfo[];
}

export default function EvidencePanel({ open, onClose, sources }: EvidencePanelProps) {
  const { isDark } = useTheme();

  return (
    <Drawer
      title={<Space><FileSearchOutlined /><span>证据面板</span></Space>}
      placement="right"
      size="default"
      open={open}
      onClose={onClose}
      styles={{ body: { background: isDark ? '#141414' : '#fafafa' } }}
    >
      <EvidenceContent sources={sources} />
    </Drawer>
  );
}
