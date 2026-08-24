# 项目质量与健壮性增强 Spec

## Why
当前项目已完成模型升级（Embedding v3、gte-rerank-v2 重排、qwen-max 生成），但在代码健壮性、功能完整性和可维护性方面仍有优化空间。本变更旨在系统性提升项目质量，降低线上故障风险，同时补齐对话记忆、表格检索等关键功能缺口。

## What Changes
- **健壮性增强**: API 调用增加超时控制、LLM 重试增加指数退避、日志术语修正
- **代码去重**: 提取公共工具函数（`_read_windows_env_var`、`get_api_key`）到 `src/utils.py`
- **对话记忆**: 支持多轮对话上下文，Streamlit 和 API 均支持对话历史
- **BM25 财经词典**: jieba 加载财经领域自定义词典，提升关键词检索精度
- **表格检索优化**: 对表格 Markdown 文本做结构化预处理，提升 Embedding 质量
- **代码质量**: 魔法数字常量化、来源摘要中移除无效的 `rerank_reasoning` 字段
- **对比查询优化**: 增大候选数量避免关键数据被截断，新增营收数据保底补充机制
- **查询改写增强**: 支持对话上下文传入，补全隐含的公司名、年份、指标等信息
- **检索日志增强**: 上下文片段内容预览，方便定位数据缺失问题

## Impact
- Affected specs: 无（新变更）
- Affected code: `src/retrieval.py`, `src/query_processor.py`, `src/api_service.py`, `src/ingestion.py`, `app_streamlit.py`, `src/utils.py`(新增), `config/financial_dict.txt`(新增), `src/conversation.py`(新增)

---

## ADDED Requirements

### Requirement: API 调用超时控制
所有 DashScope API 调用（Embedding、LLM、TextReRank）SHALL 设置合理的超时时间，防止网络异常导致请求无限挂起。

#### Scenario: LLM 生成超时
- **WHEN** dashscope.Generation.call 超过 60 秒未返回
- **THEN** 系统抛出超时异常，并记录日志

#### Scenario: Embedding API 超时
- **WHEN** dashscope.TextEmbedding.call 超过 30 秒未返回
- **THEN** 系统抛出超时异常，触发重试逻辑

#### Scenario: gte-rerank-v2 超时
- **WHEN** dashscope.TextReRank.call 超过 15 秒未返回
- **THEN** 系统回退到 hybrid 分数排序

### Requirement: 公共工具函数提取
项目中的 `_read_windows_env_var` 和 `get_api_key` 函数在多个模块中重复定义，SHALL 提取到 `src/utils.py` 统一管理。

#### Scenario: 统一 API Key 获取
- **WHEN** 任意模块调用 `from utils import get_api_key`
- **THEN** 获取到统一逻辑处理的 API Key（优先级：os.getenv → Windows 注册表 → .env）

#### Scenario: 各模块不再重复定义
- **WHEN** 检查 `retrieval.py`、`query_processor.py`、`pdf_mineru.py`、`ingestion.py`
- **THEN** 不再包含独立的 `_read_windows_env_var` 和 `get_api_key` 定义

### Requirement: 对话记忆
系统 SHALL 支持多轮对话，在生成答案时自动携带最近 N 轮对话历史作为上下文。

#### Scenario: 多轮追问
- **WHEN** 用户先问"中国移动2024年营收是多少"，然后追问"同比增速呢"
- **THEN** 系统能理解"同比增速"指的是中国移动2024年营收的同比增速

#### Scenario: 对话历史限制
- **WHEN** 对话轮次超过 5 轮
- **THEN** 系统只保留最近 5 轮对话，早期对话自动丢弃

#### Scenario: 新对话开始
- **WHEN** 用户点击"新对话"或发送完全不相关的新问题
- **THEN** 对话历史被清空，从零开始

### Requirement: BM25 财经自定义词典
系统 SHALL 在 jieba 分词时加载财经领域自定义词典，提升关键词检索精度。

#### Scenario: 财经术语分词
- **WHEN** 用户查询"归母净利润同比增长"
- **THEN** jieba 正确分词为 ["归母净利润", "同比", "增长"]，而非 ["归", "母", "净利润", "同比", "增长"]

#### Scenario: 词典外部化管理
- **WHEN** 需要新增财经术语
- **THEN** 只需编辑 `config/financial_dict.txt` 文件，无需修改代码

### Requirement: 表格文本结构化预处理
系统 SHALL 在 Embedding 前对表格 Markdown 文本做预处理，移除冗余的排版字符，保留结构化数据。

#### Scenario: 表格文本预处理
- **WHEN** 子块文本包含 Markdown 表格（`|---|---|` 格式）
- **THEN** 系统保留表格数据行的核心内容，移除冗余的列对齐符号

#### Scenario: 普通文本不受影响
- **WHEN** 子块文本不包含表格格式
- **THEN** 文本保持原样，不做任何预处理

