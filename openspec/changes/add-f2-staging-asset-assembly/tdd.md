# TDD：隔离 staging 评测资产装配

## RED

- RED-01：本地资产哈希清单缺失任一声明文件时不能进入上传。
- RED-02：服务器任一资产哈希不一致时装配不得就绪。
- RED-03：候选 metadata 为 `release_ready=false` 时只允许预验收，不得自动发布。

## GREEN 目标

- 装配前后文件哈希、PDF 数量和候选 metadata 状态一致。
- staging Compose 使用独立端口和数据目录，正式容器状态不变。
- 来源完整性绑定和数据集绑定失败时返回非零并保留报告。
