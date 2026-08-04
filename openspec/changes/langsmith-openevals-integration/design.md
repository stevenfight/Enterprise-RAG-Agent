# 技术设计: 接入 LangSmith + OpenEvals 能力评测监控

> 编码: UTF-8

---

## 一、系统架构变更

### 1.1 当前架构（无在线监控）

```
┌──────────┐    ┌─────────────┐    ┌──────────┐
│ FastAPI  │───>│ Agent Core  │───>│ LLM/工具  │
│ 请求入口  │    │ ReAct 循环   │    │ DashScope │
└──────────┘    └─────────────┘    └──────────┘
                     │
                     ▼
              ┌──────────┐
              │ 本地日志   │ (logging → stdout)
              └──────────┘
```

### 1.2 目标架构（接入 LangSmith + OpenEvals）

```
┌──────────┐    ┌─────────────┐    ┌──────────┐
│ FastAPI  │───>│ Agent Core  │───>│ LLM/工具  │
│ 请求入口  │    │ ReAct 循环   │    │ DashScope │
└──────────┘    └─────┬───────┘    └──────────┘
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ 本地日志  │ │LangSmith │ │OpenEvals │
    │ stdout   │ │ 在线追踪  │ │ 离线评测  │
    └──────────┘ └──────────┘ └──────────┘
                      │              │
                      ▼              ▼
               ┌──────────┐  ┌──────────────┐
               │ Dashboard│  │ 评测报告JSON  │
               │ smith.lang│  │  + 回归对比  │
               └──────────┘  └──────────────┘
```

---

## 二、核心模块设计

### 2.1 监控模块 (`src/monitoring.py`)

**职责**: 统一管理 LangSmith Client 初始化、traceable 装饰器工厂、环境变量读取。

**设计原则**: 所有 LangSmith 相关的 import 和初始化集中在一处，其他模块通过 `src/monitoring.py` 间接使用，确保未安装或未配置时优雅降级。

```python
# src/monitoring.py

import os
import logging

logger = logging.getLogger("monitoring")

# ---- LangSmith 可用性检测 ----
_LANGSMITH_AVAILABLE = False
_traceable = None

try:
    from langsmith import Client as LangSmithClient
    from langsmith import traceable as _ls_traceable
    _LANGSMITH_AVAILABLE = True
except ImportError:
    logger.info("[monitoring] langsmith 未安装，追踪功能不可用")

# ---- 环境变量读取 ----
_LANGSMITH_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")
_LANGSMITH_PROJECT = os.getenv("LANGCHAIN_PROJECT", "financial-rag-agent")
_LANGSMITH_ENDPOINT = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")

# ---- Client 单例 ----
_client: LangSmithClient | None = None


def get_client() -> LangSmithClient | None:
    """获取 LangSmith Client 单例，未配置时返回 None"""
    global _client
    if not _LANGSMITH_AVAILABLE or not _LANGSMITH_API_KEY:
        return None
    if _client is None:
        _client = LangSmithClient(
            api_key=_LANGSMITH_API_KEY,
            api_url=_LANGSMITH_ENDPOINT,
        )
        logger.info("[monitoring] LangSmith Client 初始化成功, project=%s", _LANGSMITH_PROJECT)
    return _client


def traceable(name=None, **kwargs):
    """traceable 装饰器工厂，langsmith 不可用时返回透传装饰器"""
    if not _LANGSMITH_AVAILABLE or not _LANGSMITH_API_KEY:
        # 返回不做任何追踪的透传装饰器
        def passthrough(func):
            return func
        return passthrough
    return _ls_traceable(name=name, **kwargs)


def is_available() -> bool:
    """检查 LangSmith 是否可用（包已安装 + API Key 已配置）"""
    return _LANGSMITH_AVAILABLE and bool(_LANGSMITH_API_KEY)
```

**关键设计决策**:
- 使用模块级延迟初始化，避免 import 时抛异常
- `traceable()` 不可用时返回透传，调用方代码完全不变
- Client 单例模式，避免重复创建连接

### 2.2 追踪粒度设计

#### 2.2.1 Agent 核心 (`src/agent_core.py`)

在关键方法上加 `@traceable` 装饰器，覆盖 ReAct 循环全链路:

| 方法 | trace name | trace 内容 |
|------|-----------|-----------|
| `ReActAgent.run()` | `react-loop` | 输入: query、conversation_history、company_name；输出: AgentResult |
| `ReActAgent.run_stream()` | `react-loop-stream` | 同上，流式版本 |
| `ReActAgent._call_llm()` | `llm-call` | 输入: messages；输出: response text；metadata: model、temperature、token_usage |
| `ReActAgent._execute_action()` | `tool-execute` | 输入: action、action_input；输出: observation |

