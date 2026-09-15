# 设计：跨源 Agent SSE 研究会话

浏览器原生 `EventSource` 的第二参数支持 `EventSourceInit`。将现有构造调用改为 `new EventSource(url, { withCredentials: true })` 即可让允许凭据的跨源请求带上现有 HttpOnly Cookie；同源请求行为不变。

该选项仅要求浏览器发送已由服务端设置的 Cookie，不读取、复制或拼接令牌。因此它与后端的 `research_session` 校验和既有 Axios `withCredentials` 策略一致，不会新增认证回退路径。

验证使用 Vitest 的 EventSource Mock 检查构造选项；同时保留现有后端中间件测试，证明带有效研究会话的 SSE 可进入下游。测试不启动 Agent 或网络服务。
