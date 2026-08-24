# 技术设计: Docker 容器化部署

## 整体架构

```
用户浏览器 (http://localhost:80)
       |
       v
+------------------+         +------------------+
|   Nginx 容器     |  ----   |  FastAPI 容器    |
|   (前端静态文件)  |  /api/* |  (端口 8000)     |
|   端口映射: 80   |         |                  |
+------------------+         +------------------+
                                    |
                            +------------------+
                            |  数据卷 (Volume)  |
                            |  data/            |
                            |  config/          |
                            +------------------+
```

### 两个容器的职责

| 容器 | 基础镜像 | 职责 | 端口 |
|------|---------|------|------|
| `backend` | `python:3.11-slim` | FastAPI 服务 + RAG 引擎 | 8000 |
| `frontend` | `nginx:alpine` | 托管 React 构建产物 + 反向代理 /api/* | 80 |

### 为什么用 Nginx 而不用 Vite 开发服务器？

- Vite dev server 是开发工具，不适合生产环境
- Nginx 是工业级静态文件服务器，性能高、资源省
- Nginx 可以同时做"静态文件服务"和"API 反向代理"，前端请求 `/api/*` 自动转发到后端

## 前端构建策略: 多阶段构建

```
阶段 1: node:20-alpine (构建阶段)
  ├── 安装 npm 依赖
  ├── 执行 npm run build
  └── 产出 dist/ 静态文件

阶段 2: nginx:alpine (运行阶段)
  ├── 复制 dist/ 到 /usr/share/nginx/html
  ├── 复制 nginx.conf 配置
  └── 仅 ~15MB（不含 Node.js 运行时）
```

多阶段构建的好处：最终镜像只包含 Nginx + 静态文件，体积小、安全性高。

## 后端镜像设计

```
FROM python:3.11-slim

1. 安装系统依赖（faiss-cpu 编译需要）
   - build-essential (C++ 编译器)
   - libopenblas-dev (FAISS 数学库依赖)

2. 复制 requirements.txt 并安装 Python 包
   - 利用 Docker 层缓存：只要 requirements.txt 不变，pip install 不重跑

3. 复制项目代码
   - src/、config/、app_streamlit.py

4. 设置启动命令
   - python -m uvicorn src.api_service:app --host 0.0.0.0 --port 8000
```

## 数据卷设计

以下目录通过 Docker Volume 挂载，不写入镜像：

| 宿主机路径 | 容器内路径 | 说明 |
|-----------|-----------|------|
| `./data/` | `/app/data/` | 向量索引 + PDF + 图表 |
| `./config/` | `/app/config/` | bm25 词典 + agent 配置 |

为什么要挂载？
1. 向量索引文件很大（几百MB），放镜像里会让镜像臃肿
2. 数据更新时不需要重建镜像
3. 容器删除后数据不丢失

## 环境变量传递

敏感信息（API Key）不写入镜像，通过 `.env.docker` 文件传入：

```
DASHSCOPE_API_KEY=你的key
MINERU_API_KEY=你的key
OPENAI_API_KEY=
GEMINI_API_KEY=
JINA_API_KEY=
```

docker-compose.yml 通过 `env_file` 指令自动加载。

## API 代理配置 (Nginx)

前端发起的 `/api/*` 请求会被 Nginx 转发到 `backend:8000`：

```nginx
location /api/ {
    proxy_pass http://backend:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

前端代码中 API 请求地址需要改为相对路径（已确认 `frontend/src/services/api.ts` 使用相对路径）。
