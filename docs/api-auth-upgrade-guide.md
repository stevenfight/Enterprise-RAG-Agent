# API 升级说明: v5.1 — API Key 鉴权 + per-request Agent

> 面向: 前端/调用方开发者
> 版本: v5.1
> 生效: 本次部署后

---

## 变更摘要

本次升级新增了 **API Key 鉴权** 并修复了 Agent 的并发安全问题。
所有调用方需要在下一次部署前完成以下适配。

---

## 变更一: 所有 API 端点需要 API Key（两行改动）

### 影响范围

除以下路径外，**所有** API 端点都需要携带鉴权 Header:

| 豁免路径（无需 Key） | 用途 |
|:--|------|
| `GET /api/health` | 健康检查 / 监控探测 |
| `GET /docs` | API 文档 |
| `GET /openapi.json` | OpenAPI Schema |
| `GET /redoc` | ReDoc 文档 |

以下端点**新增鉴权要求**:

| 端点 | 方法 | 功能 |
|:--|:--:|------|
| `/api/query` | POST | RAG 问答 |
| `/api/agent/query` | POST | Agent ReAct 推理 |
| `/api/agent/stream` | GET | Agent SSE 流式推理 |
| `/api/agent/plan` | GET | 任务规划数据 |
| `/api/retrieve` | POST | 仅检索 |
| `/api/companies` | GET | 公司列表 |
| `/api/charts/list` | GET | 图表列表 |
| `/api/admin/*` | GET/POST | 管理接口 |
| `/v1/chat/completions` | POST | OpenAI 兼容接口 |
| `/api/langbot/chat` | POST | LangBot 接口 |

### 怎么改

**所有请求新增一个 Header:**

```
Authorization: Bearer <your-api-key>
```

#### 示例: curl

```bash
# 旧版（v5.0）
curl -X POST http://localhost:8000/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "贵州茅台2023年营收", "max_steps": 5}'

# 新版（v5.1） -- 多加一行 Header
curl -X POST http://localhost:8000/api/agent/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-api-key>" \
  -d '{"query": "贵州茅台2023年营收", "max_steps": 5}'
```

#### 示例: JavaScript / TypeScript (fetch)

```js
// 旧版
const resp = await fetch("http://localhost:8000/api/agent/query", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ query: "..." }),
});

// 新版 -- 多一个 header
const API_KEY = "your-api-key-here";
const resp = await fetch("http://localhost:8000/api/agent/query", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${API_KEY}`,   // 新增
  },
  body: JSON.stringify({ query: "..." }),
});
```

#### 示例: Python (requests)

```python
# 新版 -- 多一个 header
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}",   # 新增
}
resp = requests.post("http://localhost:8000/api/agent/query",
                     json={"query": "...", "max_steps": 5},
                     headers=headers)
```

### 错误响应

| 场景 | HTTP 状态码 | body |
|------|:--:|------|
| 缺少 `Authorization` Header | 401 | `{"detail": "未授权: 缺少 API Key"}` |
| Authorization 格式不对 | 401 | `{"detail": "未授权: 缺少 API Key"}` |
| Key 值不匹配 | 401 | `{"detail": "未授权: API Key 无效"}` |

### Q: API Key 从哪获取？

联系服务端管理员或在 `config/agent_config.json` 的 `api.key` 字段配置。

---

## 变更二: max_steps 硬上限 15

`max_steps` 请求参数新增硬上限 **15**。客户端传入大于 15 的值时，服务端自动截断为 15 并记录 WARNING 日志。

**无需改代码** — 这是链式保护，调用方不受影响。但如果你的前端显示"最大步数可选 20"之类的 UI，请改为 15。

---

## 变更三: 错误信息脱敏

API 返回的 HTTP 500 错误不再包含原始异常细节。例如:

| 旧版 detail | 新版 detail |
|------|------|
| `"Agent 推理错误: FileNotFoundError: xxx.py not found"` | `"Agent 推理过程发生内部错误"` |
| `"SSE 流异常: KeyError: 'content'"` | `"流式推理过程发生内部错误"` |

如果你的前端依赖解析 `detail` 中的错误类型做分支处理，请改为根据 HTTP 状态码判断（200=成功, 400=参数错误, 404=未找到, 401=未授权, 500=内部错误）。

---

## 变更四: Agent per-request 实例化（无影响）

v5.1 将 Agent 从全局单例改为每个请求独立创建。这是内部架构优化，对 API 接口、请求格式、响应格式没有任何影响。并发性能更好。

---

## 前端 UI 适配建议

| 模块 | 操作 |
|------|------|
| 请求拦截器 | 统一注入 `Authorization: Bearer <key>` Header |
| max_steps 滑块 | 上限从 20 改为 15 |
| 401 处理 | 添加 401 统一处理（跳转登录或提示"未授权"） |
| 错误提示 | 不再依赖 `detail` 字符串做精确匹配，改用状态码判断 |
| `/api/health` | 无需改动（健康检查豁免鉴权） |

---

## 时间线

| 日期 | 事项 |
|------|------|
| 今日 | 服务端部署 v5.1，上述变更生效 |
| 部署前 | 前端调用方完成适配（主要是一行 Header + 401 处理） |
| 部署后 | 同步更新 LangBot 数据库中 `api_keys` 字段为实际 API Key |

---

> 如有问题请联系后端团队。API Key 请妥善保管，勿提交到代码仓库。
