# 验证清单: 项目质量与健壮性增强

> 编码: UTF-8
> 变更: quality-robustness-enhancement

---

## 阶段1: 公共工具函数提取

- [x] `src/utils.py` 文件已创建，包含 `_read_windows_env_var` 和 `get_api_key` 函数
- [x] `src/retrieval.py` 不再包含独立的 `_read_windows_env_var` 和 `get_api_key` 定义
- [x] `src/query_processor.py` 不再包含独立的 `_read_windows_env_var` 和 `get_api_key` 定义
- [x] `src/ingestion.py` 不再包含独立的 `_read_windows_env_var` 和 `get_api_key` 定义
- [x] `src/pdf_mineru.py` 不再包含独立的 `_read_windows_env_var` 和 `get_api_key` 定义
- [x] 所有模块导入 `from utils import get_api_key` 无报错

## 阶段2: API 调用超时控制

- [x] `_generate_answer` 中 `dashscope.Generation.call` 设置了 timeout=60
- [x] `_gte_rerank` 中 `dashscope.TextReRank.call` 设置了 timeout=15，超时回退到 `_fallback_rerank`
- [x] `_get_query_embedding` 中 `dashscope.TextEmbedding.call` 设置了 timeout=30
- [x] `query_processor.py` 中 `_call_llm` 设置了 timeout=30
- [x] `ingestion.py` 中 `get_embeddings_batch` 设置了 timeout=30
- [x] 正常查询场景下所有 API 调用正常完成

## 阶段3: 日志术语与字段清理

- [x] retrieval.py 第1135行日志已修正为"阶段1: 混合检索 + gte-rerank-v2 重排"
- [x] 全项目搜索"LLM 重排"无残留（除历史文档/提案中的合理引用）
- [x] `_build_sources_summary` 返回的 scores 字典不再包含 `rerank_reasoning`
- [x] `_build_sources_summary` 返回的 scores 字典不再包含 `rerank_key_info`
- [x] `vector` 和 `bm25` 字段在存在时正确添加，不存在时不添加
- [x] Streamlit 界面来源展示正常

## 阶段4: BM25 财经自定义词典

- [x] `config/financial_dict.txt` 已创建，包含 27 个常用财经术语
- [x] `BM25Retriever` 在 `load` 方法中加载了 `jieba.load_userdict`
- [x] `ingestion.py` 的 `build_bm25_index` 在分词前加载了词典
- [x] "归母净利润同比增长" 分词结果为 ["归母净利润", "同比增长"]
- [x] "扣非净利润" 分词结果为 ["扣非净利润"]，不拆分为 ["扣", "非", "净利润"]
- [x] 加载词典后不破坏已有分词结果

## 阶段5: 表格文本预处理

- [x] `preprocess_table_text` 函数已实现
- [x] Markdown 表格的分隔行被正确移除
- [x] 表格数据行中的 `|` 被替换为空格，保持可读性
- [x] 非表格文本不做任何修改
- [x] Embedding 输入文本经过预处理，原始文本存储不受影响
- [x] 含表格的查询检索命中率有提升

## 阶段6: 对话记忆

- [x] `src/conversation.py` 文件已创建，包含 `ConversationManager` 类
- [x] `add_message(role, content)` 正确添加消息
- [x] `get_history(max_turns=5)` 正确返回最近 N 轮对话
- [x] `clear()` 正确清空对话历史
- [x] `get_context_string()` 生成正确的上下文文本
- [x] `RAGGenerator` 支持传入 `ConversationManager` 实例
- [x] Prompt 模板中注入了对话历史上下文
- [x] Streamlit 界面显示"新对话"按钮
- [x] `/api/query` 支持 `conversation_id` 参数
- [x] 响应中包含 `processing_time` 和 `conversation_id` 字段

## 阶段8: 对比查询候选数量优化

- [x] `_search_comparison` 中 `per_company` 已改为 `max(10, HYBRID_TOP_K)`
- [x] `comparison_candidates_limit` 已定义为 `max(HYBRID_TOP_K, len(mentioned_companies) * per_company)`
- [x] 候选构建 `elif` 条件已改为 `< comparison_candidates_limit`
- [x] 对比查询候选数从 20 增加到 60（3家公司 x 20条）
- [x] 中国电信含营收数字文档块（排名#10、#16、#20）不再被截断

## 阶段9: 营收数据保底补充

- [x] `_ensure_numeric_data_coverage` 方法已实现
- [x] 营收关键词列表包含 ["营业收入为", "营业收入达", "营收为", "营收达", "营业收入人民币", "营业收入达到", "全年营业收入"]
- [x] 重排后按公司分组检查是否含营收数据
- [x] 不含时从 `all_scored` 中补充含营收关键词的文档块
- [x] 子查询截断后也检查并补充含关键财务数据的文档块
- [x] 对比查询三家公司结果均含营收数据

## 阶段10: 检索上下文片段日志

- [x] `_build_context` 中每条上下文片段打印内容摘要
- [x] 日志包含公司名、来源文件、rerank分数、文本前80字符
- [x] 日志格式清晰，方便定位数据缺失原因

## 阶段11: 查询改写支持对话上下文

- [x] `REWRITE_PROMPT_TEMPLATE` 已新增 `{context_section}` 占位符
- [x] `_rewrite_query()` 已新增 `conversation_context` 参数
- [x] `process()` 已新增 `conversation_context` 参数
- [x] "那联通呢" 结合上下文改写为 "中国联通2024年营收"
- [x] 无上下文时查询改写正常执行

## 阶段12: Streamlit 对话历史同步

- [x] 用户提交查询后调用 `conversation_manager.add_message("user", prompt)`
- [x] 系统生成答案后调用 `conversation_manager.add_message("assistant", answer_summary)`
- [x] 域外问题拦截时也记录用户消息和拦截回复
- [x] 调用 `process()` 时传入 `conversation_context`
- [x] 对比查询使用原始查询进行检索
- [x] 非对比查询使用改写查询进行检索
- [x] 多轮对话上下文正确传递
- [x] "新对话"按钮清空对话历史

## 阶段13: 集成验证

- [x] 对比查询"三家运营商营收对比"三家公司数据均正确返回
- [x] 中国电信 5,236亿元、中国移动 10,408亿元、中国联通 3,896亿元
- [x] 单公司财务数据查询全流程无异常
- [x] 域外问题正确拦截
- [x] 文档 `docs/RAG搭建笔记_从文档解析到智能问答.md` 已更新