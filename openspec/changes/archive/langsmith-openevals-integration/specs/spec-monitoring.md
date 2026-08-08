# SDD 规范: LangSmith + OpenEvals 能力评测监控

> 编码: UTF-8 | 变更: langsmith-openevals-integration | 更新: 2026-07-24

---

## 功能概述

为自研 ReAct Agent 框架接入 LangSmith 在线追踪和 OpenEvals 离线评测能力，实现生产级 LLM 应用的可观测性和质量评估。

---

## 规范 1: 监控模块 (`src/monitoring.py`)

### 功能描述
提供 LangSmith Client 初始化、`traceable` 装饰器工厂函数、环境变量读取的集中管理模块。

### 输入
- 环境变量: `LANGCHAIN_API_KEY`、`LANGCHAIN_PROJECT`、`LANGCHAIN_ENDPOINT`
- 配置文件: `config/agent_config.json` 中的 `monitoring.enabled`

### 输出
- `traceable(name)` - 装饰器工厂（可用时返回 LangSmith traceable，不可用时返回透传）
- `get_client()` - LangSmith Client 单例（不可用时返回 None）
- `is_available()` - 返回布尔值表示 LangSmith 是否可用

### 边界条件
- `langsmith` 包未安装: `traceable()` 返回透传装饰器，`is_available()` 返回 False
- `LANGCHAIN_API_KEY` 为空: 同未安装，所有函数优雅降级
- 重复调用 `get_client()`: 返回同一个单例实例

### 测试用例引用
- TC-MON-01 ~ TC-MON-08 (见 tdd-monitoring.md)

---

## 规范 2: Agent 核心链路追踪

### 功能描述
在 `ReActAgent` 的关键方法上加 `@traceable` 装饰器，实现 ReAct 推理全链路追踪。

### 追踪节点

| 方法 | trace name | 追踪数据 |
|------|-----------|---------|
| `run()` | `react-loop` | query、conversation_history、company_name、AgentResult |
| `run_stream()` | `react-loop-stream` | 同 run()，流式版本 |
| `_call_llm()` | `llm-call` | messages (摘要)、response (摘要)、model、temperature、token_usage |
| `_execute_action()` | `tool-execute` | action、action_input、observation (摘要) |

### 边界条件
- LangSmith 不可用时: `@traceable` 等价于无装饰器，方法行为完全不变
- LLM 调用失败: trace 记录 error 信息，不影响异常传播
- 流式模式: `run_stream()` 的 trace 仅记录开始和结束，不追踪每个 yield

---

## 规范 3: 检索链路追踪

### 功能描述
在检索模块的关键方法上加 `@traceable` 装饰器，追踪从检索到生成的完整数据链路。

### 追踪节点

| 类/方法 | trace name | 追踪数据 |
|---------|-----------|---------|
| `VectorRetriever.search()` | `vector-search` | query、top_k、结果数量、分数分布 |
| `BM25Retriever.search()` | `bm25-search` | query、top_k、结果数量、分数分布 |
| `HybridRetriever.search()` | `hybrid-search` | query、company_name、intent、结果数量、置信度 |
| `RAGGenerator.query()` | `rag-query` | query、company_name、intent、answer 长度、sources 数量 |
| `RAGGenerator._generate_answer()` | `llm-generate` | prompt 长度、answer 长度、model、token_usage |

### 边界条件
- 检索无结果: trace 记录 `retrieved_count=0`，不报错
- gte-rerank API 调用失败: trace 记录 fallback 模式标记
- 多个公司检索: trace 记录 `companies=[...]` 列表

---

## 规范 4: API 服务集成

### 功能描述
在 `api_service.py` 启动时初始化 LangSmith Client，在 Agent 查询端点加追踪。

### 功能点
- `lifespan` 启动阶段调用 `get_client()` 初始化 LangSmith Client
- `api_agent_query()` 加 `@traceable("agent-query-endpoint")`
- 初始化失败不影响服务启动

### 边界条件
- LangSmith 初始化失败: 仅记录 WARNING 日志，服务正常启动
- 首次请求时客户端未初始化: `get_client()` 懒加载

---

## 规范 5: 优雅降级

### 功能描述
所有 LangSmith 功能必须遵循"静默降级"原则：未安装包或未配置 API Key 时，系统行为完全不变。

