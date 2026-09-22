# 测试索引

---

## 当前人工复核快照（2026-09-11）

- `gen-001`～`gen-010`、`ret-001`～`ret-010` 和 `full-v7-001`～`full-v7-050` 已完成 A-GATE-2 人工复核，共 **70/70 approved**；A-GATE-2 人工复核范围已闭环。
- 当前完整候选集 100 条的 `review_status` 均为 `verified`，但完整集仍保持 `status=draft`、复核包聚合状态仍为 `pending_review`、`release_ready=false`；这是发布前置证据和 A-GATE-2 正式收口尚未完成的门禁状态，不表示仍有未签核候选。
- 该快照优先于本文后续历史段落中的旧进度数字；每条必须先由用户明确确认，再同步候选集、复核包和追加式签核台账。

## TDD 红绿标记规则

### 规则说明

本项目遵循 **SDD (规范驱动开发) + TDD (测试驱动开发)** 流程：

1. **SDD 写 spec** → 在 `openspec/changes/rag-to-agent/specs/` 中定义各模块规格
2. **TDD 写测试** → 对照 spec 编写测试文件，初始全部标记为 **RED** (模块未实现)
3. **开发实现模块** → 逐阶段开发 src 模块代码
4. **变绿** → 每项测试通过后，将对应测试文件中的 `TEST_STATUS` 条目从 `"RED"` 改为 `"GREEN"`

### 标记格式

每个 TDD 测试文件顶部包含 `TEST_STATUS` 字典：

```python
TEST_STATUS = {
    "TC-A01": "RED",    # test_single_step_retrieve
    "TC-A02": "RED",    # test_multi_step_comparison
    ...
}
```

### 运行输出

| 标记 | 含义 | 显示颜色 |
|------|------|:---:|
| `[RED]` | 模块未实现，预期失败 | RED |
| `[GREEN]` | 模块已实现，测试通过 | GREEN |
| `[FAIL]` | 标记为 GREEN 但测试失败 | RED |
| `[WARN]` | 标记为 RED 但测试已通过，提醒更新标记 | YELLOW |

### 开发流程

```
阶段一开发 → 运行 test_agent_tools.py
  → 如果某测试通过 → 修改 TEST_STATUS["TC-Txx"] = "GREEN"
  → 继续下一个测试

全部 GREEN → 本阶段完成 → 进入下一阶段
```

---

## 测试分类

### RAG 回归测试（管道模式）

| 文件 | 说明 | 用途 |
|------|------|------|
| `integration_test.py` | 端到端 RAG 流程验证 | 每次修改后运行，确保管道正常 |
| `tdd_all_optimizations.py` | 全量 TDD 回归 | 每阶段完成后运行，全面检查 |
| `test_document_integration.py` | 文档接入自动化测试 | 新增/修改文档后运行 |

### Agent 专项测试

