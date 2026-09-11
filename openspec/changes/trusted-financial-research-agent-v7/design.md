# 设计：v7.0 可信金融研究 Agent

## 设计原则

1. 先评测后优化：所有重要能力必须先有失败样本和基线。
2. 事实与解释分离：程序负责事实、单位、公式和状态，LLM 负责语义理解与表达。
3. 原始值不可丢失：归一化、裁决和报告不能覆盖来源原文。
4. 会话记忆与任务状态分离：`AgentMemory` 保持既有语义，新建任务检查点层。
5. 复用现有接口：通过适配器扩展 `VerifiedFinancialFactRegistry`、工具结果、证据链和 DAG，不直接移除旧逻辑。
6. 有副作用才审批：只读检索与纯计算默认可自动执行，高风险或外部写操作必须审批。
7. 评测门禁分层：无密钥确定性核心集进入每次 CI；有密钥全量语义评测进入手动或受控发布工作流。
8. 多模态按需路由：优先复用 MinerU 现有结构与图片，纯文本页不调用视觉模型，低置信和能力不可用均显式失败。
9. 单一事实真值：文本、表格和图表最终都进入同一 FinancialFact、归一器、冲突规则和 SourceInfo，不建立平行视觉事实体系。
10. 代际构建而非原地覆盖：索引、schema 和制品先在不可见代际中完成校验，再原子激活；任何失败不得破坏当前可用版本。
11. 小步可运行：B、M、C 先完成一条纵向试点链，再扩展类别和页面；未完成能力通过默认关闭的显式 feature flag 隔离。
12. 源文件不可变：上传校验完成后的 PDF 只读保存，任何清洗、裁剪、重识别和索引均生成派生版本，不反写源文件。
13. 关系优先于图：先用带外键和版本的明确关系表完成可审计溯源；没有多跳评测收益证据时不引入知识图谱。

## 公共持久化与版本策略

B 阶段先建立供 B/M/C/D 共用的 `V7MetadataStore` 抽象，首版使用标准库 `sqlite3` 和单一版本化数据库。事实、制品清单、任务检查点、工具调用账本和审计事件使用不同表与仓储接口，但共享 schema migration、事务、外键、WAL、busy timeout 和备份规则，避免每个阶段各建一套 SQLite/JSON 真值。

发布真值同样位于 `V7MetadataStore`。`PublicationSet` 用一个 `publication_id` 固定索引 generation、可见 document version 集合、artifact/fact 版本边界和语料 revision。索引文件在事务外构建并保持不可变，发布只在短 SQLite 事务内校验 expected active publication/revision、插入发布集合并切换 active publication；文件指针可作诊断缓存，但不能成为真值。

数据库迁移必须具备 `schema_migrations`、顺序版本、重复执行幂等、失败回滚和启动前备份。新代码只能读取当前版本或明确支持的旧版本；遇到更高未知版本必须拒绝启动写路径，禁止自动降级或重建。用户原 PDF、旧向量索引和 AgentMemory 不迁入新库，也不被破坏。

功能开关包括 `financial_trust_enabled`、`durable_execution_enabled`、`multimodal_enabled`、`research_tasks_enabled`，默认均为 false。依赖关系为：multimodal 依赖 financial_trust 与 durable_execution，research_tasks 依赖 financial_trust 与 durable_execution；依赖未显式开启时配置校验失败，不自动连带启用。开关关闭时旧 API 和旧数据链完全不经过未完成的新实现；开关开启但配置、schema、provider 或索引代际无效时必须 fail closed，并返回可诊断 unavailable，不得使用默认模型或旧逻辑伪装成功。现有 `_load_agent_config()` 的历史回退行为暂不改，但 v7 新配置使用独立严格校验器。

实施前冻结 v5.19 的 OpenAPI、关键 JSON 响应、配置样例、索引 registry/metadata 和数据库不存在时行为，作为兼容夹具。每个阶段只在开关后增加可选字段或新端点，并对开关开/关分别回归。

## 目标架构

