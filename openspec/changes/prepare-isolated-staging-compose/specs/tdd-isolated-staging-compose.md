# TDD：隔离服务器测试 Compose 配置

| 编号 | 状态 | 验证内容 | 预期结果 |
|---|---|---|---|
| S-C01 | GREEN | Compose 文件存在且可解析 | 使用测试模板可成功执行 `docker compose config`。 |
| S-C02 | GREEN | 服务隔离 | 使用 staging 容器/网络/回环端口，且不挂载正式数据或宿主机 config。 |
| S-C03 | GREEN | 配置安全 | `.env.staging` 被忽略，模板不含真实密钥并声明 HTTP Cookie 边界。 |
| S-C04 | GREEN | 共机资源边界 | 服务禁用自动重启并设置 CPU、内存限制。 |

## 执行记录

| 日期 | 用例 | 结果 | 证据 |
|---|---|---|---|
| 2026-09-12 | S-C01 | RED | `docker compose -f docker-compose.staging.yml config` 报文件不存在。 |
| 2026-09-12 | S-C01 至 S-C04 | GREEN | `tests/test_staging_compose_contract.py`：2 passed；以 `STAGING_ENV_FILE=staging.env.example` 运行 `docker compose -f docker-compose.staging.yml config` 成功。 |
