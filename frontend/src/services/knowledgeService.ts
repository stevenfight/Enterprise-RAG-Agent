// -*- coding: utf-8 -*-
/**
 * 知识库管理 API 封装
 */

import apiClient from './api';
import type { KnowledgeDocument } from '@/types/chat';

export interface KnowledgeListData {
  documents: KnowledgeDocument[];
  total: number;
}

export interface UploadResult {
  success: boolean;
  filename: string;
  size: number;
  size_mb: number;
}

/** 获取文档列表 */
export async function getDocuments(): Promise<KnowledgeListData> {
  const res = await apiClient.get<KnowledgeListData>(
      '/api/knowledge/documents');
  return res.data;
}

/** 上传 PDF */
export async function uploadDocument(
    file: File,
    onProgress?: (pct: number) => void,
): Promise<UploadResult> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await apiClient.post<UploadResult>(
      '/api/knowledge/upload', formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (e.total) {
            onProgress?.(Math.round((e.loaded * 100) / e.total));
          }
        },
      },
  );
  return res.data;
}

/** 删除文档 */
export async function deleteDocument(
    filename: string,
): Promise<{ success: boolean }> {
  const res = await apiClient.delete(
      `/api/knowledge/documents/${encodeURIComponent(filename)}`);
  return res.data;
}
