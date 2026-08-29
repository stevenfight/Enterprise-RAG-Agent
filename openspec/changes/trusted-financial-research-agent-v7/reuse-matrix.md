# v7.0 函数级复用矩阵

## 使用规则

- 本矩阵是实施前约束，不是建议清单。开发每个任务前先定位对应行；未列出的替换或重写必须先补充 OpenSpec 并说明原因。
- “保留”表示不改变既有函数语义；“扩展”只增加可选字段或旁路；“适配”表示旧入口继续存在、内部调用新服务；“集中”表示把分散规则迁移到唯一所有者并保留兼容调用。
- 新增符号均为规划名称，实施时可因代码审查调整，但其职责边界不得改变。
- 多模态不复制 PDF 上传、MinerU 解析、文本切分、混合检索、来源响应或前端证据组件。

## 后端与数据链复用矩阵

| 新需求 | 现有文件 / 符号 | 当前职责 | 决策 | 允许的最小改动 | 禁止重复建设 | 必须保留的回归 |
|---|---|---|---|---|---|---|
| PDF 清单与上传 | `src/knowledge_service.py::get_documents/upload_pdf` | 文件枚举、PDF 校验、大小限制、文件名安全；当前同名目标会直接写入 | 开关内适配 | 保留旧校验和响应；v7 路径增加同文件系统 staging、关闭后校验/哈希、不可变 blob 与逻辑/内容版本登记 | 第二套上传 API；继续同名覆盖；在源 PDF 上清洗 | 开关关闭时原响应不变；非法文件、路径安全、失败无半成品版本 |
| PDF 删除 | `src/knowledge_service.py::delete_pdf` | 当前只删除原始 PDF，未清理索引 | 开关内适配 | 先逻辑不可见，再幂等清理派生产物；共享 blob 按引用计数和保留期回收 | 未失效索引即宣称删除完成；误删其他逻辑文档共享 blob | 旧删除结果；新路径无孤儿引用且在途请求语义明确 |
| MinerU 转换 | `src/pdf_mineru.py::_extract_single` | VLM PDF→Markdown，已启用表格与公式 | 保留并旁路扩展 | 按 `REUSE/ENRICH/TARGETED_REEXTRACT/FULL_REEXTRACT` 决策复用或处理；记录页批次完整性 | 重新实现整套 PDF 解析器；无差别重跑 MinerU/OCR/VLM | 现有 Markdown 结果；失败页段不可伪装完整；源 PDF 哈希不变 |
| 大 PDF 分批 | `src/pdf_mineru.py::_process_large_pdf` | 按页批次解析和合并 | 扩展状态 | 保留原批处理逻辑，额外记录成功/失败页段 | 静默忽略失败批次后标记完整 | 既有大文档流程；不完整状态可见 |
| 页数与页图 | PyMuPDF（现有依赖）与规划 `PageRenderer` | 当前用于页数/文本定位，尚无统一页图服务 | 新增集中能力 | 以文档哈希和页码生成可复用页图、缩略图和规范化坐标 | 引入第二个 PDF 渲染包；每次请求重复渲染 | 相同输入制品 ID 稳定、旋转页坐标准确 |
| 文本页码 | `src/text_splitter.py::build_line_page_map` | Markdown 行到 PDF 页码的近似映射 | 保留 | 文本证据继续使用；视觉证据使用独立精确定位 | 改写为 bbox 真值；把近似页码包装成精确坐标 | 现有切分和页码测试 |
| 文本切分 | `split_markdown_file/split_markdown_reports` | Markdown 分块与元数据 | 适配 | 给文本块增加可选 artifact 引用 | 为视觉文本另建完全独立分块系统 | 现有 chunk ID、检索召回 |
| 索引构建 | `src/ingestion.py::build_bm25_index/build_faiss_index/build_company_index` | 生成 BM25、FAISS 和 metadata；当前 rebuild 先删旧目录，embedding 失败会补零向量 | 兼容扩展 | 首轮为全部 active 文档构建新 generation 并重算无版本证据的 embedding；后续以完整缓存键复用；视觉摘要走同一索引 | 第二套向量库；原地覆盖 active；直接导入无法证明兼容的旧向量；把零向量记为成功 | 旧 CLI 与目录读取；新代际失败不影响 active；请求代际固定 |
| 文档—报告溯源 | 规划 `V7MetadataStore` 与现有 SourceInfo/EvidenceBundle | 当前已有回答级来源，但无完整文档版本→制品→事实→声明→计算→报告外键链 | 新增关系表 | 使用明确 join table、稳定 ID、版本与外键约束；由现有证据入口消费 | 通用三元组库、图数据库、平行证据模型 | 旧来源字段兼容；已发布关系无悬空引用 |
| 表格检索文本 | `src/retrieval.py::preprocess_table_text` | 表格扁平化以利 embedding | 保留 | 结构化表格另存，扁平文本只做检索描述 | 把扁平文本当单元格事实真值 | 现有表格召回结果 |
| 向量/BM25/混合检索 | `VectorRetriever/BM25Retriever/HybridRetriever` | 文本召回、融合、重排 | 扩展元数据 | 索引视觉制品的文本描述和 artifact ID，继续走原检索链 | 第二套视觉专用检索 API 或融合算法 | 文本路径指标不下降 |
| 来源权威度 | `src/retrieval.py::_compute_source_authority_boost` | 年报等来源加权 | 集中 | 抽取为统一 `SourceAuthorityPolicy`，原函数改为兼容调用 | 在冲突裁决、多模态各写一套权重常量 | 原排序；同一来源在各模块结论一致 |
| 文本模型调用 | `src/llm_provider.py::BaseLLMProvider.chat` 及实现 | 纯文本消息与用量 | 保留 | 不改变消息类型和文本调用语义 | 把图片路径混入文本 message；改变旧响应格式 | 现有模型 Provider 测试 |
| 视觉模型调用 | 规划 `src/multimodal/vision_provider.py::BaseVisionProvider` | 类型化图片、区域、任务和结构化响应 | 新增集中能力 | 复用现有认证/配置读取方式，单独声明视觉模型能力 | 每个解析器直接调用厂商 SDK；模型不可用时静默文本猜测 | 明确 unavailable/incomplete；用量可审计 |
| 人工核验事实 | `VerifiedFinancialFactRegistry` 公共方法 | 三大运营商 2024 固定事实 | 适配 | 内部转为 `FinancialFactService`，保留公共方法 | 删除硬编码兼容入口；新建平行注册表 | 旧比较答案和图表制品 |
| 数字、单位与币种 | `VerifyTool._extract_numbers/_scale_to_unit`、`Reflector._extract_numbers_from_text/_scale_to_unit` | 两处已有文本数字提取和单位换算 | 集中 | 将公共规则迁移至 `src/financial_trust/normalization.py`，两个旧类均以兼容方法调用 | 保留两套 UNIT_MULTIPLIERS；新增视觉专用换算表 | VerifyTool 与 Reflector 既有输出及边界 |
| 确定性计算 | `calc_yoy_growth/calc_cagr/calc_margin/calc_pct_change`、`CalculatorTool.run` | 财务公式计算与工具入口 | 扩展 | 新入口增加事实 ID、公式版本和证据，旧参数逻辑保留 | 用 LLM 重算；复制公式到报告层 | 原计算结果和异常边界 |
| 图表生成 | `ChartTool._render_chart` | 从结构化数据生成图表 | 保留并复用输出 | 视觉图表理解结果可转换为其数据结构用于展示 | 把图表生成误当图表识别；重写绘图库 | 原图表列表与渲染 |
| 回答来源模型 | `src/api_service.py::SourceInfo/_build_agent_answer_sources` | 后端统一来源响应 | 可选字段扩展 | 增加 `evidence_type/page_image_url/bbox/artifact_id`，其中 URL 只能由 artifact ID 生成，缺省时旧 JSON 不变 | 新建不兼容的 VisualSource 响应；返回本地绝对路径 | 旧 `/api/query`、Agent API、SSE 格式 |
| 视觉制品读取 | `APIAuthMiddleware` 与规划 `api_artifact_image` | 现有 API 认证；目前只挂载图表静态目录 | 新增受控端点 | 通过 artifact ID 查询清单、校验文档关联后返回页图/区域图，支持缓存头 | 把制品目录直接 StaticFiles 暴露；接受用户文件路径 | 越权/遍历被拒绝，合法来源可预览 |
| Agent/模型配置 | `src/api_service.py::_load_agent_config` 与现有 YAML 配置 | 加载角色模型、工具和路由配置 | 适配 | 增加独立 multimodal 配置段和能力校验，旧字段缺省行为不变 | 视觉模块自行读取另一份密钥/配置 | 旧配置可启动、文本模型选择不变 |
| 旧即时问答 API | `api_query/api_agent_query/api_agent_stream/api_retrieve` | 现有同步与流式问答 | 保留 | 仅消费增强来源；研究任务使用新端点 | 破坏旧参数或强制走持久任务 | v5.19 API 契约 |
| 来源完整性反思 | `src/reflector.py::_check_source_completeness/check_hallucination` | 依据回答和来源检查数字支持 | 适配 | 消费增强 SourceInfo/VisualEvidence，继续保留文本检查 | 另建视觉专用“幻觉分数”替代 A 评测 | 原反思结果；视觉未解析不得计为支持 |
| 工具检索入口 | `src/tools/retrieve_tool.py::_resolve_vector_db_dir/run` | Agent 工具访问现有向量库 | 保留 | 通过原索引读取含 artifact 元数据的结果 | 新增 VisualRetrieveTool 复制检索 | 原工具参数、输出和目录解析 |
| 对比检索入口 | `src/tools/compare_tool.py` 内部 `HybridRetriever` | CompareTool 独立延迟缓存检索器 | 适配 | 与 RAGGenerator/RetrieveTool 共同通过 `PublicationResolver` 固定请求发布快照 | 只刷新其中一个 Retriever 缓存 | 对比工具原参数和结果；发布快照一致 |
| 任务记忆 | `AgentMemory` | 会话与工作记忆持久化 | 保留 | 只通过 task ID 关联新检查点 | 用任务状态覆盖会话记忆 | 原会话恢复行为 |
| 多 Agent 共享上下文 | `SharedMemory` | 单次运行上下文和 Agent 结果 | 适配 | Checkpoint 只保存可序列化快照或稳定 ID | 直接序列化 Agent/队列/线程对象 | 原 DAG 汇总和 token 统计 |
| 规划与编排 | `PlannerAgent/OrchestratorAgent` 和现有 DAG | 计划、Worker 协作与路由 | 扩展步骤边界 | 在步骤前后挂接检查点、审计和制品引用 | 整体迁移 LangGraph；新增无评测收益角色 | single/multi 既有结果和流式事件 |
| 追踪与评测 | `src/monitoring.py`、`tests/eval_langsmith.py`、`tests/eval_openevals.py` | 追踪及少量评测入口 | 适配 | 新 Runner 提供统一结果，现有脚本调用它 | 平行指标实现；强制依赖未锁定 openevals | 无密钥核心评测可独立运行 |

