# OpenSpec 批量删除与发布集生命周期审计清单

审计日期：2026-09-23

## 总结

- 初始删除范围：20 个变更目录、102 个文件。
- 审计结论：没有任何目录具备“可直接删除”的证据；所有文件均已恢复至 HEAD。
- 恢复后：20/20 个目录通过 `openspec validate <change> --strict`；OpenSpec 删除清单为空。
- 唯一清理项：`openspec-lifecycle-and-ci-quality-gate/specs/tdd-openspec-lifecycle-and-ci.md` 是未跟踪、与 `legacy-specs/tdd-openspec-lifecycle-and-ci.md` SHA-1 完全一致的错位副本，已移除。

## 必须保留：当前活动规格与发布门禁

| 目录 | 依据 | 动作 |
| --- | --- | --- |
| `trusted-financial-research-agent-v7` | 删除 7 份 delta 后严格校验失败；评测数据还引用其设计文件 | 恢复全部 delta，保留为活动变更 |
| `openspec-lifecycle-and-ci-quality-gate` | README 指定为当前质量门禁；任务仍含未完成的 GitHub 保护和受控部署项 | 恢复 metadata 与 legacy TDD，保留为活动变更 |

## 必须保留：安全、会话、部署与来源审计证据

| 目录组 | 目录 | 依据 | 动作 |
| --- | --- | --- | --- |
| F2 来源审计 | `add-f2-binding-manifest`、`add-f2-source-evidence-audit`、`add-f2-source-integrity-binding`、`add-f2-staging-asset-assembly` | 当前 `0c3adfe` 已恢复的来源审计兼容能力依赖这些历史验收边界；仓库无归档副本 | 恢复并保留 |
| 会话与跨域安全 | `configure-cors-allowed-origins`、`fix-cors-preflight-authentication`、`fix-cross-origin-agent-sse-session`、`fix-agent-stream-authentication`、`harden-research-session-cookie-config` | 分别对应 CORS、预检、SSE Cookie、SSE 鉴权与 Cookie Secure 契约；无等价归档 | 恢复并保留 |
| 部署安全 | `prepare-isolated-staging-compose`、`deploy-isolated-staging-server`、`harden-local-deploy-credentials` | 是隔离 staging、正式栈隔离和 SSH 凭据轮换的唯一实施记录 | 恢复并保留 |

## 恢复后待单独归档评审：已完成但未归档的历史变更

| 目录 | 当前事实 | 本轮动作 |
| --- | --- | --- |
| `fix-conflict-refusal-scoring`、`fix-rag-unit-conversion`、`make-f1-tests-reproducible` | 任务已完成且关联实现已提交；当前没有同名 archive 副本 | 恢复；后续以 `git mv` 归档，不直接删除 |
| `migrate-legacy-openspec-validation`、`migrate-legacy-product-spec-deltas`、`migrate-v7-capability-spec-deltas` | 记录旧 OpenSpec 向当前格式迁移的验证依据；没有归档副本 | 恢复；后续按迁移闭环单独归档 |

## 后续归档规则

1. 先确认目录任务全部完成，且不存在 README、评测数据、交接、代码或测试反向引用。
2. 使用 `git mv` 移入 `openspec/changes/archive/`，保留完整历史而非删除。
3. 为每个归档组单独运行 `openspec validate --strict`、Git 状态和引用扫描；不得与产品代码变更混合提交。
