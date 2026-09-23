// -*- coding: utf-8 -*-
/** 受控读取已完成页图制品，复用统一 Bearer 鉴权拦截器。 */

import type { VisualLocator } from '@/types/chat';
import apiClient from './api';

/**
 * 读取页图二进制内容。
 * 不在 URL 中携带密钥，axios 会通过统一拦截器附加 Authorization 头。
 */
export async function getVisualArtifactImage(locator: VisualLocator): Promise<Blob> {
  const response = await apiClient.get<Blob>(
    `/api/artifacts/manifests/${encodeURIComponent(locator.manifest_id)}/pages/${encodeURIComponent(locator.page_artifact_id)}/image`,
    { responseType: 'blob' },
  );
  return response.data;
}
