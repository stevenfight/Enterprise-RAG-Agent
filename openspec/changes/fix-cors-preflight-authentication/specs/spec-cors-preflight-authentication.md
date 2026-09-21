# 规格：CORS 预检鉴权顺序

## 需求：允许来源的真实预检可得到 CORS 响应

### 场景：允许的本地开发来源

- **当** `http://localhost:5173` 向受保护 API 发送真实 CORS OPTIONS 预检
- **那么** 响应 MUST 为 200，包含该来源和 `access-control-allow-credentials: true`。

### 场景：未配置来源

- **当** 未配置来源发送真实 CORS OPTIONS 预检
- **那么** CORS 中间件 MUST 拒绝请求，且不得回显该来源。

## 需求：实际业务请求仍须鉴权

### 场景：无凭据 SSE GET

- **当** 无研究会话且无正确 Bearer API Key 的客户端请求 SSE
- **那么** 响应 MUST 保持 401。
