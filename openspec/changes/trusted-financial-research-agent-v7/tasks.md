# 任务清单：v7.0 可信金融研究 Agent 升级

> 状态约定：规划阶段全部未开始。实施时每项必须先运行对应 RED 测试，完成实现与回归后，才允许把 TDD 和任务同时改为 GREEN/完成。

## 0. 实施前门禁

- [ ] 0.1 用户批准 proposal、design、roadmap、specs 和三轮核查结论。
- [ ] 0.2 从最新 main 创建 `codex/trusted-financial-agent-v7` 开发分支或隔离 worktree。
- [ ] 0.3 重新确认工作区干净、HEAD 与远端同步、v5.19 基线可定位。
- [ ] 0.4 运行并记录现有后端、前端、构建和 OpenSpec 质量门禁基线。
- [ ] 0.5 复核候选依赖的解释器可见性、包元数据和锁文件三者是否一致；本机 `openevals` 当前可定位但 `pip show` 与锁文件均不承认，首版不得依赖该状态。
- [ ] 0.5.1 核查 OpenSpec CLI 是否可用；当前环境无 `openspec` 命令，如实施需要安装，先说明用途并征得用户同意。
- [ ] 0.6 记录活动变更 `openspec-lifecycle-and-ci-quality-gate` 的未闭环项；它不阻塞 A1/A2 本地开发，但在修改现有 Quality Gate 前必须完成合并核查。
- [ ] 0.7 确认 v7.0 是路线版本；禁止提前创建 Git 标签。
- [ ] 0.8 逐项批准 `reuse-matrix.md` 的函数边界；实施中出现未列明替换、平行服务或新增依赖时先更新规格。
- [ ] 0.9 核对多模态本地依赖：PyMuPDF/Pillow、MinerU 元数据、DashScope 实际版本和锁文件；当前未安装 OCR/OpenCV 相关包，不得默认引入。
- [ ] 0.10 冻结 v5.19 OpenAPI、关键 JSON、配置、company_registry/metadata 和“无 v7 数据库”兼容夹具。
- [x] 0.11 定义 v7 四个默认关闭的功能开关及严格配置 schema；multimodal/research_tasks 依赖 financial_trust 与 durable_execution，依赖缺失时 fail closed 且不自动连带启用。

## A. 金融评测基线与发布门禁

### A1. 数据规范与核心集

- [x] A1.1 建立 `evals/` 目录、样本 schema、数据集元数据和版本规则。
- [x] A1.2 编写 schema 校验器及重复 ID、来源缺失、容差错误检查。
- [ ] A1.3 将现有 generation/retrieval 各 10 条样本迁移为新格式，原文件先保留。
- [ ] A1.4 建立 30 条核心高风险集：数值、单位、期间、拒答、冲突和工具轨迹。
- [ ] A1.5 为每条核心样本核对文档、页码、摘录、标准答案和允许误差。
- [x] A1.6 保存经校验的固定回答、来源和工具轨迹夹具，供无密钥 CI 回放。
- [ ] A1.7 扩展完整集到不少于 100 条并记录分类覆盖率。

### A2. 评估器与运行器

- [x] A2.1 新建评测结果模型和统一 Runner 接口。
- [x] A2.2 实现数字、单位、币种、期间和页码确定性评估器。
- [x] A2.3 实现拒答、工具选择和工具轨迹评估器。
- [ ] A2.4 实现声明—证据支持度评估器；无法确定时不得自动通过。
- [ ] A2.5 适配现有 LangSmith/OpenEvals 脚本，不复制评测逻辑。
- [x] A2.6 记录模型、提示词、索引、数据集、代码 SHA 和运行配置。
- [x] A2.7 生成 JSON 与 Markdown 双报告。
- [x] A2.8 明确答案级证据基线与 B 阶段声明级证据门禁的指标名称和启用条件。

### A3. 基线与门禁

