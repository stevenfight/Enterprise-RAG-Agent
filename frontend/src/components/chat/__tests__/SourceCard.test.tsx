// -*- coding: utf-8 -*-
/** 引用来源匹配度语义测试。 */
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SourceCard from '@/components/chat/SourceCard';
import { getVisualArtifactImage } from '@/services/visualArtifactService';

vi.mock('@/hooks/useTheme', () => ({ useTheme: () => ({ isDark: false }) }));
vi.mock('@/services/visualArtifactService', () => ({
  getVisualArtifactImage: vi.fn().mockResolvedValue(new Blob(['page-image'])),
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal('URL', {
    createObjectURL: vi.fn(() => 'blob:visual-evidence'),
    revokeObjectURL: vi.fn(),
  });
});

describe('SourceCard', () => {
  it('RW-R03-03: 仅将 hybrid 分数显示为检索匹配度百分比', () => {
    render(<SourceCard source={{
      index: 1,
      source_file: '示例年报.pdf',
      pages: [1],
      company_name: '中芯国际',
      scores: { bm25: 18.6, rerank: 7.2 },
    }} />);

    expect(screen.getByText('匹配度未提供')).toBeInTheDocument();
    expect(screen.queryByText('100%')).toBeNull();
  });

  it('CP-R19: 展开后显示后端提供的受限命中摘要', () => {
    const { container } = render(<SourceCard source={{
      index: 1,
      source_file: '移动2024年度报告.pdf',
      pages: [17],
      company_name: '中国移动',
      excerpt: '营业收入为 1,040,759 百万元。',
      scores: { hybrid: 0.9 },
    }} />);

    fireEvent.click(container.querySelector('.ant-card')!);
    expect(screen.getByText('命中文本摘要')).toBeInTheDocument();
    expect(screen.getByText('营业收入为 1,040,759 百万元。')).toBeInTheDocument();
  });

  it('CP-R21: 评分详情可展示后端返回的非数值状态字段', () => {
    render(<SourceCard source={{
      index: 1,
      source_file: '示例年报.pdf',
      pages: [1],
      company_name: '中芯国际',
      scores: { hybrid: 0.9, confidence: 'unknown' },
    }} />);

    expect(screen.getByText('90%')).toBeInTheDocument();
  });

  it('E-T29: 从证据链定位来源时直接展开评分详情', async () => {
    render(<SourceCard source={{
      index: 1,
      source_file: '示例年报.pdf',
      pages: [1],
      company_name: '中芯国际',
      scores: { hybrid: 0.9, rerank: 7.2, vector: 0.8, bm25: 6.1 },
    }} highlighted />);

    expect(await screen.findByText('评分详情')).toBeInTheDocument();
    expect(screen.getByText('hybrid: 0.9000')).toBeInTheDocument();
    expect(screen.getByText('rerank: 7.2000')).toBeInTheDocument();
  });

  it('M1.7: 已确认视觉区域会请求受控页图并展示 bbox 高亮', async () => {
    const { container } = render(<SourceCard source={{
      index: 1,
      source_file: '示例年报.pdf',
      pages: [3],
      company_name: '中芯国际',
      scores: {},
      visual_locator: {
        manifest_id: 'manifest-1',
        page_artifact_id: 'page-1',
        visual_region_id: 'region-1',
        normalized_bbox: [0.1, 0.2, 0.8, 0.9],
        artifact_status: 'complete',
      },
    }} />);

    fireEvent.click(container.querySelector('.ant-card')!);
    expect(screen.getByText('视觉区域可定位')).toBeInTheDocument();
    expect(screen.getByText('x=10%–80%，y=20%–90%')).toBeInTheDocument();
    expect(await screen.findByAltText('示例年报.pdf 第 3 页视觉区域')).toBeInTheDocument();
    expect(screen.getByLabelText('视觉区域高亮')).toHaveStyle({
      left: '10%',
      top: '20%',
      width: '70%',
      height: '70%',
    });
  });

  it('M1.7: 不完整视觉制品只显示无障碍提示，不请求或伪造页图', () => {
    const { container } = render(<SourceCard source={{
      index: 1,
      source_file: '不完整报告.pdf',
      pages: [4],
      company_name: '示例公司',
      scores: {},
      visual_preview_status: 'incomplete',
    }} />);

    fireEvent.click(container.querySelector('.ant-card')!);
    expect(screen.getByText('视觉页图尚未完成，当前无法预览。')).toBeInTheDocument();
    expect(container.querySelector('img')).toBeNull();
    expect(getVisualArtifactImage).not.toHaveBeenCalled();
  });
});
