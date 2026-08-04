// -*- coding: utf-8 -*-
/**
 * 知识库管理页面 (占位)
 * Phase 3 实现
 */

import { DatabaseOutlined } from '@ant-design/icons';
import PlaceholderPage from '@/components/common/PlaceholderPage';

export default function KnowledgePage() {
  return (
    <PlaceholderPage
      title="知识库管理"
      description="文档列表、索引状态、PDF 上传与解析管理"
      icon={<DatabaseOutlined style={{ fontSize: 72, color: '#1a3a5c' }} />}
      phase="Phase 3"
    />
  );
}
