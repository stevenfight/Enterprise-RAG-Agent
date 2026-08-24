# 实现任务清单: 项目质量与健壮性增强

> 编码: UTF-8
> 变更: quality-robustness-enhancement
> 状态: 已完成

---

## 阶段1: 公共工具函数提取 (P2)

### 1.1 创建 src/utils.py
- [x] 新建 `src/utils.py`，将 `_read_windows_env_var` 和 `get_api_key` 提取为公共函数
- [x] 函数签名与原有实现保持一致，日志前缀使用 `[utils]`

### 1.2 更新各模块导入
- [x] `src/retrieval.py`: 删除本地的 `_read_windows_env_var` 和 `get_api_key`，改为 `from utils import get_api_key`
- [x] `src/query_processor.py`: 同上
- [x] `src/ingestion.py`: 同上
- [x] `src/pdf_mineru.py`: 同上（使用 `get_api_key("MINERU_API_KEY")`）

### 1.3 验证
- [x] 执行 `python -c "from utils import get_api_key; print('OK')"`
- [x] 确认各模块导入无报错

---

## 阶段2: API 调用超时控制 (P0)

### 2.1 retrieval.py 超时控制
- [x] `_generate_answer` 方法中 `dashscope.Generation.call` 增加 timeout=60
- [x] `_gte_rerank` 方法中 `dashscope.TextReRank.call` 增加 timeout=15，超时回退到 `_fallback_rerank`
- [x] `_get_query_embedding` 方法中 `dashscope.TextEmbedding.call` 增加 timeout=30

### 2.2 query_processor.py 超时控制
- [x] `_call_llm` 方法中 LLM 调用增加 timeout=30

### 2.3 ingestion.py 超时控制
- [x] `get_embeddings_batch` 中 Embedding 调用增加 timeout=30

### 2.4 验证
- [x] 正常查询场景下各 API 调用正常完成
- [x] TDD 测试通过（43/44 PASS）

---

## 阶段3: 日志术语与字段清理 (P1)

### 3.1 retrieval.py 日志修正
- [x] 第1135行: "阶段1: 混合检索 + LLM 重排" → "阶段1: 混合检索 + gte-rerank-v2 重排"
- [x] 检查其他位置是否有类似"LLM 重排"表述

### 3.2 _build_sources_summary 字段清理
- [x] 移除 `rerank_reasoning` 和 `rerank_key_info` 字段
- [x] 保留 `vector` 和 `bm25` 可选字段（条件性添加）

### 3.3 验证
- [x] 检查 `_build_sources_summary` 返回的 scores 字典不再包含无效字段
- [x] 确认 Streamlit 界面的来源展示不受影响

---

## 阶段4: BM25 财经自定义词典 (P1)

### 4.1 创建财经词典文件
- [x] 新建 `config/financial_dict.txt`，包含常用财经术语
- [x] 术语覆盖：归母净利润、扣非净利润、营业收入、同比增长、环比增长、产能利用率、资产负债率、净资产收益率、经营活动现金流、自由现金流、EBITDA、市盈率、市净率等

### 4.2 修改 BM25Retriever 加载词典
- [x] 在 `BM25Retriever.load` 方法中调用 `jieba.load_userdict`
- [x] 在 `ingestion.py` 的 `build_bm25_index` 中调用 `jieba.load_userdict`

### 4.3 验证
- [x] 测试财经术语分词效果："归母净利润同比增长" → ["归母净利润", "同比增长"]
- [x] 确保不破坏已有分词结果

---

## 阶段5: 表格文本预处理 (P1)

### 5.1 实现表格预处理函数
- [x] 在 `src/retrieval.py` 中实现 `preprocess_table_text(text)` 函数
- [x] 识别 Markdown 表格格式
- [x] 移除分隔行，保留表头和数据行
- [x] 将表格数据行中的 `|` 替换为空格

### 5.2 嵌入 Embedding 流程
- [x] 在 `VectorRetriever._get_query_embedding` 中对查询文本做预处理
- [x] 在 `get_embeddings_batch`（ingestion.py）中对子块文本做预处理
- [x] 预处理仅用于 Embedding 输入，不影响原始文本存储

### 5.3 验证
- [x] 测试表格 Markdown 文本预处理前后对比
- [x] 确保普通文本不受影响

---

## 阶段6: 对话记忆 (P1)

### 6.1 实现对话历史管理器
- [x] 新建 `src/conversation.py`，实现 `ConversationManager` 类
- [x] 支持 `add_message(role, content)` 添加消息
- [x] 支持 `get_history(max_turns=5)` 获取最近 N 轮对话
- [x] 支持 `clear()` 清空对话历史
- [x] 支持 `get_context_string()` 生成注入 Prompt 的对话历史文本

### 6.2 修改 RAGGenerator 集成对话历史
- [x] `RAGGenerator` 构造函数接受可选的 `ConversationManager` 参数
- [x] `_build_xxx_prompt` 方法在 Prompt 中注入对话历史上下文
- [x] 在 Prompt 中增加指令："如果用户问题省略了主语或上下文，请参考对话历史理解"

### 6.3 修改 Streamlit 界面
- [x] `app_streamlit.py` 中创建 `ConversationManager` 实例
- [x] 每次问答后调用 `add_message` 记录对话
- [x] 添加"新对话"按钮，点击后调用 `clear()`
- [x] 在 sidebar 显示对话历史摘要

### 6.4 修改 API 接口
- [x] `/api/query` 接口支持可选的 `conversation_id` 参数
- [x] 服务端维护 `conversation_id → ConversationManager` 映射
- [x] 响应中返回 `conversation_id` 和 `processing_time`

