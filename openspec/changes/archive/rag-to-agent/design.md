# 技术设计: RAG 管道升级为 RAG-Agent 智能体

> 编码: UTF-8

---

## 一、系统架构对比

### 1.1 当前架构（RAG 管道）

```
┌──────────┐    ┌──────────────┐    ┌────────────────┐    ┌──────────┐
│ 用户查询  │───>│ QueryProcessor│───>│ HybridRetriever│───>│RAGGenerator│
└──────────┘    │ 意图识别+改写 │    │ BM25+向量+重排  │    │ Qwen-Max   │
                └──────────────┘    └────────────────┘    └──────────┘
                单步、线性、无反馈
```

### 1.2 目标架构（RAG-Agent）

```
┌──────────┐    ┌─────────────────────────────────────────────────┐
│ 用户查询  │───>│                 Agent Core (ReAct)               │
└──────────┘    │                                                 │
                │  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
                │  │ Planner  │  │ Executor │  │  Reflector   │  │
                │  │ 任务拆解  │  │ 工具调度  │  │  答案验证    │  │
                │  └──────────┘  └────┬─────┘  └──────────────┘  │
                │                    │                            │
                │       ┌────────────┼────────────┐              │
                │       ▼            ▼            ▼              │
                │  ┌─────────┐ ┌─────────┐ ┌──────────┐         │
                │  │retrieve │ │calculate│ │ compare  │  ...    │
                │  │  检索   │ │  计算   │ │  对比    │         │
                │  └─────────┘ └─────────┘ └──────────┘         │
                │                                                 │
                │  ┌──────────────────────────────────┐         │
                │  │         Agent Memory (三层)       │         │
                │  │  工作记忆 │ 情景记忆 │ 长期记忆   │         │
                │  └──────────────────────────────────┘         │
                └─────────────────────────────────────────────────┘
                                          │
                                          ▼
                                    ┌──────────┐
                                    │ 最终答案  │
                                    └──────────┘
```

---

## 二、核心模块设计

### 2.1 Agent Core (`src/agent_core.py`)

**职责**: ReAct 循环主控制器，管理 Thought → Action → Observation 循环。

**核心类**:

```python
class ReActAgent:
    def __init__(self, config: AgentConfig, tools: ToolRegistry, memory: AgentMemory)
    def run(self, query: str, context: dict) -> AgentResult
    def _think(self, observation: str) -> Thought
    def _act(self, action: Action) -> Observation
    def _should_stop(self, thought: Thought, step: int) -> bool
```

**ReAct 循环逻辑**:

```python
def run(self, query, context):
    self.memory.reset_working()
    step = 0
    
    while step < self.config.max_steps:
        thought = self._think(context)      # LLM 推理
        if thought.is_final_answer:         # 判定是否结束
            break
        action = thought.action             # 解析行动
        observation = self._act(action)     # 执行工具
        self.memory.add(thought, action, observation)
        step += 1
    
    # 最终答案生成
    return self._generate_final_answer()
```

**System Prompt 设计**:

```
你是一个企业财务年报分析专家 Agent。

可用工具:
- retrieve: 从财报数据库中检索信息。参数: query, company_name(可选), top_n(可选)
- calculate: 计算财务指标。参数: expression 或 metric_name
- compare: 多公司对比分析。参数: companies[], metrics[], year
- chart: 生成财务图表。参数: data, chart_type
- verify: 验证数据准确性。参数: claim, source_text

输出格式:
Thought: 你的推理过程
Action: 工具名称
Action Input: JSON 格式的工具参数

当获取了足够信息后，输出:
Thought: 我已经收集了足够的信息
Final Answer: 最终答案
```

### 2.2 Agent Memory (`src/agent_memory.py`)

**职责**: 三层记忆管理。

**核心类**:

```python
class AgentMemory:
    def __init__(self, config: dict)
    def reset_working(self)                     # 重置工作记忆
    def add(self, thought, action, observation)  # 添加记录
    def get_working_context(self) -> str         # 获取工作记忆上下文
    def summarize_to_episodic(self)              # 工作记忆→情景记忆
    def get_episodic_context(self, turns) -> str # 获取情景记忆上下文
```

**三层结构**:

| 层级 | 数据结构 | 存储方式 |
|------|---------|---------|
| 工作记忆 | `List[Step]` | 内存列表 |
| 情景记忆 | `List[ConversationSummary]` | 会话级 dict |
| 长期记忆 | `Dict[str, Knowledge]` | 可选 SQLite/JSON |