```text
用户/研究工作台
       │
       ▼
ResearchTask API ───────────────► 审批/暂停/恢复/取消
       │
       ▼
任务状态机 + Checkpoint Store
       │
       ▼
现有 Planner / Orchestrator / Worker / Tools
       │                    │
       │                    └──► Tool Policy + Idempotency + Audit
       ▼
Financial Trust Core
  ├─ Fact Model / Fact Store
  ├─ Metric Dictionary
  ├─ Unit / Currency / Period Normalizer
  ├─ Deterministic Calculator
  ├─ Conflict Detector / Adjudicator
  └─ Claim Evidence Bundle
       │
       ▼
Multimodal Document Intelligence
  ├─ DocumentAssetManifest / Completeness
  ├─ PageRenderer / PageRouter
  ├─ Table / Chart / Scan Extractor
  ├─ Visual-Text Alignment / Conflict Check
  └─ VisualEvidence / Region Location
       │
       ▼
现有 RAG / Evidence Chain / Charts / Page Preview

Evaluation Plane（旁路）
  Dataset → Runner → Deterministic Evaluators → Optional LLM Judge
          → Baseline Diff → Quality Gate → Reports
```

## A：评测平面设计

### 数据集

建议新增：

- `evals/schema/case.schema.json`：样本结构。
- `evals/datasets/core.jsonl`：30 条无密钥核心集。
- `evals/datasets/financial_agent_v1.jsonl`：不少于 100 条完整集。
- `evals/baselines/v5.19.json`：当前版本基线。
- `evals/fixtures/`：经 schema 校验的固定回答、来源和工具轨迹，用于无密钥 CI 回放评估器。
- `evals/config/thresholds.yaml`：阈值与适用范围。

单条样本至少包含：`id`、`category`、`query`、`companies`、`expected_answer`、`expected_facts`、`expected_sources`、`expected_pages`、`numeric_tolerance`、`expected_behavior`、`expected_tools`、`risk_level`、`review_status`、`dataset_version`。

### 评估器分层

- L0 schema：字段、ID、类型和来源完整性。
- L1 确定性：数字、单位、币种、期间、页码、拒答、工具轨迹。
- L2 证据：声明是否被指定来源支持。
- L3 语义：正确性、相关性、完整性；允许使用固定版本 LLM 裁判。
- L4 系统：延迟、Token、成本、失败率、恢复率。

质量门禁不得只看平均分；高风险样本出现关键数值错误时应直接失败。

A 阶段在现有答案结构上建立来源、页码和预期事实基线；B 阶段引入结构化 Claim/EvidenceBundle 后，再把声明级证据支持率升级为发布硬门禁，禁止用 A 阶段近似指标冒充声明级指标。

### 运行模式

- `offline-core`：使用受版本控制的固定输出与轨迹夹具验证 schema、评估器、差异器和门禁，不调用外部模型，进入 PR CI。它验证“评测系统本身不回归”，不等同于证明当前在线模型质量。
- `local-full`：使用本地项目配置运行完整集。
- `release-full`：受控密钥环境运行并对比批准基线。

## B：金融可信内核设计

### 核心实体

`FinancialFact` 建议字段：

- 身份：`fact_id`、`metric_key`、`company_id`。
- 时间：`period_start`、`period_end`、`fiscal_year`、`period_type`。
- 数值：`raw_value`、`raw_unit`、`normalized_value`、`normalized_unit`、`currency`、`scale`。
- 口径：`scope`、`accounting_standard`、`audited`。
- 来源：`logical_document_id`、`document_version_id`、`source_file`、`pages`、`excerpt`、`source_type`、`authority_level`。
- 质量：`extraction_method`、`confidence`、`review_status`。

事实实体使用不可变数据对象；修订通过新版本和 supersedes 关系表达。

### 冲突类型

- `UNIT_MISMATCH`：万元与亿元等。
- `CURRENCY_MISMATCH`：人民币与美元等。
- `PERIOD_MISMATCH`：季度、年度或起止日期不同。
- `SCOPE_MISMATCH`：集团、母公司、持续经营等口径不同。
- `METRIC_MISMATCH`：营业收入与主营业务收入等指标不同。
- `VALUE_CONFLICT`：完成归一后仍超过容差。
- `SOURCE_CONFLICT`：一手与二手来源结论不同。

裁决规则优先处理可解释差异；只有同指标、同期间、同币种、同单位、同口径后仍不一致，才进入真实数值冲突。无法裁决必须返回待人工确认。

### 兼容策略

- 保留 `VerifiedFinancialFactRegistry` 公共方法。
- 内部逐步改为调用 `FinancialFactService`，旧三大运营商固定答案继续通过原测试。
- 现有 `CalculatorTool` 保留原操作；新增带事实引用的计算入口，不移除旧参数逻辑。
- 现有证据链增加可选 `claim_id`、`fact_ids`、`calculation_id` 和 `conflict_id`，旧响应字段保持兼容。

