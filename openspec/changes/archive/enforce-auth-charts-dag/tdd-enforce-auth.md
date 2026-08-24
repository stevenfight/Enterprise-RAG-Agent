# TDD 测试用例：图表与 DAG 接口鉴权收紧

> 编码: UTF-8
> 约定: <span style="color:red">红色</span> = 未通过, <span style="color:green">绿色</span> = 已通过

---

## 一、测试范围

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-AUTH-01 | 无鉴权头访问 /api/charts/list 被拒绝 | 1. 不带 Authorization 请求 `GET /api/charts/list` | 401 | <span style="color:green">GREEN</span> |
| TC-AUTH-02 | 错误 Key 访问 /api/charts/list 被拒绝 | 1. 带 `Bearer wrong-key` 请求 `GET /api/charts/list` | 401 | <span style="color:green">GREEN</span> |
| TC-AUTH-03 | 正确 Key 访问 /api/charts/list 放行 | 1. 带正确 Key 请求 `GET /api/charts/list` | 非 401 | <span style="color:green">GREEN</span> |
| TC-AUTH-04 | 无鉴权头访问 /api/agent/plan 被拒绝 | 1. 不带 Authorization 请求 `GET /api/agent/plan?query=x` | 401 | <span style="color:green">GREEN</span> |
| TC-AUTH-05 | 错误 Key 访问 /api/agent/plan 被拒绝 | 1. 带 `Bearer wrong-key` 请求 `GET /api/agent/plan?query=x` | 401 | <span style="color:green">GREEN</span> |
| TC-AUTH-06 | 正确 Key 访问 /api/agent/plan 放行 | 1. 带正确 Key 请求 `GET /api/agent/plan?query=x` | 非 401 | <span style="color:green">GREEN</span> |
| TC-AUTH-07 | /api/agent/stream 仍豁免鉴权 | 1. 确认 stream 保留在 SKIP_PATHS | 仍豁免 | <span style="color:green">GREEN</span> |
| TC-AUTH-08 | /api/charts/images/ 仍豁免鉴权 | 1. 不带 Authorization 请求图片静态资源 | 非 401（404） | <span style="color:green">GREEN</span> |
| TC-AUTH-09 | /api/health 仍豁免鉴权 | 1. 不带 Authorization 请求 `GET /api/health` | 200 | <span style="color:green">GREEN</span> |

---

## 二、测试统计

| 项目 | 数量 |
|------|:--:|
| 用例总数 | 9 |
| 已通过 | 9 |
| 未通过 | 0 |
