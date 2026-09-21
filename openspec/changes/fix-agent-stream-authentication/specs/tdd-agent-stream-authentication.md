# TDD：Agent SSE 流式接口鉴权旁路

| 编号 | 状态 | 验证内容 | 预期结果 |
|---|---|---|---|
| S-A01 | GREEN | 无 Key SSE 请求 | 返回 401，且下游路由不被调用。 |
| S-A02 | GREEN | 错误 Key SSE 请求 | 返回 401，且下游路由不被调用。 |
| S-A03 | GREEN | 正确 Bearer API Key SSE 请求 | 中间件调用下游路由。 |
| S-A04 | GREEN | 有效研究会话 SSE 请求 | 中间件调用下游路由，支持 EventSource。 |
| S-A05 | GREEN | 健康检查匿名请求 | 保持既有白名单，调用下游路由。 |

## 执行记录

| 日期 | 用例 | 结果 | 证据 |
|---|---|---|---|
| 2026-09-12 | S-A01 至 S-A05 | RED | 新增中间件回归测试后，S-A01/S-A02 将因 `/api/agent/stream` 位于 `SKIP_PATHS` 而错误透传下游。 |
| 2026-09-12 | S-A01 至 S-A05 | GREEN | 移除 SSE 静态白名单项后，`python -m pytest -q tests/test_agent_stream_auth.py`：3 passed；无 Key/错误 Key 均在下游前 401，正确 Bearer Key 与有效研究会话均透传。 |
