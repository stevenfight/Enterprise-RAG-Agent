// -*- coding: utf-8 -*-
/**
 * axios 实例 + 拦截器
 * 统一请求/响应处理
 */

import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 120000, // Agent 推理可能耗时较长
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // API 鉴权 header
    const apiKey = import.meta.env.VITE_API_KEY || 'no-key-needed';
    config.headers.Authorization = `Bearer ${apiKey}`;
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

// 响应拦截器: 统一错误处理
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.code === 'ECONNABORTED' || error.code === 'ERR_CANCELED') {
      // 超时
      console.error('[API] 请求超时:', error.config?.url);
    } else if (!error.response) {
      // 网络错误 (后端不可用)
      console.error('[API] 网络错误:', error.message);
    } else {
      // 后端返回错误状态码
      const status = error.response.status;
      const data = error.response.data;
      console.error(`[API] HTTP ${status}:`, data);
    }
    return Promise.reject(error);
  },
);

export default apiClient;
