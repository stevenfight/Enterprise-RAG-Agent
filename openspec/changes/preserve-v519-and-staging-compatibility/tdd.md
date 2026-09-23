# TDD 台账

| 编号 | 初始状态 | 契约 | 验证证据 |
| --- | --- | --- | --- |
| P-T1 | GREEN | v5.19 指纹清单及其合约测试必须存在，且不声称缺失运行时资料已冻结 | `python -m pytest -q tests/test_v519_compatibility_manifest.py --disable-warnings --tb=short`：7 passed；`git diff --exit-code HEAD --` 目标清单和测试无差异 |
| P-T2 | GREEN | staging Compose 与环境模板必须仅提供 localhost 隔离配置和占位值 | `docker compose -f docker-compose.staging.yml config --no-interpolate` 解析通过，端口仅为 `127.0.0.1:18000/18081`；真实 Key/密码扫描为空 |
| P-T3 | GREEN | 恢复文件不改变正式 Compose、服务器或真实凭据 | 仅恢复工作区中曾删除的 HEAD 文件；未运行部署命令、未修改正式 Compose、服务器或凭据 |
