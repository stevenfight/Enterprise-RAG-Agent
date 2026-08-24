# 变更提案: ReAct 空结果安全阀

> 编码: UTF-8
> 状态: 已完成

---

## 1. 变更背景

ReAct Agent 在运行时，当检索工具返回空结果或执行失败（如查询域外公司），LLM 会持续调整 query 重试检索，导致：

- 无效循环消耗 API token
- max_steps 耗尽后无产出，用户体验差
- 隐藏 bug 长期未被发现（`_generate_forced_answer` 引用 `run()` 局部变量导致 `NameError`）

本变更在 ReAct 主循环中增加三层安全阀，确保即使 LLM 陷入无效循环，也能在可控步数内给出降级答案。

## 2. 变更目标

| 目标 | 衡量标准 |
|------|----------|
| 检测空结果 | 13 种空标记全部正确识别，零误报 |
| 计数器防抖动 | 有有效结果时计数器退回，不惩罚正常波动 |
| 强制降级 | max_steps 耗尽时给出非空降级答案，success=True, forced_stop=True |
| 修复隐藏 bug | `_generate_forced_answer` 不再引用外部局部变量 |
| 日志可观测 | 空结果判定、计数器状态、强制降级全链路 INFO 级日志 |

## 3. 变更范围

| 项目 | 内容 | 涉及文件 |
|------|------|----------|
| 空结果检测 | `_is_empty_result()` 新增 `[工具执行失败]` 前缀 + `未检索到相关数据` 等标记 | `src/agent_core.py` |
| 空结果计数器 | `empty_result_count` 累加/重置逻辑 + WARNING 日志 | `src/agent_core.py` |
| 强制降级答案 | `_generate_forced_answer()` 显式传参 `reasoning_chain` | `src/agent_core.py` |
| 日志埋点 | 空结果判定 INFO 日志、计数器重置 INFO 日志 | `src/agent_core.py` |
| 纯 Mock 测试 | 13 个标记覆盖、计数器全状态、NameError 修复验证、日志埋点 | `tests/test_agent_mock_boundary.py` |
| 端到端测试 | 真实 LLM 空结果、合成空结果 monkey-patch、降级答案非空 | `tests/test_agent_boundary_verify.py` |
| 文档更新 | 博客文章"坑 3"精简版 + 引流汇总修正 | `_local/blog/Agent项目/01-入门系列/02-ReAct模式实战.md` |

## 4. 影响

- 新增文件: `tests/test_agent_mock_boundary.py`
- 修改文件: `src/agent_core.py`, `tests/test_agent_boundary_verify.py`
- 无破坏性变更：向后兼容，所有现有测试通过