## 前端复用矩阵

| 新需求 | 现有文件 / 符号 | 决策 | 最小改动 | 禁止事项 | 回归重点 |
|---|---|---|---|---|---|
| 来源类型 | `frontend/src/types/chat.ts::SourceInfo` | 可选字段扩展 | 与后端增加相同视觉字段 | 新建第二套来源类型 | 旧消息可反序列化 |
| 声明与证据聚合 | `buildEvidenceBundles` | 扩展 | 把 artifact、事实和声明按稳定 ID 聚合 | 另建视觉 EvidenceBundle | 旧 bundle 顺序与引用 |
| 证据链 | `buildEvidenceChain` | 扩展 | 视觉来源仍进入同一声明链 | 单独的视觉证据图 | 旧引用解析 |
| 证据抽屉 | `EvidencePanel` | 扩展 | 加页图预览、区域高亮和不完整警告 | 重写证据面板 | 空来源、关闭、键盘行为 |
| 来源卡片 | `SourceCard` | 扩展 | 增加证据类型、页图入口和定位状态 | 改变旧评分展示 | 旧字段缺省显示 |
| 证据关系图 | `EvidenceChainGraph` | 扩展 | 同图展示文本、表格、图表节点 | 新图组件复制关系算法 | 点击来源定位 |
| 生成图表展示 | 现有 Charts 页面与图表组件 | 复用 | 展示识别后的结构化系列和来源标识 | 用截图替代可访问图表 | 暗色模式、表格视图 |
| 研究任务布局 | `PageShell/PageHeader`、DAG 组件 | 复用 | 新页组合既有布局和状态组件 | 修改所有稳定页面样式 | 旧路由、响应式、可访问性 |

