# 变更日志

> 格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)
> 版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)

---

## [2.1.0] - 2026-06-21

### 新增

- **ReAct 空结果安全阀**：三层防护机制防止 LLM 在无效检索上陷入死循环
  - `_is_empty_result()` 空结果检测：8 个关键词标记 + 2 个失败前缀，O(n) 字符串匹配
  - `empty_result_count` 计数器：连续空结果累加，有有效结果则退回，>=2 次输出 WARNING
  - `forced_stop` + `_generate_forced_answer()`：max_steps 耗尽时给出非空降级答案
- **日志埋点**：空结果判定 INFO 日志、计数器重置 INFO 日志，全链路可观测
- **纯 Mock 单元测试**：`tests/test_agent_mock_boundary.py`，覆盖 13 个标记判定、计数器全状态、NameError 修复验证、日志输出验证

### 修复

- **隐藏 bug**: `_generate_forced_answer()` 原代码引用 `run()` 局部变量 `reasoning_chain` 导致 `NameError`，改为显式传参
- **文档事实错误**: 引流汇总中 `max_steps=10` 修正为 `5`，`agent_core.py 200 多行` 修正为 `约 500 行`

### 文档

- 博客文章"坑 3"精简为与坑 1/坑 2 对齐的 8 行列表格式
- 效果验证表新增"空结果强制终止"行
- 经验总结新增第 6 条"罕见路径必须测试"

---

## [2.0.0] - 2026-06-XX

### 新增

- Agent 模式：ReAct 循环、工具调用、自我反思、任务规划
- 五个工具：retrieve、calculator、compare、chart、verify
- 三层记忆系统：工作记忆、情景记忆、长期记忆
- API 服务：`/api/agent/query` 端点

### 保留

- 管道模式（RAG Pipeline）向后兼容