## M：多模态财报理解设计

### 复用边界

`src/pdf_mineru.py::_extract_single()` 继续作为 PDF→Markdown、图片、表格和公式的主解析入口；`_process_large_pdf()` 的原批处理语义不改。新增层只盘点其产物并补充完整性、页图、定位、结构化事实和证据关系。完整函数决策见 `reuse-matrix.md`。

`build_line_page_map()` 继续服务文本证据的近似页码，不承担视觉 bbox 真值。`preprocess_table_text()` 继续生成检索文本，不承担结构化单元格真值。`ChartTool._render_chart()` 继续负责生成展示图，不承担理解 PDF 图表。

### 源文件身份与只读边界

源 PDF 是不可变输入。上传先写入同一受控文件系统内、不可由下载端点访问的 staging 文件，关闭写句柄后校验 `%PDF-` 文件头、非空与大小限制、页数、加密状态和可读性，计算 SHA-256，再发布到内容寻址 blob 并在数据库事务中登记 `logical_document_id` 与 `document_version_id`。数据库登记失败允许留下不可见孤儿 blob，但必须由幂等清理器回收；不得出现可查询半版本或覆盖 active 文件。加密且无解密凭据、零页、截断或页数无法稳定读取时分别返回明确错误状态，不进入解析队列。

`logical_document_id` 表示用户语义上的文档，`document_version_id` 表示一次不可变内容版本，物理 blob 以内容哈希寻址。同一逻辑文档上传相同哈希时幂等返回既有版本；命中既有哈希键时仍核对文件大小与内容，冲突则拒绝登记并告警。相同字节以不同逻辑文档上传时允许共享物理 blob，但保留各自逻辑关联，不能因全局去重而合并用户语义。原始文件名只作经过长度、控制字符和 Windows 保留名校验的显示元数据，不参与物理路径拼接。共享 blob 只有引用计数为 0 且超过保留期后才允许物理回收。

Markdown、图片、页图、区域裁剪、表格结构、事实和索引全部写入包含 `document_version_id`、生成器版本和配置哈希的派生目录或数据库记录。任何增强或修复只生成新派生产物，不修改源 PDF 字节。

### V7 与 legacy 热加载的身份隔离

现有 `MineruHotLoadPipeline` 继续只消费 legacy `pdf_ingestion_manifest.json` 的 filename/SHA 与 legacy PDF 目录。feature flag 打开的 V7 上传只写内容寻址 blob 与 SQLite，不写入 legacy 目录或 JSON 清单；二者不存在可由文件名推断的稳定 `document_version_id`/`manifest_id` 映射。不得把 V7 的解析批次、页图或 complete 状态直接写入 legacy worker，否则同名替换或不同版本会发生证据错绑。

V7 必须使用默认关闭的独立文档处理协调器：以 `document_version_id` 和 blob 为输入，显式创建 DocumentAssetManifest，再按 PDF 物理页记录解析批次、页图、区域和发布候选。只有该协调器的完整性校验通过，后续 PublicationSet 才可考虑激活；legacy worker 行为和旧 JSON 响应保持不变。

### 既有产物复用与重处理决策

每个文档版本必须生成可审计的处理决策，状态只能是：

- `REUSE`：源哈希、页数、解析器类型/版本/配置哈希、输出哈希、引用文件和页批次均完整，可直接复用。
- `ENRICH`：Markdown/图片/表格内容完整，但缺少 v7 manifest、页级定位或版本元数据；只补充确定性元数据，不重跑 MinerU。
- `TARGETED_REEXTRACT`：已确认具体缺失页、失败批次、损坏表格、图表、扫描页或无法定位区域；只对记录范围重处理。
- `FULL_REEXTRACT`：源哈希变化、旧产物损坏、输出格式与适配器不兼容、全局页数错位或无法定位到具体故障范围；重新解析整个文档版本。

判定依据和失败原因写入 manifest；不得以未校准的任意比例阈值触发重处理。普通文本页不调用视觉模型，页图按证据定位和难例需要生成，禁止仅为“多模态覆盖率”渲染或识别全部页面。

