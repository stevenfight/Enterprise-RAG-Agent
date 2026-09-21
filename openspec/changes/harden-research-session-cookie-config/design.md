# 设计：研究会话 Cookie 配置

新增一个只读取 `RESEARCH_SESSION_COOKIE_SECURE` 的小型解析函数。未设置时返回 true；值经小写与首尾空白规范化后仅允许 `true`/`false`，否则抛出明确异常。登录端点继续使用该函数设置既有 Cookie，其他 Cookie 属性不变。

这样本地 HTTP 必须由操作者明确配置 `false`，HTTPS 部署保持默认或显式 `true`。无效拼写不会降级为不安全 Cookie。测试仅验证 Set-Cookie 属性和配置解析，不使用真实身份或网络。