**记忆流转**:
```
工作记忆(当前任务)
  → 任务完成后
  → summarize_to_episodic()
  → 情景记忆(历史会话)
  → 定期梳理
  → 长期记忆(知识积累)
```

### 2.3 Planner (`src/planner.py`)

**职责**: 将复杂查询拆解为子任务 DAG。

**核心类**:

```python
class TaskPlanner:
    def __init__(self, llm_config: dict)
    def plan(self, query: str, context: dict) -> TaskPlan
    def decompose(self, complex_query: str) -> List[SubTask]
    def build_dag(self, tasks: List[SubTask]) -> ExecutionOrder
```

**拆解策略**:

| 查询类型 | 拆解方式 |
|---------|---------|
| 单公司单指标 | 不拆解，直接检索 |
| 多公司对比 | 按公司拆解为并行子查询 |
| 趋势分析 | 先检索历史数据，再生成趋势 |
| 复合计算 | 先检索原始数据，再调用 calculate |

### 2.4 Reflector (`src/reflector.py`)

**职责**: 对 Agent 生成的中间/最终答案进行质量验证。

**核心类**:

```python
class AnswerReflector:
    def __init__(self, llm_config: dict)
    def verify(self, answer: str, sources: List[dict]) -> RefectionResult
    def check_hallucination(self, claim: str, source_text: str) -> bool
    def check_completeness(self, answer: str, query: str) -> float
    def suggest_correction(self, answer: str, issues: List[str]) -> str
```

**验证维度**:

| 维度 | 方法 | 说明 |
|------|------|------|
| 数值准确性 | `check_hallucination` | 与来源文本交叉验证 |
| 来源完整性 | `_verify_sources` | 每个数据点是否有来源支撑 |
| 回答完整性 | `check_completeness` | 是否回答了所有子问题 |
| 逻辑一致性 | `_check_consistency` | 内部数据不自相矛盾 |

---

## 三、工具系统设计

### 3.1 工具接口

```python
class BaseTool:
    name: str
    description: str
    parameters: dict  # JSON Schema 格式
    
    def run(self, **kwargs) -> ToolResult:
        raise NotImplementedError

class ToolResult:
    success: bool
    data: Any
    error: str = ""
    metadata: dict = {}
```

### 3.2 工具注册

```python
class ToolRegistry:
    def __init__(self)
    def register(self, tool: BaseTool)
    def get(self, name: str) -> BaseTool
    def list_all(self) -> List[BaseTool]
    def get_tool_descriptions(self) -> str  # 给 LLM 看的工具说明
```

### 3.3 各工具设计

#### retrieve_tool (检索工具)
- 封装 `HybridRetriever.search()` + `RAGGenerator.generate()`
- 输入: query, company_name(可选), top_n(默认5)
- 输出: 检索结果列表，包含 answer + sources
- **复用现有代码，不改动 retrieval.py**

#### calculator_tool (计算工具)
- 支持: 同比增长率、环比增长率、利润率、毛利率等
- 输入: metric_name + company_data 或 raw_expression
- 输出: 计算结果 + 计算公式
- 使用 Python 原生 `eval` + 安全沙箱

#### compare_tool (对比工具)
- 基于现有对比查询逻辑
- 输入: companies[], metrics[], year
- 输出: 结构化对比表（Markdown 格式）
- 自动触发三层保底机制

#### chart_tool (图表工具)
- 使用 matplotlib 生成财务趋势图
- 输入: data (dict), chart_type (bar/line/pie)
- 输出: 图表文件路径
- 不引入外部依赖（matplotlib 可能已安装）

#### verify_tool (验证工具)
- 输入: claim (待验证陈述), source_text (来源文本)
- 调用 LLM 判断陈述是否与来源一致
- 输出: verification_result + confidence

---

## 四、API 设计

### 4.1 新增端点

```
POST /api/agent/query
```

**请求体**:

```json
{
    "query": "中芯国际2024年营收同比增长率是多少",
    "company_name": null,
    "max_steps": 5,
    "conversation_id": null
}
```

**响应体**:

```json
{
    "answer": "中芯国际2024年营收...",
    "sources": [...],
    "reasoning_chain": [
        {"step": 1, "thought": "...", "action": "retrieve", "observation": "..."},
        {"step": 2, "thought": "...", "action": "calculate", "observation": "..."}
    ],
    "tool_calls": 2,
    "processing_time": 12.5,
    "conversation_id": "uuid"
}
```

**保留原有端点**:

