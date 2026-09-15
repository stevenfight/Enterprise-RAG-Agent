# TDD：本地部署凭据去硬编码

| 用例 | 初始状态 | 期望 |
| --- | --- | --- |
| LDC-S01 | 🟢 GREEN | `deploy.py` 不得定义硬编码 `SERVER_PASSWORD` 常量 |
| LDC-S02 | 🟢 GREEN | 未设置 `ENTERPRISE_RAG_SSH_PASSWORD` 时连接前立即失败，不尝试网络连接 |
| LDC-S03 | 🟢 GREEN | 设置新环境变量后可使用新密码连接隔离服务器并读取健康状态 |
