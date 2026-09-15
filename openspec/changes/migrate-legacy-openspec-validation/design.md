# 设计

1. 仅当变更范围是部署编排、凭据注入、CI 或 OpenSpec 生命周期且不改变产品需求时，添加 `schema: spec-driven` 和 `skip_specs: true`。
2. CORS、SSE、鉴权、金额换算、Cookie 与 v7 研究能力均属于产品行为，不在本轮添加 `skip_specs`，后续必须补 delta 规格。
3. 每次修改后先验证单个变更，再运行全库严格校验，记录剩余失败项而不掩盖它们。