```python
# 修改示例 (agent_core.py)
from src.monitoring import traceable

class ReActAgent:
    @traceable(name="react-loop")
    def run(self, query, conversation_history="", company_name=None):
        ...

    @traceable(name="llm-call")
    def _call_llm(self, messages):
        ...
```

#### 2.2.2 检索模块 (`src/retrieval.py`)

| 方法 | trace name | trace 内容 |
|------|-----------|-----------|
| `VectorRetriever.search()` | `vector-search` | 输入: query、top_k；输出: results 数量 + 分数分布 |
| `BM25Retriever.search()` | `bm25-search` | 输入: query、top_k；输出: results 数量 + 分数分布 |
| `HybridRetriever.search()` | `hybrid-search` | 输入: query、company_name；输出: results 数量 + 置信度 |
| `RAGGenerator.query()` | `rag-query` | 输入: query、company_name、intent；输出: answer 长度 + sources 数量 |
| `RAGGenerator._generate_answer()` | `llm-generate` | 输入: prompt；输出: answer；metadata: model、token_usage |

#### 2.2.3 API 服务 (`src/api_service.py`)

| 端点 | trace name | 内容 |
|------|-----------|------|
| `api_agent_query()` | `agent-query-endpoint` | 输入: AgentQueryRequest；输出: answer 长度 + steps + elapsed |

### 2.3 OpenEvals 评测模块

#### 2.3.1 评测数据集

评测数据集由开发者维护为 JSON 文件，格式如下:

```json
// tests/eval_datasets/retrieval_queries.json
[
    {
        "query": "中芯国际2024年营收是多少",
        "expected_sources": ["中芯国际2024年年度报告"],
        "expected_keywords": ["营业收入", "亿元"],
        "company_name": "中芯国际"
    },
    ...
]
```

```json
// tests/eval_datasets/generation_queries.json
[
    {
        "query": "中芯国际2024年营收是多少",
        "reference_answer": "中芯国际2024年营业收入为577.96亿元...",
        "company_name": "中芯国际",
        "relevant_context_keywords": ["营业收入"]
    },
    ...
]
```

#### 2.3.2 检索评测 (`tests/eval_retrieval.py`)

```python
# 评测流程
def evaluate_retrieval(retriever, dataset_path):
    for item in dataset:
        results = retriever.search(item["query"], company_name=item["company_name"])
        # 使用 OpenEvals 评分
        relevancy_score = context_relevancy(item["query"], results)
        precision_score = context_precision(item["query"], results)
    return aggregate_scores
```

评测指标:
- **ContextRelevancy**: 检索结果文档与 query 的平均语义相关性 (0-1)
- **ContextPrecision**: 检索结果中文档的精确率 (与 expected_sources 匹配度)
- **HitRate@K**: Top-K 结果中命中期盼来源的比例

#### 2.3.3 生成评测 (`tests/eval_generation.py`)

```python
def evaluate_generation(rag_generator, dataset_path):
    for item in dataset:
        result = rag_generator.query(item["query"], company_name=item["company_name"])
        # OpenEvals 评分
        correctness = correctness_eval(result["answer"], item["reference_answer"])
        faithfulness = faithfulness_eval(result["answer"], result["sources"])
        relevancy = answer_relevancy(result["answer"], item["query"])
    return aggregate_scores
```

评测指标:
- **Correctness**: 答案与参考答案的语义一致性 (0-1)
- **Faithfulness**: 答案是否忠实于检索到的来源文档 (0-1)
- **AnswerRelevancy**: 答案是否直接回应用户问题 (0-1)

---

## 三、配置设计

### 3.1 环境变量 (`.env` 新增)

```
# ===== 可选 =====
# LangSmith API Key（用于在线追踪与监控）
# 获取地址：https://smith.langchain.com/
LANGCHAIN_API_KEY=

# LangSmith 项目名（可选，默认 financial-rag-agent）
LANGCHAIN_PROJECT=financial-rag-agent

# LangSmith 自定义端点（可选，默认 https://api.smith.langchain.com）
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

### 3.2 Agent 配置 (`config/agent_config.json` 新增)

```json
{
    "agent": { ... },
    "reflector": { ... },
    "monitoring": {
        "enabled": true,
        "project_name": "financial-rag-agent",
        "trace_level": "detailed"
    }
}
```

其中 `trace_level` 取值:
- `minimal`: 只追踪入口级别（agent-query-endpoint, react-loop）
- `standard`: 追踪 Agent + 检索链路（默认）
- `detailed`: 追踪所有 LLM 调用细节（含 prompt/response 全文）

### 3.3 依赖 (`requirements.txt` 新增)

```
# LangSmith 在线追踪与监控（框架无关，可选）
langsmith

