# 规格 S：源文件、索引迁移与关系型溯源

## 要求：源 PDF 不可变

系统必须把校验后的源 PDF 作为不可变输入，任何解析、清洗、裁剪、识别和索引输出只能写入版本化派生产物。

### 增量热加载边界

在首轮迁移或任何全量重建前，系统必须对当前源 PDF 生成只读冻结清单。清单逐份记录相对源路径、文件名、SHA-256、字节数、PDF 物理页数、加密状态、可读状态和既有 registry 证实的 logical document 映射。物理页数仅用于解析、覆盖率与审计，不得写入或推断 `document_pages`。冻结过程不得改写源 PDF；输出清单必须使用原子替换，避免半份 JSON 成为迁移基线。

新增 PDF 采用同文件系统临时文件写入后原子替换，并在清单中进入 `pending_index` 状态；上传接口立即返回文件身份和状态，后续解析、切分和索引由独立处理步骤消费待处理清单。相同文件名和相同 SHA-256 重复上传必须幂等，不重复触发处理。旧索引不因新文件上传而自动变为不可用，只有新索引代际完成校验后才允许发布切换。

索引处理步骤必须携带上传时的 SHA-256；若处理期间文件已被新版本替换，旧步骤不得把新文件标记为已索引。失败状态保留错误原因并允许后续重试，不能伪装为已完成。

增量索引必须先写入独立的 generation staging 目录，并校验 FAISS、BM25、metadata 和 parent text 制品后，才原子更新 active generation 指针。构建异常或校验失败不得修改旧 active 指针；staging 残留不得被检索端读取。

同一公司的增量构建必须合并既有合格 chunk；当新版本替换同名源 PDF 时，只移除该源文件对应的旧 chunk，再加入新解析结果。不得仅用新增 PDF 建立公司 generation，否则会造成历史年度或既有研报从检索语料中丢失。

目录登记扫描通过 `hot_load.directory_sync_enabled` 显式开启，调度器绑定 API lifespan 的启动和关闭；该扫描仅登记文件，不得在启动线程中隐式触发 MinerU、Embedding 或 active generation 发布。

实际索引消费必须由独立的 `hot_load.indexing_enabled` 显式开启。关闭时只能运行目录登记 worker；开启时才允许创建 MinerU pipeline、调用既有切分/Embedding/发布链。两种模式都必须在 API lifespan 关闭阶段停止调度器；若创建过 MinerU 客户端，还必须释放该客户端。默认关闭实际索引，避免部署或测试启动时产生未授权的外部调用和费用。

资料库页面必须复用文档列表接口中的状态字段：存在 `pending_index` 或 `index_failed` 文档时以不阻塞页面操作的方式定时刷新；没有活动任务时不得持续轮询。刷新失败只能记录前端错误，不得清空已展示的文档状态。

自动索引失败必须持久化尝试次数并设置上限，达到上限后不得由常驻调度器无限重试或继续产生外部调用；失败文档必须支持显式重试，显式重试时重置尝试次数并重新进入 `pending_index`。

MinerU 单文档解析超时必须来自 `hot_load.parse_timeout_seconds` 配置；配置值必须为正数，默认值保持现有 600 秒行为。超时或解析器未返回时只能进入失败状态，不得继续切分、Embedding 或发布。

文本分块和引用必须区分 PDF 物理页序与文档自身印刷页码。`pages` 字段保持为从 1 开始的 PDF 物理页序，用于解析页段、覆盖率、检索位置排序和兼容既有索引；新增 `document_pages` 字段保存从 PDF 页眉/页脚或 PDF page label 直接可靠识别的文档页码，允许字符串以支持罗马数字或带前缀页码。无法直接识别的文档页码必须留空或标记未解析，不得用物理页序、比例推算或相邻页面猜测替代。用户来源展示优先使用 `document_pages`，同时保留物理页序供审计；任何文档页码不能超过其 PDF 物理页数的约束只适用于物理页字段，不得据此改写合法的印刷页码。

当 MinerU 按物理页段解析或合并批次时，批次范围必须使用 PDF 物理页序；合并 Markdown 后不得因批次重排、封面、目录或印刷页码重置而把文档页码写入 `pages`。批次进度必须记录当前物理页范围和总页数；任一批次失败时整个文档只能进入失败/不完整状态，不得发布部分文本索引。页码映射失败只能降级为物理页引用或“文档页码未解析”，不得阻断文本索引，也不得宣称印刷页码精确。

