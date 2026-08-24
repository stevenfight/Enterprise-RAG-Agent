# 设计文档：图表与 DAG 接口鉴权收紧

## 方案

仅调整 `APIAuthMiddleware.SKIP_PATHS` 集合，移除以下两个路径：

- `/api/charts/list`
- `/api/agent/plan`

保留：

- `/api/health`、`/docs`、`/openapi.json`、`/redoc`（健康检查与文档）。
- `/api/agent/stream`（EventSource 无法携带自定义请求头）。
- `/api/charts/images/` 前缀（静态图片标签无法携带鉴权头）。

## 前端兼容性

第一阶段已将以下请求统一到 `apiClient`：

- `chartService.getCharts()` → `GET /api/charts/list`
- `dagService.getAgentPlan()` → `GET /api/agent/plan`

`apiClient` 请求拦截器会自动附加 `Authorization: Bearer <VITE_API_KEY || 'no-key-needed'>`，与后端 `_api_key` 默认值 `no-key-needed` 匹配，因此前端无需改动。

## 边界确认

- `/api/agent/plan` 是 GET 请求，移除豁免后携带鉴权头即可访问。
- `/api/charts/list` 返回的数据中 `image_url` 指向 `/api/charts/images/{filename}`，图片由 `<img>` 直接加载，因此 `SKIP_PREFIXES` 保留不变。

## 影响面

- 后端中间件集合变更，无路由、模型、业务逻辑改动。
- 未带鉴权头访问这两个接口将返回 401。
