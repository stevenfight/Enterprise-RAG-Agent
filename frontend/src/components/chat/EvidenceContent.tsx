// -*- coding: utf-8 -*-
/** 可复用于桌面侧栏与移动抽屉的回答级证据内容。 */
import { Empty, Typography } from 'antd';
import type { SourceInfo } from '@/types/chat';
import SourceCard from './SourceCard';

const { Text } = Typography;

interface EvidenceContentProps {
  sources: SourceInfo[];
}

export default function EvidenceContent({ sources }: EvidenceContentProps) {
  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <Text strong style={{ display: 'block', marginBottom: 4 }}>回答级证据</Text>
        <Text type="secondary" style={{ fontSize: 12, lineHeight: 1.6 }}>
          以下来源用于支撑当前回答；检索匹配度反映来源与问题的匹配程度，不表示单项 KPI 的确定性。
        </Text>
      </div>

      <Text type="secondary" style={{ display: 'block', fontSize: 12, marginBottom: 8 }}>
        检索匹配度
      </Text>

      {sources.length > 0 ? (
        sources.map((source) => <SourceCard key={source.index} source={source} />)
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前回答暂无引用来源" />
      )}
    </>
  );
}
