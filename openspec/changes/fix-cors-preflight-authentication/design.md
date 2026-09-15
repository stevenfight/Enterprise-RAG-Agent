# 设计：CORS 预检与 API 鉴权顺序

仅当请求同时满足 OPTIONS、存在 Origin 和存在 Access-Control-Request-Method 时，API 鉴权中间件调用下游。内层 CORS 中间件随后按既有白名单处理允许或拒绝来源。

这不是 OPTIONS 的通用白名单：没有 CORS 预检头的 OPTIONS 仍按正常鉴权流程；实际 GET/POST 请求也不会绕过认证。测试以允许本地来源、未配置来源和既有 SSE 实际请求回归证明边界。
