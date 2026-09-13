# 任务清单：v7.0 可信金融研究 Agent 升级

> 状态约定：规划阶段全部未开始。实施时每项必须先运行对应 RED 测试，完成实现与回归后，才允许把 TDD 和任务同时改为 GREEN/完成。

## 0. 实施前门禁

- [ ] 0.1 用户批准 proposal、design、roadmap、specs 和三轮核查结论。
- [ ] 0.2 从最新 main 创建 `codex/trusted-financial-agent-v7` 开发分支或隔离 worktree。
- [ ] 0.3 重新确认工作区干净、HEAD 与远端同步、v5.19 基线可定位。
- [ ] 0.4 运行并记录现有后端、前端、构建和 OpenSpec 质量门禁基线。
- [x] 0.5 复核候选依赖的解释器可见性、包元数据和锁文件三者是否一致；全局 `openevals` 的可见性异常被隔离环境排除，首版不得依赖该状态。2026-09-13 隔离 Python 3.11 以 `requirements.lock` 完整安装，`pip check`、`compileall` 与 CI 指定后端集合 32 passed；隔离 Node 20.19.5 以 `npm ci` 安装 421 包。Linux 一次性 Node 20.19.5 容器用原样 `npm test` 为 53 文件/287 passed，随后原样 `npm run build` 通过；临时服务器目录已删除。Windows 本机 Vitest 仍会卡住，但已确认不代表候选测试失败，故此依赖一致性任务完成。
- [ ] 0.5.1 核查 OpenSpec CLI 是否可用；当前环境无 `openspec` 命令，如实施需要安装，先说明用途并征得用户同意。
- [ ] 0.6 记录活动变更 `openspec-lifecycle-and-ci-quality-gate` 的未闭环项；它不阻塞 A1/A2 本地开发，但在修改现有 Quality Gate 前必须完成合并核查。
- [ ] 0.7 确认 v7.0 是路线版本；禁止提前创建 Git 标签。
- [ ] 0.8 逐项批准 `reuse-matrix.md` 的函数边界；实施中出现未列明替换、平行服务或新增依赖时先更新规格。
- [ ] 0.9 核对多模态本地依赖：PyMuPDF/Pillow、MinerU 元数据、DashScope 实际版本和锁文件；当前未安装 OCR/OpenCV 相关包，不得默认引入。
- [ ] 0.10 冻结 v5.19 OpenAPI、关键 JSON、配置、company_registry/metadata 和“无 v7 数据库”兼容夹具。（2026-09-12 已新增不含敏感值的 Git 配置指纹、无 Key OpenAPI/关键 JSON 指纹、旧操作签名一致、既有响应模型仅新增可选字段及 14 个无 Key 响应的脱敏正文指纹；既有 `/api/agent/stream` 鉴权旁路已由独立变更 `fix-agent-stream-authentication` 修复，候选对无 Key/错误 Key SSE 改为 401，作为安全例外保留历史 503 指纹。2026-09-13 复核 `v5.19` 标签为 `a6bbad99`，且为 main/候选祖先；清单与结构化事实兼容回归 13 passed。该 Git 树仅跟踪 `data/stock_data/subset.csv`，不含 company_registry/metadata；正式服务器仍为更早的 `8f8b26b`、含未跟踪手工备份，实际存在索引元数据但时间为 2026-08-12/14，早于 v5.19 标签且服务器不能解析该标签，不能证明为 v5.19 数据来源。后续只读寻址确认 GitHub 远端全部标签/分支中，v5.17～v5.19、两个备份标签与 v1 分支的 data 树均只有 subset.csv，Release 为 0 条；本地同级旧项目也无 v5.19 对象，其 v1 索引备份与当前同名备份哈希一致且时间为 2026-05-28；服务器 `/opt/data` 索引时间为 2026-07-18，未发现版本化归档、Docker 卷或额外挂载备份盘。完整 OpenAPI 正文、认证成功响应、可审计历史运行时索引数据和无 v7 数据库夹具仍未捕获，任务不得标绿。）
- [x] 0.10.1 将当前候选 `8486c0c` 同步并构建至隔离测试栈：Compose 隔离契约 2 passed，后端/前端健康为 200，匿名 SSE 401、CORS 预检 200、研究登录/会话 200，且仅挂载隔离数据目录；研究任务提交/立即驳回/读取/执行摘要为 200，未获批执行或调用 Provider。干净 Python 3.11 定向集合 36 passed、差异检查通过。真实浏览器读屏、候选远端 CI/分支保护和 A3.1 历史数据仍保持 RED，不得以本项替代。
- [ ] 0.10.2 恢复最新候选的服务器/浏览器外部门禁：2026-09-13 后续两次 SSH TCP 诊断均超时，Chrome 调试未附加，故不能复核服务器文件哈希、Nginx 代理、真实读屏或 Provider；未修改服务器。Quality Gate 只随面向 main 的 PR 触发，候选推送不触发 CI/镜像发布，创建 PR 需负责人明确授权。
- [ ] 0.10.3 处置隔离测试目录完整性漂移：SSH 恢复后，`STAGING_CANDIDATE_COMMIT=8486c0c` 与三个关键文件 SHA-256 不一致，且不匹配本地候选、先前隔离候选或正式 `8f8b26b`；隔离容器已退出，来源未知。未取得目录维护者确认或显式覆盖授权前，不得启动、覆盖、删除或重建该目录。候选 `a046a6a` 的 GitHub 推送也须明确授权将源码外发至指定远端分支。
- [x] 0.10.4 修复 PR 前端门禁中的 ChartsPage 异步测试竞态：GitHub PR #1 的 frontend 检查在 `ChartsPage.test.tsx:59` 失败；研究筛选条件区域会先于异步 `getCharts()` 结果渲染，原同步 `getByText` 不保证图表标题已出现。已改为等待型断言，未改产品数据或图表过滤逻辑；本地 `ChartsPage.test.tsx` 4 passed，生产构建通过。`033dcbd` 推送后，PR #1 的 frontend、backend、workflow-lint 均为 success。
- [ ] 0.10.5 完成合并权限与人工门禁：单人仓库例外已获用户明确授权。`main` 仍严格要求 `frontend`、`backend`、`workflow-lint`，管理员同样受限，禁止强制推送/删除且要求对话解决；已移除无法由单账号满足的独立批准审查要求。PR #1 三项 CI 成功且状态为 `clean`。真实浏览器/辅助技术读屏、历史 v5.19 运行时基线、真实 Provider 验收和明确最终合并授权仍不能被 CI 替代。
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
- [x] C0.9 已运行 C0 回归和代码审查，提交 `feat(execution): add durable run foundation`。