### 6.5 验证
- [x] 导入验证通过
- [x] API 接口支持 conversation_id

---

## 阶段7: 集成验证 (P2)

### 7.1 端到端测试
- [x] 执行 TDD 测试脚本 `tests/tdd_all_optimizations.py`（43 PASS, 1 FAIL 为预存耗时问题）
- [x] 单公司财务数据查询全流程
- [x] 多公司对比查询全流程
- [x] 域外问题拦截

### 7.2 文档更新
- [x] 更新 `docs/RAG搭建笔记_从文档解析到智能问答.md` 中新增功能相关内容
- [x] 更新 `openspec/changes/model-upgrade/project_issues.md` 版本记录

---

## 阶段8: 对比查询候选数量优化 (P0)

### 8.1 增大 per_company
- [x] `_search_comparison` 中 `per_company` 从 `max(5, HYBRID_TOP_K // len)` 改为 `max(10, HYBRID_TOP_K)`
- [x] 确保每家公司子查询返回足够多的候选，避免含关键数据的文档块被截断

### 8.2 增大总候选上限
- [x] 新增 `comparison_candidates_limit = max(HYBRID_TOP_K, len(mentioned_companies) * per_company)`
- [x] 3家公司各20条时，候选上限从20增加到60

### 8.3 修复候选构建逻辑
- [x] `elif len(candidates) < HYBRID_TOP_K` 改为 `< comparison_candidates_limit`
- [x] 避免某家公司后续结果因总候选数达20而被过早截断

### 8.4 验证
- [x] 对比查询"三家运营商营收对比"候选数从20增加到60
- [x] 中国电信含营收数字文档块（排名#10、#16、#20）不再被截断
- [x] 三家公司数据均正确返回

---

## 阶段9: 营收数据保底补充 (P0)

### 9.1 实现 _ensure_numeric_data_coverage 方法
- [x] 在 `retrieval.py` 中新增 `_ensure_numeric_data_coverage` 方法
- [x] 定义营收关键词列表：["营业收入为", "营业收入达", "营收为", "营收达", "营业收入人民币", "营业收入达到", "全年营业收入"]
- [x] 按公司分组检查重排后结果是否含营收数据

### 9.2 营收数据补充逻辑
- [x] 某家公司结果中无营收数据时，从 `all_scored` 中查找含营收关键词的文档块
- [x] 找到后追加到结果中，避免该公司数据缺失
- [x] 补充后打印日志，记录补充条数和公司名

### 9.3 子查询财务数据保底
- [x] `_search_comparison` 中截断后检查是否含关键财务数据
- [x] 不含则从 `merged[per_company:]` 中补充含数字和财务关键词的文档块
- [x] 最多补充2条，避免过多无关数据进入结果

### 9.4 验证
- [x] 对比查询重排后，三家公司结果均含营收数据
- [x] 中国电信 5,236亿元、中国移动 10,408亿元、中国联通 3,896亿元 均正确提取
- [x] 保底补充日志正确打印

---

## 阶段10: 检索上下文片段日志 (P1)

### 10.1 _build_context 日志增强
- [x] `_build_context` 方法中，每条上下文片段打印内容摘要
- [x] 日志格式：公司名、来源文件、rerank分数、文本前80字符
- [x] 方便快速定位某家公司数据缺失的原因

### 10.2 验证
- [x] 日志中正确打印6条上下文片段的内容摘要
- [x] 文本预览长度约80字符，不影响日志可读性

---

## 阶段11: 查询改写支持对话上下文 (P1)

### 11.1 REWRITE_PROMPT_TEMPLATE 改造
- [x] Prompt 模板新增 `{context_section}` 占位符
- [x] 有上下文时注入对话历史和改写指令
- [x] 无上下文时显示"（无对话上下文）"

### 11.2 _rewrite_query 方法改造
- [x] 新增 `conversation_context` 参数，默认空字符串
- [x] 根据是否有上下文构建不同的 `context_section`
- [x] 打印日志记录上下文长度

### 11.3 process 方法改造
- [x] 新增 `conversation_context` 参数，默认空字符串
- [x] 调用 `_rewrite_query` 时传入 `conversation_context`
- [x] 更新函数文档注释

### 11.4 验证
- [x] "那联通呢" 结合上下文改写为 "中国联通2024年营收"
- [x] 无上下文时查询改写正常执行

---

## 阶段12: Streamlit 对话历史同步 (P1)

### 12.1 用户消息记录
- [x] 用户提交查询后，调用 `conversation_manager.add_message("user", prompt)`
- [x] 在 `query_processor.process()` 之前记录，确保上下文完整

### 12.2 助手消息记录
- [x] 系统生成答案后，调用 `conversation_manager.add_message("assistant", answer_summary)`
- [x] 域外问题拦截时也记录拦截回复

### 12.3 对话上下文传入
- [x] 调用 `process()` 时传入 `conversation_context = conversation_manager.get_context_string(max_turns=3)`
- [x] 确保查询改写能利用对话历史

### 12.4 对比查询检索策略
- [x] 对比查询（intent="comparison"）使用原始查询进行检索
- [x] 非对比查询使用改写查询进行检索
- [x] 避免改写查询丢失公司列表信息

### 12.5 验证
- [x] 多轮对话上下文正确传递
- [x] 对话历史在 sidebar 正确显示
- [x] "新对话"按钮清空对话历史

---

## 版本记录

| 版本 | 轮次 | 说明 |
|------|------|------|
| v1.0 | 第二轮 | 初始任务清单 |
| v1.1 | 第二轮 | 全部任务完成，TDD 43/44 PASS |
| v1.2 | 第三轮 | 新增对比查询优化、营收数据保底、查询改写对话上下文、Streamlit 对话同步 |