- [ ] A3.0 在修改 `.github/workflows/quality-gate.yml` 前，核对并收口现有质量门禁活动变更，禁止两个提案同时修改同一工作流。
- [ ] A3.1 跑出 v5.19 真实基线，保留所有失败样本。
- [ ] A3.2 实现候选版本与批准基线差异报告。
- [ ] A3.3 实现高风险单项硬门禁和整体阈值门禁。
- [ ] A3.4 在现有 Quality Gate 中加入无密钥核心评测，不另建重复 PR 门禁。
- [ ] A3.5 建立受控全量评测入口，确保密钥和 PR 环境隔离。
- [ ] A3.6 更新评测使用说明、版本记录和交接文档。
- [ ] A3.7 运行 A 包回归和代码审查，提交 `feat(eval): establish financial agent release gate`。

### A 包退出条件

- [ ] A-GATE-1 30 条核心集在无密钥环境稳定通过 Runner 自测。
- [ ] A-GATE-2 不少于 100 条完整集完成来源复核。
- [ ] A-GATE-3 v5.19 基线和差异报告可复现。
- [ ] A-GATE-4 CI 失败能定位具体样本与指标。

## B. 金融可信内核

### B0. 公共持久化与纵向试点

- [x] B0.1 定义 B/M/C/D 共用的 V7MetadataStore、连接工厂、仓储边界和 schema_migrations。
- [x] B0.2 使用标准库 sqlite3 实现单数据库迁移：外键、WAL、busy timeout、启动前备份、失败回滚和重复执行幂等。
- [x] B0.3 验证未知更高 schema 版本拒绝写入，旧 v5.19 文件和索引不被迁移或删除。
- [x] B0.4 已完成“旧人工事实→统一归一→FinancialFact→旧比较 API”的营业收入单指标纵向试点；扩展事实类别仍待 B1/B2 后续任务。
- [x] B0.5 已对 financial_trust_enabled 开/关执行比较 API 与图表投影契约回归；关闭时不创建 V7 SQLite，新开关配置非法时 fail closed。

### B1. 事实与标准化

- [x] B1.1 已新建 `FinancialFact` 的来源、期间、口径和修订版本实体；旧营业收入兼容事实暂不伪造 V7 文档版本映射。
- [x] B1.2 已建立严格指标词典与白名单别名映射；相近收入指标不会自动合并。
- [x] B1.3 已集中 VerifyTool 的金额单位规则为共享 Decimal 定义；新归一器直接复用，VerifyTool 保留原公开常量与行为。
- [x] B1.4 已实现币种比较前置校验；无可审计汇率来源时明确拒绝跨币种换算。
- [x] B1.5 已实现期间、集团/母公司、会计准则和审计状态的显式兼容性检查。
- [x] B1.6 已建立 V7 事实上下文存储接口与首版本地实现，使用事务、schema v7、真实文档版本外键和同 ID 证据不可变性门禁。
- [x] B1.7 已用适配器接管启用后的已核验比较路径，保持公共行为，并隔离缺少真实文档版本映射的 legacy 事实。

### B2. 计算与冲突

- [x] B2.1 已为事实同比计算增加输入事实 ID、公式版本和不可变结果证据持久化，不移除旧 CalculatorTool 操作。
- [x] B2.2 已批准并实现事实驱动的同比与 CAGR 公式及输入兼容校验；其他 CalculatorTool 操作不自动视为批准金融公式。
- [x] B2.3 已实现同口径容差冲突与来源权威度复核排序；权威度不自动裁决或覆盖事实。
- [x] B2.4 已实现无法裁决冲突的不可变人工确认状态，确认前不覆盖事实。
- [x] B2.5 已建立声明级 EvidenceBundle，以 `v7_claims` 与 `v7_evidence_bundles` 关联声明、事实、计算与冲突，拒绝悬空引用与静默改写；既有比较响应与旧来源字段保持不变，新载荷仅以可选字段提供。
- [x] B2.6 前端证据面板展示原始值、归一值、公式和冲突原因。
- [x] B2.7 用 A 评测集验证升级收益；未达到门禁则修正而不是降低阈值。声明级证据支持率硬门禁已启用（thresholds.yaml 切换为 enabled 并被评测门禁真实消费），升级候选通过门禁且无新增失败，缺声明级载荷或调低通过率均无法通过门禁。
- [x] B2.8 已运行 B 包全回归和代码审查，提交 `feat(finance): add verifiable financial trust core`。