### C0 包退出条件

- [x] C0-GATE-1 同一步骤在任意时刻只有一个有效租约执行者。
- [x] C0-GATE-2 状态 CAS、重复命令和事件序号测试全绿。
- [x] C0-GATE-3 超时/取消后的晚到结果无法改变当前状态或可见数据。
- [x] C0-GATE-4 M 可直接复用该基础执行模拟入库，不新增平行状态机。

## M. 可验证多模态财报理解

### M0. 源文件迁移、处理决策与首轮索引

- [x] M0.1 冻结当前全部源 PDF 的路径、SHA-256、页数、加密/可读状态和 logical document 映射；迁移过程只读。
- [x] M0.2 在 `multimodal_enabled` 路径内适配 `upload_pdf()`：同文件系统 staging 写入、关闭后校验与哈希、数据库登记成功后发布不可变 document version；开关关闭时旧契约不变。
- [x] M0.3 已实现 logical_document_id、document_version_id 与内容寻址 blob；同逻辑同 hash 幂等，相同 blob 的不同逻辑文档不合并，物理回收遵守引用计数和保留期。
- [x] M0.4 为当前每个文档生成 `REUSE/ENRICH/TARGETED_REEXTRACT/FULL_REEXTRACT` 决策、依据和错误状态；禁止任意比例阈值和无证据全量重跑。
- [x] M0.5 对 REUSE/ENRICH 复用现有 MinerU Markdown、图片和表格；只为明确失败页、复杂表格/图表、扫描页或定位失败区域建立定向任务。
- [x] M0.6 在 V7MetadataStore 建立 document version、artifact、fact、claim、calculation、report 及关联表、外键、版本和失效状态；不引入图数据库。
- [x] M0.7 侧向构建首个 v7 generation，覆盖迁移基线全部 active 文档；复用合格 chunk，但重算缺少 parser/splitter/preprocess/embedding/schema 版本证据的旧向量。
- [x] M0.8 校验新 generation 的文档覆盖、chunk 数量、向量维度、文件哈希、BM25/FAISS metadata 对齐和抽样检索；任何失败不改变旧 active publication。
- [x] M0.9 记录迁移前后源 PDF 哈希、处理决策、索引发布/回滚和溯源外键完整性证据。
- [x] M0.10 冻结旧上传/删除/查询 JSON 夹具，定义新上传异步状态的可选字段和功能开关开/关回归。
- [x] M0.11 补齐 PDF magic、空文件、加密、页数、截断、Windows 显示文件名和哈希键冲突校验；staging/孤儿 blob 不得被任何读取端点访问。
- [x] M0.12 定义稳定错误分类、有限重试和不可重试边界；磁盘、数据库、解析或索引失败不得产生 complete 状态。
- [x] M0.12.a 将 MinerU 单文档解析超时接入 `hot_load.parse_timeout_seconds`，默认 600 秒，校验正数并覆盖配置读取、适配器传参和失败状态测试。
- [x] M0.12.b 热加载普通 PDF 复用 `extract_batch` 异步轮询，大 PDF 按 150 页物理页分批并输出物理页进度。
- [x] M0.12.c 合并大 PDF Markdown 时写入物理页批次标记，任一批次失败则阻断本次解析结果。
- [x] M0.12.d 修复热加载临时 Markdown 未参与页映射的问题，并过滤批次标记，避免污染检索文本。
- [x] M0.13 实现 PublicationSet：绑定 index generation、可见 document versions、artifact/fact 版本边界和 corpus revision；active publication 以 SQLite 为唯一真值。
- [x] M0.14 首轮基线固定 corpus revision；并发上传/删除进入下一 publication，发布使用 expected revision/CAS，过期构建标记 superseded。
- [x] M0.15 以短事务发布已校验的不可变文件；实现跨索引、文档、制品和事实的整组回滚，不允许只回滚索引指针。

### M1. 评测、清单与页图

