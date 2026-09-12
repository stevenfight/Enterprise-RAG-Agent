# TDD：隔离服务器测试部署

| 编号 | 初始状态 | 验收项 | 通过标准 |
|---|---|---|---|
| D-S01 | RED | 服务器前置 | 测试目录不存在，18000/18081 空闲，正式容器正常。 |
| D-S02 | RED | 候选来源 | 测试目录存在且提交标识为 `5e17993`。 |
| D-S03 | RED | 服务可用性 | 后端健康检查和研究登录均返回成功。 |
| D-S04 | RED | 安全回归 | 未授权 SSE 返回 401，CORS 预检允许测试前端来源。 |
| D-S05 | RED | 隔离性 | 正式容器与正式端口运行态未被测试部署改变。 |
| D-S06 | RED | 资源处置边界 | 仅清理可回收 BuildKit 缓存和悬空无标签镜像，正式容器、卷、网络、具名镜像和项目数据均保留。 |
| D-S07 | RED | 无 Provider 验收启动条件 | 健康和鉴权验证不发起 Agent 请求；若服务启动仅要求非空 Key，可使用不可用于 Provider 的测试占位值。 |
| D-S08 | RED | 浏览器会话与 SSE 首帧 | 经本机 SSH 回环隧道，浏览器登录后 Cookie 可用，带会话的 SSE 收到不触发 Provider 的首个服务端事件。 |
| D-S09 | GREEN | 真实 SSE 内容首帧 | 使用仅限测试的真实 Provider 凭据，浏览器在带会话的有效 SSE 查询中收到首个服务端事件。 |
| D-S10 | GREEN | Provider 模型权限边界 | 仅允许 `qwen-turbo` 的测试 Key 时，隔离容器内实际会触发 Provider 的 Agent 角色模型均为 `qwen-turbo`；仓库配置和正式容器不变。 |

## 运行记录

| 日期 | 编号 | 状态 | 证据 |
|---|---|---|---|
| 2026-09-12 | D-S01 至 D-S05 | RED | 隔离 Compose 已完成本地静态验证，但服务器测试栈尚未创建。 |
| 2026-09-12 | D-S01 | GREEN | 测试目录初始不存在，18000/18081 未监听；正式后端为 `running/healthy`、正式前端为 `running`。 |
| 2026-09-12 | D-S02 | GREEN | 已上传 `5e17993` 归档至独立目录，并写入仅含该提交标识的 `STAGING_CANDIDATE_COMMIT`。 |
| 2026-09-12 | D-S03 至 D-S04 | RED | Compose 构建运行超过受限等待窗口仍未创建容器，不能执行健康、登录、SSE 与 CORS 验收。 |
| 2026-09-12 | D-S05 | GREEN | 终止未完成测试构建后，未见测试容器或 18000/18081 监听；正式后端仍 `running/healthy`、正式前端仍 `running`。 |
| 2026-09-12 | D-S06 | RED | 已获用户授权，但尚未读取 Docker 可回收对象或执行受限清理。 |
| 2026-09-12 | D-S07 | RED | 后端构建完成后因 `DASHSCOPE_API_KEY` 未设置而退出，健康检查无法执行；尚未调用任何 Provider。 |
| 2026-09-12 | D-S06 | GREEN | `docker builder prune -af` 回收 3.668GB，`docker image prune -f` 回收 6.3GB；未删除容器、卷、网络、具名镜像或项目数据。 |
| 2026-09-12 | D-S07 | GREEN | 仅在 `.env.staging` 设置不可用于 Provider 的占位值后，后端健康启动；验收只访问健康、身份、SSE 未授权与 CORS，不调用 Agent 业务接口。 |
| 2026-09-12 | D-S03 | GREEN | 后端 `/api/health`、登录、会话均为 200；隔离前端 Nginx `/api/health` 与登录代理也为 200。 |
| 2026-09-12 | D-S04 | GREEN | 无凭据且带有效 query 的 SSE 为 401；测试 Origin 的预检为 200，并返回允许来源与凭据头。 |
| 2026-09-12 | D-S05 | GREEN | 正式后端 `running/healthy`、正式前端 `running`；测试服务仅使用 `127.0.0.1:18000/18081` 和 `/opt/enterprise-rag-staging/.staging/data`。 |
| 2026-09-12 | D-S08 | RED | 本机尚无到服务器 `127.0.0.1:18081` 的 SSH 隧道，无法验证真实浏览器 Cookie 与 EventSource。 |
| 2026-09-12 | D-S08 | GREEN（会话与预检） | 临时 `127.0.0.1:19081` 隧道中，真实 Chrome 显示 `login=200`、`me=200`；带 Cookie 的 `fetch` SSE 安全参数预检为 400，`EventSource` 触发错误回调，标准工作台识别 `staging-admin`。请求 `max_steps=0`，在参数校验处停止且未调用 Provider。 |
| 2026-09-12 | D-S09 | RED | 有效 SSE 查询会进入 Agent/Provider；当前只有不可用占位 Key，不能将预检错误回调表述为内容首帧。 |
| 2026-09-12 | D-S10 | RED | 候选默认配置含 `qwen-max` 与 `qwen-plus`，与本轮仅允许 `qwen-turbo` 的测试 Key 不兼容。 |
| 2026-09-12 | D-S09 | GREEN | 临时回环隧道中的真实 Chrome 收到 `connected`、`thought`、`answer_chunk`、`answer`；验收页只记录事件类型，不展示模型答案。 |
| 2026-09-12 | D-S10 | GREEN | 首次临时覆盖误写入 JSON 根层，日志证实运行时仍使用 `qwen-max` 并收到 403；已修正为 `agent.model` 和 `agent.models.*` 后仅重试一次，浏览器收到 `answer`。仓库配置与正式容器未改。 |
| 2026-09-12 | D-S09 至 D-S10 | GREEN（回收） | 测试凭据已恢复为无效占位值，隔离后端已重建；临时页面、服务器脚本、本机隧道和日志均已删除，隔离与正式后端均为 healthy。 |
