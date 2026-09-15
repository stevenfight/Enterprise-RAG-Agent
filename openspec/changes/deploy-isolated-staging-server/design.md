# 设计：部署隔离服务器测试栈

候选源码使用 `git archive 5e17993` 传输，不依赖服务器正式仓库的远端分支。服务器目标目录在部署前必须不存在；创建后写入仅含提交短哈希的 `STAGING_CANDIDATE_COMMIT` 标识文件。

`.env.staging` 仅保存在服务器测试目录，包含随机生成的临时研究管理员密码、`RESEARCH_SESSION_COOKIE_SECURE=false` 和用于验收的 `CORS_ALLOWED_ORIGINS=http://127.0.0.1:18081`。凭据和 Cookie 值不写入版本库、命令输出或交接文档。

启动命令固定为 `docker compose -p enterprise-rag-staging -f docker-compose.staging.yml --env-file .env.staging up -d --build`。Compose 已限制为回环端口、独立卷和保守资源上限。验收仅访问回环地址，且检查正式 `rag-backend`、`rag-frontend` 的运行态未改变。