### B 包退出条件

- [x] B-GATE-1 旧三大运营商核验事实测试无回归。
- [x] B-GATE-2 数值、单位、币种、期间、口径边界全绿。
- [x] B-GATE-3 所有派生指标可追溯事实和公式。
- [x] B-GATE-4 冲突不可裁决时不输出单一确定值。

## C0. 通用可恢复执行基础

- [x] C0.1 已在 V7MetadataStore 定义 ExecutionRun、StepAttempt、Checkpoint、Invocation、TaskEvent、Lease 及其外键。
- [x] C0.2 已实现带 revision 的状态迁移与 CAS；暂停、恢复、取消命令携带 command_id 并可安全重复。
- [x] C0.3 已实现运行租约、续租、过期接管和同一步骤单执行者约束。
- [x] C0.4 已实现检查点、调用账本、步骤状态和事件序号同事务提交；并行事件由单写入器分配 ID。
- [x] C0.5 幂等键已纳入规范化输入、代码/工具、模型、提示词、事实/制品版本和 index generation。
- [x] C0.6 已实现 cancellation/attempt token；超时或取消后的晚到结果记录 discarded，禁止提交事实、索引或 completed。
- [x] C0.7 已明确外部线程/模型调用超时不等于真实取消，并在步骤边界停止后续工作。
- [x] C0.8 已用模拟 PDF 入库步骤完成进程中断、租约接管、重复命令和晚到结果故障演练。
- [ ] C0.9 运行 C0 回归和代码审查，提交 `feat(execution): add durable run foundation`。

### C0 包退出条件

- [x] C0-GATE-1 同一步骤在任意时刻只有一个有效租约执行者。
- [x] C0-GATE-2 状态 CAS、重复命令和事件序号测试全绿。
- [x] C0-GATE-3 超时/取消后的晚到结果无法改变当前状态或可见数据。
- [x] C0-GATE-4 M 可直接复用该基础执行模拟入库，不新增平行状态机。

## M. 可验证多模态财报理解

### M0. 源文件迁移、处理决策与首轮索引

