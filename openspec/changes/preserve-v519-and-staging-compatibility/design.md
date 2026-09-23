# 设计

1. 逐字恢复 `v5.19-compatibility-manifest.json`，它只包含指纹与公开兼容元数据，不包含凭据或业务正文。
2. 逐字恢复 `docker-compose.staging.yml` 与 `staging.env.example`，二者只定义 localhost 隔离服务、资源上限和占位环境变量；不得替换正式 Compose。
3. 恢复 v5.19 清单合约测试，并在含 Git 元数据的当前工作树运行；该测试只验证已保存的历史指纹，不把当前运行时数据伪装成 v5.19 基线。
4. 本次提交不包含其他 OpenSpec 删除、生产部署文件或服务器操作。