- [ ] M1.1 在 A 的数据框架中建立不少于 40 个区域级多模态案例和独立指标分母，按文档/公司拆分开发集与至少 25% 的冻结留出集。
- [x] M1.1.a 扩展评测 schema 和独立多模态覆盖报告，拒绝文档/公司跨 development 与 holdout 泄漏；现有真实可复核样本不足 40 条，M1.1 主任务保持未关闭。
- [x] M1.1.b 基于真实 PDF 页和归一化 bbox 建立 pending_review 区域候选扫描器；候选与 verified 评测样本严格分离，批量人工复核后才可进入主任务分母。
- [x] M1.1.c 生成并校验 385 条候选记录（8 个文档）；源 SHA256、物理页和 bbox 漂移检查为 0，候选集仍保持 pending_review。
- [x] M1.1.d 生成首批普通表格人工复核包：30 条 development 与 10 条 holdout 按公司/文档隔离，逐条复验源 SHA256、物理页和 bbox；全部保持 pending_review，不计入 M1.1 主任务分母。
- [x] M1.2 清点 12 份现有 PDF/Markdown 的图片引用、HTML/Markdown 表格、公式与缺失文件，不重新生成可复用制品。
- [x] M1.3 定义带 schema 版本和状态迁移的 DocumentAssetManifest、PageArtifact、VisualRegion、TableArtifact、ChartArtifact 和 VisualEvidence，并通过 V7MetadataStore 事务持久化；JSON 仅作诊断导出。
- [x] M1.3.a 为 TableArtifact、ChartArtifact、VisualEvidence 增加 V7MetadataStore 事务仓储，并拒绝跨 manifest 的页图、区域、表格和图表关联；统一状态迁移和端到端试点仍待完成。
- [x] M1.3.b 为 TableArtifact、ChartArtifact、VisualEvidence 增加受限状态迁移和同事务审计事件。
- [x] M1.3.c 为 Manifest 的完整性导出状态、VisualRegion 与 ParseBatch 增加受限迁移/同事务审计；migration 18 为 PageArtifact、VisualRegion、TableArtifact、ChartArtifact、VisualEvidence 补齐 `schema_version`，PageArtifact 保持“只以完整文件创建为 immutable complete”的既有语义。
- [x] M1.4 为 MinerU _extract_single/_process_large_pdf 增加旁路状态记录，保留原解析结果和逻辑。
- [x] M1.5 使用现有 PyMuPDF 实现幂等页图、缩略图、规范化坐标和内容哈希缓存。
- [x] M1.6 实现制品清单完整性校验；缺页批次、缺失图片和 unresolved 定位均禁止 complete 状态。
- [ ] M1.7 先用一份 PDF、一个普通表格和一个复杂视觉区域完成“清单→事实→SourceInfo→前端定位”纵向试点，默认开关关闭；试点通过后再批量扩展。
- [x] M1.7.a 为 `SourceInfo` 增加可选 `visual_locator`：仅透传 complete 制品的 manifest/page/region/bbox，旧来源 JSON 不增加空字段；前端来源卡只显示只读坐标说明，不伪造页图预览。
- [x] M1.7.b 增加默认关闭的受控 PageArtifact PNG 端点：只接受 manifest 与已登记页制品 ID，从 SQLite 解析完整文件；拒绝路径、未知 ID 和跨 manifest 请求，不引入文档级 ACL 承诺。
- [x] M1.7.c 前端通过统一 Bearer 鉴权读取 complete 页图 Blob，并按规范化 bbox 叠加只读高亮；不得在 URL 传递密钥或为 incomplete 制品伪造预览。
- [x] M1.7.d 为 incomplete 视觉制品增加不含路径和坐标的可访问提示；保持 complete 页图读取路径不变且不触发无效请求。
- [x] M1.7.e 为未发布且未进入索引代际的 V7 文档增加制品清理服务：事务清理 manifest、页图、区域、表图制品、视觉证据和解析批次，已发布/已索引/已关联事实的文档显式拒绝。
- [x] M1.7.f 为页图根目录增加 `.deleting` 遗留文件的受限幂等恢复清理，避免目录外文件被误删。
- [x] M1.1.b 区域级评测样本强制记录 PDF SHA-256 与物理页，并拒绝同一源页或裁剪变体跨 development/holdout 分区。
- [x] M1.7.g 将页图 `.deleting` 恢复入口收敛到 V7 处理协调器的实际 PageImageRenderer 输出根目录。
- [x] M1.1.c 同步区域级源页身份到 JSON Schema，避免运行时与对外数据契约不一致。
- [x] M1.7.h 为已索引文档提供“排除后候选代际”构建入口：冻结排除后的文档基线并审计，但不原地改写 active 文档或 active publication。
- [x] M1.8.a 将候选 generation 的 staging 制品验证与 PublicationSet 的 prepared/CAS 基线连接；该步骤只准备、不激活。
- [x] M1.8.b 将实际 `IndexPublicationManager` 的 staging generation 制品注册为 V7 candidate 的不可变制品目录/manifest 绑定（持久化路径无关的 hash/size manifest）；绑定失败时不得创建 PublicationSet，active publication 保持不变。
- [x] M1.8.c 在 `V7GenerationPublicationCoordinator` 上提供受控显式 CAS activation 入口：并发/过期基线得到 `superseded`，绝不通过 legacy JSON active 指针激活 V7 publication。
- [x] M1.8.d 为旧 generation 回收建立前置条件资格记录（无 active publication 引用、无活动请求引用、已过保留期、Windows 文件未打开）；只记录资格，不物理删除。
- [x] M1.8.e 端到端编排收口：排除文档构建候选 → 实际索引构建发布 → 制品绑定 → CAS 准备 → 显式激活 → 旧代际回收资格评估，并验证激活 superseded 与整组回滚（回滚后旧代际重新被 active 引用即失格）。
- [x] M1.8 实现不可变索引 generation、staging 构建和完整校验；由 PublicationSet 原子发布并整组回滚，不以文件指针为真值。
- [x] M1.9 建立统一 PublicationResolver，请求开始固定 publication ID，并让索引、文档、artifact、事实查询及 RAGGenerator、RetrieveTool、CompareTool 缓存使用同一快照。
  - [x] M1.9.a PublicationResolver 请求级快照固定：begin_request 在请求开始捕获 active 快照并在请求期间保持不变（期间激活新 publication 不影响本请求），current_snapshot/end_request/request_scope 提供完整请求作用域语义；无 active publication 时返回 None。
  - [x] M1.9.b HybridRetriever 快照代际注入：支持 generation_resolver 优先于 legacy JSON active 指针解析检索目录（generations/<generation_id>/<company>），未注入或解析为空时保持 legacy 指针与旧目录契约不变；检索器缓存按代际变化自动重载。
  - [x] M1.9.c 三工具接线同一快照：RetrieveTool/CompareTool/RAGGenerator 接受可选 publication_resolver，请求开始固定快照、finally 释放，检索使用快照代际，返回结果携带 publication_id；未注入时行为与现状完全一致。
- [x] M1.10 旧 generation 仅在无活动引用并通过保留期后回收；Windows 下不得删除正在打开的 FAISS/BM25 文件。
  - [x] M1.10.a 提供显式启停的受控批量回收入口：仅扫描 `validated` generation，按稳定顺序和 batch 上限逐项调用既有执行器；在途引用、保留期、active publication 和文件锁仍由执行器逐项审计并拦截。
- [x] M1.11 区分 logical_document_id 与 document_version_id：同 hash 上传幂等，不同 hash 的同名文件创建新版本，完整索引前不替换 active 版本。

### M2. 路由与结构提取

