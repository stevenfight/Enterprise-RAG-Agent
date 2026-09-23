# 设计

## SSE 会话

`streamAgentQuery` 继续使用浏览器原生 EventSource，并显式设置 `withCredentials: true`。该选项使跨源请求可携带服务端 HttpOnly 研究会话；身份信息不得写入查询参数或日志。

## 路由依赖

将 `package.json` 和 `package-lock.json` 恢复为 HEAD 中的 `react-router-dom/react-router 7.18.3` 解析结果及原 npm registry 地址。不安装依赖、不更改其他包。

## 验证

先恢复 SSE 凭据契约测试并确认其在当前实现下失败，再恢复实现并运行服务层测试、前端类型/构建验证和锁文件差异核验。
