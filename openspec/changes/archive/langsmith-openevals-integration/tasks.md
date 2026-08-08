# 任务清单: 接入 LangSmith + OpenEvals 能力评测监控

> 编码: UTF-8
> 每个阶段完成后运行 `python tests/tdd_all_optimizations.py` 确保管道回归通过
> 更新: 2026-07-24

---

## 阶段一：基础设施搭建

- [x] 1.1 创建 `src/monitoring.py` - LangSmith 初始化 + traceable 工厂 + 优雅降级
- [x] 1.2 修改 `requirements.txt` - 新增 `langsmith`、`openevals`
- [x] 1.3 修改 `env` - 新增 `LANGSMITH_API_KEY`、`LANGCHAIN_PROJECT`、`LANGCHAIN_ENDPOINT`
- [x] 1.4 修改 `config/agent_config.json` - 新增 `monitoring` 配置节
- [x] 1.5 验证: `python -c "from src.monitoring import traceable, is_available; print(is_available())"` 在未配置 Key 时输出 False
- [x] 1.6 运行管道回归测试，确保无影响

---

## 阶段二：Agent 核心链路追踪

- [x] 2.1 修改 `src/agent_core.py` - `ReActAgent.run()` 加 `@traceable("react-loop")`
- [x] 2.2 修改 `src/agent_core.py` - `ReActAgent.run_stream()` 加 `@traceable("react-loop-stream")`
- [x] 2.3 修改 `src/agent_core.py` - `ReActAgent._call_llm()` 加 `@traceable("llm-call")`
- [x] 2.4 修改 `src/agent_core.py` - `ReActAgent._execute_action()` 加 `@traceable("tool-execute")`
- [x] 2.5 运行 Agent 测试 (`tests/test_agent_core.py`)，确保追踪不影响原有逻辑

---

## 阶段三：检索链路追踪

- [x] 3.1 修改 `src/retrieval.py` - `VectorRetriever.search()` 加 `@traceable("vector-search")`
- [x] 3.2 修改 `src/retrieval.py` - `BM25Retriever.search()` 加 `@traceable("bm25-search")`
- [x] 3.3 修改 `src/retrieval.py` - `HybridRetriever.search()` 加 `@traceable("hybrid-search")`
- [x] 3.4 修改 `src/retrieval.py` - `RAGGenerator.query()` 加 `@traceable("rag-query")`
- [x] 3.5 修改 `src/retrieval.py` - `RAGGenerator._generate_answer()` 加 `@traceable("llm-generate")`
- [x] 3.6 运行检索回归测试，确保追踪不影响原有逻辑

---

## 阶段四：API 服务集成

- [x] 4.1 修改 `src/api_service.py` - 启动时调用 `init_langsmith()` 初始化 Client
- [x] 4.2 修改 `src/api_service.py` - `api_agent_query()` 加 `@traceable("agent-query-endpoint")`
- [x] 4.3 验证: 启动服务后调用 `/api/health`，确认监控模块不影响服务启动
- [x] 4.4 运行全量回归测试

---

## 阶段五：TDD 测试用例

- [x] 5.1 创建 `openspec/changes/langsmith-openevals-integration/specs/spec-monitoring.md` - SDD 规范
- [x] 5.2 创建 `openspec/changes/langsmith-openevals-integration/specs/tdd-monitoring.md` - TDD 测试用例
- [x] 5.3 编写 `tests/test_monitoring.py` - 监控模块独立单元测试（8 条用例）
- [x] 5.4 运行 `tests/test_monitoring.py` 验证 RED 状态正确 (8/8 passed → 全部标绿)
- [x] 5.5 开发实现后逐条验证，通过后改 GREEN（TC-MON-01~08 已通过集成验证标绿）

---

## 阶段六：OpenEvals 评测脚本

- [x] 6.1 创建 `tests/eval_datasets/retrieval_queries.json` - 检索评测数据集
- [x] 6.2 创建 `tests/eval_datasets/generation_queries.json` - 生成评测数据集（10 条用例）
- [x] 6.3 编写 `tests/eval_langsmith.py` - LangSmith 在线评测脚本
- [x] 6.4 编写 `tests/eval_openevals.py` - OpenEvals 离线评测脚本（LLM-as-Judge 三维度评分）
- [x] 6.5 验证: 运行评测脚本，确认输出评分报告（2026-07-24 完成，通过率 80%）

---

## 阶段七：Prompt 规则迭代优化

- [x] 7.1 规则5 - 单位换算（千元 ÷ 100,000 = 亿元），修复 gen-010
- [x] 7.2 规则6 - 禁止汇率换算，避免 Agent 自行折算
- [x] 7.3 规则7 - 优先人民币数据
- [x] 7.4 规则9 - 优先年报来源，年报优先于研报
- [x] 7.5 规则10 - 年报检索强化: 首次仅研报时追加检索"年度报告"关键词
- [x] 7.6 规则11 - 同源对比原则: 同源同币种计算增长率
- [x] 7.7 运行完整评测验证效果（2026-07-24，8/10 通过，gen-007/gen-008 未通过）

---

## 阶段八：文档与收尾

- [x] 8.1 更新 `CHANGELOG.md` - 记录 v5.0 变更（LangSmith + OpenEvals 接入 + Prompt 优化）
- [x] 8.2 更新 `openspec/project.md` - 演进路线 v5.0 状态更新
- [x] 8.3 更新 SDD `spec-monitoring.md` - 补充实际实现和评测结果
- [x] 8.4 更新 TDD `tdd-monitoring.md` - TC-MON 标绿，新增 TC-EVAL-01~10 评测用例
- [x] 8.5 记录 tags 打标传参方案为后续优化（_local/blog/Agent项目/后续优化想法/Tags打标传参方案.md）
- [x] 8.6 归档本变更提案到 `openspec/changes/archive/`
- [x] 8.7 全量回归测试通过 (223 passed, 5 skipped, 0 failed)
