# 规格：研究会话 Cookie 配置

## 需求：Cookie Secure 配置必须明确且安全

系统 MUST 默认以 Secure 属性签发研究会话 Cookie，仅接受明确布尔配置。

### 场景：未配置时保持 HTTPS 安全默认

- **当** 未设置 `RESEARCH_SESSION_COOKIE_SECURE`
- **那么** 登录响应的研究会话 Cookie MUST 带 `Secure`。

### 场景：本地 HTTP 明确配置

- **当** `RESEARCH_SESSION_COOKIE_SECURE=false`
- **那么** 登录响应的研究会话 Cookie MUST 不带 `Secure`，供受控本地 HTTP 调试使用。

### 场景：无效配置失败关闭

- **当** 配置不是 `true` 或 `false`
- **那么** 系统 MUST 拒绝该配置，不得签发弱化的 Cookie。
