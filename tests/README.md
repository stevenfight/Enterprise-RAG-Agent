# 测试索引

---

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
| **合计** | | **40** | **全部 GREEN** |

详细用例清单见: `openspec/changes/rag-to-agent/specs/test-cases.md`

---

## 运行方式

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
```
