# 变更提案: 接入 LangSmith + OpenEvals 能力评测监控

> 编码: UTF-8
> 状态: 已完成

---

## 1. 变更背景

当前系统具备本地单元测试和集成测试（`tests/` 目录下 30+ 测试文件），覆盖 Agent 推理、工具调用、检索管道、记忆系统等功能。但缺乏生产级在线监控和评估能力：

- **无 LLM 调用追踪**: 每次 LLM 请求的 Prompt/Response/Token 用量无结构化记录
- **无检索质量评估**: 混合检索的召回率、精确率无自动化评估
- **无答案质量评测**: RAG 生成的答案缺乏标准化评测（正确性、忠实度、相关性）
- **无可视化监控面板**: 无集中式 Dashboard 观察系统运行状态和趋势
- **测试结果分散**: 本地 TDD 测试结果需手动运行脚本查看，无聚合分析

LangSmith 和 OpenEvals 是 LangChain 团队出品的框架无关工具，不依赖 LangChain 框架即可使用。本项目使用自研 ReAct Agent 框架（不引入 LangChain），通过 `@traceable` 装饰器和 `Client` API 即可接入。

---

## 2. 变更目标

| 目标 | 衡量标准 |
|------|---------|
| 接入 LangSmith Tracing | Agent 推理全链路（plan → retrieve → rerank → generate → reflect）可追踪 |
| 接入 OpenEvals 评测 | 检索质量（召回率/精确率）+ 生成质量（正确性/忠实度/相关性）自动化评分 |
| 零侵入接入 | 不改动现有核心逻辑，通过装饰器和独立评测脚本实现 |
| 原有 TDD 回归通过 | 所有现有测试不受影响 |
| 配置可选开关 | LangSmith 和 OpenEvals 均为可选功能，未配置 API Key 时不影响现有功能 |

---

## 3. 变更范围

### 3.1 新增模块

| 模块 | 文件名 | 职责 |
|------|--------|------|
| 监控模块 | `src/monitoring.py` | LangSmith Client 初始化、`@traceable` 装饰器工厂、环境变量读取 |
| 检索评测 | `tests/eval_retrieval.py` | 基于 OpenEvals 的检索质量评测脚本 |
| 生成评测 | `tests/eval_generation.py` | 基于 OpenEvals 的答案质量评测脚本 |

### 3.2 修改模块

| 模块 | 文件 | 修改内容 |
|------|------|---------|
| Agent 核心 | `src/agent_core.py` | `run()`、`run_stream()`、`_call_llm()`、`_execute_action()` 加 `@traceable` |
| 检索模块 | `src/retrieval.py` | `VectorRetriever.search()`、`BM25Retriever.search()`、`HybridRetriever.search()`、`RAGGenerator.query()`、`_generate_answer()` 加 `@traceable` |
| API 服务 | `src/api_service.py` | 启动时初始化 LangSmith Client |
| 依赖配置 | `requirements.txt` | 新增 `langsmith`、`openevals` |
| 环境变量 | `env` | 新增 `LANGCHAIN_API_KEY`、`LANGCHAIN_PROJECT` 等 |
| Agent 配置 | `config/agent_config.json` | 新增 `monitoring` 配置节（enabled、project_name 等） |
| 变更日志 | `CHANGELOG.md` | 记录 v5.0 变更 |

### 3.3 保留不变

- `src/tools/` - 全部工具模块不变
- `src/query_processor.py` - 意图识别不变
- `src/planner.py` - 规划器不变
- `src/reflector.py` - 反思器不变
- `src/conversation.py` - 对话管理不变
- `src/agent_memory.py` - 记忆系统不变
- `frontend/` - 前端不变
- 全部 `config/` 中除 `agent_config.json` 外的文件不变
- 全部 `data/` 文件不变

---

## 4. 技术方案概要

### 4.1 LangSmith Tracing (追踪链路)

```
用户请求
  → api_agent_query [trace: agent-query]
    → ReActAgent.run [trace: react-loop]
      → _call_llm [trace: llm-call] x N
      → _execute_action [trace: tool-execute] x N
        → VectorRetriever.search [trace: vector-search]
        → BM25Retriever.search [trace: bm25-search]
        → HybridRetriever.search [trace: hybrid-search]
          → _gte_rerank [trace: rerank]
        → RAGGenerator.query [trace: rag-query]
          → _generate_answer [trace: llm-generate]
```

### 4.2 OpenEvals 评测维度

| 评测维度 | 评估器 | 说明 |
|---------|--------|------|
| 检索召回率 | `ContextRelevancyEvaluator` | 检索结果与 query 的相关性评分 |
| 检索精确率 | `ContextPrecisionEvaluator` | 检索结果中相关文档占比 |
| 答案正确性 | `CorrectnessEvaluator` | 答案与参考答案的语义一致性 |
| 答案忠实度 | `FaithfulnessEvaluator` | 答案是否忠实于检索到的文档 |
| 答案相关性 | `AnswerRelevancyEvaluator` | 答案是否直接回应用户问题 |

### 4.3 可选的开关控制

```json
// config/agent_config.json
{
    "monitoring": {
        "enabled": true,
        "project_name": "financial-rag-agent",
        "trace_level": "detailed"
    }
}
```

---

## 5. 技术决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 接入方式 | `@traceable` 装饰器 + Client API | 框架无关，不依赖 LangChain，零侵入 |
| tracing 粒度 | 模块级别（每个关键方法一个 trace） | 既不过细（不追踪内部辅助方法），也不过粗（不错过关键节点） |
| 评测方式 | 离线评测脚本 (`tests/eval_*.py`) | 在线评测会增加延迟和成本，离线评测适合定期质量审计 |
| 可选开关 | 配置文件 + 环境变量双重控制 | 未配置时不影响现有功能，零回归风险 |
| LangSmith 项目 | `financial-rag-agent` | 统一项目名，便于跨环境对比 |

---

## 6. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| `@traceable` 增加调用延迟 | 每次 trace 上报约增加 50-200ms 网络延迟 | LangSmith 异步上报，不阻断主流程 |
| 未安装包导致 ImportError | 服务无法启动 | `monitoring.py` 中 try/except 导入，未安装时优雅降级 |
| API Key 泄露 | 安全风险 | Key 仅从 `.env` 读取，`.gitignore` 已排除 `.env` |
| 过度追踪导致 LangSmith 费用增加 | 运营成本 | `trace_level` 可配置，支持 `minimal` 模式只追踪入口 |

---

## 7. 受影响的规范

- `openspec/changes/rag-to-agent/` - Agent 核心推理链路被追踪
- `openspec/changes/model-upgrade/` - 模型调用被追踪
- `openspec/changes/quality-robustness-enhancement/` - 检索质量被追踪