处理错误使用稳定分类：无效文件、加密不支持和资源上限属于不可重试输入错误；临时文件系统/数据库忙、受控远端超时属于有上限的可重试错误；解析器错误、索引完整性失败在输入或版本不变时不得无限重试。磁盘写入、数据库事务、manifest 或索引校验失败均保持 `incomplete/failed`，禁止用旧结果或文本猜测伪装成功。

### 核心实体

- `DocumentAssetManifest`：`schema_version`、`logical_document_id`、`document_version_id`、文档哈希、页数、解析器/配置版本、处理决策、批次状态、制品列表、缺失页段及 `pending/processing/complete/incomplete/deleting/deleted` 状态。
- `PageArtifact`：页码、宽高、旋转角、文本层状态、页图/缩略图路径、内容哈希和页面类型。
- `VisualRegion`：规范化 bbox、区域类型、定位方法、置信度和定位状态。
- `TableArtifact`：行列结构、合并单元格、单位、期间、脚注、续表关系、原始结构和解析方法。
- `ChartArtifact`：标题、图例、轴、单位、期间、系列、数据点、趋势和原始区域。
- `VisualEvidence`：artifact ID、document version ID、页码、bbox、摘录/结构摘要、提取方法、置信度和审核状态。

制品 ID 由文档哈希、页码、区域、制品类型和解析器版本生成；重复运行必须幂等。无法从现有 Markdown 图片引用可靠反推页码或区域时，定位状态为 `unresolved`，禁止猜测。

清单元数据由 `V7MetadataStore` 中的 `DocumentAssetRepository` 持久化，状态与制品关系使用数据库事务；可导出 JSON 仅用于诊断，不是真值。状态和制品写入失败时不得推进 complete。进程重启后从数据库状态恢复或重新执行幂等步骤，不以目录中“碰巧存在文件”作为成功真值。

### 处理链路

```text
原 PDF
  ├─ 现有 MinerU VLM → Markdown / images / tables / formulas
  └─ PyMuPDF → 页数 / 文本层 / 页图 / 坐标空间
                │
                ▼
      DocumentAssetManifest + 完整性检查
                │
                ▼
     PageRouter（text/table/chart/scan/mixed）
        ├─ text：原 RAG
        ├─ table：既有结构优先 → 复杂难例 VisionProvider
        ├─ chart：VisionProvider → 文本交叉核验
        └─ scan：无可用文本层时按需识别
                │
                ▼
     FinancialFact / Conflict / EvidenceBundle
                │
                ▼
       SourceInfo → 页图预览与区域高亮
```

路由先使用文本层、Markdown 结构、图片引用和页面几何等可解释信号；只有图表、扫描页、复杂表头、损坏结构和冲突难例进入视觉模型。相同文档哈希、区域和解析版本命中缓存时不得重复调用模型。

### 视觉能力接口

新增独立 `BaseVisionProvider`，输入类型至少包含图片/区域、任务类型、结构化输出 schema、文档上下文和安全边界；输出包含结构化结果、置信度、模型、用量和错误状态。现有 `BaseLLMProvider.chat()` 保持纯文本契约，不用字符串图片路径绕过类型检查。

视觉模型配置必须明确声明 provider、model、支持任务、最大图片大小和预算。模型未配置、调用失败或不支持任务时返回 `unavailable/incomplete`；不使用另一路径静默猜测。当前 OCR/OpenCV 相关包未安装，若实施决定引入，必须先核查本地状态、说明用途并征得用户同意。

### 表格、图表与扫描页

- 表格优先解析 MinerU 已生成的 HTML/Markdown；保留合并单元格、空值、表头层级、脚注和原始字符串。跨页续表只有在标题/表头、列结构、相邻页和语义均满足规则时合并，否则保持两个制品并标记候选关系。
- 图表识别必须输出轴、图例、单位、期间和数据点来源；只识别出趋势时不得伪造精确数值。文本与图表冲突进入 B 阶段冲突引擎，不静默选择。
- 扫描页只在文本层不可用或质量门禁失败时处理。识别结果保留原区域和置信度；低置信数值不能进入 verified 状态。

### 安全与生命周期

图片内文字、OCR 结果、图例和脚注均是不可信内容，不得改变系统指令、工具权限、预算或审批。渲染前校验页数、像素、文件大小和资源预算，避免畸形 PDF/图片造成资源耗尽。

