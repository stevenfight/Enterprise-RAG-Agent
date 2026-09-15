# TDD：研究会话 Cookie 配置

| 编号 | 状态 | 验证内容 | 预期结果 |
|---|---|---|---|
| H-C01 | GREEN | 缺省配置 | Set-Cookie 带 Secure。 |
| H-C02 | GREEN | 明确本地 HTTP 配置 | Set-Cookie 不带 Secure。 |
| H-C03 | GREEN | 非法配置 | 配置解析抛出明确异常。 |

## 执行记录

| 日期 | 用例 | 结果 | 证据 |
|---|---|---|---|
| 2026-09-12 | H-C01 至 H-C03 | RED | 严格配置解析函数尚不存在；当前代码把任何非 `true` 值静默当作 false。 |
| 2026-09-12 | H-C01 至 H-C03 | GREEN | `python -m pytest -q tests/test_research_identity_api.py`：3 passed；缺省为 Secure、明确 false 不带 Secure、非法值抛出明确异常。 |
