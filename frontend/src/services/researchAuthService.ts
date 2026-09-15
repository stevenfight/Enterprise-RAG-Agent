// -*- coding: utf-8 -*-
/** E-T22 研究会话身份 API 封装；令牌只由浏览器 HttpOnly Cookie 持有。 */
import apiClient from './api';

/** 登录或登出完成后通知依赖当前研究身份的页面重新读取服务端会话。 */
export const RESEARCH_IDENTITY_CHANGED_EVENT = 'research-identity-changed';

export interface ResearchCurrentIdentity {
  user_id: string;
  username: string;
  roles: string[];
}

export interface ResearchLoginInput {
  username: string;
  password: string;
}

interface ResearchLoginResponse {
  username: string;
  roles: string[];
}

/** 登录只传递凭据，不读取或保存服务端下发的会话令牌。 */
export async function loginResearch(input: ResearchLoginInput): Promise<ResearchLoginResponse> {
  const response = await apiClient.post<ResearchLoginResponse>('/api/research/auth/login', input);
  return response.data;
}

/** 获取当前会话对应的身份；未登录时由调用方按 401 处理。 */
export async function getCurrentResearchIdentity(): Promise<ResearchCurrentIdentity> {
  const response = await apiClient.get<ResearchCurrentIdentity>('/api/research/auth/me');
  return response.data;
}

/** 让服务端作废当前会话 Cookie 对应的令牌。 */
export async function logoutResearch(): Promise<void> {
  await apiClient.post('/api/research/auth/logout');
}