# OpenEvals 离线评测（框架无关，可选）
openevals
```

---

## 四、数据流

### 4.1 Tracing 数据流

```
用户请求
  → FastAPI api_agent_query()
    → [trace: agent-query-endpoint]
    → ReActAgent.run()
      → [trace: react-loop]
      → ReActAgent._call_llm()
        → [trace: llm-call] x N
        → LangSmith 异步上报 (input/output/metadata)
      → ReActAgent._execute_action()
        → [trace: tool-execute]
        → Tool.run()
          → VectorRetriever.search() [trace: vector-search]
          → BM25Retriever.search() [trace: bm25-search]
          → HybridRetriever.search() [trace: hybrid-search]
          → RAGGenerator.query() [trace: rag-query]
            → RAGGenerator._generate_answer() [trace: llm-generate]
    → 返回 AgentResult
```

### 4.2 评测数据流

```
开发者维护 eval_datasets/*.json
  → tests/eval_retrieval.py
    → HybridRetriever.search() x N 次
    → OpenEvals 评分
    → 输出评测报告 (JSON + 控制台)
  → tests/eval_generation.py
    → RAGGenerator.query() x N 次
    → OpenEvals 评分
    → 输出评测报告 (JSON + 控制台)
```

---

## 五、优雅降级策略

所有 LangSmith/OpenEvals 相关代码遵循"静默降级"原则:

| 场景 | 行为 |
|------|------|
| `langsmith` 包未安装 | `traceable()` 返回透传装饰器，所有追踪代码等价于无操作 |
| `LANGCHAIN_API_KEY` 未配置 | 同未安装，不连接 LangSmith |
| `openevals` 包未安装 | 评测脚本会报友好提示并 exit(0)，不影响主服务 |
| LangSmith API 不可达 | `@traceable` 异步上报失败静默忽略，不阻塞主流程 |
| 评测脚本无数据集 | 输出提示 "评测数据集未找到，请先创建 eval_datasets/*.json" |

---

## 六、测试策略

### 6.1 新增 TDD 测试文件

| 文件 | 测试内容 | 用例数 |
|------|---------|:---:|
| `tests/test_monitoring.py` | 监控模块初始化、降级逻辑、traceable 透传验证 | 8 |

### 6.2 回归测试

所有现有测试必须保持通过:
- `tests/tdd_all_optimizations.py` - 全量回归
- `tests/test_agent_core.py` - Agent 核心
- `tests/test_agent_tools.py` - 工具
- `tests/test_planner_quick.py` - 规划器
- `tests/test_reflector_quick.py` - 反思器

### 6.3 评测脚本（不定期运行，不阻塞 CI）

- `tests/eval_retrieval.py` - 检索质量离线评测
- `tests/eval_generation.py` - 生成质量离线评测

---

## 七、目录结构变更

```
企业级财务年报分析智能RAG—AGENT/
├── config/
│   └── agent_config.json              # [修改] 新增 monitoring 配置节
├── env                                # [修改] 新增 LangSmith 环境变量
├── requirements.txt                   # [修改] 新增 langsmith + openevals
├── CHANGELOG.md                       # [修改] 记录 v5.0
├── src/
│   ├── monitoring.py                  # [新增] LangSmith 初始化 + traceable 工厂
│   ├── agent_core.py                  # [修改] 关键方法加 @traceable
│   ├── retrieval.py                   # [修改] 关键方法加 @traceable
│   └── api_service.py                 # [修改] 启动时初始化 LangSmith Client
├── tests/
│   ├── test_monitoring.py             # [新增] 监控模块 TDD 测试
│   ├── eval_retrieval.py              # [新增] OpenEvals 检索评测
│   ├── eval_generation.py             # [新增] OpenEvals 生成评测
│   └── eval_datasets/                 # [新增] 评测数据集目录
│       ├── retrieval_queries.json
│       └── generation_queries.json
└── openspec/
    └── changes/
        └── langsmith-openevals-integration/  # [新增] 本变更
```
