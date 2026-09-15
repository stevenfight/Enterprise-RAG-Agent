## ADDED Requirements

### Requirement: 允许来源的真实 CORS 预检必须先由 CORS 处理

系统 MUST 让真实 CORS OPTIONS 预检到达既有 CORS 中间件，同时不放宽实际业务请求鉴权。

#### Scenario: 允许来源的预检获得凭据许可

- **WHEN** `http://localhost:5173` 向受保护 API 发送真实 CORS OPTIONS 预检
- **THEN** 响应为 200，回显该来源并包含 `access-control-allow-credentials: true`

#### Scenario: 实际无凭据 SSE 请求仍被拒绝

- **WHEN** 客户端没有有效研究会话和正确 Bearer API Key 而请求 SSE
- **THEN** 实际 GET 请求仍在路由前返回 401
