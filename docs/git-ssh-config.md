# Git SSH 配置与操作流程

## 1. SSH 配置（无需 VPN）

### 本地密钥

| 项目 | 值 |
|------|-----|
| 私钥文件 | `id_ed25519_local`（项目根目录） |
| 公钥文件 | `id_ed25519_local.pub`（项目根目录） |
| 密钥类型 | ed25519 |
| 注释 | local-dev |

### SSH Config 配置

文件路径：`C:\Users\111\.ssh\config`

```
Host github.com
    HostName github.com
    User git
    IdentityFile d:\文件信息\AI应用开发\AI实战练习\github-project\企业级财务年报分析智能RAG—AGENT\id_ed25519_local
    IdentitiesOnly yes
```

### 服务器密钥

| 项目 | 值 |
|------|-----|
| 密钥类型 | ed25519 |
| 注释 | server-deploy |
| 已添加至 GitHub | 是 |

服务器上已配置 SSH remote，无需 VPN。

---

## 2. Git Remote 配置

### 本地

```
origin  git@github.com:stevenfight/Enterprise-RAG-Agent.git (SSH)
```

### 服务器

```
origin  git@github.com:stevenfight/Enterprise-RAG-Agent.git (SSH)
```

---

## 3. 日常操作流程（无需 VPN）

### 方式一：deploy.py 一键部署（推荐）

```bash
python deploy.py deploy           # 完整部署：git pull → 重建容器 → 健康检查
python deploy.py status           # 查看容器状态
python deploy.py check            # 健康检查
python deploy.py logs backend     # 查看后端日志
python deploy.py logs frontend    # 查看前端日志
python deploy.py sync             # 仅 git pull 同步（不重建容器）
```

### 方式二：手动 SSH 部署

```bash
# 1. 本地修改代码
# 2. 提交并推送
git add <文件>
git commit -m "描述"
git push origin main

# 3. 登录服务器部署
ssh root@47.96.255.13
cd /opt/enterprise-rag
git pull origin main
docker compose up -d --build
```

### 服务器上的 git 用户配置

```bash
cd /opt/enterprise-rag
git config user.email "stevenfight@users.noreply.github.com"
git config user.name "stevenfight"
```

---

## 4. GitHub Actions CI/CD

### 自动构建：`.github/workflows/docker-build.yml`
- 触发：push 到 main 分支
- 构建产物：推送到 `ghcr.io/stevenfight/enterprise-rag-agent/`
- 镜像名已全小写（GHCR 要求）

### 自动部署示例：`.github/workflows/deploy-to-server.example.yml`
- 用途：Docker 构建完成后自动 SSH 到服务器拉取镜像并重启
- 需要配置 GitHub Secrets：`SSH_HOST`、`SSH_USER`、`SSH_KEY`
- 当前为示例文件（`.example.yml`），如需启用，去掉 `.example` 后缀并配置 Secrets

---

## 5. 注意事项

- `id_ed25519_local` 私钥文件权限需限制为仅当前用户可读（Windows 已用 icacls 修复）
- SSH config 文件不能用 UTF-8 BOM 编码（曾导致 `Bad configuration option` 错误）
- 临时脚本文件（deploy.py、check_data.py 等）未加入版本控制，不影响项目
- 服务器无法直连 GitHub HTTPS，已改用 SSH