上传沿用 `src/knowledge_service.py::upload_pdf()` 的校验和路径安全，但不沿用“同名直接覆盖”的身份语义。新增逻辑文档 ID 与内容版本 ID：相同内容哈希重复上传幂等返回原版本；同名但哈希不同创建新版本，原 active 版本继续可查，只有新版本制品、事实和索引门禁通过后才原子激活。

删除沿用并扩展 `delete_pdf()`。由于文件系统、事实库与 FAISS/BM25 无法组成单一数据库事务，删除先原子标记文档版本为 `deleting` 并使新查询快照排除它，再幂等清理原 PDF 派生的 Markdown、页图、区域图、视觉事实和索引，全部成功后标记 `deleted`；失败保留可重试状态。删除接口默认返回任务/状态而非提前宣称完成。已在删除线性化点之前固定旧 generation 的在途请求可按记录完成，但删除完成后 artifact API 和新检索必须不可见。

视觉结构摘要通过现有 `build_company_index()` 进入同一 FAISS/BM25 索引，不建立第二套向量库。现有 `build_faiss_index()` 的文本默认路径保持兼容；视觉制品使用新增可选 strict 模式，任一 embedding 批次失败即中止该视觉索引步骤并标记 incomplete，禁止把补零向量当成功。缺页批次、缺失图片、索引失败或清理失败必须留下可查询状态。

现有 `ingestion.py --rebuild` 会先删除旧公司目录，且 registry 直接覆盖写入；v7 不复用这一破坏性激活方式。新增 `IndexGenerationManager`：在 `generations/<generation_id>/` staging 目录构建完整 FAISS、BM25、metadata 和校验清单，验证数量、维度、哈希与抽样检索后，由 `PublicationSet` 事务把 generation 与同批文档、制品和事实可见性一起发布。旧 publication 在新 publication 通过冒烟测试前始终可用；回滚创建一个重新指向上一组不可变版本的新 publication 记录，不重建或反向修改文件。

首轮 v7 迁移必须为当前全部 active 文档版本生成一个完整新 generation。文本/表格/图片派生产物可按上述决策复用，但当前旧索引没有足够的 parser、splitter、preprocess、embedding model/version、维度和 schema 证据，旧向量不得直接导入新代际；首轮重新切分或核验可复用 chunk 后统一重算 embedding。后续只有缓存键同时包含规范化文本哈希、embedding 模型与版本、预处理版本和向量维度时，才允许跨 generation 复用 embedding。

首轮迁移在记录基线时固定 `corpus_revision`。基线之后上传、删除或替换的文档进入下一 publication；若要求并入首轮，必须基于新 revision 重新校验受影响步骤，不能一边构建一边改变分母。构建任务保存其 expected publication/revision，发布时 CAS 不匹配则标记 superseded 并重新规划，不得覆盖更新后的 active 状态。

`RAGGenerator`、`HybridRetriever`、RetrieveTool 和 CompareTool 当前各自可能缓存 Retriever。所有新请求必须从统一 `PublicationResolver` 获取 active publication，并在一次请求开始时固定 publication ID；检索、artifact、事实与报告查询全部使用同一 publication，途中不得切换。激活后新请求按新 publication 创建或刷新对应代际缓存，旧请求继续使用旧 publication；旧 publication/代际只有在无活动租约且达到保留策略后才能回收。进程异常遗留的租约按超时和 owner token 回收；Windows 上不替换或删除正在被 FAISS/BM25 打开的文件。

页图和 staging 文件不通过公开静态目录暴露。`page_image_url` 由服务端依据 artifact ID 生成，受现有 API 认证保护；读取端点只能从 manifest 解析真实路径并校验文档关联和当前发布可见性，不接受调用方传入本地文件路径，防止路径遍历和跨文档越权。现有代码只有统一 API key，故 v7 首版只承诺单用户/单租户端点级认证；不宣称用户间文档 ACL。

功能开关关闭时，`upload_pdf()` 与 `delete_pdf()` 的状态码、同步语义和返回字段保持 v5.19 冻结夹具一致。开关开启时上传成功响应仍保留 `filename/size/size_mb`，只允许增加可选 `logical_document_id/document_version_id/task_id/status`；处理中不得先返回“索引完成”。

### 关系型溯源，不建设完整知识图谱

