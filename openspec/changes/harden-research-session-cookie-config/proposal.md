# 变更提案：收紧研究会话 Cookie 配置

## 背景

研究登录 Cookie 默认 `Secure=true`，这是部署安全要求；但 `.env.example` 未说明本地 HTTP 调试必须显式关闭它。同时现有解析将除精确 `true` 以外的任意值都视为 false，拼写错误会静默降低 Cookie 安全属性。

## 目标

1. 保持未配置时 `Secure=true`。
2. 仅接受 `true` 或 `false`，其他值失败关闭。
3. 在无敏感值的环境模板中说明本地 HTTP 与 HTTPS 部署的取值边界。

## 非目标

- 不改变 `SameSite=Strict`、HttpOnly、Cookie 名称、CORS 白名单或部署域名。
- 不为未知远端域名添加宽泛 CORS 放行。