### 降级场景
1. `langsmith` 包未安装: `traceable()` 返回透传，不报错
2. `LANGCHAIN_API_KEY` 为空: 不初始化 Client，不报错
3. LangSmith API 调用失败: trace 上报失败静默忽略，不抛异常
4. `openevals` 包未安装: 评测脚本输出提示并正常退出

### 验证方式
- 删除 `langsmith` 包后运行 Agent 测试，所有测试通过
- 清空 `LANGCHAIN_API_KEY` 后启动 API 服务，`/api/health` 正常响应

---

## 规范 6: OpenEvals 离线评测

### 功能描述
提供独立的离线评测脚本，基于 OpenEvals 框架评估检索质量和生成质量。

### 评测维度

#### 检索评测 (`tests/eval_retrieval.py`)
- ContextRelevancy: 检索结果与 query 的相关性
- ContextPrecision: 检索结果的精确率
- HitRate@K: Top-K 命中率

#### 生成评测 (`tests/eval_generation.py`)
- Correctness: 答案与参考答案的语义一致性
- Faithfulness: 答案对来源文档的忠实度
- AnswerRelevancy: 答案与问题的相关性

### 数据集格式
评测数据由 `tests/eval_datasets/*.json` 文件提供，每条记录包含 query、expected_output、metadata。

### 边界条件
- 数据集文件不存在: 输出友好提示并退出
- `openevals` 包未安装: 输出提示并退出
- 评测过程中 LLM 调用失败: 记录错误，继续评测下一条

### 实际实现

实际创建的评测脚本与规范略有调整（基于 OpenEvals 框架适配）:

| 文件 | 说明 |
|------|------|
| tests/eval_langsmith.py | LangSmith 在线评测脚本，连接评测数据集到 LangSmith 平台 |
| tests/eval_openevals.py | OpenEvals 离线评测脚本，LLM-as-Judge 三维度评分 |
| tests/eval_datasets/retrieval_queries.json | 检索评测数据集 |
| tests/eval_datasets/generation_queries.json | 生成评测数据集（10 条用例 gen-001 ~ gen-010）|

### 评测结果摘要 (2026-07-24)

| 指标 | 值 |
|------|-----|
| 总用例数 | 10 |
| 通过数 | 8 (通过率 80%) |
| 平均正确性 (Correctness) | 0.77 |
| 平均忠实度 (Groundedness) | 0.90 |
| 平均相关性 (Relevance) | 0.95 |
| 未通过用例 | gen-007 (correctness=0.2), gen-008 (correctness=0.5) |

---

## 规范 7: Prompt 规则迭代优化

### 功能描述

基于 OpenEvals 评测结果，针对失败用例迭代优化 Agent 的 System Prompt 规则，形成"评测 -> 分析 -> 优化 -> 再评测"的闭环。

### Prompt 规则演进

| 版本 | 规则 | 内容 | 影响用例 | 效果 |
|------|------|------|----------|------|
| v5.0-rc1 | 规则5 | 单位换算: 千元 ÷ 100,000 = 亿元 | gen-010 | 修复 903.0亿元 → 90.3亿元 |
| v5.0-rc1 | 规则6 | 禁止汇率换算 | gen-007 | 避免 Agent 自行汇率折算 |
| v5.0-rc1 | 规则7 | 优先人民币数据 | gen-007 | 优先人民币列报 |
| v5.0-rc1 | 规则9 | 优先年报来源: 年报优先于研报 | gen-007 | 部分改善，检索层面仍返回研报 |
| v5.0-rc2 | 规则10 | 年报检索强化: 首次仅研报时追加检索"年度报告"关键词 | gen-007 | 2024年数据成功检索到年报 |
| v5.0-rc2 | 规则11 | 同源对比原则: 同源同币种计算增长率 | gen-007 | 未能完全阻止2023年数据混用研报 |

### 迭代结论

- Prompt 规则优化对"数据来源选择"类问题有部分效果（规则10 成功让 Agent 追加检索年报）
- 但仅靠 Prompt 规则无法彻底解决检索层面的数据混杂问题（规则11 未能阻止混用研报美元数据）
- 后续需在检索策略层面实施 tags 打标传参方案，确保年报数据优先返回

### 后续优化方向

- tags 打标传参方案: 在 text_splitter.py 阶段打文档类型标签，检索时按标签加权（详见 _local/blog/Agent项目/后续优化想法/Tags打标传参方案.md）
- gen-008 多步检索: 用户可在前端选择 5/10 步，或优化多公司对比查询的检索策略
