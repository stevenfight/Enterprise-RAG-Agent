# 变更提案：让 CORS 预检到达 CORS 中间件

## 背景

`APIAuthMiddleware` 位于 CORS 中间件外层。浏览器为跨源且带 Authorization 的请求发送 OPTIONS 预检时，鉴权中间件先返回 401，导致允许来源无法获得 `Access-Control-Allow-Origin` 或凭据许可，实际请求不会发送。

## 目标

1. 仅让真实的 CORS 预检请求进入既有 CORS 中间件。
2. 保持所有实际 API 请求的研究会话/Bearer API Key 认证不变。
3. 继续由既有 CORS 白名单拒绝未配置来源。

## 非目标

- 不增加 CORS 来源、不放宽 API 鉴权、不在 OPTIONS 中返回业务数据。
- 不修改 SSE 事件协议、Cookie 配置或部署域名。
