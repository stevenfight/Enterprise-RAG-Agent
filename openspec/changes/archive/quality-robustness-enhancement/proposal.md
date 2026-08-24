# 变更提案: 项目质量与健壮性增强

> 编码: UTF-8
> 状态: 已完成

---

## 1. 变更背景

当前系统已完成模型升级（v1.0），但在代码健壮性、功能完整性和可维护性方面仍有优化空间。本变更旨在系统性提升项目质量，降低线上故障风险，同时补齐对话记忆、表格检索等关键功能缺口。

## 2. 变更目标

| 目标 | 衡量标准 |
|------|----------|
| 提升代码健壮性 | API 超时控制、重试机制、公共函数提取 |
| 补齐功能缺口 | 多轮对话上下文、BM25 财经词典、表格检索优化 |
| 提升查询质量 | 对比查询保底、查询改写增强、检索日志增强 |
| 消除术语错误 | 日志中"LLM 重排"修正为"gte-rerank-v2 重排" |

## 3. 变更范围

### 3.1 健壮性增强 (P0)

| 项目 | 内容 | 涉及文件 |
|------|------|----------|
| API 超时控制 | Embedding 30s / LLM 60s / 重排 15s | retrieval.py, query_processor.py, ingestion.py |
| 重试机制 | Embedding 指数退避重试，最多 3 次 | retrieval.py |
| 重排回退 | gte-rerank-v2 超时后回退 hybrid 排序 | retrieval.py |
| 公共函数提取 | `_read_windows_env_var` / `get_api_key` 提取到 utils.py | 新增 utils.py，修改 4 个模块 |

### 3.2 功能完整性 (P1)

| 项目 | 内容 | 涉及文件 |
|------|------|----------|
| 对话记忆 | ConversationManager 支持 5 轮历史上下文 | 新增 conversation.py，修改 app_streamlit.py / api_service.py |
| BM25 财经词典 | 27 个财经术语自定义词典，jieba 正确分词 | 新增 financial_dict.txt，修改 ingestion.py / retrieval.py |
| 表格检索优化 | Markdown 表格排版符号预处理，提升 Embedding 质量 | retrieval.py |
| 对比查询保底 | 候选截断保护 + 营收数据补充机制 | retrieval.py |
| 查询改写增强 | 对话上下文传入，补全指代信息 | query_processor.py |
| 检索日志增强 | 上下文片段预览，方便定位数据缺失 | retrieval.py |

### 3.3 代码质量 (P2)

| 项目 | 内容 | 涉及文件 |
|------|------|----------|
| 日志术语修正 | "LLM 重排"改为"gte-rerank-v2 重排" | retrieval.py |
| 来源字段清理 | 移除无效的 `rerank_reasoning` 和 `rerank_key_info` | retrieval.py |
| 魔法数字常量化 | `BATCH_SIZE=10`、`MAX_INPUT_TOKENS=2048` 等 | 多个文件 |

## 4. 影响

- 新增文件: `src/utils.py`, `src/conversation.py`, `config/financial_dict.txt`
- 修改文件: `src/retrieval.py`, `src/query_processor.py`, `src/api_service.py`, `src/ingestion.py`, `app_streamlit.py`
- 测试验证: `tests/tdd_all_optimizations.py`（更新对应测试用例）
