// -*- coding: utf-8 -*-
/** 资料库页面层级与字段边界回归测试。 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const getDocuments = vi.hoisted(() => vi.fn());

vi.mock('@/services/knowledgeService', () => ({
  getDocuments,
  uploadDocument: vi.fn(),
  deleteDocument: vi.fn(),
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
});
