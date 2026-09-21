# 规格：Agent SSE 流式接口鉴权

## 需求：SSE 流式接口必须受到全局鉴权保护

系统 MUST 不将 `/api/agent/stream` 置于 API Key 静态放行路径中。

### 场景：缺少凭据的流式请求被路由前拒绝

- **当** 客户端请求 `/api/agent/stream` 且没有有效研究会话和 Bearer API Key
- **那么** 中间件 MUST 返回 401，且不得调用下游路由。

### 场景：错误 Bearer API Key 的流式请求被路由前拒绝

- **当** 客户端请求 `/api/agent/stream` 且 Bearer API Key 错误
- **那么** 中间件 MUST 返回 401，且不得调用下游路由。

### 场景：正确 Bearer API Key 的流式请求保留原有路由访问

- **当** 客户端携带正确 Bearer API Key 请求 `/api/agent/stream`
- **那么** 中间件 MUST 调用下游路由。

### 场景：有效研究会话支持 EventSource

- **当** 客户端携带服务端验证通过的 `research_session` 请求 `/api/agent/stream`
- **那么** 中间件 MUST 调用下游路由，无需额外 Bearer API Key。

## 需求：既有公开健康检查不受影响

### 场景：健康检查仍可匿名访问

- **当** 客户端无凭据访问 `/api/health`
- **那么** 中间件 MUST 调用下游路由。
