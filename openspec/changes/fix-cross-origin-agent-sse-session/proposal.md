# 变更提案：让跨源 Agent SSE 携带研究会话

## 背景

`/api/agent/stream` 已改为要求有效 Bearer API Key 或服务端研究会话。前端普通 Axios 请求设置了 `withCredentials: true`，但 `streamAgentQuery` 使用 `new EventSource(url)`，跨源 `VITE_API_BASE_URL` 场景下不会携带 HttpOnly `research_session` Cookie，登录后的用户会被后端正确拒绝为 401。

## 目标

1. 让旧 Agent SSE 的浏览器 EventSource 在跨源后端场景携带既有研究会话 Cookie。
2. 不在 URL、日志或 JavaScript 中暴露会话令牌。
3. 保持既有 URL 参数、事件处理和关闭行为不变。

## 非目标

- 不修改后端鉴权、中间件、SSE 事件协议或 CORS 策略。
- 不调用真实 Provider、真实 API Key 或生产数据。
