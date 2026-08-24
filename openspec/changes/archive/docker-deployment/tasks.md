# 实现任务清单: Docker 容器化部署

## Phase 1: 基础设施配置

- [x] 1.1 创建 `openspec/changes/docker-deployment/` 文档目录
- [x] 1.2 编写 proposal.md（变更提案）
- [x] 1.3 编写 design.md（技术设计）
- [x] 1.4 编写 tasks.md（本文件）

## Phase 2: Docker 配置文件

- [x] 2.1 创建 `.dockerignore` -- 排除不需要打包的文件（node_modules, __pycache__, .git, _local 等）
- [x] 2.2 创建 `.env.docker` -- Docker 环境下的环境变量模板
- [x] 2.3 创建 `Dockerfile.backend` -- 后端 FastAPI 镜像
- [x] 2.4 创建 `Dockerfile.frontend` -- 前端 React 镜像（多阶段构建）
- [x] 2.5 创建 `nginx.conf` -- Nginx 静态文件 + API 代理配置
- [x] 2.6 创建 `docker-compose.yml` -- 前后端服务编排

## Phase 3: 版本记录

- [ ] 3.1 更新 `CHANGELOG.md` -- 记录 v4.0 Docker 部署变更
- [ ] 3.2 更新 `openspec/project.md` -- 补充 v4.0 演进路线

## Phase 4: 验证

- [x] 4.1 验证 `.dockerignore` 排除规则是否正确
- [x] 4.2 验证 `docker compose build` 能否成功构建 (backend + frontend)
- [x] 4.3 验证 `docker compose up` 能否正常启动
- [x] 4.4 验证前端页面能否访问
- [x] 4.5 验证 API 健康检查 `/api/health` 返回正常
- [x] 4.6 验证多Agent API `/api/agent/query` (mode=multi) 功能正常 (orchestrator → delegate → DataAgent 完整链路通过)