- [x] M0.1 冻结当前全部源 PDF 的路径、SHA-256、页数、加密/可读状态和 logical document 映射；迁移过程只读。
- [x] M0.2 在 `multimodal_enabled` 路径内适配 `upload_pdf()`：同文件系统 staging 写入、关闭后校验与哈希、数据库登记成功后发布不可变 document version；开关关闭时旧契约不变。
- [ ] M0.3 实现 logical_document_id、document_version_id 与内容寻址 blob；同逻辑同 hash 幂等，相同 blob 的不同逻辑文档不合并，物理回收遵守引用计数和保留期。
- [x] M0.4 为当前每个文档生成 `REUSE/ENRICH/TARGETED_REEXTRACT/FULL_REEXTRACT` 决策、依据和错误状态；禁止任意比例阈值和无证据全量重跑。
- [ ] M0.5 对 REUSE/ENRICH 复用现有 MinerU Markdown、图片和表格；只为明确失败页、复杂表格/图表、扫描页或定位失败区域建立定向任务。
- [ ] M0.6 在 V7MetadataStore 建立 document version、artifact、fact、claim、calculation、report 及关联表、外键、版本和失效状态；不引入图数据库。
- [ ] M0.7 侧向构建首个 v7 generation，覆盖迁移基线全部 active 文档；复用合格 chunk，但重算缺少 parser/splitter/preprocess/embedding/schema 版本证据的旧向量。
- [ ] M0.8 校验新 generation 的文档覆盖、chunk 数量、向量维度、文件哈希、BM25/FAISS metadata 对齐和抽样检索；任何失败不改变旧 active publication。
- [ ] M0.9 记录迁移前后源 PDF 哈希、处理决策、索引发布/回滚和溯源外键完整性证据。
- [ ] M0.10 冻结旧上传/删除/查询 JSON 夹具，定义新上传异步状态的可选字段和功能开关开/关回归。
- [ ] M0.11 补齐 PDF magic、空文件、加密、页数、截断、Windows 显示文件名和哈希键冲突校验；staging/孤儿 blob 不得被任何读取端点访问。
- [ ] M0.12 定义稳定错误分类、有限重试和不可重试边界；磁盘、数据库、解析或索引失败不得产生 complete 状态。
- [x] M0.12.a 将 MinerU 单文档解析超时接入 `hot_load.parse_timeout_seconds`，默认 600 秒，校验正数并覆盖配置读取、适配器传参和失败状态测试。
- [x] M0.12.b 热加载普通 PDF 复用 `extract_batch` 异步轮询，大 PDF 按 150 页物理页分批并输出物理页进度。
- [x] M0.12.c 合并大 PDF Markdown 时写入物理页批次标记，任一批次失败则阻断本次解析结果。
- [x] M0.12.d 修复热加载临时 Markdown 未参与页映射的问题，并过滤批次标记，避免污染检索文本。
- [ ] M0.13 实现 PublicationSet：绑定 index generation、可见 document versions、artifact/fact 版本边界和 corpus revision；active publication 以 SQLite 为唯一真值。
- [ ] M0.14 首轮基线固定 corpus revision；并发上传/删除进入下一 publication，发布使用 expected revision/CAS，过期构建标记 superseded。
- [ ] M0.15 以短事务发布已校验的不可变文件；实现跨索引、文档、制品和事实的整组回滚，不允许只回滚索引指针。

### M1. 评测、清单与页图

- [ ] M1.1 在 A 的数据框架中建立不少于 40 个区域级多模态案例和独立指标分母，按文档/公司拆分开发集与至少 25% 的冻结留出集。
- [x] M1.2 清点 12 份现有 PDF/Markdown 的图片引用、HTML/Markdown 表格、公式与缺失文件，不重新生成可复用制品。
- [ ] M1.3 定义带 schema 版本和状态迁移的 DocumentAssetManifest、PageArtifact、VisualRegion、TableArtifact、ChartArtifact 和 VisualEvidence，并通过 V7MetadataStore 事务持久化；JSON 仅作诊断导出。
- [ ] M1.4 为 MinerU `_extract_single/_process_large_pdf` 增加旁路状态记录，保留原解析结果和逻辑。
- [ ] M1.5 使用现有 PyMuPDF 实现幂等页图、缩略图、规范化坐标和内容哈希缓存。
- [ ] M1.6 实现制品清单完整性校验；缺页批次、缺失图片和 unresolved 定位均禁止 complete 状态。
- [ ] M1.7 先用一份 PDF、一个普通表格和一个复杂视觉区域完成“清单→事实→SourceInfo→前端定位”纵向试点，默认开关关闭；试点通过后再批量扩展。
- [ ] M1.8 实现不可变索引 generation、staging 构建和完整校验；由 PublicationSet 原子发布并整组回滚，不以文件指针为真值。
- [ ] M1.9 建立统一 PublicationResolver，请求开始固定 publication ID，并让索引、文档、artifact、事实查询及 RAGGenerator、RetrieveTool、CompareTool 缓存使用同一快照。
- [ ] M1.10 旧 generation 仅在无活动引用并通过保留期后回收；Windows 下不得删除正在打开的 FAISS/BM25 文件。
- [ ] M1.11 区分 logical_document_id 与 document_version_id：同 hash 上传幂等，不同 hash 的同名文件创建新版本，完整索引前不替换 active 版本。