删除 PDF 时必须同步移除其热加载 manifest 条目；删除过程的清单写入失败必须恢复源文件。同名 PDF 后续重新出现时必须创建新的待索引状态，不得因旧 manifest 条目误判为已索引。旧 generation 的物理失效和 PublicationSet 级清理由后续完整删除流程负责。

### 场景：正常上传

- 给定一个未加密、页数有效且在大小限制内的 PDF
- 当上传服务完成 staging 写入、关闭文件、校验和 SHA-256 计算
- 那么系统登记不可变 document version 并保留源哈希
- 并且后续处理不得改变源文件字节

### 场景：上传中断或校验失败

- 给定上传写入中断、文件头不是 `%PDF-`、空文件、零页、截断或无法读取页数
- 当 staging 校验失败
- 那么系统返回明确错误，不创建可查询 document version，也不覆盖 active 版本

### 场景：发布登记失败

- 给定源 blob 已写入但数据库事务失败
- 当上传流程终止
- 那么该 blob 对查询和 artifact API 不可见，并由幂等孤儿清理器在保留窗口后回收

### 场景：Windows 文件名边界

- 给定包含控制字符、超长名称或 Windows 保留名的原始文件名
- 当系统登记显示名称
- 那么系统拒绝或规范化为安全显示元数据，且原始名称不参与物理路径拼接

### 场景：加密 PDF

- 给定一个需要密码且系统没有解密凭据的 PDF
- 当系统检查可读性
- 那么返回 `unsupported_encrypted`，不进入解析或索引队列

## 要求：逻辑身份与内容版本分离

系统必须区分用户语义上的 logical document、不可变 document version 和按哈希寻址的物理 blob。

### 场景：同一逻辑文档重复上传相同内容

- 给定相同 logical document 与相同 SHA-256
- 当用户重复上传
- 那么幂等返回既有 document version，不重复创建派生产物

### 场景：不同逻辑文档内容相同

- 给定两个 logical document 具有相同 SHA-256
- 当系统执行物理去重
- 那么可以共享 blob，但必须保留两个逻辑关联、权限和生命周期

### 场景：内容哈希键异常冲突

- 给定既有 SHA-256 键对应的大小或字节与新上传不一致
- 当系统尝试复用 blob
- 那么拒绝登记、记录审计错误，不把两个内容视为相同版本

## 要求：证据化复用与重处理

每个 document version 必须依据源哈希、页数、解析器类型/版本/配置、输出哈希、页批次和引用文件，选择且记录 `REUSE`、`ENRICH`、`TARGETED_REEXTRACT` 或 `FULL_REEXTRACT`。

### 场景：已有完整 MinerU 产物

- 给定源哈希和页数匹配，解析配置可识别，Markdown、图片引用和页批次完整
- 当迁移评估既有产物
- 那么选择 `REUSE` 或仅补元数据的 `ENRICH`，不重跑 MinerU/VLM

### 场景：只有确定页段失败

- 给定 manifest 能定位缺页批次、损坏表格、图表、扫描页或 unresolved 区域
- 当系统创建修复任务
- 那么选择 `TARGETED_REEXTRACT` 且任务范围不得超出已记录范围

### 场景：产物整体不可证明兼容

- 给定源哈希变化、产物损坏、输出格式不兼容、全局页数错位或无法定位故障范围
- 当系统评估复用安全性
- 那么选择 `FULL_REEXTRACT` 并保留原因，不以任意比例阈值替代证据

### 场景：处理错误分类

- 给定无效输入、临时 I/O、数据库忙、解析器失败或索引校验失败
- 当任务记录错误
- 那么使用稳定错误类型和有限重试策略；不可重试错误不循环，失败状态不被旧结果或文本猜测覆盖

## 要求：首轮 v7 索引代际

系统必须为迁移基线中的全部 active document version 侧向构建首个 v7 generation；旧 generation 在新代际完整发布前保持可用。

### 场景：旧向量缺少版本证据

- 给定旧 metadata 未完整记录 parser、splitter、preprocess、embedding model/version、维度和 schema
- 当构建首个 v7 generation
- 那么不得直接导入旧向量，必须在核验 chunk 后重算 embedding

### 场景：新代际构建失败

- 给定 FAISS、BM25、metadata、哈希、维度、覆盖率或抽样检索任一校验失败
- 当 staging 构建终止
- 那么 active publication 保持不变，失败代际不可查询

### 场景：请求期间发生激活

- 给定查询开始时已固定 publication ID
- 当另一个执行者发布包含新 generation 的 PublicationSet
- 那么该请求的索引、文档、artifact 和事实继续读取旧快照，新请求读取新 publication

### 场景：迁移期间语料发生变化

