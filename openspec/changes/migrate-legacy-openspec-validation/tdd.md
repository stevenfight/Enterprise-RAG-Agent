# TDD：OpenSpec 历史迁移

| 用例 | 初始状态 | 期望 |
| --- | --- | --- |
| OSM-S01 | GREEN | 四个纯工具/部署变更在严格 OpenSpec 校验下以 `skip_specs` 合法通过：`deploy-isolated-staging-server`、`harden-local-deploy-credentials`、`openspec-lifecycle-and-ci-quality-gate`、`prepare-isolated-staging-compose`。 |
| OSM-S02 | GREEN | 全库校验仅保留 7 个真实产品行为变更：CORS 允许来源、Agent SSE 鉴权、CORS 预检、跨源 SSE 会话、RAG 单位换算、研究 Cookie、v7 研究 Agent。 |