### M2. 路由与结构提取

- [ ] M2.1 实现可解释 PageRouter，区分 text/table/chart/scan/mixed，并证明纯文本页不调用视觉模型。
- [ ] M2.2 实现 MinerU HTML/Markdown 表格结构适配器，保留多级表头、row/colspan、脚注、单位、期间和原始值。
- [ ] M2.3 实现保守的跨页续表关系；条件不充分时保持分离和待确认。
- [ ] M2.4 新增类型化 BaseVisionProvider、VisionRequest、VisionResponse 和显式 capability/config 检查，保持 BaseLLMProvider.chat 不变。
- [ ] M2.5 对复杂表格难例调用视觉能力并输出结构化结果、置信度、模型、用量和区域。
- [ ] M2.6 实现图表标题、图例、轴、单位、期间、系列、数据点和趋势提取；不能可靠读数时只输出趋势候选。
- [ ] M2.7 只在无可用文本层或既有解析失败时处理扫描页；能力不可用时返回 incomplete，不静默猜测。

### M3. 金融事实、证据与安全

- [ ] M3.1 把视觉数值接入 B 阶段统一归一器和 FinancialFactService，禁止视觉专用换算表或事实库。
- [ ] M3.2 实现正文—表格—图表交叉核验，并把真实差异送入统一冲突引擎。
- [ ] M3.3 扩展 SourceInfo 与 `_build_agent_answer_sources()` 的可选视觉字段，缺省响应保持兼容。
- [ ] M3.4 给视觉内容增加提示词注入、越权指令、异常像素/文件和预算安全边界。
- [ ] M3.5 低置信或定位未解析结果只保存 candidate/pending_review，不进入 verified 事实和确定性计算。
- [ ] M3.6 扩展 `delete_pdf()` 和重建索引流程，清理或失效所有视觉制品、事实和索引，验证无孤儿数据。
- [ ] M3.7 复用 `build_company_index()` 与原 FAISS/BM25 metadata 生成链写入 artifact 引用；禁止建立第二套视觉向量库。
- [ ] M3.8 给视觉索引启用兼容的 strict 模式，embedding 失败时标记 incomplete，禁止零向量制品进入可用索引。
- [ ] M3.9 新增受认证的 artifact ID 图像读取端点；不挂载公开制品目录，不接受客户端文件路径。
- [ ] M3.9.1 明确首版仅为现有 API key 下的单用户/单租户端点认证，不实现或宣称文档级多租户 ACL。
- [ ] M3.10 定义查询、重建、版本激活和删除的线性化点：新查询排除 deleting 版本；删除返回完成前等待活动引用释放或明确返回异步状态。
- [ ] M3.11 删除 logical document/version 时先失效其事实和索引可见性，标记受影响声明、计算与报告为 stale；共享 blob 仅在零引用和保留期后物理回收。
- [ ] M3.12 使用外键 RESTRICT 与软失效保留历史审计；共享 blob 引用变更和删除资格在同一事务串行化，覆盖并发上传/回收。

### M4. 前端与验收

- [ ] M4.1 扩展前端 SourceInfo、buildEvidenceBundles 和 buildEvidenceChain，保持旧来源兼容。
- [ ] M4.2 在 EvidencePanel、SourceCard 和 EvidenceChainGraph 增加页图预览、区域高亮、证据类型与完整性警告。
- [ ] M4.3 复用现有图表组件展示识别后的系列及原始图表证据，不重写 Charts 模块。
- [ ] M4.4 跑多模态专集、文本回归、上传/删除生命周期、安全与成本报告。
- [ ] M4.4.1 单列冻结留出集结果、高风险误入库数、视觉路由比例、缓存命中、调用量、失败率与 P95；M 基线后留痕批准成本门禁。
- [ ] M4.4.2 检查页图预览与区域高亮的键盘操作、替代文本和结构化表格/图表说明。
- [ ] M4.4.3 准备一例成功视觉定位与一例显式拒绝结论的失败演示，禁止只挑最佳样本。
- [ ] M4.5 运行 M 包全回归和代码审查，提交 `feat(multimodal): add verifiable financial document intelligence`。