```
POST /api/query       ← 管道模式，完全不变
POST /api/retrieve    ← 仅检索，完全不变
GET  /api/companies   ← 公司列表，完全不变
GET  /api/health      ← 健康检查，完全不变
```

### 4.2 Streamlit 界面

新增 Agent 模式开关：

- 侧边栏新增"Agent 模式"复选框
- Agent 模式下展示推理链（可折叠的步骤卡片）
- 显示工具调用历史和每步耗时
- 管道模式功能完全不变

---

## 五、数据流

### 5.1 Agent 模式完整数据流

```
用户输入
  → app_streamlit.py 或 api_service.py
  → ReActAgent.run(query, context)
    → Planner.plan()                    # 拆解任务
    → 循环:
      → Agent._think()                  # LLM 推理
      → 解析 Action
      → ToolRegistry.get(name).run()    # 执行工具
      → AgentMemory.add()               # 记录步骤
    → Reflector.verify()                # 验证答案
    → AgentMemory.summarize_to_episodic()
  → 返回 AgentResult (answer + reasoning_chain)
  → Streamlit 渲染 或 API JSON 响应
```

### 5.2 与原管道的兼容性

```
                    ┌── Agent 模式 ──> ReActAgent
用户查询 → API ────┤
                    └── 管道模式 ──> QueryProcessor → HybridRetriever → RAGGenerator
                    (完全不变)
```

---

## 六、配置设计

### 6.1 `config/agent_config.json`

```json
{
    "max_steps": 5,
    "max_tool_calls": 10,
    "temperature": 0.3,
    "max_tokens": 2048,
    "enabled_tools": [
        "retrieve",
        "calculate",
        "compare",
        "chart",
        "verify"
    ],
    "memory": {
        "working_memory_limit": 10,
        "episodic_memory_turns": 5,
        "enable_long_term": false
    },
    "reflection": {
        "enable_verification": true,
        "enable_hallucination_check": true,
        "auto_correct": true
    }
}
```

---

## 七、测试策略

### 7.1 新增测试文件

| 文件 | 测试内容 |
|------|---------|
| `tests/test_agent_core.py` | ReAct 循环、停步条件、异常处理 |
| `tests/test_agent_tools.py` | 各工具单元测试 |
| `tests/test_agent_memory.py` | 三层记忆的存取和流转 |
| `tests/test_reflector.py` | 验证逻辑、幻觉检测 |

### 7.2 回归测试

保留并运行原有 3 个测试文件：
- `tests/integration_test.py`
- `tests/tdd_all_optimizations.py`
- `tests/test_document_integration.py`

确保管道模式零回归。

---

## 八、项目目录结构（Agent 完成后）

```
企业级财务年报分析智能RAG—AGENT/
├── .gitignore                    # 排除 _local/ 等
├── README.md
├── app_streamlit.py              # [修改] +Agent模式
├── env
├── config/
│   ├── bm25_expansions.json
│   ├── financial_dict.txt
│   └── agent_config.json         # [新增]
├── data/                         # 不变
├── docs/
│   ├── 企业文档接入开发指南.md
│   ├── 快速上手指南_新开发者.md
│   ├── 上线部署清单.md
│   └── 系统设计决策记录.md
├── openspec/
│   └── changes/
│       ├── model-upgrade/
│       ├── quality-robustness-enhancement/
│       └── rag-to-agent/
├── src/
│   ├── __init__.py               # [修改] 导出Agent模块
│   ├── agent_core.py             # [新增]
│   ├── agent_memory.py           # [新增]
│   ├── planner.py                # [新增]
│   ├── reflector.py              # [新增]
│   ├── api_service.py            # [修改] +/api/agent/query
│   ├── conversation.py           # [修改] 扩展记忆
│   ├── tools/                    # [新增]
│   │   ├── __init__.py
│   │   ├── retrieve_tool.py
│   │   ├── calculator_tool.py
│   │   ├── compare_tool.py
│   │   ├── chart_tool.py
│   │   └── verify_tool.py
│   ├── ingestion.py              # 不变
│   ├── pdf_mineru.py             # 不变
│   ├── query_processor.py        # 不变
│   ├── retrieval.py              # 不变
│   ├── text_splitter.py          # 不变
│   └── utils.py                  # 不变
└── tests/
    ├── integration_test.py
    ├── tdd_all_optimizations.py
    ├── test_document_integration.py
    ├── test_agent_core.py         # [新增]
    ├── test_agent_tools.py        # [新增]
    ├── test_agent_memory.py       # [新增]
    └── test_reflector.py          # [新增]
```
