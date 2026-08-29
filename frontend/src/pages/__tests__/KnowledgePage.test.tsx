// -*- coding: utf-8 -*-
/** 资料库页面层级与字段边界回归测试。 */
import { act, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const getDocuments = vi.hoisted(() => vi.fn());
const retryDocumentIndex = vi.hoisted(() => vi.fn());

vi.mock('@/services/knowledgeService', () => ({
  getDocuments,
  uploadDocument: vi.fn(),
  deleteDocument: vi.fn(),
  retryDocumentIndex,
}));

import KnowledgePage from '@/pages/KnowledgePage';

describe('KnowledgePage', () => {
  it('AP-R02-01: 展示上传区、资料清单和接口返回的真实文档数量', async () => {
    getDocuments.mockResolvedValue({
      total: 2,
      documents: [
        { filename: '年报A.pdf', size: 1, size_mb: 1, upload_time: '2026-08-25', indexed: true },
        { filename: '年报B.pdf', size: 2, size_mb: 2, upload_time: '2026-08-25', indexed: false },
      ],
    });

    render(<KnowledgePage />);

    expect(await screen.findByText('上传资料')).toBeInTheDocument();
    expect(screen.getByText('资料清单（2）')).toBeInTheDocument();
    expect(screen.queryByText(/公司|年度|章节/)).toBeNull();
  });

  it('CP-R61: 资料页以证据资产工作区组织上传和清单，不推断文件属性', async () => {
    getDocuments.mockResolvedValue({ total: 0, documents: [] });
    const { container } = render(<KnowledgePage />);

    expect(await screen.findByText('上传资料')).toBeInTheDocument();
    expect(container.querySelector('.knowledge-archive')).toBeInTheDocument();
    expect(container.querySelector('.knowledge-archive__list')).toBeInTheDocument();
    expect(screen.queryByText(/公司|年度|章节/)).toBeNull();
  });

  it('HL-UI-01: 存在待处理文档时定时刷新索引状态', async () => {
    vi.useFakeTimers();
    getDocuments.mockClear();
    getDocuments
      .mockResolvedValueOnce({
        total: 1,
        documents: [
          { filename: '处理中.pdf', size: 1, size_mb: 1, upload_time: '2026-08-28', indexed: false, index_status: 'pending_index' },
        ],
      })
      .mockResolvedValueOnce({
        total: 1,
        documents: [
          { filename: '处理中.pdf', size: 1, size_mb: 1, upload_time: '2026-08-28', indexed: true, index_status: 'indexed' },
        ],
      });

    try {
      render(<KnowledgePage />);
      await act(async () => { await Promise.resolve(); });
      expect(screen.getByText('处理中')).toBeInTheDocument();
      await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
      expect(getDocuments).toHaveBeenCalledTimes(2);
      expect(screen.getAllByText('已索引').length).toBeGreaterThanOrEqual(2);
    } finally {
      vi.useRealTimers();
    }
  });
});