- [x] M2.1 实现可解释 PageRouter，区分 text/table/chart/scan/mixed，并证明纯文本页不调用视觉模型。
- [x] M2.2 实现 MinerU HTML/Markdown 表格结构适配器，保留多级表头、row/colspan、脚注、单位、期间和原始值。
- [x] M2.3 实现保守的跨页续表关系；条件不充分时保持分离和待确认。
- [x] M2.4 新增类型化 BaseVisionProvider、VisionRequest、VisionResponse 和显式 capability/config 检查，保持 BaseLLMProvider.chat 不变。
- [x] M2.5 对复杂表格难例调用视觉能力并输出结构化结果、置信度、模型、用量和区域。
- [x] M2.6 实现图表标题、图例、轴、单位、期间、系列、数据点和趋势提取；不能可靠读数时只输出趋势候选。
- [x] M2.7 只在无可用文本层或既有解析失败时处理扫描页；能力不可用时返回 incomplete，不静默猜测。

### M3. 金融事实、证据与安全

- [x] M3.1 把视觉数值接入 B 阶段统一归一器和 FinancialFactService，禁止视觉专用换算表或事实库。`VisualFactCandidateRepository` 强制调用共享归一器，`VisualFactAdmissionService` 只经既有 FinancialFactRepository 写入；接口层回归通过，真实 Provider 端到端验收另列 M-GATE。
- [x] M3.2 实现正文—表格—图表交叉核验，并把真实差异送入统一冲突引擎。已审核且关联事实的视觉候选经 `VisualFactConflictBridge` 复用既有冲突仓储，定向回归通过。
- [x] M3.3 扩展 SourceInfo 与 `_build_agent_answer_sources()` 的可选视觉字段，缺省响应保持兼容。来源兼容与视觉定位定向回归通过。
- [x] M3.4 给视觉内容增加提示词注入、越权指令、异常像素/文件和预算安全边界。`VisionSafetyGuard` 在实际 Provider 调用前隔离不可信内容、校验 PNG/JPEG 尺寸与文件大小，并限制调用次数和预估 Token；拒绝结果显式为 incomplete。
- [x] M3.5 低置信或定位未解析结果只保存 candidate/pending_review，不进入 verified 事实和确定性计算。候选审核、低置信拒绝和已审核准入回归通过。
- [x] M3.6 扩展 `delete_pdf()` 和重建索引流程，清理或失效所有视觉制品、事实和索引，验证无孤儿数据。
  - [x] M3.6.a `delete_pdf(filename, deletion_coordinator=...)` 集成 V7 删除协调器：多模态开关开启时端点注入协调器，为同名全部未删除版本幂等创建删除请求（已 deleting 版本跳过），V7 请求先于文件删除创建；不注入时行为与现状完全一致。后续推进复用 M3.10.c/M3.11 链（advance → cleanup_ready → 事实失效/stale 传播/blob 回收）与 M3.10.b 重建发布链、M1.10 旧代际回收。
- [ ] M3.7 复用 `build_company_index()` 与原 FAISS/BM25 metadata 生成链写入 artifact 引用；禁止建立第二套视觉向量库。
  - [x] M3.7.a metadata 链 artifact 引用承接：`build_company_index()` 在既有 metadata 生成链上为携带 `artifact_refs` 的子块写入引用，未携带的子块不新增字段（旧 9 字段契约不变）；FAISS/BM25 仍由同一构建链产出，无第二套向量库。视觉子块上游生产随 M3.1-M3.5 视觉链路。
- [ ] M3.8 给视觉索引启用兼容的 strict 模式，embedding 失败时标记 incomplete，禁止零向量制品进入可用索引。
  - [x] M3.8.a strict 模式索引构建语义：`build_faiss_index(..., strict=True)` 任一 embedding 批次失败即抛出 `EmbeddingIncompleteError` 中止构建，不补零向量、不写 index.faiss 制品；默认 strict=False 保持 legacy 补零行为不变。视觉编排层捕获异常后标记 incomplete 的接线随视觉链路启用。
- [x] M3.9 新增受认证的 artifact ID 图像读取端点；不挂载公开制品目录，不接受客户端文件路径。
- [x] M3.9.1 明确首版仅为现有 API key 下的单用户/单租户端点认证，不实现或宣称文档级多租户 ACL。
- [x] M3.10 定义查询、重建、版本激活和删除的线性化点：新查询排除 deleting 版本；删除返回完成前等待活动引用释放或明确返回异步状态。
  - [x] M3.10.a 建立文档版本删除线性化与文档级查询可见性：短事务把版本置为 `deleting` 并记录失效；已固定快照保持原 ID，新查询仅选择 `active` 版本，原始 blob 解析拒绝 deleting 版本。
  - [x] M3.10.b 将删除可见性接入 PublicationResolver、generation 检索与活动请求租约；已完成 PublicationResolver 的 fail-closed 过滤、活动请求租约计数、`waiting_for_active_requests/rebuild_required` 删除请求状态，以及 generation 级排除：`deleting` 线性化版本可被排除构建候选代际，经制品绑定与 PublicationSet CAS 发布使替代 publication 生效；租约等待/过期治理、异步删除执行和物理清理由 M3.10.c 与 M3.11/M3.12 完成。
  - [x] M3.10.c 租约等待/过期治理与异步删除执行：过期租约自动不再阻塞删除进度；`advance_request()` 在存在未过期租约时返回 `waiting_for_active_requests`，租约归零但 active publication 仍含被删版本时保持 `rebuild_required`，替代 publication 生效后进入 `cleanup_ready` 稳定终态（schema v22 放宽 CHECK 约束），全程不触碰版本本体。
- [x] M3.11 `cleanup_request()` 物理清理执行器：失效事实可见性（删除版本的事实关联行）、经 ProvenanceRepository 传播受影响计算/声明/报告为 stale 并写入软失效审计；共享 blob 在排除 `deleting` 引用后零引用且超过保留期时物理回收文件，deleting 版本行经外键继续保护 blob 登记行。
- [x] M3.12 外键 RESTRICT 全库启用并验证 `PRAGMA foreign_key_check` 一致；软失效审计（`v7_document_version_invalidations`）保留删除请求与清理动作历史；共享 blob 引用变更（上传登记）与删除资格判定（回收）均在 `BEGIN IMMEDIATE` 事务内串行化，并发引用插入经写锁等待后基于最新引用判定。

### M4. 前端与验收

