// -*- coding: utf-8 -*-
/** E-T22 研究会话服务契约测试。 */
import { describe, expect, it, vi } from 'vitest';

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import apiClient from '@/services/api';
import { getCurrentResearchIdentity, loginResearch, logoutResearch } from '@/services/researchAuthService';

const mockGet = apiClient.get as ReturnType<typeof vi.fn>;
const mockPost = apiClient.post as ReturnType<typeof vi.fn>;

describe('研究会话服务', () => {
  it('E-T22-01: 登录只提交用户名和密码，并返回服务端当前身份', async () => {
    mockPost.mockResolvedValueOnce({ data: { username: 'alice', roles: ['approver'] } });

    const identity = await loginResearch({ username: 'alice', password: 'secret' });

    expect(mockPost).toHaveBeenCalledWith('/api/research/auth/login', { username: 'alice', password: 'secret' });
    expect(identity).toEqual({ username: 'alice', roles: ['approver'] });
  });

  it('E-T22-02: 当前身份与登出均通过既有 HttpOnly 会话请求', async () => {
    mockGet.mockResolvedValueOnce({ data: { user_id: 'user-1', username: 'alice', roles: ['approver'] } });
    mockPost.mockResolvedValueOnce({ data: { status: 'ok' } });

    await expect(getCurrentResearchIdentity()).resolves.toEqual({ user_id: 'user-1', username: 'alice', roles: ['approver'] });
    await logoutResearch();

    expect(mockGet).toHaveBeenCalledWith('/api/research/auth/me');
    expect(mockPost).toHaveBeenCalledWith('/api/research/auth/logout');
  });
});
