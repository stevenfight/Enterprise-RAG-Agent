# 项目概览

## 项目名称
企业级财务年报分析智能 RAG-Agent

## 项目描述
从管道式 RAG 问答系统升级为具备自主推理、工具调用、自我反思能力的 RAG-Agent 智能体。面向企业年报（中芯国际、中国移动、中国联通、中国电信，共 12 份 PDF）的自然语言问答场景。

## 技术栈

| 层级 | 技术 |
|------|------|
| PDF 解析 | MinerU API |
| 文本分块 | tiktoken (cl100k_base), Small-to-Big 策略 |
| Embedding | DashScope text-embedding-v3 (1024 维) |
| 向量检索 | FAISS IndexFlatIP |
| 关键词检索 | rank_bm25 + jieba + 财经自定义词典 |
| 重排 | DashScope gte-rerank-v2 |
| 生成 | DashScope Qwen-Max |
| 意图识别 | DashScope Qwen-Plus |
| Agent 框架 | 自研 ReAct (不引入 LangChain 等) |
| 后端 | FastAPI + Uvicorn |
| 前端(主) | React 19 + Ant Design 6 + TypeScript (Phase 2 已完成) |
| 前端(备) | Streamlit |

## 演进路线

| 版本 | 变更ID | 说明 | 状态 |
|------|--------|------|:--:|
| v0.x | rag-pipeline | 原始 RAG 管道（独立仓库 enterprise-rag-financial-reports）| 已完成 |
| v1.0 | model-upgrade | 模型升级 + 检索精准度 (8 项优化) | 已完成 |
| v1.1 | quality-robustness-enhancement | 健壮性 + 功能完整性 (15 项优化) | 已完成 |
| v2.0 | rag-to-agent | RAG 管道 → RAG-Agent 智能体 | 已完成 |
| v3.0 | modern-ui | 现代化前端展示界面 (React + Ant Design, 3 阶段交付) | Phase 1 已完成<br>Phase 2 已完成<br>Phase 3 规划中 |
| v4.0 | docker-deployment | Docker 容器化部署 | 已完成 |
| v5.0 | langsmith-openevals-integration | 接入 LangSmith + OpenEvals 能力评测监控 | 实施中（评测通过率 80%，待归档）|
| v5.1 | p0-critical-fixes | P0 关键缺陷修复（empty_result_count + run_stream推理链 + memory配置 + 并发安全 + API鉴权）| 规划中 |

## 项目结构

```
├── src/          # 核心源码（agent_core, tools, retrieval, ...）
├── frontend/     # 现代化前端（React + Ant Design, Phase 2 已完成）
├── config/       # 配置文件（bm25, financial_dict, agent_config）
├── data/         # 数据文件（分块 JSON, 向量索引）
├── tests/        # 测试（回归 + Agent 专项）
├── docs/         # 工程文档（接入指南、部署清单、设计决策）
├── openspec/     # SDD 规范驱动开发文档
└── app_streamlit.py  # Web 入口 (Streamlit 备用)
```

## 界面

- **React 前端**: `cd frontend && npm run dev` (开发), `npm run build` (生产)
- **Streamlit**: `streamlit run app_streamlit.py`
- **FastAPI**: `uvicorn src.api_service:app --host 0.0.0.0 --port 8000`
