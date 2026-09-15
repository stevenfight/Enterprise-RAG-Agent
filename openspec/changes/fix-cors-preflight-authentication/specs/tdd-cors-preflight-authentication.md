# TDD：CORS 预检鉴权顺序

| 编号 | 状态 | 验证内容 | 预期结果 |
|---|---|---|---|
| P-C01 | GREEN | 允许来源 OPTIONS 预检 | 200 且返回允许来源和凭据头。 |
| P-C02 | GREEN | 未配置来源 OPTIONS 预检 | 被 CORS 拒绝且不回显来源。 |
| P-C03 | GREEN | 实际 SSE 无凭据 GET | 仍在路由前返回 401。 |

## 执行记录

| 日期 | 用例 | 结果 | 证据 |
|---|---|---|---|
| 2026-09-12 | P-C01、P-C02 | RED | 实测允许来源 OPTIONS 被 APIAuthMiddleware 返回 401，未进入 CORS 中间件。 |
| 2026-09-12 | P-C01 至 P-C03 | GREEN | `python -m pytest -q tests/test_agent_stream_auth.py`：4 passed；允许来源预检 200，未配置来源 400，实际 SSE 无凭据仍由既有回归在下游前拒绝。 |
