## ADDED Requirements

### Requirement: 跨源 Agent SSE 必须携带既有研究会话且不得泄露令牌

前端 MUST 以 `withCredentials: true` 创建 `/api/agent/stream` 的 EventSource，并保持令牌不出现在 URL 中。

#### Scenario: 跨源登录会话被浏览器携带

- **WHEN** 设置跨源 `VITE_API_BASE_URL` 且浏览器已有 HttpOnly `research_session` Cookie
- **THEN** EventSource 构造选项启用 `withCredentials: true`

#### Scenario: SSE URL 不含凭据

- **WHEN** 前端创建流式请求 URL
- **THEN** URL 只保留既有业务查询参数，不包含 API Key 或研究会话令牌