`V7MetadataStore` 使用明确外键表表达当前已证实的审计关系：`document_versions`、`artifacts`、`financial_facts`、`artifact_facts`、`claims`、`claim_facts`、`calculations`、`calculation_inputs`、`reports`、`report_claims`。关系记录携带版本、创建来源和有效状态；数据库约束阻止悬空引用，事实修订通过新版本与 `supersedes` 表达，不覆盖历史。

溯源主记录使用外键 `RESTRICT` 与软失效，不用级联物理删除抹掉历史。删除或替代来源时，在同一事务写入 tombstone/revision、使新 publication 排除目标并把受影响 claim、calculation、report 标记 `stale`；历史报告可保留结构与失效原因，但其受保护 artifact 不再对新请求开放。共享 blob 的引用增减与删除资格检查必须在同一数据库事务中完成，避免并发上传与回收竞态。

这套关系支持“报告声明用了哪些事实、事实来自哪个页区、计算用了哪些输入、源版本变化影响哪些声明”的确定性追踪。v7 不引入通用三元组、图数据库或图推理。为未来演进保留稳定实体 ID、公司 ID、有效时间和关系类型；只有独立的多跳关系评测集证明当前关系查询无法达到批准门禁后，才创建知识图谱子变更。

## C0/C1：任务恢复设计

C 分为 M 前的 C0 与 M 后的 C1。C0 是不绑定业务 UI 的通用 ExecutionRun 基础，直接承载 PDF 解析、视觉调用和索引 generation 构建；C1 才把 Planner、Orchestrator、研究任务 API 与前端映射到同一执行内核。M 禁止建立自己的任务表、重试器或事件系统。

### 状态模型

任务状态：`pending → running → completed`，并允许从 running 进入 `waiting_approval`、`paused`、`failed` 或 `cancelled`。只有满足状态迁移表的操作才能执行。

步骤状态包含：输入摘要、输出引用、尝试次数、开始结束时间、错误类型、幂等键和依赖步骤。

每个 Run 和 StepAttempt 使用单调 `revision` 与租约。暂停、恢复、取消、审批等命令携带 `command_id + expected_revision`；重复 command_id 返回原结果，过期 revision 返回冲突而不覆盖新状态。执行者必须持有未过期 lease 才能提交步骤结果。

每个步骤必须在外部检索或模型计算前领取 lease，计算期间按 TTL 续租；未提交异常由当前 owner 原子释放 lease 并追加 `step_abandoned` 事件，不能遗留活动 lease。租约竞争或续租失败只表示当前执行者失去执行权，不得把任务误记为业务失败。

### 存储

首版复用 B 阶段 `V7MetadataStore` 的标准库 `sqlite3` 实现：短事务、每操作独立连接、WAL、busy timeout 和明确事务边界；异步 API 中的阻塞操作放入线程执行。当前部署是单 Uvicorn 进程，首版只承诺该部署模式。启用多 worker 前必须单独完成并发验收。不得再为任务创建第二个 SQLite 文件，也不得把多个任务以整文件覆盖方式写入同一 JSON。存储接口与实现分离，以便后续替换数据库。

检查点只保存带 schema 版本的 JSON 可序列化数据、制品路径或稳定 ID，不直接序列化线程、队列、Agent 实例和任意 Python 对象。

### 幂等

幂等键由 `task_id + step_id + tool_name + canonical_input_hash + code/tool_version + model/provider + prompt_version + fact/artifact_version + index_generation` 组成。恢复前检查已成功调用记录；只有全部依赖版本一致时才复用已完成步骤和成功工具/模型调用。有副作用调用不得自动重复；只有明确标记为 non-cacheable 且无副作用的调用才允许重新执行并留下原因。

Python 线程池 timeout 只表示等待方停止等待，不代表线程或远端模型调用已终止。C0 使用 cancellation token、attempt token 和 revision：超时/取消后不启动后续步骤；晚到结果可记审计但状态为 discarded，提交事务必须校验 attempt、lease 和 revision，失败时不得写事实、制品、索引或 completed。

### SSE 重连

事件持有数据库分配的单调递增 `event_id`；并行 Worker 只提交事件草稿，由单一持久化写入器排序和编号。新持久任务流使用可携带 Authorization 的 fetch streaming，客户端以最后 event ID 重连；不复制当前 `/api/agent/stream` 的 EventSource 免鉴权例外。若游标早于保留窗口，服务端明确返回需要获取任务快照，不能从当前事件静默续接。

