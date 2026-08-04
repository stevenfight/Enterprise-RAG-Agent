# 变更提案: Docker 容器化部署

## 背景

当前项目只能在开发机上通过命令行手动启动（`python -m uvicorn` + `npm run dev`），存在以下问题：

1. 环境依赖复杂（Python 3.11+, Node.js 20+, FAISS, MinerU 等），新人部署困难
2. 无法保证不同机器上的运行环境一致（"我机器上能跑"问题）
3. 没有标准化的部署流程，不利于生产环境交付
4. 前后端需要启动两个独立进程，管理不便

## 目标

将项目打包为 Docker 容器，实现：

1. **一键启动**: 用户只需一条 `docker compose up` 命令即可启动整个系统
2. **环境一致性**: 所有依赖（Python、Node.js、系统库）打包在镜像内，任何机器上运行结果一致
3. **前后端统一管理**: 通过 docker-compose 编排后端 FastAPI + 前端静态文件服务
4. **数据外挂**: PDF 文档、向量索引、图表等数据通过卷（Volume）挂载，不写入镜像

## 范围

### 包含
- 后端 FastAPI 服务的 Docker 镜像（Python 3.11）
- 前端 React SPA 的构建和 Nginx 服务镜像
- docker-compose.yml 编排文件
- .dockerignore 忽略规则
- 环境变量模板 .env.docker

### 不包含
- Streamlit 备用界面的容器化（仅作本地开发使用，不纳入 Docker 部署）
- Kubernetes 编排（后续演进）
- CI/CD 流水线对接（后续演进）

## 与现有功能的关系

- 不修改任何 `src/`、`frontend/`、`config/` 下的业务代码
- 仅新增 Docker 相关配置文件
- 不影响现有本地开发流程（`start-dev.ps1` 继续可用）

## 版本

关联版本: **v4.0** - Docker 容器化部署
