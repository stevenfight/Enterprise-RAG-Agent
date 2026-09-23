## ADDED Requirements

### Requirement: Agent SSE SHALL 受 API 鉴权保护

Agent SSE 实际请求 SHALL 要求有效 Bearer API Key 或有效的服务端研究会话；浏览器真实 CORS 预检可通过 CORS 中间件，但不得放行实际业务请求。

#### Scenario: 无凭据访问 SSE

- **WHEN** 客户端请求 `/api/agent/stream` 且没有有效 Bearer 或研究会话
- **THEN** API 返回 401
- **AND** 请求不得进入下游路由

#### Scenario: 浏览器发起真实跨域预检

- **WHEN** OPTIONS 请求同时包含 Origin 和 Access-Control-Request-Method
- **THEN** CORS 中间件根据显式安全 Origin 配置处理预检
- **AND** 实际 GET SSE 请求仍受鉴权

### Requirement: 隔离 staging 凭据 SHALL 不得被提交

隔离 staging 的实际环境文件 SHALL 保持本地化，模板是唯一可提交的配置示例。

#### Scenario: 创建 .env.staging

- **WHEN** 开发者创建包含测试凭据的 `.env.staging`
- **THEN** Git 必须忽略该文件
- **AND** `staging.env.example` 仍可被版本控制
