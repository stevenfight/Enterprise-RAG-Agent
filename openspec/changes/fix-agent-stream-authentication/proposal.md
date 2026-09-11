# 变更提案：修复 Agent SSE 流式接口鉴权旁路

## 背景

`/api/agent/stream` 被 `APIAuthMiddleware.SKIP_PATHS` 静态放行。带有效 `query` 的无 Key 或错误 Key 请求会越过 API Key 校验并进入业务路由，当前在 Agent 未初始化时返回 503。该行为把认证失败伪装成服务不可用，也使未经认证的请求可以触达后续流式逻辑。

## 目标

1. 让 `/api/agent/stream` 与其他受保护 API 一样先经过全局鉴权。
2. 缺少或错误 Bearer API Key 时在进入下游路由前返回 401。
3. 保留既有两种合法身份：正确 Bearer API Key，以及服务端验证通过的 `research_session` 会话，供 EventSource 使用。
4. 保持健康检查、文档和既有研究认证前缀的白名单范围不变。

## 非目标

- 不修改 SSE 事件格式、Agent 推理、Provider 调用或前端 EventSource 实现。
- 不新增 URL 查询参数令牌、客户端可伪造会话或其他降级认证方式。
- 不以真实 API Key、真实模型或生产财报数据验证本次修复。
