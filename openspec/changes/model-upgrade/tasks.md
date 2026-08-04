# 实现任务清单: 模型升级与检索精准度提升

> 编码: UTF-8
> 变更: model-upgrade
> 状态: 已完成 (第一轮迭代)

---

## 阶段1: Embedding 模型升级 (P0)

### 1.1 验证 text-embedding-v3 API 可用性
- [√] 编写 API 验证脚本,测试 `dashscope.TextEmbedding.call(model="text-embedding-v3", input=["测试文本"])`
- [√] 确认返回 Embedding 维度为 1024
- [√] 确认输入 token 限制(是否仍为 2048)

### 1.2 修改 retrieval.py 常量
- [√] `EMBEDDING_MODEL` 从 `"text-embedding-v1"` 改为 `"text-embedding-v3"`
- [√] `EMBEDDING_DIM` 从 `1536` 改为 `1024`

### 1.3 修改 ingestion.py 常量
- [√] `EMBEDDING_MODEL` 从 `"text-embedding-v1"` 改为 `"text-embedding-v3"`
- [√] `EMBEDDING_DIM` 从 `1536` 改为 `1024`

### 1.4 备份旧索引
- [√] 备份 `data/stock_data/databases/vector_dbs/` 目录

### 1.5 重建 FAISS 索引
- [√] 执行 `python src/ingestion.py --rebuild`
- [√] 验证新索引 FAISS 向量维度为 1024
- [√] 验证所有公司索引均重建成功

### 1.6 验证检索功能
- [√] 执行测试用例 T-E1: 单公司向量检索
- [√] 执行测试用例 T-E2: 混合检索(向量+BM25)
- [√] 执行测试用例 T-E3: 表格数据检索命中率

---

## 阶段2: 重排模型替换 (P1)

### 2.1 验证 gte-rerank API 可用性
- [√] 编写 API 验证脚本,测试 `dashscope.TextReRank.call(model="gte-rerank", query="测试", documents=["文档1", "文档2"])`
- [√] 确认返回结构包含 `relevance_score` 字段
- [√] 确认 `relevance_score` 范围为 0.0-1.0
- [√] 确认 `top_n` 参数行为
- [√] 确认 `return_documents` 参数行为

### 2.2 实现 _gte_rerank 方法
- [√] 在 `HybridRetriever` 类中新增 `_gte_rerank(self, query, candidates, top_n)` 方法
- [√] 构造 documents 列表(从 candidates 中提取 parent_text)
- [√] 调用 `dashscope.TextReRank.call()`
- [√] 解析返回结果,将 `relevance_score * 10` 映射为 rerank 分数
- [√] 处理 `rerank_reasoning` 和 `rerank_key_info` 字段(置空)
- [√] 按 rerank 分数降序排序,返回 (top_results, scored_candidates)

### 2.3 实现 _fallback_rerank 方法
- [√] 在 `HybridRetriever` 类中新增 `_fallback_rerank(self, candidates, top_n)` 方法
- [√] 按 hybrid 分数降序排序
- [√] 设置 rerank 分数为 hybrid * 10(近似映射)
- [√] 返回 (top_results, scored_candidates)

### 2.4 重写 _llm_rerank 方法
- [√] 空候选列表时返回 ([], []) (修复 ISSUE-004)
- [√] 优先调用 `_gte_rerank`
- [√] 异常时回退到 `_fallback_rerank`
- [√] 保留方法名 `_llm_rerank` 以减少调用方变更

### 2.5 验证重排功能
- [√] 执行测试用例 T-R1: 正常重排流程
- [√] 执行测试用例 T-R2: 对比查询重排
- [√] 执行测试用例 T-R3: API 失败回退
- [√] 执行测试用例 T-R4: 空候选列表
- [√] 执行测试用例 T-R5: 重排耗时验证

---

## 阶段3: 生成模型升级 (P2)

### 3.1 验证 qwen-max API 可用性
- [√] 编写 API 验证脚本,测试 `dashscope.Generation.call(model="qwen-max", ...)`
- [√] 确认 max_tokens=2048 参数兼容
- [√] 确认 result_format="message" 参数兼容

### 3.2 修改 GENERATION_MODEL 常量
- [√] `RAGGenerator.GENERATION_MODEL` 从 `"qwen-plus"` 改为 `"qwen-max"`

### 3.3 确认 QueryProcessor 模型不变
- [√] 验证 `query_processor.py` 中 `MODEL_NAME` 仍为 `"qwen-plus"`

### 3.4 验证生成功能
- [√] 执行测试用例 T-G1: 财务数据查询生成
- [√] 执行测试用例 T-G2: 对比分析生成
- [√] 执行测试用例 T-G3: 信息不足场景
- [√] 执行测试用例 T-G4: 幻觉检测

---

## 阶段4: 集成验证

### 4.1 端到端测试
- [√] 执行测试用例 T-INT1: 单公司财务数据查询(全流程)
- [√] 执行测试用例 T-INT2: 三家对比查询(全流程)
- [√] 执行测试用例 T-INT3: 域外问题拦截
- [√] 执行测试用例 T-INT4: Streamlit 界面验证

### 4.2 更新项目文档
- [√] 更新 `project_issues.md` 版本记录
- [√] 更新 `src/retrieval.py` 模块文档字符串

---

## 版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | -- | 初始任务清单 |