## 唯一所有者边界

| 规则或数据 | 唯一所有者 | 其他模块使用方式 |
|---|---|---|
| 数值、单位、币种、期间归一 | `src/financial_trust/normalization.py` | VerifyTool、表格/图表提取、冲突引擎均调用，不复制映射 |
| 来源权威度 | `SourceAuthorityPolicy` | 检索排序和冲突裁决调用同一策略 |
| 多模态制品清单与完整性 | `DocumentAssetManifest` | 解析、索引、API、删除流程只通过服务访问 |
| 视觉模型调用 | `BaseVisionProvider` | 表格、图表、扫描页解析器提交类型化请求 |
| 金融事实真值 | `FinancialFactService` | 人工事实、文本抽取和视觉抽取均写入同一模型 |
| 回答级来源契约 | 现有 `SourceInfo` 的向后兼容扩展 | 文本和视觉证据共享同一响应结构 |
| 任务状态 | ResearchTask/Checkpoint Store | AgentMemory 与 SharedMemory 不承担持久任务真值 |
| v7 元数据与迁移 | `V7MetadataStore` | FinancialFact、manifest、task、tool invocation、audit 使用同一版本化 SQLite 与分仓储接口 |
| 发布集合与索引代际 | `PublicationSet/PublicationResolver/IndexGenerationManager` | ingestion 构建不可变 generation；RAGGenerator、RetrieveTool、CompareTool、artifact/fact 查询固定同一 publication；SQLite active publication 是唯一真值 |
| 源文档身份与物理 blob | `DocumentVersionRepository/SourceBlobStore` | 上传、manifest、删除与索引仅引用不可变 document_version；物理 blob 去重不合并 logical document |
| 处理决策 | `DocumentProcessingDecisionService` | MinerU、页图、视觉提取和索引只执行有证据的 REUSE/ENRICH/TARGETED_REEXTRACT/FULL_REEXTRACT 决策 |
| 审计溯源关系 | `ProvenanceRepository` | Fact、Claim、Calculation、Report 通过明确外键和 join table 读写，不自行维护关系副本 |

## 变更审批触发条件

出现以下任一情况时停止实现并先更新规格：需要替换现有公共函数；需要新增与矩阵中“唯一所有者”重叠的服务；需要安装新 Python 包；需要更改旧 API 必填字段；需要让视觉模型处理全部页面而没有路由与成本基线；需要从近似页码推断精确 bbox；需要修改源 PDF；需要复用缺少完整版本证据的旧向量；需要引入图数据库或通用知识图谱。
