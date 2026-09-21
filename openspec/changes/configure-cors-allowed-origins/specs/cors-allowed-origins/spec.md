## ADDED Requirements

### Requirement: CORS 允许来源必须显式且可配置

系统 MUST 在未配置 `CORS_ALLOWED_ORIGINS` 时仅使用既有本地开发来源；配置时只接受逗号分隔的 HTTP(S) 来源，并交由既有 CORS 中间件使用。

#### Scenario: 显式 HTTPS 来源被加入白名单

- **WHEN** `CORS_ALLOWED_ORIGINS` 包含有效 HTTPS 来源和本地来源
- **THEN** 系统按配置顺序提供严格来源列表

#### Scenario: 非法来源配置失败关闭

- **WHEN** 配置包含空值、通配符、重复值、路径、查询参数、片段或非 HTTP(S) 来源
- **THEN** 启动配置解析拒绝该配置并指出变量名
