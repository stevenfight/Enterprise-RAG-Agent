## ADDED Requirements

### Requirement: Agent SSE 流必须经过受控鉴权

系统 MUST 不把 `/api/agent/stream` 放入 API Key 静态放行路径；无有效凭据的请求不得到达下游路由。

#### Scenario: 缺少或错误 Bearer 凭据被拒绝

- **WHEN** 客户端请求 `/api/agent/stream` 且没有有效研究会话，或携带错误 Bearer API Key
- **THEN** 鉴权中间件在路由前返回 401

#### Scenario: 合法身份保留 SSE 访问

- **WHEN** 客户端携带正确 Bearer API Key 或服务端验证通过的 `research_session`
- **THEN** 请求可以进入既有下游 SSE 路由
