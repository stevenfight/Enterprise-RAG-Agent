# 设计文档: 项目质量与健壮性增强

> 编码: UTF-8
> 变更: quality-robustness-enhancement
> 状态: 已完成

---

## 1. 架构概览

本变更不引入新架构，是对现有 RAG 管道的增强，所有修改集中在已有模块内。

```
用户查询
  -> QueryProcessor (新增对话上下文注入)
    -> HybridRetriever (新增超时控制 + 表格预处理 + 对比保底)
      -> RAGGenerator (新增日志预览)
        -> 最终答案

数据管道
  -> ingestion.py (新增 jieba 财经词典加载)
  -> retrieval.py (新增公共工具函数导入)
```

## 2. 关键设计决策

### 2.1 公共工具函数提取

**决策**: 将 `_read_windows_env_var` 和 `get_api_key` 从 4 个模块中提取到独立的 `src/utils.py`。

**理由**:
- 消除代码重复（4 个模块各有一份相同实现）
- 统一 API Key 获取逻辑（优先级: 进程环境变量 -> Windows 注册表 -> .env 文件）
- 新增模块可直接复用，无需复制粘贴

**涉及模块**: retrieval.py, query_processor.py, ingestion.py, pdf_mineru.py

### 2.2 API 超时控制策略

**决策**: 为所有 DashScope API 调用设置超时，并设计分层回退策略。

| API 类型 | 超时 | 失败策略 |
|----------|------|----------|
| LLM 生成 (qwen-max) | 60s | 抛出异常，上层处理 |
| LLM 意图识别 (qwen-plus) | 30s | 抛出异常，上层处理 |
| Embedding | 30s | 指数退避重试，最多 3 次 |
| gte-rerank-v2 | 15s | 回退到 hybrid 分数排序 |

**理由**:
- 生成和意图识别是核心链路，超时即失败，由调用方决定重试或降级
- Embedding 是批量操作，网络波动常见，重试成本可控
- 重排非核心，hybrid 分数已足够支撑基础排序

### 2.3 对话记忆设计

**决策**: ConversationManager 保留最近 5 轮对话（10 条消息），用于查询改写时的上下文补全。

**实现**:
```python
# 查询改写时传入对话历史
conversation_context = conversation_manager.get_context_string(max_turns=3)
rewritten = query_processor.process(query, conversation_context=conversation_context)
```

**理由**:
- 3 轮历史已足够补全大多数指代（如"那联通呢"）
- 超过 5 轮会增加 LLM 上下文负担，对当前查询贡献递减
- 存储截断防止内存泄漏

### 2.4 BM25 财经词典

**决策**: 在 `ingestion.py` 构建索引和 `retrieval.py` 检索时均加载 jieba 自定义词典。

**词典内容**: 27 个常用财经术语（如"归母净利润"、"扣非净利润"、"营业收入"）

**理由**:
- 确保 jieba 将财经术语作为整体分词，而不是拆成单字或通用词
- 仅在索引构建和检索分词时加载，不影响其他模块

### 2.5 表格检索优化

**决策**: `preprocess_table_text()` 在 Embedding 前移除 Markdown 表格的排版符号（`|`, `-`, `:`）。

**理由**:
- Markdown 表格的排版符号对 Embedding 模型是噪声，降低语义匹配精度
- 竖线替换为空格，保留数值和文本内容
- 预处理仅影响 Embedding 输入，不影响返回给 LLM 的原始文本

### 2.6 对比查询三层保底

**决策**: 跨公司对比查询时，执行三层防线确保每家公司有数据代表。

| 防线 | 机制 | 触发条件 |
|------|------|----------|
| 第一层 | 公平分配 | 每家公司至少 5 个名额进入重排候选 |
| 第二层 | 替换策略 | 某家公司缺失时，替换过度代表公司的最低分结果 |
| 第三层 | 保底重新检索 | 前两层失效时，用聚焦查询重新检索缺失公司的数据 |

**理由**:
- 对比查询的核心价值是"每家公司都有数据"，缺一即不完整
- 三层防线从简单到复杂，大多数场景第一层即可解决

## 3. 测试验证

- `tests/tdd_all_optimizations.py`: 更新对应测试用例，验证所有增强功能
- `tests/test_document_integration.py`: 249 项文档集成测试，验证端到端流程
- `tests/test_boundary_checklist.py`: 边界测试，验证超时和异常场景
