# 任务清单: 多 Agent 升级 - 阶段五 调优（第一轮）

> 编码: UTF-8
> 日期: 2026-08-07
> 状态: 已完成（代码实施 + 12/12 TDD 全部通过）

---

## 步骤 5.1：工具描述嵌套参数展示增强

- [x] `ToolRegistry.get_tool_descriptions()` 新增私有辅助函数 `_format_param_desc()` 递归展示 items.properties
- [x] delegate 工具描述包含 `agent`/`task` 字段说明（LLM 可见）
- [x] retrieve/calculator 等无嵌套参数工具描述格式不变（回归）
- [x] 验证：TDD 工具描述 4 项全部转绿

## 步骤 5.2：orchestrator 提示词补充 delegate 调用示例

- [x] `config/agent_prompts.yaml` orchestrator 节新增「调用示例」小节
- [x] 示例含单任务 tasks 数组格式
- [x] 示例含多任务并行 tasks 数组格式（company_name 字段）
- [x] 验证：TDD orchestrator prompt 2 项全部转绿

## 步骤 5.3：DelegateTool 并行批次统计

- [x] `DelegateTool.run()` 返回 data 增加 `parallel_batch_count` 字段
- [x] `DelegateTool.run()` 返回 data 增加 `estimated_serial_ms` 字段（各 worker 耗时之和）
- [x] 单任务批次 parallel_batch_count=1
- [x] 多任务并行批次 parallel_batch_count=1（同批并行）
- [x] 检索+分析混合任务 parallel_batch_count=2（两批）
- [x] 验证：TDD delegate 统计 3 项全部转绿

## 步骤 5.4：api_service 成本观测日志 + 路由回归

- [x] `_handle_multi_agent_query()` 日志增加 `total_tokens` 字段
- [x] 日志包含 `workers` 数量（shared_memory.agent_outputs）
- [x] 验证：TDD api_service 日志 2 项全部转绿
- [x] 验证：TDD 简单查询路由回归 1 项转绿

## 验证（全部步骤完成后）

- [x] 运行新增 12 项 TDD 测试全部通过
- [x] 运行阶段一~四全部 TDD 测试通过（回归，206 passed + 5 skipped，零回归）
- [x] 手动 curl POST `{"mode":"multi","query":"中国移动2024年营业收入是多少"}` 验证委派任务非空
- [x] 手动 curl GET SSE `mode=multi` 验证事件完整推送

---
## 实施记录

| 日期 | 步骤 | 文件 | 操作 | 说明 |
|------|------|------|:--:|------|
| 2026-08-07 | 5.1 | `src/tools/__init__.py` | 修改 | 新增 _format_param_desc 递归展示嵌套参数 |
| 2026-08-07 | 5.2 | `config/agent_prompts.yaml` | 修改 | orchestrator 节新增 delegate 调用示例 |
| 2026-08-07 | 5.3 | `src/tools/delegate_tool.py` | 修改 | run() 返回 data 增加 parallel_batch_count/estimated_serial_ms |
| 2026-08-07 | 5.4 | `src/api_service.py` | 修改 | multi_agent 日志增加 total_tokens |
| 2026-08-07 | TDD | `tests/tdd_multi_agent_step08.py` | 新增 | 12 项 TDD 测试全部通过 |
| 2026-08-07 | 回归 | 阶段零~四+五 8 个 TDD 文件 | 验证 | 206 passed + 5 skipped，零回归 |
| 2026-08-08 | 手动 | curl POST mode=multi | 验证 | HTTP 200，DataAgent 正确返回"中国移动2024年营业收入为人民币10,408亿元"，parallel_batch_count=1, estimated_serial_ms=5051 |
| 2026-08-08 | 手动 | curl GET SSE mode=multi | 验证 | SSE 连接成功，收到 connected/orchestrator_start/delegating 事件，5 个 Worker Agent 已注册 |