### M 包退出条件

- [ ] M-GATE-1 表格、图表、单位/期间、区域定位和低置信拦截达到 acceptance.md 阈值。
- [ ] M-GATE-2 所有视觉事实可定位原文制品，无法定位时明确 unresolved 且不猜测。
- [ ] M-GATE-3 缺页、视觉模型不可用和低置信均产生显式 incomplete/candidate 状态，不存在隐藏回退。
- [ ] M-GATE-4 原文本检索、问答、上传、证据链和图表生成无回归。
- [ ] M-GATE-5 冻结留出集无高风险视觉数字错误进入 verified，且成本与失败样本报告完整。
- [ ] M-GATE-6 当前文档处理决策与首轮 v7 generation 覆盖率均为 100%，源 PDF 哈希零变化，新代际失败可回滚，已发布溯源无悬空引用。

## C1. 可恢复研究任务产品化

### C1.1 研究任务模型与持久化

- [ ] C1.1 将 ResearchTask、TaskStep 和 DAG 节点映射到 C0 ExecutionRun/StepAttempt，不创建第二套状态表。
- [ ] C1.2 扩展研究任务合法迁移和 waiting_approval 语义，继续使用 C0 revision/CAS。
- [ ] C1.3 复用 V7MetadataStore、事务、租约、事件和调用账本；不得创建第二个任务数据库。
- [ ] C1.4 保持 `AgentMemory` 会话记忆逻辑不变，通过 task_id 关联而非替换。
- [ ] C1.5 定义研究检查点 JSON schema，只保存稳定 ID、generation、制品/事实版本和可序列化数据。

### C1.2 恢复、编排与事件

- [ ] C2.1 恢复时复用依赖版本一致的已完成步骤和成功工具/模型调用；版本变化时拒绝错误复用。
- [ ] C2.2 实现错误分类、有限重试、暂停、恢复和取消，并继承 C0 晚到结果隔离。
- [ ] C2.3 在 Planner/Orchestrator/DAG 步骤边界写入 C0 状态；现有线程超时不得直接视为调用已停止。
- [ ] C2.4 为任务事件流增加持久 ID、保留期限和“游标早于最旧事件”的明确重同步响应。
- [ ] C2.5 新任务流采用带 Authorization 的 fetch streaming；禁止加入 APIAuthMiddleware 免鉴权前缀或在 URL 放长期 API Key。
- [ ] C2.6 新增任务创建、查询、事件流、暂停、恢复、取消 API，命令携带 command_id/revision，保持原即时问答 API 不变。
- [ ] C2.7 持久任务失败时保存选定路径，不静默回退或切换 single/multi。
- [ ] C2.8 前端按 revision 合并事件，展示运行、暂停、等待审批、失败、取消和恢复状态。
- [ ] C2.9 执行 Worker 异常、进程中断、并发控制命令、超时晚到结果和断线重连故障演练。
- [ ] C2.10 运行 C1 包全回归和代码审查，提交 `feat(tasks): productize durable research execution`。

### C1 包退出条件

- [ ] C1-GATE-1 五类故障与并发演练全部达到预期状态。
- [ ] C1-GATE-2 依赖版本一致的已完成步骤及成功调用重复执行为 0；有副作用调用自动重复执行为 0。
- [ ] C1-GATE-3 非法/过期 revision 状态迁移全部阻止，晚到结果无法复活任务。
- [ ] C1-GATE-4 新任务流需要有效鉴权，旧聊天和会话记忆无回归。

## D. 安全、审计与成本治理

