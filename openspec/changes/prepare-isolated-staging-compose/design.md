# 设计：隔离服务器测试 Compose 配置

新增 `docker-compose.staging.yml`，由部署命令显式使用 `-p enterprise-rag-staging`。后端仅绑定 `127.0.0.1:18000`，前端仅绑定 `127.0.0.1:18081`，避免将候选服务直接暴露到公网。

测试后端仅挂载 `./.staging/data` 到容器 `/app/data`，不挂载正式 `./data`。镜像内的候选 `config` 用于启动，测试栈不绑定宿主机配置目录。服务名称、容器名称和网络均使用 `staging` 后缀，并设置保守 CPU、内存上限及 `restart: "no"`。

测试环境文件为未跟踪的 `.env.staging`，由已跟踪的 `staging.env.example` 复制生成。HTTP 本机隧道验收可显式使用 `RESEARCH_SESSION_COOKIE_SECURE=false`；该值不得用于正式 HTTPS 部署。`CORS_ALLOWED_ORIGINS` 保持未设置，因为本配置通过 Nginx `/api` 走同源代理。
