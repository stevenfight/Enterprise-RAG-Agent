import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import KnowledgeOverview from '../KnowledgeOverview';
import type { KnowledgeDocument } from '@/types/chat';

const documents: KnowledgeDocument[] = [
  { filename: 'a.pdf', size: 100, size_mb: 1, upload_time: '2026-08-22', indexed: true },
  { filename: 'b.pdf', size: 200, size_mb: 2, upload_time: '2026-08-22', indexed: false },
  { filename: 'c.pdf', size: 300, size_mb: 3, upload_time: '2026-08-22', indexed: true },
];

describe('KnowledgeOverview', () => {
  it('显示文档统计和索引完成率', () => {
    render(<KnowledgeOverview documents={documents} />);

    expect(screen.getByRole('region', { name: '知识库概览' })).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('2 / 3 篇')).toBeInTheDocument();
    expect(screen.getByText('67%')).toBeInTheDocument();
    expect(screen.getByText('等待处理')).toBeInTheDocument();
  });

  it('空文档列表显示 0% 和暂无文档', () => {
    render(<KnowledgeOverview documents={[]} />);

    expect(screen.getByText('0%')).toBeInTheDocument();
    expect(screen.getByText('暂无文档')).toBeInTheDocument();
  });
});