| 文件 | 对应模块 | 用例数 | 当前状态 |
|------|---------|:-----:|:------:|
| `test_agent_core.py` | agent_core.py (ReAct 循环) | 10 | 10 GREEN / 0 RED |
| `test_agent_tools.py` | tools/* (5个工具) | 12 | 12 GREEN / 0 RED |
| `test_agent_memory.py` | agent_memory.py (三层记忆) | 7 | 7 GREEN / 0 RED |
| `test_reflector.py` | reflector.py (反思验证) | 11 | 11 GREEN / 0 RED |
| **合计（后端）** | | **40** | **全部 GREEN** |

### 前端组件测试 (Phase 2 新增)

> 前端测试位于 `frontend/src/components/*/__tests__/`，使用 Vitest + React Testing Library + jsdom。

| 文件 | 对应模块 | 用例数 | 当前状态 |
|------|---------|:-----:|:------:|
| `charts/__tests__/ChartContainer.test.tsx` | ChartContainer (ECharts 交互图表) | 22 | 22 GREEN |
| `chat/__tests__/ThoughtChainDrawer.test.tsx` | ThoughtChainDrawer (思维链抽屉) | 17 | 17 GREEN |
| `dag/__tests__/DagFlow.test.tsx` | DagFlow (DAG 流程图) | 8 | 8 GREEN |
| **合计（前端）** | | **47** | **全部 GREEN** |

详细用例清单见: `openspec/changes/rag-to-agent/specs/test-cases.md`

---

## 运行方式

### v7 金融 Agent 评测平面

v7 评测 CLI 默认运行无密钥的 `offline-core`，使用版本化固定输出、来源和工具轨迹夹具；它验证评测器与质量门禁，不代表在线模型质量。PR 上下文应显式使用 `--execution-context pr`：

```bash
python -m src.evaluation.cli --dataset evals/datasets/core.jsonl --fixtures evals/fixtures/offline-core.json --output-dir .tmp/evaluation-core --mode offline-core --execution-context pr
```

A-GATE-1 使用已完成人工签核的 30 条 v7 核心集和独立固定回放夹具；该命令只验证 Runner、评估器和质量门禁，不调用外部 Provider：

```bash
python -m src.evaluation.cli --dataset evals/datasets/core-v7-candidate.jsonl --fixtures evals/fixtures/offline-core-v7.json --output-dir .tmp/evaluation-v7-core --mode offline-core --execution-context pr
```

`local-full` 必须显式使用 `--execution-context local`，并同时提供代码、模型、提示词、索引和数据集五项版本来源。缺少任一项时命令在读取数据集和调用 Provider 前直接失败；这能保证本地候选报告可追溯，但不等于已得到真实 v5.19 baseline。`release-full` 必须显式使用 `--execution-context release`。执行上下文不匹配时命令直接失败，CLI 不读取密钥，也不把模式静默降级：

```bash
python -m src.evaluation.cli --dataset <完整集.jsonl> --fixtures <固定输出.json> --output-dir .tmp/evaluation-local --mode local-full --execution-context local --code-sha <git-sha> --model-id <model-id> --prompt-version <prompt-version> --index-version <index-version> --dataset-version <dataset-version>
python -m src.evaluation.cli --dataset <已签核完整集.jsonl> --fixtures <受控输出.json> --output-dir .tmp/evaluation-release --mode release-full --execution-context release
```

每次 CLI 报告的 `metadata.input_sha256` 会记录实际指定的数据集、固定输出夹具和阈值文件的 SHA-256，可据此核对运行输入是否一致；它不能证明样本已经人工签核，也不能替代真实 Provider 或批准的 v5.19 baseline。

报告的 `metadata.quality_gate_thresholds` 同时记录本次实际用于门禁判定的完整阈值；若传入 `--minimum-pass-rate`，记录的是覆盖后的值。它与阈值文件哈希共同用于复现退出码，不改变任何发布准入条件。

报告的 `metadata.python_runtime` 仅记录 Python 实现名和版本，用于解释本地解释器差异；不写入机器路径、用户、环境变量或依赖清单。

真实基线前可先运行只读就绪检查。该命令只读取数据集并写出覆盖、审核计数、未审核 ID 与 blocker；未就绪时返回 1，不读取夹具、不调用 Provider、不会生成评测结果：

```bash
python -m src.evaluation.cli --dataset evals/datasets/full-v7-candidate.jsonl --baseline-readiness-output .tmp/baseline-readiness.json
```

常规评测可额外启用旧来源审计接口：`--source-root` 检查来源文件可定位性，`--source-inventory` 核对 SHA-256、文件大小和物理页数，`--source-binding-manifest` 核对数据集与来源清单绑定。三者均只读；任一已启用审计未就绪时，常规评测返回非零。基线就绪检查不替代这些来源审计：

```bash
python -m src.evaluation.cli --dataset evals/datasets/core.jsonl --fixtures evals/fixtures/offline-core.json --output-dir .tmp/evaluation-source-audit --source-root data/stock_data --source-inventory data/stock_data/pdf_source_inventory.json --source-binding-manifest evals/datasets/core-source-binding.manifest.json
```

`release-full` 只有在核心集人工签核、完整集覆盖、批准基线和受控 provider/Secrets 均准备完成后才可作为发布评测使用；当前 A3.5 只完成入口边界前置，真实 provider、Secrets、完整集和发布工作流仍未完成。阈值默认读取 `evals/config/thresholds.yaml`，可用 `--thresholds` 指定已校验配置。

 A1.7 完整候选集位于 `evals/datasets/full-v7-candidate.jsonl`，当前共 100 条。其元数据位于 `evals/datasets/full-v7-candidate.metadata.json`：30 条核心样本、20 条历史迁移样本和 50 条本轮新增候选；`full-v7-041`～`full-v7-050` 的最后 10 条阶段性 draft 已全部完成人工签核，当前 100 条 `review_status` 均为 `verified`。完整集的数量、分类/公司/期间覆盖、来源文件登记和物理页范围可运行：

```bash
python -m pytest tests/test_full_evaluation_dataset.py -q --disable-warnings --tb=short
```

该测试不等同于 A-GATE-2；它不替代逐条摘录、期间/来源口径、标准答案和容差签核。当前 100 条均已完成来源复核并提升为 `verified`，但 A-GATE-2 仍需按正式发布门禁核对整体证据和审批边界。

A-GATE-2 人工复核包位于 `evals/datasets/full-v7-candidate.review.jsonl`，共 70 条，对应完整集的人工复核范围；元数据位于 `evals/datasets/full-v7-candidate.review.metadata.json`。当前 70 条均为 `verified`/`approved`，且追加式台账已有 70 条 `approved` 记录。复核时仍需确认 document、page、period_and_source_caliber、excerpt、answer、tolerance、tools 七项；复核包聚合状态仍为 `pending_review`，不能把单行批准直接当成整体发布就绪。定向验证命令：

```bash
python -m pytest tests/test_full_evaluation_dataset.py -q --disable-warnings --tb=short
```

该命令当前为 **6 passed**，证明复核范围、已批准行/待审核行、来源定位边界和进度元数据一致，不代表 A-GATE-2 已关闭。

A-GATE-2 的追加式签核校验位于 `src/evaluation/manual_signoff.py`，对应测试为 `tests/test_evaluation_manual_signoff.py`。它只在用户给出明确结论后追加记录，禁止重复 case ID、版本不匹配、未知 case、`pending` 决策和缺少七项核对结果；不会自动修改完整候选集状态。定向命令：

```bash
python -m pytest tests/test_evaluation_manual_signoff.py -q --disable-warnings --tb=short
```

当前为 **14 passed**；实际台账已完成 `gen-001`～`gen-010`、`ret-001`～`ret-010` 和 `full-v7-001`～`full-v7-050` 共 **70/70 approved**。完整候选集 100 条均为 `verified`；这表示数据集人工复核范围已闭环，不表示 `release_ready=false` 的整体发布门禁已关闭。

```bash
# 全量回归（开发前基线检查）
python tests/tdd_all_optimizations.py

# Agent 专项测试（逐个运行）
python tests/test_agent_tools.py      # 12 用例，当前: 全部 GREEN
python tests/test_agent_core.py       # 10 用例，当前: 全部 GREEN
python tests/test_agent_memory.py     # 7 用例，当前: 全部 GREEN
python tests/test_reflector.py        # 11 用例，当前: 全部 GREEN

# 一键运行所有 Agent 测试 (Windows PowerShell)
python tests/test_agent_tools.py; python tests/test_agent_core.py; python tests/test_agent_memory.py; python tests/test_reflector.py

# 前端组件测试
cd frontend && npm test               # 47 用例，当前: 全部 GREEN
cd frontend && npm run test:watch     # 监视模式
```