新增 ResearchTask 创建、查询、事件流、暂停、恢复和取消端点；保留现有 `/api/agent/query` 与 `/api/agent/stream` 行为。持久任务一旦选择 single 或 multi 路径，失败时不得静默切换路径，必须保存失败并由显式重试或重新规划处理。

## D：治理设计

- 工具策略：`read_only`、`compute`、`external_read`、`external_write`、`privileged`。当前工具主要是只读和计算，实施时不得为了演示新增虚构的危险工具；审批优先落在关键冲突裁决、正式报告签发和未来真实写操作上。
- 审批记录绑定任务、步骤、工具、规范化参数、过期时间和批准人。
- 审计事件只追加，包含 actor、action、resource、result、timestamp、correlation_id。
- 日志脱敏先于持久化和外发追踪。
- 成本预算同时检查 Token、模型调用次数、工具调用次数和墙钟时间。
- 路由优化先比较 single/multi 两条现有路径，不先引入新模型供应商。

## E：前端与报告设计

- 新增独立研究任务页和任务详情页，复用现有 PageShell、DAG、EvidencePanel、图表和主题体系。
- 报告由结构化 `ResearchReport` 生成，章节、声明、事实、计算和来源均有稳定 ID。
- 第一版导出 Markdown/HTML；PDF、Word、Excel 分别独立验收，避免一次引入多个文档依赖。

## 数据迁移

- v5.19 数据不做破坏性迁移。
- 迁移前记录全部源 PDF 哈希、页数、加密/可读状态和现有派生产物清单；迁移后逐文件复核哈希，任何源字节变化均为硬失败。
- 当前全部 active 文档进入首轮 v7 generation；合格 MinerU 产物按决策复用，无法证明兼容的旧 embedding 全部重算。
- 首轮基线固定 corpus revision；基线后的上传/删除进入下一 publication，或触发受影响范围重新校验，不允许静默改变首轮覆盖分母。
- 旧 publication 在新 generation 完成完整性、维度、哈希、抽样检索和回归门禁前保持 active；迁移失败只清理未发布 staging，不删除旧数据。
- 现有硬编码事实通过启动时适配进入新模型，原文件暂不删除。
- 旧会话记忆继续读取；研究任务检查点使用独立目录或数据库。
- 新 schema 均携带 `schema_version`。

## 可观测性

每次任务至少关联：`task_id`、`run_id`、`conversation_id`、`dataset_version`、`model_id`、`prompt_version`、`index_version`。在线追踪失败不得改变任务业务结果，但本地审计与任务状态写入失败必须使相关状态更新失败，不能静默吞掉。

## 实施文件预估

以下是设计期预估，实施时以代码核查为准：

- 新增 `src/evaluation/`、`src/persistence/`、`src/financial_trust/`、`src/multimodal/`、`src/research_tasks/`、`src/governance/`。
- 修改 `src/verified_financial_facts.py`、`src/pdf_mineru.py`、`src/knowledge_service.py`、`src/tools/calculator_tool.py`、`src/tools/verify_tool.py`、`src/orchestrator_agent.py`、`src/api_service.py`。
- 修改前端服务、store、路由和研究任务组件；不重写现有聊天组件。
- 扩展 `.github/workflows/quality-gate.yml`，另建受控全量评测工作流时必须保证密钥隔离。

本机核查显示 `openevals` 可由解释器定位，但 `pip show openevals` 无包元数据且锁文件未声明；`aiosqlite` 可定位但也未进入项目锁文件。PyMuPDF `1.27.2.3` 与 Pillow `10.4.0` 可用，`cv2`、`pytesseract` 和 `pymupdf4llm` 不可用；`mineru` 可定位但 `pip show` 无元数据；实际 `dashscope 1.25.17` 还需与项目锁文件核对。首版评测使用项目代码与 pytest，任务存储使用标准库 sqlite3，多模态页图使用现有 PyMuPDF。任何新增包必须先统一依赖声明并获得用户同意。

## 发布与回滚

- 每个工作包单独提交，保留可运行主线。
- 数据 schema 变更必须向后兼容或提供迁移验证。
- 质量下降时回滚该工作包提交，不回滚用户既有数据；数据可见性回滚通过新 PublicationSet 重新引用上一组不可变索引、文档、制品和事实版本，不能只切索引指针。
- v7.0 标签仅在 A、B、C0、M、C1、D、E 必选验收、CHANGELOG、交接文档和发布核查全部完成后创建。
