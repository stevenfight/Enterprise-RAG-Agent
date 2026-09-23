# TDD 台账

| 编号 | 初始状态 | 契约 | 验证证据 |
| --- | --- | --- | --- |
| A-T1 | GREEN | SSE 必须要求有效 Bearer 或研究会话，真实预检仍可通过 CORS | 初始白名单旁路导致失败；恢复后 `test_agent_stream_auth.py` 5 passed |
| A-T2 | GREEN | CORS 配置必须显式、唯一且安全 | 初始 `_cors_allowed_origins` 缺失导致失败；恢复后同一测试覆盖默认、合法与非法 Origin |
| A-T3 | GREEN | `.env.staging` 必须不被 Git 跟踪 | 初始 `.gitignore` 缺少规则导致失败；恢复后 `test_staging_compose_contract.py` 2 passed，`git check-ignore` 确认生效 |