### Requirement: 对比查询候选数量优化
对比查询模式下，系统 SHALL 增大每家公司候选数量和总候选上限，避免含关键财务数据的文档块被截断。

#### Scenario: 每家公司候选数量
- **WHEN** 对比查询涉及 N 家公司
- **THEN** 每家公司至少取 `max(10, HYBRID_TOP_K)` 条候选

#### Scenario: 总候选上限
- **WHEN** 对比查询合并 N 家公司的子查询结果
- **THEN** 总候选上限为 `max(HYBRID_TOP_K, N * per_company)`，确保所有公司候选都能进入重排

#### Scenario: 候选构建逻辑修复
- **WHEN** 构建候选列表时，某家公司第一条结果已加入
- **THEN** 该公司后续结果在总候选数未达上限前均可加入，不因 `HYBRID_TOP_K` 被过早截断

### Requirement: 营收数据保底补充
对比查询重排后，系统 SHALL 检查每家公司的结果是否包含营收数据，如不含则从全部候选中补充。

#### Scenario: 营收数据检测
- **WHEN** 重排后某家公司的结果中不含"营业收入为"、"营业收入达"、"营收为"等关键词
- **THEN** 系统标记该公司需要补充营收数据

#### Scenario: 营收数据补充
- **WHEN** 某家公司结果中无营收数据
- **THEN** 从全部候选（含未进入重排的）中查找第一条含营收关键词的文档块，追加到结果中

### Requirement: 检索上下文片段日志
系统 SHALL 在构建上下文时打印每条检索结果的内容摘要，方便定位数据缺失问题。

#### Scenario: 上下文片段日志
- **WHEN** 调用 `_build_context` 方法
- **THEN** 日志中打印每条上下文片段的公司名、来源文件、分数和文本前 80 字符

### Requirement: 查询改写支持对话上下文
查询改写 SHALL 支持传入对话上下文，补全用户查询中隐含的公司名、年份、指标等信息。

#### Scenario: 上下文依赖查询改写
- **WHEN** 用户先问"中国移动2024年营收是多少"，然后追问"那联通呢"
- **THEN** 改写后的查询为"中国联通2024年营收"，而非仅"联通"

#### Scenario: 无上下文时正常改写
- **WHEN** 用户查询无对话上下文
- **THEN** 查询改写正常执行，不依赖上下文信息

### Requirement: Streamlit 对话历史同步
Streamlit 界面 SHALL 将用户和助手的消息同步写入对话管理器，确保对话历史完整。

#### Scenario: 用户消息记录
- **WHEN** 用户在 Streamlit 界面提交查询
- **THEN** 调用 `conversation_manager.add_message("user", prompt)` 记录用户消息

#### Scenario: 助手消息记录
- **WHEN** 系统生成答案后
- **THEN** 调用 `conversation_manager.add_message("assistant", answer_summary)` 记录助手消息

#### Scenario: 域外问题拦截时记录
- **WHEN** 用户查询被判定为域外问题
- **THEN** 系统仍记录用户消息和拦截回复到对话历史

#### Scenario: 对比查询检索策略
- **WHEN** 用户发起对比查询（如"三家运营商营收对比"）
- **THEN** 检索时使用原始查询而非改写查询，避免改写查询丢失公司列表信息

---

## MODIFIED Requirements

### Requirement: 日志术语修正
系统日志和注释中残留的"LLM 重排"表述 SHALL 修正为"重排"或"gte-rerank-v2 重排"。

#### Scenario: 检索日志
- **WHEN** 查看 `retrieval.py` 第1135行日志
- **THEN** "阶段1: 混合检索 + LLM 重排" 改为 "阶段1: 混合检索 + gte-rerank-v2 重排"

### Requirement: 来源摘要字段清理
`_build_sources_summary` 方法中 SHALL 移除始终为空的 `rerank_reasoning` 和 `rerank_key_info` 字段（gte-rerank-v2 不提供此信息）。

#### Scenario: 来源摘要返回
- **WHEN** 调用 `_build_sources_summary` 方法
- **THEN** 返回的 scores 字典中不再包含 `rerank_reasoning` 和 `rerank_key_info` 字段

### Requirement: LLM 调用指数退避重试
`ingestion.py` 中 `get_embeddings_with_retry` 的指数退避策略 SHALL 与 `query_processor.py` 中的 LLM 调用保持一致。

#### Scenario: Embedding API 重试
- **WHEN** Embedding API 调用失败
- **THEN** 按 1s、2s、4s 的间隔重试，最多 3 次，记录每次重试的原因

### Requirement: API 接口响应增强
`/api/query` 接口 SHALL 在响应中增加 `processing_time` 和 `conversation_id` 字段。

#### Scenario: 处理时间返回
- **WHEN** 调用 `/api/query` 接口
- **THEN** 响应中包含 `processing_time`（秒）和 `conversation_id`（对话标识）

---

## REMOVED Requirements
无移除的需求。