# TDD：跨源 Agent SSE 研究会话

| 编号 | 状态 | 验证内容 | 预期结果 |
|---|---|---|---|
| C-S01 | GREEN | EventSource 构造选项 | `withCredentials` 为 true。 |
| C-S02 | GREEN | 有效研究会话后端通道 | 既有后端中间件回归允许会话请求进入下游。 |
| C-S03 | GREEN | URL 令牌泄露 | SSE URL 不含 API Key 或研究会话 token。 |

## 执行记录

| 日期 | 用例 | 结果 | 证据 |
|---|---|---|---|
| 2026-09-12 | C-S01 | RED | 现有 `new EventSource(url)` 未传入构造选项。 |
| 2026-09-12 | C-S01 | GREEN | `new EventSource(url, { withCredentials: true })` 后，`npm test -- src/services/__tests__/chatService.test.ts`：2 passed。 |
| 2026-09-12 | C-S02、C-S03 | GREEN | 后端 `tests/test_agent_stream_auth.py tests/test_research_session_auth.py`：4 passed；同一前端 Mock 同时断言 EventSource URL 不含 `research_session` 或 `api_key`。 |