- [ ] D1.1 定义工具风险等级、权限策略和默认拒绝边界。
- [ ] D1.2 实现参数绑定、时效限制的审批记录。
- [ ] D1.2.1 审批哈希同时绑定 task revision、plan、事实/制品版本和 index generation；任一依赖变化使旧审批失效。
- [ ] D1.3 为关键冲突裁决和正式报告签发加入审批门禁；仅在存在真实高风险工具时扩展到工具执行。
- [ ] D1.4 建立只追加审计事件和任务回放查询。
- [ ] D1.4.1 关键状态迁移、审批消费和审计事件在 V7MetadataStore 同一事务提交，避免“已执行但无审计”或“已审计但未执行”。
- [ ] D1.5 在日志、追踪和报告持久化前实施敏感字段脱敏。
- [ ] D1.6 扩展安全集：文档注入、工具参数注入、跨 Agent 污染和越权调用。
- [ ] D1.7 统计任务 Token、调用次数、延迟和成本估算。
- [ ] D1.8 实现软预算预警和硬预算暂停。
- [ ] D1.9 比较现有 single/multi 路由质量—成本曲线并保存理由。
- [ ] D1.10 运行 D 包回归和代码审查，提交 `feat(governance): add agent policy audit and budgets`。

### D 包退出条件

- [ ] D-GATE-1 未审批高风险调用执行为 0。
- [ ] D-GATE-2 审计日志能重建一次完整任务关键路径。
- [ ] D-GATE-3 安全攻击集达到批准结果。
- [ ] D-GATE-4 超预算任务安全暂停且可恢复。

## E. 研究工作流与可审计报告

- [ ] E1.1 定义 ResearchPlan、Claim、ResearchReport 与审核状态模型。
- [ ] E1.2 新增研究任务列表和详情 API。
- [ ] E1.3 新增研究任务页面并复用现有布局、DAG、证据、图表组件。
- [ ] E1.4 支持执行前调整范围和预算重新计算。
- [ ] E1.5 支持关键冲突批准、驳回和保持未决。
- [ ] E1.6 生成声明级可追溯 Markdown/HTML 报告。
- [ ] E1.7 实现事实修订后的局部失效与报告版本比较。
- [ ] E1.8 记录 PDF、Word、Excel 三个后续独立 OpenSpec 子变更；它们不阻塞 v7.0 首发，需要新包时先核查并申请。
- [ ] E1.9 准备 5 分钟主流程、冲突、恢复和安全演示数据。
- [ ] E1.10 运行 E 包回归、可访问性检查和代码审查，提交 `feat(research): deliver auditable research workflow`。

### E 包退出条件

- [ ] E-GATE-1 完成计划—执行—审核—报告闭环。
- [ ] E-GATE-2 关键声明都有证据、计算或分析判断标识。
- [ ] E-GATE-3 事实修订仅影响依赖声明。
- [ ] E-GATE-4 现有聊天与其他页面不回归。

## F. 总验收与发布

- [ ] F1. 运行全部后端测试、前端测试、生产构建、OpenSpec 检查和乱码扫描。
- [ ] F2. 运行完整金融评测、故障演练、安全集与成本对比。
- [ ] F3. 完成三方审查：规格符合性、代码质量、产品演示价值；确认 A、B、C0、M、C1、D、E 均已退出。
- [ ] F4. 更新 README、CHANGELOG、`openspec/project.md` 和交接文档，区分事实与目标指标。
- [ ] F5. 推送开发分支，核查 GitHub Actions 与分支保护实际结果。
- [ ] F6. 合并 main 后再次验证远端 SHA、工作区和回归结果。
- [ ] F7. 用户确认发布后创建 annotated tag `v7.0`，标签说明包含七个工作包与关键指标。
- [ ] F8. 归档 OpenSpec 变更并核对归档完整性。

## 提交原则

- 每个工作包至少一个语义清晰的 Conventional Commit，不将七个阶段压成一个巨大提交。
- RED 测试可与对应最小实现同一提交，但提交前必须证明测试先红后绿，并把证据写入 TDD。
- 不在阶段中途打版本标签；里程碑只使用分支提交和 OpenSpec 状态。