- [x] M4.1 扩展前端 SourceInfo、buildEvidenceBundles 和 buildEvidenceChain，保持旧来源兼容。
- [x] M4.2 在 EvidencePanel、SourceCard 和 EvidenceChainGraph 增加页图预览、区域高亮、证据类型与完整性警告。
- [x] M4.3 复用现有图表组件展示识别后的系列及原始图表证据，不重写 Charts 模块。
- [ ] M4.4 跑多模态专集、文本回归、上传/删除生命周期、安全与成本报告；本地 fail-closed 准入报告已完成，真实 Provider、人工复核与运行账本未齐，主项保持未关闭。
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

- [x] C1.1 将 ResearchTask、TaskStep 和 DAG 节点映射到 C0 ExecutionRun/StepAttempt，不创建第二套状态表。
- [x] C1.2 扩展研究任务合法迁移和 waiting_approval 语义，继续使用 C0 revision/CAS。
- [x] C1.3 复用 V7MetadataStore、事务、租约、事件和调用账本；不得创建第二个任务数据库。
- [x] C1.4 保持 `AgentMemory` 会话记忆逻辑不变，通过 task_id 关联而非替换。
- [x] C1.5 定义研究检查点 JSON schema，只保存稳定 ID、generation、制品/事实版本和可序列化数据。

### C1.2 恢复、编排与事件

- [x] C2.1 恢复时复用依赖版本一致的已完成步骤和成功工具/模型调用；版本变化时拒绝错误复用。
- [x] C2.2 实现错误分类、有限重试、暂停、恢复和取消，并继承 C0 晚到结果隔离。
- [x] C2.3 在 Planner/Orchestrator/DAG 步骤边界写入 C0 状态；现有线程超时不得直接视为调用已停止。
- [x] C2.4 为任务事件流增加持久 ID、保留期限和“游标早于最旧事件”的明确重同步响应。
- [x] C2.5 新任务流采用带 Authorization 的 fetch streaming；禁止加入 APIAuthMiddleware 免鉴权前缀或在 URL 放长期 API Key。
- [x] C2.6 新增任务创建、查询、事件流、暂停、恢复、取消 API，命令携带 command_id/revision，保持原即时问答 API 不变。实现见 `src/research_task_api.py`（挂载于 api_service），TDD 记录 C-T21。
- [x] C2.7 持久任务失败时保存选定路径，不静默回退或切换 single/multi。实现见 `src/research_task_adapter.py`（路由决策只追加表 migration 23），TDD 记录 C-T22。
- [x] C2.8 前端按 revision 合并事件，展示运行、暂停、等待审批、失败、取消和恢复状态。实现见 `frontend/src/services/researchTaskState.ts`、`frontend/src/stores/researchTaskStore.ts` 与 `frontend/src/components/chat/ResearchTaskStatusTag.tsx`，TDD 记录 C-T18。
- [x] C2.9 执行 Worker 异常、进程中断、并发控制命令、超时晚到结果和断线重连故障演练。实现见 `tests/test_research_task_fault_drills.py` 与 `src/research_task_orchestrator.py`（新增 handle_step_failure/recover_interrupted_task），TDD 记录 C-T23。
- [ ] C2.10 运行 C1 包全回归和代码审查，提交 `feat(tasks): productize durable research execution`。

### C1 包退出条件

- [x] C1-GATE-1 五类故障与并发演练全部达到预期状态。（tests/test_research_task_fault_drills.py 5 passed）
- [x] C1-GATE-2 依赖版本一致的已完成步骤及成功调用重复执行为 0；有副作用调用自动重复执行为 0。（故障演练进程中断复用断言）
- [x] C1-GATE-3 非法/过期 revision 状态迁移全部阻止，晚到结果无法复活任务。（C2.6 API 409 语义与 C2.9 晚到 discarded 断言）
- [x] C1-GATE-4 新任务流需要有效鉴权，旧聊天和会话记忆无回归。（test_research_task_stream_auth.py 与 m0 兼容回归）

## D. 安全、审计与成本治理

- [x] D1.1 定义工具风险等级、权限策略和默认拒绝边界。（src/governance/tool_policy.py 五级风险 + tests/test_governance_tool_policy.py 4 passed）
- [x] D1.2 实现参数绑定、时效限制的审批记录。（src/governance/approval.py grant/check_gate/consume + tests/test_governance_approval.py 14 passed 含参数化）
- [x] D1.2.1 审批哈希同时绑定 task revision、plan、事实/制品版本和 index generation；任一依赖变化使旧审批失效。（ApprovalBinding digest + check_gate dependencies_changed）
- [x] D1.3 为关键冲突裁决和正式报告签发加入审批门禁；仅在存在真实高风险工具时扩展到工具执行。（SUBJECT_CONFLICT_RESOLUTION/SUBJECT_REPORT_SIGNOFF/SUBJECT_TOOL_EXECUTION）
- [x] D1.4 建立只追加审计事件和任务回放查询。（src/governance/audit.py + 迁移 24 + tests/test_governance_audit.py 4 passed）
- [x] D1.4.1 关键状态迁移、审批消费和审计事件在 V7MetadataStore 同一事务提交，避免“已执行但无审计”或“已审计但未执行”。（consume_in_transaction BEGIN IMMEDIATE 原子性）
- [x] D1.5 在日志、追踪和报告持久化前实施敏感字段脱敏。（src/governance/redaction.py + 审计 _insert 边界脱敏 + tests/test_governance_redaction.py 4 passed）
- [x] D1.6 扩展安全集：文档注入、工具参数注入、跨 Agent 污染和越权调用。（src/governance/security.py + tests/test_governance_security.py 7 passed）
- [x] D1.7 统计任务 Token、调用次数、延迟和成本估算。（src/governance/metrics.py + tests/test_governance_metrics.py 3 passed）
- [x] D1.8 实现软预算预警和硬预算暂停。（src/governance/budget.py + tests/test_governance_budget.py 4 passed）
- [x] D1.9 比较现有 single/multi 路由质量—成本曲线并保存理由。（src/governance/routing_rationale.py + tests/test_governance_routing_rationale.py 3 passed）
- [x] D1.10 运行 D 包回归和代码审查，提交 `feat(governance): add agent policy audit and budgets`。（1428ef6，治理定向 43 passed，全量 641 passed + 1 skipped）

### D 包退出条件

