# 变更提案：图表与 DAG 接口鉴权收紧

## 背景

`APIAuthMiddleware.SKIP_PATHS` 中当前包含 `/api/charts/list` 与 `/api/agent/plan`，二者被免鉴权放行。加入白名单的历史原因是前端此前使用原生 `fetch` 无法携带鉴权头。

第一阶段已完成前端请求统一：`ChartsPage` 与 `DagBoardPage` 均已迁移到 `apiClient`（axios），请求拦截器会自动附加 `Authorization: Bearer <key>` 头。因此这两个接口已具备恢复正常鉴权的前提。

当前风险：

- `/api/charts/list` 允许未认证访问财务图表数据。
- `/api/agent/plan` 允许未认证触发 Agent 任务规划、暴露工具参数并消耗模型资源。

## 目标

- 从 `SKIP_PATHS` 移除 `/api/charts/list` 与 `/api/agent/plan`，恢复鉴权校验。
- 保留 `/api/agent/stream` 豁免（EventSource 无法携带自定义请求头）。
- 保留 `/api/charts/images/` 前缀豁免（`<img>` 静态图片标签无法携带鉴权头）。
- 前端功能不受影响（apiClient 已自动附带鉴权头）。

## 非目标

- 不改变后端接口返回结构。
- 不改变前端请求逻辑（第一阶段已统一）。
- 不处理其他接口的鉴权策略。
- 不新增第三方依赖。
