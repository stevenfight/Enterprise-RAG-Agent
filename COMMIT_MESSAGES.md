# 提交信息记录 (Commit Messages)

> 本文件用于记录项目每次提交的 commit message，便于追溯代码变化历史。
> 提交时从下方"待提交"区块选取对应的 message 使用；每次提交完成后，在"已提交"区块追加对应记录。

---

## 待提交（2026-08-14）

### 本次变更摘要

多 Agent 升级阶段九至十五（step09~step15），加上 step07/step08 测试修复。

- 后端：`src/` 8 个文件改动（agent_core / api_service / text_splitter / retrieval / ingestion / delegate_tool / retrieve_tool）
- 配置：`config/agent_prompts.yaml`
- 前端：`frontend/src/` 5 个文件改动 + 新增 `utils/agentEvent.ts` 及其测试
- 测试：`tests/run_all.py` 纳入 step09~15，新增 6 个测试文件 + 1 个 Mock 演示脚本
- 文档：`openspec/changes/` 新增 step09~15 共 7 个变更目录

验证结果：后端 `run_all.py --skip-llm` 318 PASS / 0 FAIL；前端 `vitest run` 62/62 全绿。

### 推荐 commit message（单次提交）

```
feat: 多Agent升级阶段九~十五 + step07/08测试修复

涵盖 7 个变更提案（step09~15）与回归测试修复：

- step09: 多Agent启用/运行验证，补测3项历史修复(嵌套JSON解析/空正文回退/单位换算)
- step10: 前端多Agent流式可视化(agentEvent reducer纯函数 + Worker步骤展示)
- step11: 回答来源标注具体页码(prompt规则强化)
- step12: Worker步骤事件接入SSE(ReActAgent.run接入step_callback)
- step13: 单/多Agent SSE流式一致性(统一answer_chunk, 清理workers_done)
- step14: 数据来源页码映射修复(markdown路径多跳一层)
- step15: 文档类型标签打标与检索加权(tags + 年报三层防线)
- 测试: step07/08修复sys.path/mock字段/patch目标, 纳入run_all.py回归

验证: 后端318 PASS/0 FAIL, 前端vitest 62/62
```

### 分批 commit message（可选）

> 注意：`agent_core.py`、`api_service.py`、`text_splitter.py`、`config/agent_prompts.yaml` 被多个 step 共享修改，分批需 `git add -p` 做 hunk 级暂存。

```text
# 1. 测试修复（独立，最先提交）
fix: 修复step07/08测试(sys.path缺失/mock字段不全/patch目标错误)

# 2. step09
test: 多Agent启用运行验证 + 3项历史修复回归补测(25项)

# 3. step10
feat: 前端多Agent流式可视化(agentEvent reducer + Worker步骤展示)

# 4. step11
feat: 多Agent回答来源标注具体页码

# 5. step12
feat: Worker步骤事件接入SSE(ReActAgent.run接入step_callback)

# 6. step13
refactor: 单/多Agent SSE流式一致性(统一answer_chunk, 删除workers_done)

# 7. step14
fix: 数据来源页码映射修复(markdown路径多跳一层)

# 8. step15
feat: 文档类型标签打标与检索加权(tags + 年报三层防线)
```

---

## 已提交

- 2026-08-14 `57e4b81` ci: 新增GitHub Actions自动构建Docker镜像流水线
- 2026-08-14 `66e4d6f` fix: Dockerfile.backend 添加 ca-certificates 解决SSL证书验证问题
- 2026-08-14 `51b0941` feat: 多Agent升级阶段九~十五 + step07/08测试修复