- [x] D-GATE-1 未审批高风险调用执行为 0。（test_governance_tool_policy.py 越权工具 DENIED 断言）
- [x] D-GATE-2 审计日志能重建一次完整任务关键路径。（test_governance_audit.py 与 test_governance_routing_rationale.py 审计事件回放断言）
- [x] D-GATE-3 安全攻击集达到批准结果。（test_governance_security.py 文档注入/参数注入/跨 Agent 污染/越权调用全部拒绝）
- [x] D-GATE-4 超预算任务安全暂停且可恢复。（test_governance_budget.py 超硬预算抛 BudgetExceededError 携带成本快照）

## E. 研究工作流与可审计报告

- [x] E1.1 定义 ResearchPlan、Claim、ResearchReport 与审核状态模型。（E-T10 RED→GREEN：稳定 ID、预算快照、声明依据与审核状态模型，4 passed）
- [x] E1.2 新增研究任务列表和详情 API。（复用 C2.6 详情 API；新增只读列表 API，E-T11 RED→GREEN，研究任务定向回归 30 passed）
- [x] E1.3 新增研究任务页面并复用现有布局、DAG、证据、图表组件。（E-T12 RED→GREEN：任务页、路由和无结果降级；2026-09-11 补充 E-T09 根聊天路由与 `/research` 分离契约，隔离 worktree 前端定向 37 passed、build 通过）
- [x] E1.4 支持执行前调整范围和预算重新计算。（E-T02 RED→GREEN：范围直接影响与下游闭包、无关步骤成本保持、pending 门禁、DAG/预算一致性拒绝；研究任务定向回归 34 passed）
- [x] E1.5 支持关键冲突批准、驳回和保持未决。（E-T04 RED→GREEN：原冲突不覆盖、裁决历史只追加、批准/驳回同事务消费匹配审批；2026-09-11 修正完整计划哈希遗漏的步骤绑定/输入，冲突治理回归 13 passed）
- [x] E1.6 生成声明级可追溯 Markdown/HTML 报告。（E-T07 RED→GREEN：报告/计划/数据版本、声明与证据 ID 完整输出，HTML 转义；6 passed）
- [x] E1.7 实现事实修订后的局部失效与报告版本比较。（E-T06 RED→GREEN：事实→声明反向定位、旧报告不变、新版本可比较；7 passed）
- [x] E1.8 记录 PDF、Word、Excel 三个后续独立 OpenSpec 子变更；它们不阻塞 v7.0 首发，需要新包时先核查并申请。（已建立三份独立 proposal）
- [x] E1.9 准备 5 分钟主流程、冲突、恢复和安全演示数据。（E-T13 RED→GREEN：四个离线场景清单，1 passed；预算暂停明确为 D-T09 待实现目标）
- [ ] E1.10 运行 E 包回归、可访问性检查和代码审查，提交 `feat(research): deliver auditable research workflow`。（当前主工作区的后端 724 passed、1 skipped、前端 53 个文件/293 项、lint/build、compileall、范围化安全审查和自动化 a11y 已完成；本轮在独立副本 `codex/research-e110-isolated-20260901` 形成 60 文件可审计提交，最终提交 SHA 见交接文档；当前仓库因 `.git/FETCH_HEAD` 与 ref lock 无写权限无法导入该引用；真实屏幕阅读器验收仍待完成，因此本任务保持未勾选）

