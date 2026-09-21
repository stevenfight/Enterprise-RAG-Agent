## ADDED Requirements

### Requirement: 研究会话 Cookie 的 Secure 配置必须显式且失败关闭

系统 MUST 在未配置时签发 Secure 研究会话 Cookie；仅接受 `true` 或 `false` 作为 `RESEARCH_SESSION_COOKIE_SECURE` 的值。

#### Scenario: 未配置保持安全默认

- **WHEN** 未设置 `RESEARCH_SESSION_COOKIE_SECURE`
- **THEN** 登录响应的研究会话 Cookie 带 `Secure`

#### Scenario: 非法配置不降低安全属性

- **WHEN** 配置值不是 `true` 或 `false`
- **THEN** 配置解析拒绝该值，且不得签发弱化的 Cookie
