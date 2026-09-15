# 规格：跨源 Agent SSE 研究会话

## 需求：登录后的跨源 SSE 请求携带服务端会话

前端 MUST 使用带 `withCredentials: true` 的 EventSource 请求 `/api/agent/stream`。

### 场景：跨源 API 基础地址

- **当** 设置了跨源 `VITE_API_BASE_URL` 且已存在 HttpOnly `research_session` Cookie
- **那么** 创建的 EventSource MUST 设置 `withCredentials: true`，由浏览器携带该 Cookie。

### 场景：令牌不暴露给前端 URL

- **当** 创建流式请求
- **那么** URL MUST 只包含既有业务查询参数，不得包含 API Key 或研究会话令牌。