- 给定首轮任务已固定 corpus revision
- 当并发上传、删除或替换改变 active publication
- 那么变更进入下一 publication，或当前构建基于新 revision 重校验；旧构建不得静默改变覆盖分母

## 要求：发布集合原子一致

发布必须以单一 `publication_id` 绑定 index generation、可见 document version、artifact/fact 版本边界和 corpus revision。文件构建在事务外完成，active 切换在短 SQLite 事务内以 expected revision/CAS 完成。

Retriever 必须兼容 v7 仅存在 active generation 指针而尚未生成旧式 `company_registry.json` 的过渡状态：当根 registry 缺失时，只能从格式有效且已发布的 active 指针发现公司；active 指针和 registry 均未发现可用公司时必须明确失败，不得猜测公司或读取 staging 目录。

### 场景：两个构建者并发发布

- 给定两个构建任务基于相同 expected publication/revision
- 当二者竞争提交
- 那么最多一个 CAS 成功，失败者标记 superseded，不覆盖胜者

### 场景：事实发布失败

- 给定索引文件已通过校验，但 PublicationSet 数据库事务失败
- 当发布终止
- 那么新索引、artifact 和事实全部不可见，active publication 不变

### 场景：回滚发布

- 给定新 publication 质量门禁失败
- 当执行回滚
- 那么系统创建引用上一组不可变 index/document/artifact/fact 版本的新 publication，不能只切换索引文件

## 要求：关系型溯源完整性

系统必须使用带外键、版本和有效状态的明确关系表连接 document version、artifact、financial fact、claim、calculation 和 report，不以无约束 JSON 或通用三元组作为已发布真值。

### 场景：报告声明回溯

- 给定一个已发布报告声明
- 当用户查看溯源
- 那么系统可确定性列出声明使用的事实、计算输入、artifact、document version、页码和区域状态

### 场景：来源版本失效

- 给定 document version 或 financial fact 被删除、替代或失效
- 当系统提交状态变化
- 那么数据库不产生悬空引用，并把受影响 claim、calculation 和 report 标记为 stale 或待复核

### 场景：保留历史审计

- 给定报告所依赖事实已失效
- 当用户查看历史报告元数据
- 那么报告结构和失效原因仍可审计，但已删除版本的受保护 artifact 不向新请求开放

## 要求：删除分为逻辑失效与物理回收

删除必须先使目标 document version 对新查询不可见，再幂等清理派生产物；共享物理 blob 只有引用计数为零且超过保留期后才能删除。

### 场景：删除与查询并发

- 给定旧查询已固定发布快照，新删除进入线性化点
- 当新查询到达
- 那么新查询排除 deleting 版本，旧查询按已记录快照完成

### 场景：共享 blob 仍被引用

- 给定另一个 logical document 仍引用相同物理 blob
- 当一个 logical document 被删除
- 那么只删除其逻辑关联和派生可见性，不删除共享源 blob

### 场景：删除与相同内容上传并发

- 给定回收任务准备删除零引用 blob，同时新上传登记相同内容
- 当二者并发提交
- 那么引用计数增减和删除资格在同一事务串行化，仍有引用的 blob 不得被删除

## 要求：权限与兼容边界

v7 首版只承诺现有 API key 保护下的单用户/单租户端点级认证，不宣称文档级多租户 ACL。artifact 端点必须只接受 artifact ID，并验证其关联 document version 当前可见。

### 场景：非法 artifact 访问

- 给定路径、未知 artifact ID、已删除版本或不属于当前可见发布集合的 artifact
- 当客户端请求页图
- 那么服务拒绝访问且不泄露本地路径

### 场景：功能开关关闭

- 给定 `multimodal_enabled=false`
- 当调用旧上传、删除、查询和来源接口
- 那么 v5.19 的必填字段、状态码和同步语义保持冻结夹具一致

### 场景：功能开关开启后的上传兼容

- 给定一个成功登记但尚未完成索引的文档版本
- 当上传接口响应
- 那么仍包含旧 `filename/size/size_mb` 字段，只增加可选版本/任务/状态字段，并不得宣称索引完成

## 要求：知识图谱延后

v7 不得引入图数据库或通用知识图谱。只有至少 30 个经复核的多跳关系案例证明关系型方案未达到批准门禁，并明确需要实体消歧、时态关系和图推理时，才允许建立独立变更。

### 场景：当前审计关系需求

- 给定需求仅为从报告回溯声明、事实、计算、artifact 和 document version
- 当选择存储模型
- 那么使用关系表和外键，不增加图基础设施