- [x] E-T01 创建研究任务时持久化计划与预算快照。（迁移 27、`ResearchPlanRepository`；创建响应/详情可读，25 passed）
- [x] E-T14 在研究任务详情读取最新持久化报告，并在报告缺失时展示明确空态。（测试先行；当前 worktree 初次 RED 因无 `node_modules` 无法执行，复用原项目已安装依赖后 GREEN：前端定向 9 passed、build 通过）
- [x] E-T15 从持久化计划和声明输入创建不可变报告版本。（RED：POST 报告路由返回 405；GREEN：定向 3 passed、关联回归 28 passed；2026-09-12 补充断言：已持久化计划的 `pending` 任务可创建待审核草稿，防止后续无产品决策时擅自增加 `completed` 门禁。）
- [x] E-T16 建立服务端任务—冲突依赖上下文并由当前任务/计划生成审批绑定。（RED：模块缺失 3 failed、过期有效期未拒绝 1 failed；GREEN：4 passed）
- [x] E-T17 配置独立审批密钥和部署审批主体，开放只授予审批的受保护 API；缺配置或密钥不匹配必须拒绝，客户端不得提交审批主体或绑定字段。（RED：端点缺失 3 failed；GREEN：3 passed，关联治理/任务回归完成）
- [x] E-T18 以可信任务—冲突上下文提供冲突列表/历史和受审批保护的裁决 API；批准/驳回必须服务端重建绑定并同事务消费审批，保持未决不消费审批。（RED 3 failed：端点缺失；GREEN 3 passed，关联回归 26 passed）
- [x] E-T19 在研究任务页展示任务范围内的冲突及其裁决历史，并在无冲突时明确空态；浏览器不得持有部署审批密钥或直接调用裁决端点。（RED 1 failed：面板缺失；GREEN 5 passed；生产构建受共享依赖缓存权限阻断）
- [x] E-T20 建立用户、角色与 HttpOnly 会话身份；审批端点仅接受具有 approver 角色的当前会话，首个管理员只能由部署配置初始化。（RED 2 failed：登录端点缺失；GREEN 与关联回归 14 passed）
- [x] E-T21 全局 API 门禁接受有效研究会话，同时保留既有 Bearer API Key 客户端兼容；审批角色检查不放宽。（独立 RED：`1428ef6` 只读基线副本中旧 `api_service` 缺少 `_research_session_is_valid`，1 failed；当前实现 GREEN：定向 6 passed）
- [x] E-T22 在既有页头提供登录、登出和当前会话身份状态；仅调用研究身份 API，不在浏览器保存密码、会话令牌或审批凭据。（独立 RED→GREEN：前端定向 13 passed，关联回归 23 passed）
- [x] E-T23 在研究任务冲突卡提供 approver 裁决交互；普通用户只读，前端先请求服务端生成的审批再提交裁决，不接触绑定字段或审批密钥。（独立 RED→GREEN：任务页 7 passed，前端关联回归 25 passed）
- [x] E-T23.1 驳回冲突时不提交事实选择，先取得 `selected_fact_id=null` 的服务端审批再提交裁决，避免被后端治理规则拒绝。（RED→GREEN：研究任务页 12 passed）
- [x] E-T24 正式报告签发必须经过 approver 一次性审批，且存在未裁决关键冲突时服务端拒绝；签发记录只追加保存。已补充重复签发保护：同一报告已签发时返回 409，剩余有效审批保持 granted；唯一约束并发竞争同样映射为 409。（独立 RED→GREEN：初始 2 passed；重复签发 RED 为 SQLite 唯一约束异常，GREEN 3 passed，签发/身份/会话/报告关联回归 29 passed）
- [x] E-T25 在任务页为 approver 接入报告签发与持久化签发状态；普通用户只读，刷新后仍从服务端记录展示状态。（独立 RED→GREEN：后端 2 passed、任务页 9 passed；关联后端 47 passed、前端 27 passed）
- [x] E-T26 为研究登录、冲突裁决和报告签发完成键盘操作与失败提示 a11y 验收；失败信息必须被辅助技术明确通知。（独立 RED→GREEN：登录错误提示 12 passed；页面键盘签发/错误提示与页头 22 passed，前端关联回归 29 passed）
- [x] E-T27 对 E-T20 至 E-T26 完成范围化代码审查，核对会话、角色、审批绑定、签发事务和浏览器边界。（无阻塞问题；身份/审批/签发定向回归 47 passed）
- [x] E-T28 重启前后端后在真实浏览器核验登录与研究任务页的键盘焦点、语义和空态。（登录与刷新按钮均获得可见 `:focus-visible` 轮廓；未登录任务页保持明确空态）
- [x] E-T28.1 登录或登出后同步研究任务页的当前会话身份，审批人无需手动刷新即可看到签发入口。（RED：任务页已登录但缺签发入口；GREEN：认证事件触发页面重读身份，任务页与页头 23 passed）
- [x] E-T28.2 记录发布范围决策：真实屏幕阅读器验收暂缓为后续无障碍验收项，不作为 E1.10 当前发布阻塞；保留 E-T26 自动化和真实键盘验收，且不伪造读屏通过。
- [x] E-T29 证据链定位来源时自动展开对应来源卡片及评分详情，保留后端原始 `hybrid`、`rerank`、`vector`、`bm25` 与状态字段。
- [x] E-T30 知识库索引完成率优先使用热加载清单的 `index_status`，仅无清单记录时兼容旧向量目录推断，避免已索引文件被错误计为待索引。
- [x] E-T31 研究员只能在有效会话下创建研究任务；创建后先形成只追加的“已提交”记录，审批人可批准并启动执行或驳回，任务快照公开当前提交状态与操作人。（RED→GREEN：提交审批 API 2 passed；研究任务/冲突/签发关联回归 28 passed）
- [x] E-T32 研究任务页提供最小“提交研究任务”入口和提交状态展示；仅研究员可提交、仅审批人可决定执行或驳回，浏览器不提交审批人身份。（RED→GREEN：`ResearchTasksPage.test.tsx` 13 passed；生产构建和 lint 通过）
- [x] E-T33 批准后的最小执行器在外部检索或模型计算前领取步骤租约，按 TTL 续租并在异常时原子释放；按计划步骤顺序提交 C0 检查点，仅在检索获得来源证据时写入待审核报告，全部步骤成功后完成任务。有效步骤租约由其他工作者持有时，本执行器保持任务 running 且不追加 failure 决策。（续审 RED：竞争租约下仍调用外部查询并误迁移 failed；GREEN：执行前领取、长查询续租、异常释放与租约竞争回归 20 passed，关联执行/轨迹/提交/遗留处置回归通过）
- [x] E-T34 API 装配真实查询执行器；批准仅调度执行，执行异常应明确标记 failed，不能留下无产物的 running 状态。（RED→GREEN：提交审批 API 2 passed；端到端新任务 completed 且报告含 source）
- [x] E-T35 任务详情公开只读执行进度：已完成步骤、当前步骤、终态完成时间与经脱敏的失败原因；页面据此展示 DAG 节点状态。运行中任务每 5 秒刷新任务状态、执行摘要、报告和冲突，终态停止轮询。（RED→GREEN：后端摘要 1 passed；新增前端自动刷新用例 RED→GREEN；研究页 18 passed，研究前端定向集合 61 passed，lint/build 通过）
- [x] E-T36 审批人可处置无有效租约、检查点或调用记录的遗留 `running` 任务：仅允许以 CAS 标记 failed 并只追加原因，禁止删除/重置/伪造报告。（RED 端点 404 → GREEN `test_research_task_legacy_disposition_api.py` 2 passed）
- [x] E-T37 最终报告、最终步骤 checkpoint/调用记录和任务 completed 状态在同一 SQLite 事务内提交；失败必须整体回滚。（RED 模拟报告写入失败后仍 completed → GREEN 回滚断言通过）
- [x] E-T38 审批人可基于已失败历史任务的持久化计划创建新的 `-retry-N` pending 任务；保留原任务审计，新任务重新 submitted，不得自动执行或回迁原运行。（RED retry 端点 404 → GREEN 4 passed）
- [x] E-T39 研究计划步骤显式绑定 `AgentRegistry` 中的 Agent 与允许工具；执行时校验绑定并将每步 Agent、工具调用和脱敏结果摘要持久化到 C0 调用账本，任务摘要与研究任务页只读展示轨迹。（RED `agent_registry` 参数缺失 → GREEN `test_research_task_trace.py` 8 passed，含受控 HTTP 提交→审批→执行→摘要链路；研究任务 API/执行/遗留处置/重规划回归 48 passed；页面 15 passed；前端全量 52 文件/285 项通过；lint/build 通过。正式服务只读 HTTP 已确认旧无绑定任务与完成报告可读；正式库没有已执行的绑定任务，不能将此项误写为真实绑定执行证据。）
- [x] E-T40 对绑定 `retrieve` 步骤接入现有 `ToolRegistry` 实际调用；调用账本仅记录工具名称、状态与脱敏来源数量，工具未装配/失败/无来源时失败，旧无绑定计划保持通用查询兼容。（RED 构造参数错误 → GREEN 13 passed；关联研究任务回归 48 passed；后端全量 700 passed、1 skipped；前端全量 52 文件/285 项、lint/build 通过）
- [x] E-T41.1 对绑定 `DataAgent + retrieve` 的步骤接入实际 `DataAgent` ReAct 运行；仅在服务已装配 `LLMProvider` 时启用，复用受控 `RetrieveTool`，记录脱敏 Worker 摘要并保留 E-T40 的非 Worker 工具执行路径。此项不代表 VerifyAgent、报告或其他 Worker 已实际执行。（RED 构造参数错误 → GREEN 14 passed；关联与全量后端核查见交接文档）
- [x] E-T41.2 对绑定 `VerifyAgent + verify` 的 `review` 步骤接入实际 VerifyAgent ReAct 运行。审核输入必须来自当次检索的声明和来源正文，工具策略仅允许 `verify`；审核不通过、无结论或未实际调用 verify 时任务失败，账本仅记录脱敏结论和 Worker 统计。此项不代表报告 Worker 或其他 Agent 已实际执行。（RED 未调用 verify → GREEN 15 passed；关联与全量后端核查见交接文档）
- [x] E-T41.3a 为 CalcAgent 增加审批时持久化的结构化计算输入（操作类型及相应数值字段），拒绝从目标或来源正文推断数值；计划创建阶段拒绝未知操作、缺失/额外字段与非有限数值，CalcAgent 仅注册 calculator，实际 action_input 必须与批准快照完全一致，C0 仅回放 operation、结果存在性和 Worker 步数。（RED 安全轨迹/字段契约缺口 → GREEN；后端全量 707 passed、1 skipped）
- [x] E-T41.3b 为 CompareAgent 增加审批时持久化的结构化对比输入（公司、指标、年份及 top_n），拒绝从目标或来源正文推断公司/指标；字段白名单、仅含 compare 的实际 Worker 和完整任务 C0 invocation 脱敏回放均已验证。（RED 4 failed → GREEN；后端全量 713 passed、1 skipped）
- [x] E-T41.3c 为 ChartAgent 增加审批时持久化的图表 data/chart_type/title 输入；计划创建阶段拒绝空数据、空标签、布尔/非有限数值、未知图表类型及额外字段，实际 Worker 仅注册 chart 且 action_input 必须与审批快照完全一致；完整任务 C0 回放只保留 chart_type、结果存在性及 Worker 步数，不保存图表数据。（定向与关联 61 passed；后端全量 718 passed、1 skipped）
- [x] E-T41.4 对绑定 `PlanAgent + []` 的 `plan` 步接入实际无工具 Worker。Worker 只读取已审批且已持久化的计划快照，模型输出不得修改步骤、范围、预算或绑定；C0 仅回放计划版本、范围/步骤计数、确认状态和 Worker 步数，不保存目标、风险、提示词或模型原文。旧未绑定或历史 `DataAgent` plan 绑定保持直接提交兼容。（RED 2 failed → GREEN；关联 63 passed，后端全量 720 passed、1 skipped）
- [x] E-T41.5 对绑定 `ReportAgent + []` 的 `report` 步接入实际无工具 Worker。报告必须先由已审核检索结果构造为不可变草稿，Worker 只确认草稿，模型输出不得新增或改写声明；C0 仅回放报告版本、声明计数、审核状态、确认状态和 Worker 步数。（RED 1 failed → GREEN；关联 64 passed，后端全量 721 passed、1 skipped）
- [x] E-T42 为失败研究任务提供 approver 可见的安全重放入口；只调用既有 retry API 创建新的 submitted 任务，原任务保持失败且不可自动执行。（页面测试 16 passed，前端 build 通过）
- [x] E-T43 为 approver 提供遗留 running 任务的审计处置入口；必须填写原因并调用既有 legacy-disposition API，不删除、重启或直接改写原记录。（页面测试 17 passed，前端 build 通过）
- [x] E-T44 修复绑定 DataAgent 丢失审批范围的问题；Worker 查询上下文必须同时包含 objective 与已审批 scope，旧未绑定查询路径保持不变。（RED：scope 仅持久化但未传入 Worker，1 failed；GREEN：scope 上下文契约及 DataAgent Worker 回归通过，研究执行/轨迹 24 passed）
- [x] E-T45 修复绑定 VerifyAgent 使用截断来源或模型自带来源的问题；回答级摘要保持兼容，审核 Worker 使用本次检索的完整进程内正文，执行器固定 canonical 声明/来源并忽略 action_input 的替换，C0 仍只保存脱敏审核摘要。（RED：200 字符摘要导致审核输入丢失，1 failed；GREEN：完整正文传递、输入固定及既有审核回归 3 passed）
- [x] E-T46 人工创建待审核报告的端点必须要求当前会话具有 `researcher` 角色；服务端继续确定报告 ID、版本和 `pending_review` 状态，不接受客户端伪造身份。任务是否必须 `completed` 暂不在本项擅自收紧，保留现有 E-T15 的 pending 任务兼容。（RED：移除 researcher 角色后仍返回 200；GREEN：补充匿名访问 401 后，研究任务 API、身份、报告、执行和 C0 关联回归 104 passed。）

### E 包退出条件

- [x] E-GATE-1 完成计划—执行—审核—报告闭环。（2026-09-12：研究后端受控回归 117 passed，覆盖提交、审批、执行、检查点、报告、签发与失败处置；不替代真实 Provider 或远端 CI 证据。）
- [x] E-GATE-2 关键声明都有证据、计算或分析判断标识。（2026-09-12：`test_research_delivery_models.py` 纳入 117 passed，声明无可审计依据时拒绝落库。）
- [x] E-GATE-3 事实修订仅影响依赖声明。（2026-09-12：`test_research_report_invalidation.py` 纳入 117 passed，失效传播保持报告与声明级关联。）
- [x] E-GATE-4 现有聊天与其他页面不回归。（2026-09-12：路由、页头、研究页 a11y/交互与认证前端集合 5 文件 40 passed；根路由仍为 ChatPage。真实读屏验收另行保留。）

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
