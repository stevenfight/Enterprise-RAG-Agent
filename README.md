# 企业知识库智能问答系统 (RAG-Agent)

> **当前状态**: RAG-Agent 智能体架构开发完成。管道模式 (Streamlit + FastAPI) 和 Agent 模式 (ReAct + 工具调用 + 自我反思) 均可用。
> 开发进度: 64/64 项任务 (100%), TDD 179 GREEN / 0 RED (100%)。

> 基于 RAG 技术的企业年报智能 Agent 系统，从管道 RAG 进化而来，支持 ReAct 自主推理 + 工具调用。
> 原始 RAG 项目：[enterprise-rag-financial-reports](https://github.com/stevenfight/enterprise-rag-financial-reports)
> 完整搭建笔记见知乎专栏：[《企业级 RAG Agent 实战》系列](https://www.zhihu.com/column/c_2050590785557487739)

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.x-green)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-red)](https://streamlit.io/)

---

## 功能特性

- **PDF 智能解析**：MinerU API 将 PDF 转为 Markdown，支持超 200 页年报分页解析
- **Small-to-Big 检索**：子块 150 tokens 做 Embedding，父块 500 tokens 做 LLM 上下文
- **混合检索**：BM25 关键词 + 向量语义，意图驱动动态权重调整
- **gte-rerank-v2 重排**：批量评分替代逐条 LLM 调用，耗时从 54s 降至 2s
- **意图识别**：6 类意图分类 + 域外问题拦截 + 查询改写
- **多轮对话**：ConversationManager 支持 5 轮对话上下文，查询改写结合对话历史补全指代信息
- **对比查询四层保底**：公平分配 + 替换策略 + 保底重新检索 + 营收数据保底补充，解决多公司对比数据缺失问题
- **指令细分化 Prompt**：针对 financial_data / trend / comparison / business_analysis 设计专用 Prompt
- **双界面**：Streamlit Web 界面 + FastAPI REST API
- **Agent 智能体模式**：ReAct 自主推理 + 5 个工具调用 + 自我反思修正 (NEW)
- **三层记忆系统**：工作记忆 / 情景记忆 / 长期记忆，支持多轮追问 (NEW)
- **企业级内存保护**：会话隔离 + 容量上限 + 存储截断，防 OOM (NEW)
- **并发安全**：8 场景验证，会话隔离架构保证线程安全 (NEW)

## 技术栈

| 组件 | 技术 |
|------|------|
| PDF 解析 | MinerU API |
| 文本分块 | tiktoken (cl100k_base) |
| Embedding | DashScope text-embedding-v3 (1024 维) |
| 向量索引 | FAISS IndexFlatIP |
| 关键词检索 | rank_bm25 + jieba + 财经自定义词典 |
| 重排 | DashScope gte-rerank-v2 (批量) |
| 生成 | DashScope Qwen-Max |
| 意图识别 | DashScope Qwen-Plus |
| 后端 | FastAPI + Uvicorn |
| 前端 | Streamlit |

## 项目结构

```
├── app_streamlit.py          # Streamlit 界面入口 (管道 + Agent)
├── src/
│   ├── api_service.py        # FastAPI REST API (管道 + Agent 端点)
│   ├── pdf_mineru.py         # PDF 解析 (MinerU API)
│   ├── text_splitter.py      # Small-to-Big 文本分块
│   ├── ingestion.py          # 向量数据库构建 (FAISS + BM25)
│   ├── retrieval.py          # 混合检索 + gte-rerank-v2 重排 + RAG 生成
│   ├── query_processor.py    # 意图识别 + 查询改写 + 域外拦截
│   ├── conversation.py       # 多轮对话历史管理 + 存储截断
│   ├── agent_core.py         # ReAct Agent 主循环 (NEW)
│   ├── agent_memory.py       # 三层记忆系统 (NEW)
│   ├── planner.py            # 查询规划器 (NEW)
│   ├── reflector.py          # 答案反思验证 (NEW)
│   ├── tools/                # Agent 工具集 (NEW)
│   │   ├── __init__.py       # ToolResult/BaseTool/ToolRegistry
│   │   ├── retrieve_tool.py  # 混合检索工具
│   │   ├── calculator_tool.py # 财务指标计算
│   │   ├── compare_tool.py   # 多公司对比
│   │   ├── chart_tool.py     # 图表生成
│   │   └── verify_tool.py    # 反幻觉验证
│   └── utils.py              # 公共工具函数 (API Key 获取)
├── config/
│   ├── agent_config.json     # Agent 行为参数配置 (NEW)
│   ├── bm25_expansions.json  # BM25 查询扩展词典
│   └── financial_dict.txt    # BM25 财经自定义词典
├── tests/
│   ├── test_e2e_agent.py      # 端到端集成测试 (NEW)
│   ├── test_agent_core.py     # Agent 核心循环测试 (NEW)
│   ├── test_agent_tools.py    # 工具集测试 (NEW)
│   ├── test_agent_memory.py   # 三层记忆系统测试 (NEW)
│   ├── test_reflector.py      # 反思验证测试 (NEW)
│   ├── run_all.py             # 全量测试一键脚本 (NEW)
│   ├── test_memory_leak_fixes.py    # 内存泄漏修复测试 (NEW)
│   ├── test_memory_isolation_demo.py  # 会话隔离验证测试 (NEW)
│   ├── test_agent_memory_multiturn.py # 多轮追问测试 (NEW)
│   ├── test_agent_memory_interrupt.py # 中断恢复测试 (NEW)
│   ├── test_agent_memory_concurrent.py # 并发安全测试 (NEW)
│   ├── test_boundary_checklist.py     # 边界测试 (NEW)
│   ├── test_document_integration.py   # 企业文档接入测试
│   ├── tdd_all_optimizations.py       # 全量管道回归测试
│   └── integration_test.py            # 集成测试
├── docs/                     # 项目文档
│   ├── 快速上手指南_新开发者.md      # 新开发者入门，含架构详解、调试排错
│   ├── 企业文档接入开发指南.md      # 新增/修改/删除企业文档的完整操作指南
│   ├── 上线部署清单.md              # 环境确认、数据迁移、服务启动
│   └── 系统设计决策记录.md          # 关键技术约束与架构决策
├── openspec/                 # SDD 规范驱动开发文档
│   └── changes/
│       ├── rag-to-agent/            # 第四轮迭代：Agent 智能体架构
│       ├── model-upgrade/    # 第一轮迭代：模型升级
│       └── quality-robustness-enhancement/  # 第二轮迭代：健壮性增强
├── snippets/                 # 独立工具代码片段
│   ├── small_to_big_chunker.py       # Small-to-Big 分块算法演示
│   └── coverage_guarantee.py         # 覆盖率保障逻辑
├── env                       # 环境变量配置模板（复制为 .env 后填入密钥）
├── data/stock_data/databases/
│   ├── chunked_reports/      # 分块数据 (12 份 JSON)
│   └── vector_dbs/           # 向量数据库 (按公司分库)
│       ├── 中芯国际/
│       ├── 中国移动/
│       ├── 中国联通/
│       └── 中国电信/
```

## 快速开始

### 1. 环境准备

```bash
# Python 3.11+
pip install -r requirements.txt
```

### 2. 配置 API Key

将项目根目录下的 `env` 文件复制为 `.env`，并填入你的 API 密钥：

```bash
copy env .env
```

编辑 `.env` 文件，至少填入 `DASHSCOPE_API_KEY`（必需），如需 PDF 解析还需填入 `MINERU_API_KEY`。

### 3. 构建向量数据库

```bash
# 构建所有公司的索引
python src/ingestion.py

# 构建指定公司
python src/ingestion.py --company 中芯国际

# 重建索引
python src/ingestion.py --company 中芯国际 --rebuild
```

### 4. 启动服务

**Streamlit 界面**：
```bash
streamlit run app_streamlit.py
```
打开后，在侧边栏打开 **Agent 推理模式** 开关即可使用 ReAct 自主推理。
如果关闭此开关，系统自动降级为管道模式。

**FastAPI 接口**：
```bash
uvicorn src.api_service:app --host 0.0.0.0 --port 8000
```

### 5. API 调用

验证服务是否正常：
```bash
curl http://localhost:8000/api/health
```

```bash
# Agent 智能体查询 (推荐)
curl -X POST http://localhost:8000/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "中芯国际2024年营收是多少？", "max_steps": 3}'

# 完整问答
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "中国移动2024年营收是多少？"}'

# 仅检索
curl -X POST http://localhost:8000/api/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "中国移动2024年营收"}'

# 公司列表
curl http://localhost:8000/api/companies
```

## 性能指标

| 指标 | 值 |
|------|-----|
| 端到端查询耗时 | ~20s |
| Agent 平均推理步数 | 2~3 步 |
| Agent 反思置信度 | 80%~95% (无幻觉场景) |
| 重排耗时 | ~2s (gte-rerank-v2 批量) |
| 支持文档数 | 12 份 PDF |
| 支持公司数 | 4 家 (中芯国际/中国移动/中国联通/中国电信) |
| 对比查询覆盖率 | 95%+ (四层保底机制) |
| 查询改写准确率 | 多轮指代消解成功率 > 90% |
| 回归测试通过率 | 137 PASS, 0 FAIL (100%) |

## 核心架构

### 管道模式 (原 RAG)
```
用户查询
  -> QueryProcessor (意图识别 + 查询改写 + 域外拦截)
  -> HybridRetriever (混合检索: BM25 + 向量 + gte-rerank-v2 重排)
  -> RAGGenerator (Prompt 选择 + LLM 生成 + 对话记忆)
  -> 最终答案 + 来源信息 + 置信度
```

### Agent 模式 (NEW)
```
用户查询
  -> TaskPlanner (拆解为子任务 DAG)
  -> ReActAgent (Thought -> Action -> Observation 循环)
       -> ToolRegistry (retrieve/calculator/compare/chart/verify)
            -> HybridRetriever (底层检索)
       -> AgentMemory (工作记忆 + 情景记忆 + 长期记忆)
  -> AnswerReflector (幻觉检测 + 来源完整性 + 自动修正)
  -> 最终答案 + 推理链 + 修正建议
```

### API 调用 (Agent 模式)

```bash
# Agent 智能体查询
curl -X POST http://localhost:8000/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "中芯国际2024年营收和净利润是多少？", "conversation_id": "session-1"}'

# 管道模式查询 (降级方案)
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "中国移动2024年营收是多少？"}'
```

## 迭代历史

| 迭代 | 变更 ID | 核心内容 |
|------|---------|---------|
| 第四轮 | rag-to-agent | Agent 智能体架构（ReAct 推理循环 + 5 工具系统 + 三层记忆 + 反思验证）、企业级内存保护、并发安全（8 场景）、全量回归测试（135 PASS） |
| 第一轮 | model-upgrade | 模型升级 (Embedding v3 / gte-rerank-v2 / qwen-max)、检索权重自适应、指令细分化 Prompt |
| 第二轮 | quality-robustness-enhancement | 代码去重、API 超时控制、对话记忆、BM25 财经词典、表格文本预处理 |
| 第三轮 | quality-robustness-enhancement | 对比查询优化（候选截断保护、营收数据保底）、查询改写上下文注入、检索日志增强 |

详见 openspec/changes/ 目录下的各轮迭代设计文档

## 文档

| 文档 | 说明 |
|------|------|
| [快速上手指南](docs/快速上手指南_新开发者.md) | 新开发者入门，含架构详解、调试排错 |
| [企业文档接入指南](docs/企业文档接入开发指南.md) | 新增/修改/删除企业文档的完整操作指南 |
| [上线部署清单](docs/上线部署清单.md) | 环境确认、数据迁移、服务启动、冒烟测试 |
| [系统设计决策记录](docs/系统设计决策记录.md) | 关键技术约束与架构决策 |

> 更多技术博客文章（避坑指南、架构优化、测试报告等）见 _local/blog/ 文件夹，已发布至知乎专栏