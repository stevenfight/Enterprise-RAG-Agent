// -*- coding: utf-8 -*-
/**
 * 系统状态 API 封装
 */

import apiClient from './api';
import type { SystemStatusData } from '@/types/chat';

/** 获取系统状态 */
export async function getSystemStatus(): Promise<SystemStatusData> {
  const res = await apiClient.get<SystemStatusData>('/api/system/status');
  return res.data;
}
