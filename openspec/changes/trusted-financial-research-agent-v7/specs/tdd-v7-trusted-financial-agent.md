# TDD：v7.0 可信金融研究 Agent

> 当前状态：A 阶段评测平面首批测试已按 RED→GREEN 实施；其余未实施测试仍为 🔴 RED。任何测试只有在观察到预期失败、完成最小实现、再次运行通过并记录命令与证据后，才能改为绿色（通过）。

## A. 评测与门禁

| ID | 状态 | 测试目标 | 预期 RED 原因 |
|---|---|---|---|
| A-T01 | 绿色（通过） | 合法评测样本通过 schema | `pytest tests/test_evaluation_quality_gate.py -q`：19 passed |
| A-T02 | 绿色（通过） | 缺少来源或页码的样本被拒绝 | `pytest tests/test_evaluation_quality_gate.py -q`：19 passed |
| A-T03 | 绿色（通过） | 重复样本 ID 被拒绝 | `pytest tests/test_evaluation_quality_gate.py -q`：19 passed |
| A-T04 | 绿色（通过） | 数字舍入在容差内通过 | `pytest tests/test_evaluation_quality_gate.py -q`：19 passed |
| A-T05 | 绿色（通过） | 数量级错误即使平均分高也失败 | `pytest tests/test_evaluation_quality_gate.py -q`：19 passed |
| A-T06 | 绿色（通过） | 单位、币种和期间分别评分 | `pytest tests/test_evaluation_quality_gate.py -q`：19 passed |
| A-T07 | 绿色（通过） | 应拒答样本正确识别 | `pytest tests/test_evaluation_quality_gate.py -q`：19 passed |
| A-T08 | 绿色（通过） | 预期工具和实际轨迹比较 | `pytest tests/test_evaluation_quality_gate.py -q`：19 passed |
| A-T09 | 绿色（通过） | 无密钥模式不调用外部服务 | `pytest tests/test_evaluation_quality_gate.py -q`：19 passed |
| A-T09A | 绿色（通过） | 无密钥回放明确不冒充在线模型质量 | `pytest tests/test_evaluation_quality_gate.py -q`：19 passed |
| A-T10 | 绿色（通过） | 基线差异列出新增失败和修复 | `pytest tests/test_evaluation_quality_gate.py -q`：19 passed |
| A-T11 | 绿色（通过） | 报告包含代码、模型、提示词、索引和数据集版本 | `pytest tests/test_evaluation_quality_gate.py -q`：19 passed |
| A-T12 | 绿色（通过） | CI 阈值失败返回非零退出码 | `pytest tests/test_evaluation_quality_gate.py -q`：19 passed |
| A-T13 | 绿色（通过） | A 阶段答案级指标不能冒充声明级指标 | `pytest tests/test_evaluation_quality_gate.py -q`：19 passed |
| A-T14 | 绿色（通过） | 覆盖报告显式暴露样本、公司、期间和分类缺口 | `pytest tests/test_evaluation_quality_gate.py -q`：19 passed |
| A-T15 | 绿色（通过） | 发布模式拒绝未复核或覆盖不完整的数据集 | `pytest tests/test_evaluation_quality_gate.py -q`：20 passed |
| A-T16 | 绿色（通过） | 未显式传入数据集版本时从样本元数据推导版本 | `pytest tests/test_evaluation_quality_gate.py -q`：20 passed |
| A-T17 | 🟢 GREEN | v5.19 已跟踪配置基线必须以 Git 指纹冻结；未跟踪索引数据和未导出的 OpenAPI 必须显式标为未捕获，禁止用当前运行目录或占位内容冒充基线 | RED：夹具文件不存在，`tests/test_v519_compatibility_manifest.py` 2 failed；GREEN：新增不含配置正文的 v5.19 配置 blob 清单，回归 **2 passed**。OpenAPI、关键 JSON、company_registry/metadata 和无 v7 数据库夹具继续保持 RED。 |
| A-T18 | 🟢 GREEN | v5.19 无 Key、禁用 tracing 的临时导出副本必须记录 OpenAPI 与关键 JSON 指纹；候选可新增端点但不得移除 v5.19 路径 | RED：`candidate_openapi_compatibility` 缺失，兼容清单回归 **1 failed**；GREEN：v5.19 OpenAPI 为 17 路径，`/api/health` 为 200、`/api/system/status` 和 `/api/companies` 为 401；候选 39 路径且旧路径零缺失。夹具只保存字段、状态和哈希，不保存响应正文；相关回归 **30 passed**。 |
| A-T19 | 🟢 GREEN | v5.19 既有操作的方法、参数必填性、请求体必填性、内容类型、响应状态码与直接 JSON schema 引用必须保持；既有组件仅允许增加非必填字段 | RED：字段级兼容记录缺失，兼容清单回归 **1 failed**；GREEN：17 条旧路径的操作签名哈希在候选中完全相同，21 个 v5 schema 均存在；`KnowledgeUploadResponse` 与 `SourceInfo` 只新增可选字段，既有字段和 required 集合不变。相关回归 **31 passed**。 |
| A-T20 | 🟢 GREEN | v5.19 无 Key 请求的状态、顶层字段和脱敏正文必须保持；运行目录等环境值只可按明确脱敏规则比较 | RED：无 Key 响应兼容记录缺失，兼容清单回归 **1 failed**；GREEN：14 个安全探测请求均无变化，12 个受保护请求为 401，缺 query 的 stream 为 422，health 为 200；仅将 `vector_db_dir` 替换为占位符后 health 正文哈希一致。相关回归 **32 passed**。 |

## B. 金融可信内核

| ID | 状态 | 测试目标 | 预期 RED 原因 |
|---|---|---|---|
| B-T01 | 🟡 已实现待补 RED 记录 | FinancialFact 同时保留原始值和归一值 | `tests/test_financial_fact.py`：6 passed；本次恢复上下文前未保留初始 RED 输出，不伪造 GREEN 记录 |
| B-T02 | 🟡 已实现待补 RED 记录 | 万元、百万元、亿元正确换算 | `tests/test_financial_fact_normalizer.py`：通过；初始 RED 输出未保留，不伪造 GREEN 记录 |
| B-T03 | 绿色（通过） | 负数、百分比和每股单位边界正确 | `tests/test_financial_unit_rules.py`：RED 1 failed（百分比与每股金额被识别为“个”）→ GREEN；VerifyTool 保留 `%`/`元/股` 单位并拒绝跨量纲匹配，金额归一器继续明确拒绝这两类非总金额单位。联合相关回归 20 passed。 |
| B-T04 | 绿色（通过） | 无汇率来源时拒绝币种换算 | `tests/test_financial_fact_compatibility.py`：新增 RED 1 failed（专用异常不存在）→ GREEN；异常兼容旧 `IncompatibleFinancialFactsError` 捕获 |
| B-T05 | 绿色（通过） | 季度与年度不被当作同期间 | `tests/test_financial_fact_context.py`：RED 1 failed（门禁模块不存在）→ GREEN；比较前拒绝不同期间类型/边界/财年 |
| B-T06 | 绿色（通过） | 集团和母公司口径差异不判定为数值冲突 | `tests/test_financial_fact_context.py`：同一 RED→GREEN 测试覆盖；比较前拒绝不同合并范围、会计准则或审计状态 |
| B-T07 | 绿色（通过） | 派生计算关联输入事实与公式版本 | `tests/test_fact_calculation_repository.py`：新增仓储 RED 1 failed→GREEN；冲突拒绝 RED 1 failed→GREEN；服务持久化入口 RED 1 failed→GREEN |
| B-T08 | 🟡 已实现待补 RED 记录 | 不兼容输入阻止计算 | `tests/test_fact_calculation_service.py`：通过；初始 RED 输出未保留，不伪造 GREEN 记录 |
| B-T09 | 绿色（通过） | 同口径超容差创建 VALUE_CONFLICT | `tests/test_financial_fact_conflict_service.py`：RED 2 failed（模块不存在）→ GREEN 2 passed；超阈值返回 `VALUE_CONFLICT/pending_review` |
| B-T10 | 🟡 已验证待补历史 RED 记录 | 可解释单位差异不创建真实冲突 | `tests/test_financial_fact_conflict_service.py` 新增“100亿元 = 10000百万元”回归并通过；实现早于本次测试，初始 RED 输出未保留，不伪造 GREEN 记录。与兼容性回归 10 passed。 |
| B-T11 | 🟡 已实现待补 RED 记录 | 无法裁决返回需人工确认 | 冲突服务返回 `pending_review`；初始 RED 输出未保留，不伪造 GREEN 记录 |
| B-T12 | 🟡 已实现待补 RED 记录 | 旧 VerifiedFinancialFactRegistry 行为保持兼容 | `tests/test_financial_fact_registry_adapter.py` 与 `tests/test_verified_financial_facts.py`：10 passed；初始 RED 输出未保留，不伪造 GREEN 记录 |
| B-T13 | 绿色（通过） | EvidenceBundle 关联 claim、fact、calculation、conflict | `python -m pytest tests/test_evidence_bundle.py -q --basetemp=.tmp/pytest-b25`：RED 5 failed（模块不存在）→ GREEN 5 passed；幂等重放、冲突拒绝、悬空引用与兼容性由同套用例覆盖 |
| B-T14 | 绿色（通过） | V7MetadataStore 迁移重复执行不重复建表或丢数据 | `python -m pytest -q tests/test_v7_metadata_store.py`：RED 3 failed → GREEN 3 passed |
| B-T15 | 绿色（通过） | 迁移中途失败回滚并保留启动前备份 | `python -m pytest -q tests/test_v7_metadata_store.py`：追加备份时机 RED 1 failed → GREEN 3 passed |
| B-T16 | 绿色（通过） | 未知更高 schema 版本拒绝写入而非自动降级，且拒绝路径不改变 SQLite journal mode | `python -m pytest -q tests/test_v7_metadata_store.py`：RED 3 failed、追加无配置写入 RED 1 failed → GREEN 3 passed |
| STORE-T01 | 绿色（通过） | V7MetadataStore 的连接上下文退出后必须关闭 SQLite 文件句柄，Windows 下可立即删除临时数据库 | `python -m pytest tests/test_v7_metadata_store.py::test_store_connection_context_closes_database_file_on_windows -q`：RED 1 failed（WinError 32）→ GREEN 1 passed |
| B-T17 | 绿色（通过） | financial_trust_enabled 关闭时旧 API 不实例化新事实链 | `tests/test_financial_fact_registry_provider.py`：RED 2 failed（提供器不存在）→ GREEN；关闭时公开比较 API 不创建 V7 SQLite，开启后响应保持兼容 |
| B-T18 | 绿色（通过） | 新功能开启但严格配置无效时 fail closed | `python -m pytest -q tests/test_v7_feature_flags.py`：RED 5 failed → GREEN 5 passed |
| B-T19 | 🟡 已实现待补 RED 记录 | 单指标纵向试点保持旧比较 API 字段与结果兼容 | `tests/test_financial_fact_vertical_slice.py`、既有评测门禁与旧注册表回归：27 passed；初始 RED 输出未保留，不伪造 GREEN 记录 |
| B-T20 | 绿色（通过） | 非自然财年、口径、文档版本来源、物理页与事实修订关系均有显式边界 | `tests/test_financial_fact_context.py`：RED 5 failed（模块不存在）→ GREEN 6 passed；非自然财年复核用例通过 |
| B-T21 | 绿色（通过） | 指标别名只映射批准的 canonical key，近似收入指标不自动合并 | `tests/test_financial_metric_dictionary.py`：RED 5 failed（模块不存在）→ GREEN 5 passed |
| B-T22 | 绿色（通过） | 共享 Decimal 单位规则与 VerifyTool 的公开单位乘数保持一致 | `tests/test_financial_unit_rules.py`：RED 1 failed（模块不存在）→ GREEN 1 passed；`tests/test_agent_tools.py` 回归通过 |
| B-T23 | 绿色（通过） | 期间、口径和来源仓储仅接受真实文档版本，重放幂等且冲突证据拒绝 | `tests/test_financial_fact_context_repository.py`：RED 1 failed（仓储不存在）→ GREEN；追加冲突 RED 1 failed（异常不存在）→ GREEN |
| B-T24 | 绿色（通过） | 已核验比较响应携带原始值、归一值、公式和冲突原因可选载荷，且旧字段零改动 | `tests/test_comparison_evidence_payload.py`：RED 4 failed（适配器不识别 calculation_repository 参数）→ GREEN 4 passed；注入仓储才输出新载荷，未注入时响应与 legacy 严格相等；兼容回归 31 passed（旧字段逐项保持） |
| B-T25 | 绿色（通过） | 前端比较卡片证据明细展示每个事实的原始值、归一值、公式与冲突原因 | `frontend/src/components/chat/__tests__/ClaimEvidenceDetails.test.tsx`：RED 导入失败（组件不存在）→ GREEN 3 passed；VerifiedComparisonCard 既有 5 用例回归通过，旧载荷不渲染明细 |
| B-T26 | 绿色（通过） | 用 A 评测集验证升级收益：启用声明级证据支持率硬门禁，升级候选通过门禁且无新增失败；缺声明级载荷或调低通过率都无法让门禁通过 | `tests/test_upgrade_benefit_validation.py`：RED ImportError（`load_thresholds` 不存在）→ GREEN 4 passed；实现 `src/evaluation/thresholds.py` 加载校验 thresholds.yaml，评估器新增声明级证据支持率指标，门禁启用时逐条强制；兼容与 B 包定向回归 95 passed（含既有评测门禁 20 用例零回归） |
| B-T27 | 绿色（通过） | B2.8 审查修复：零值、负数、万亿/千亿、原始误差阈值、非法阈值配置、页脚页码、Streamlit 包导入和空公司列表均有回归保护 | `tests/test_b28_review_fixes.py`：RED 6 failed、5 errors（其中 5 errors 是 `D:` 临时目录权限问题）；改用仓库内临时目录后 GREEN 11 passed。联合 `tests/test_financial_unit_rules.py`、`test_upgrade_benefit_validation.py`、`test_page_metadata.py`、`test_verified_financial_facts.py`、`test_agent_tools.py` 为 41 passed。 |

## C0. 通用可恢复执行基础

| ID | 状态 | 测试目标 | 预期 RED 原因 |
|---|---|---|---|
| C0-T01 | 绿色（通过） | `tests/test_durable_execution.py`：同一步骤只有一个有效 lease 执行者 | 首次 RED 为 9 failed（模块不存在）；GREEN 25 passed |
| C0-T02 | 绿色（通过） | `tests/test_durable_execution.py`：lease 过期后新 attempt 可接管 | 首次 RED 为 9 failed（模块不存在）；GREEN 25 passed |
| C0-T03 | 绿色（通过） | `tests/test_durable_execution.py`：原 attempt 晚到结果被标记 discarded | 首次 RED 为 9 failed（模块不存在）；GREEN 25 passed |
| C0-T04 | 绿色（通过） | `tests/test_durable_execution.py`：并发暂停与取消只有一个 revision CAS 成功 | 首次 RED 为 9 failed（模块不存在）；GREEN 25 passed |
| C0-T05 | 绿色（通过） | `tests/test_durable_execution.py`：相同 command_id 重复提交返回原结果 | 首次 RED 为 9 failed（模块不存在）；GREEN 25 passed |
| C0-T06 | 绿色（通过） | `tests/test_durable_execution.py`：并行事件由单写入器生成单调唯一 event ID | 首次 RED 为 9 failed（模块不存在）；GREEN 25 passed |
| C0-T07 | 绿色（通过） | `tests/test_durable_execution.py`：幂等键包含模型、提示词、事实/制品和索引代际 | 首次 RED 为 9 failed（模块不存在）；GREEN 25 passed |
| C0-T08 | 绿色（通过） | `tests/test_durable_execution.py`：超时线程晚到结果不能写事实、索引或 completed | 首次 RED 为 9 failed（模块不存在）；GREEN 25 passed |
| C0-T09 | 绿色（通过） | `tests/test_durable_execution.py`：模拟入库进程中断后从检查点恢复且不重复成功调用 | 首次 RED 为 9 failed（模块不存在）；GREEN 25 passed |
| C0-T10 | 绿色（通过） | `tests/test_durable_execution.py`：M 复用 C0 表与仓储而不建立平行状态机 | RED 为协调器构造参数不存在；GREEN 25 passed |
| C0-T11 | 绿色（通过） | multimodal/research_tasks 缺少显式前置开关时 fail closed | `python -m pytest -q tests/test_v7_feature_flags.py`：RED 5 failed → GREEN 5 passed |

## S. 源文件、索引迁移与关系型溯源

| ID | 状态 | 测试目标 | 预期 RED 原因 |
|---|---|---|---|
| S-T01 | 🔴 RED | 上传成功后源 PDF SHA-256 在全部处理步骤前后不变 | 不可变源文件存储不存在 |
| S-T02 | 🔴 RED | staging 写入或校验失败不创建可查询版本且不覆盖 active | 上传当前直接写目标文件 |
| S-T03 | 🔴 RED | 加密、零页、截断和页数不可读分别返回明确错误 | 完整 PDF 可读性校验不存在 |
| VALID-T01 | 绿色（通过） | 独立 PDF 校验器区分合法、伪装、截断和加密文件并只返回 PDF 物理页数 | `python -m pytest -q tests/test_pdf_validation.py`：RED 3 failed → GREEN 3 passed；追加真实加密 PDF 1 passed；正式 12/12 valid、971 页 |
| UPLOAD-T01 | 绿色（通过） | `multimodal_enabled` 上传走同文件系统 staging、关闭后校验和不可变版本登记；关闭分支保持 legacy；缺少 service/逻辑键 fail closed | `python -m pytest -q tests/test_v7_upload_adapter.py tests/test_v7_pdf_upload_service.py`：RED 2 failed → GREEN 4 passed |
| S-T04 | 绿色（通过） | 同一 logical document 与相同 hash 幂等返回既有版本 | `python -m pytest -q tests/test_v7_document_repository.py`：RED 3 failed → GREEN 3 passed |
| S-T05 | 绿色（通过） | 相同 hash 的不同 logical document 不被错误合并 | `python -m pytest -q tests/test_v7_document_repository.py`：RED 3 failed → GREEN 3 passed |
| S-T06 | 绿色（通过） | 全部当前文档均生成且只生成一种有依据的处理决策 | `python -m pytest -q tests/test_document_reuse_decision.py`：RED 4 failed、原子写入 RED 1 failed → GREEN 5 passed；真实清单 12/12 ENRICH |
| S-T07 | 绿色（通过） | 完整 MinerU Markdown 与根目录内本地图片作为 `REUSE_EXISTING_ASSETS` 的实际输入，不调用解析器 | `tests/test_document_reuse_decision.py`：RED 4 failed（模块不存在）→ GREEN 9 passed；复用/清点回归 12 passed |
| S-T08 | 绿色（通过） | 只接受有明确页码、类别和原因的 `failed_page/complex_table/chart/scanned_page/location_failure` 定向任务；不完整清点不推断扩大范围 | `tests/test_document_reuse_decision.py`：RED 4 failed → GREEN 9 passed |
| S-T09 | 🔴 RED | 全局不兼容时 FULL_REEXTRACT 留下明确原因 | 全量重提取判定不存在 |
| SRC-T01 | 绿色（通过） | 源 PDF 冻结清单记录哈希、物理页、加密/可读状态及既有 registry 的逻辑映射；冲突映射不猜测；原子写入保证源文件字节不变 | `python -m pytest -q tests/test_source_inventory.py`：RED 2 failed、追加边界 RED 1 failed → GREEN 3 passed |
| S-T10 | 绿色（通过） | 普通文本页不因首轮迁移调用视觉模型 | `tests/test_v7_document_processing_coordinator.py`：RED 1 failed（`AttributeError: route_document_pages`）→ GREEN 4 passed；协调器在校验真实 PDF 后收集页信号、生成 PageRouter 快照，只将 `use_vision=True` 页交给分发器，文本页不分发 |
| S-T11 | 绿色（通过） | 候选 v7 generation 以全部 active document version 与 blob hash 固定 corpus revision；缺任一 active 文档时拒绝构建 | `tests/test_v7_generation_migration.py`：RED 5 failed（模块不存在）→ GREEN 6 passed；generation/metadata/index 定向回归 22 passed |
| S-T12 | 绿色（通过） | chunk 缺 parser/splitter/preprocess/embedding/schema 任一版本证据时记录 `reembed_required`，不会标记为旧向量可复用 | `tests/test_v7_generation_migration.py`：RED 5 failed → GREEN 6 passed |
| S-T13 | 绿色（通过） | 候选制品哈希、大小、metadata 容器类型、维度或抽样检索失败时记录 `validation_failed` 审计且不写 legacy active 指针 | `tests/test_v7_generation_migration.py`：RED 5 failed；追加失败审计 RED 1 failed → GREEN 6 passed |
| S-T14 | 🔴 RED | 查询在并发激活期间固定同一 generation 快照 | 请求级 Resolver 不存在 |
| S-T15 | 绿色（通过） | 发布事实、制品、计算、声明、报告的关联表均由 SQLite 外键保护，悬空写入拒绝且不留部分关系 | `tests/test_provenance_repository.py`：RED 3 failed（模块不存在）→ GREEN 3 passed；含 metadata、EvidenceBundle、计算仓储回归 15 passed |
| S-T16 | 绿色（通过） | 来源 document version 失效会精确将直接/间接依赖的计算、声明和报告标记为 `stale` 并留下失效记录 | `tests/test_provenance_repository.py`：RED 3 failed → GREEN 3 passed |
| S-T17 | 绿色（通过） | `tests/test_v7_document_repository.py`：零引用且超过保留期前不回收共享 blob；最后引用释放后才允许物理回收 | RED AttributeError（引用计数接口不存在）→ GREEN 文档仓储、上传与协调器回归 9 passed |
| S-T18 | 🔴 RED | artifact API 拒绝路径、未知/删除/不可见 artifact 且不泄露路径 | 受控制品端点不存在 |
| S-T19 | 绿色（通过） | `multimodal_enabled` 关闭时上传、查询、删除严格匹配冻结 JSON 字段；开启时只追加处理状态和版本标识 | `tests/test_m0_compatibility_contract.py`：RED 2 failed（字段未声明）→ 3 passed；追加 API 装配 RED 1 failed → GREEN 4 passed；兼容回归 22 passed |
| S-T20 | 🔴 RED | 当前溯源实现不引入图数据库或通用三元组依赖 | 依赖边界尚未实施验证 |
| S-T21 | 绿色（通过） | blob 只能由已登记 `document_version_id` 解析；未登记孤儿 blob 没有按 hash/path 读取接口，过期 staging 文件可幂等清理 | `tests/test_m0_input_and_orphans.py`：RED 2 failed（接口不存在）→ GREEN 3 passed；输入/上传/仓储回归 16 passed |
| S-T22 | 绿色（通过） | hash 键命中但数据库 size 或磁盘字节不一致均拒绝复用，不创建新 document version | `tests/test_m0_input_and_orphans.py`：数据库大小冲突 GREEN；既有磁盘字节校验由仓储路径覆盖 |
| S-T23 | 绿色（通过） | 控制字符、路径分隔符和 Windows 保留文件名不进入 v7 文档版本元数据或物理路径 | `python -m pytest -q tests/test_v7_document_repository.py`：追加边界 RED 1 failed → GREEN 4 passed |
| S-T24 | 绿色（通过） | I/O、数据库、解析和索引错误按稳定类别进入有限重试；确定性失败不再自动消费，任一失败均不写 indexed generation | `tests/test_pdf_hot_loader.py`：RED ImportError（不可重试异常/分类接口不存在）→ 热加载、上传、兼容与开关回归 47 passed |
| S-T25 | 绿色（通过） | 新上传响应保留 `filename/size/size_mb`，并以 `pending_index`/`pending_processing` 表示未完成，V7 字段仅为可选追加 | `tests/test_m0_compatibility_contract.py`：RED 2 failed → GREEN 4 passed |
| S-T26 | 🔴 RED | 端点级 API key 不被测试或文档误判为文档级多租户 ACL | 权限承诺边界未验证 |
| S-T27 | 绿色（通过） | PublicationSet 只接受已验证 generation，并以 SQLite 绑定 generation、完整 document version 集、页制品、事实与 corpus revision；请求开始捕获的快照不受后续激活影响 | `tests/test_publication_set.py`：RED 3 failed（模块不存在）→ PublicationSet/generation/metadata/provenance/兼容回归 31 passed |
| S-T28 | 绿色（通过） | 每个 publication build 持久化 expected active publication/corpus revision；两个构建者同基线提交时仅第一个 CAS 激活，另一个记录 `superseded` 原因 | `tests/test_publication_set.py`：RED 3 failed（expected revision 接口不存在）→ PublicationSet/generation/metadata/provenance 回归 18 passed |
| S-T29 | 绿色（通过） | publication 只接受带非空已验证索引制品清单的 generation；activation 末尾数据库故障时 active publication 与 build 状态整体回滚，新集合不可见 | `tests/test_publication_set.py`：SQLite trigger 故障注入，PublicationSet/generation/metadata/provenance/兼容回归 29 passed |
| S-T30 | 绿色（通过） | 回滚创建新的 PublicationSet，完整复用目标 snapshot 的 generation、document versions、页制品和事实，并记录 restored/replaced publication 审计 | `tests/test_publication_set.py`：RED AttributeError（回滚接口不存在）→ 29 passed |
| S-T31 | 绿色（通过） | candidate 固定 corpus revision，publication 激活必须匹配构建开始时记录的 active publication/revision；语料变化不会静默覆盖新 active 状态 | `tests/test_v7_generation_migration.py`、`tests/test_publication_set.py`：generation 基线与 CAS/superseded 回归 18 passed |
| S-T32 | 🔴 RED | 删除与同 hash 上传并发时共享 blob 不被误删 | 引用计数事务不存在 |
| S-T33 | 🔴 RED | 来源软失效保留历史审计并阻止新请求读取受保护 artifact | 软失效和发布过滤未集成 |
| S-T34 | 🔴 RED | 进程崩溃后的旧 publication 租约可安全过期且不提前回收文件 | publication 租约不存在 |

### 2026-08-28 PDF 增量热加载首批测试

| ID | 状态 | 测试目标 | 证据 |
|---|---|---|---|
| HL-T01 | 绿色（通过） | PDF 以临时文件写入并原子进入 `pending_index`，不暴露上传中临时文件 | `pytest tests/test_pdf_hot_loading.py -q`：5 passed |
| HL-T02 | 绿色（通过） | 相同文件名和内容重复上传幂等，不增加清单文档数 | `pytest tests/test_pdf_hot_loading.py -q`：5 passed |
| HL-T03 | 绿色（通过） | 新版本上传后旧 SHA-256 的索引任务不能覆盖新版本状态 | `pytest tests/test_pdf_hot_loading.py -q`：5 passed |
| HL-T04 | 绿色（通过） | 索引失败状态保留错误并可被待处理队列发现 | `pytest tests/test_pdf_hot_loading.py -q`：5 passed |
| HL-T05 | 绿色（通过） | 非 PDF 文件头被拒绝 | `pytest tests/test_pdf_hot_loading.py -q`：6 passed |
| HL-T06 | 绿色（通过） | 清单写入失败时恢复已存在的 PDF，避免磁盘与清单不一致 | `pytest tests/test_pdf_hot_loading.py -q`：6 passed |
| HL-T07 | 绿色（通过） | worker 消费待处理文档并推进 generation 状态 | `pytest tests/test_pdf_hot_loader.py tests/test_pdf_hot_loading.py -q`：8 passed |
| HL-T08 | 绿色（通过） | worker 解析失败保留可重试错误状态，不调用索引构建器 | `pytest tests/test_pdf_hot_loader.py tests/test_pdf_hot_loading.py -q`：8 passed |
| HL-T09 | 绿色（通过） | worker 扫描 PDF 目录并登记直接放入目录的新文档 | `pytest tests/test_pdf_hot_loader.py tests/test_pdf_hot_loading.py -q`：10 passed |
| HL-T10 | 绿色（通过） | 调度器显式启动/停止且重复调用安全 | `pytest tests/test_pdf_hot_loader.py -q`：5 passed |
| HL-T11 | 绿色（通过） | 调度器拒绝非正轮询间隔 | `pytest tests/test_pdf_hot_loader.py -q`：5 passed |
| HL-T12 | 绿色（通过） | 首次目录扫描认领旧 registry 已覆盖 PDF，不重复排队 | `pytest tests/test_pdf_hot_loading.py tests/test_pdf_hot_loader.py -q`：13 passed |
| HL-T13 | 绿色（通过） | API 配置可开启目录登记扫描，生命周期关闭时停止调度器 | 配置读取与 `PdfHotLoadScheduler` 编译/导入核查通过；未触发外部解析调用 |
| HL-T14 | 绿色（通过） | MinerU 适配器懒加载客户端并校验解析结果与源 SHA-256 | `pytest tests/test_pdf_hot_loader.py -q`：8 passed |
| HL-T15 | 绿色（通过） | MinerU token 与 DashScope Embedding key 分离 | `pytest tests/test_pdf_hot_loader.py -q`：8 passed |
| HL-T16 | 绿色（通过） | API 热加载默认仅目录登记，不创建外部索引 pipeline | `pytest tests/test_pdf_hot_loader.py -q`：11 passed |
| HL-T17 | 绿色（通过） | 显式开启索引时创建 pipeline，关闭资源时释放 MinerU 客户端 | `pytest tests/test_pdf_hot_loader.py -q`：11 passed |
| HL-T18 | 绿色（通过） | 有界停止遇到运行中任务时报告未停止，避免关闭正在使用的客户端 | `pytest tests/test_pdf_hot_loader.py -q`：11 passed |

| HL-UI-01 | 绿色（通过） | 页面存在待处理/失败任务时每 5 秒静默刷新，任务完成后停止轮询 | `npm run test -- --run`：44 个文件、237 项通过；build/lint 通过 |
| HL-T19 | 绿色（通过） | 增量构建保留同公司历史 chunk，仅替换同源旧版本 | `pytest tests/test_pdf_hot_loader.py -q`：13 passed |
| HL-T20 | 绿色（通过） | pipeline 实际调用发布器时传入合并后的完整公司语料 | `pytest tests/test_pdf_hot_loader.py -q`：13 passed |
| HL-T21 | 绿色（通过） | 自动重试达到上限后停止消费，保留失败状态和尝试次数 | `pytest tests/test_pdf_hot_loader.py -q`：14 passed |
| HL-T22 | 绿色（通过） | 显式重试重置次数并重新进入待处理状态 | `pytest tests/test_pdf_hot_loading.py -q`：9 passed |
| HL-T23 | 绿色（通过） | 删除后同名 PDF 重放不会继承旧 manifest/generation 状态 | `pytest tests/test_pdf_hot_loading.py tests/test_pdf_hot_loader.py -q`：24 passed |
| HL-T24 | 绿色（通过） | 删除阶段 manifest 写入失败时恢复原 PDF | `pytest tests/test_pdf_hot_loading.py tests/test_pdf_hot_loader.py -q`：25 passed |
| HL-T25 | 绿色（通过） | MinerU 解析使用可配置正数超时，默认保持 600 秒 | `pytest tests/test_pdf_hot_loader.py tests/test_pdf_hot_loading.py -q`：30 passed；覆盖自定义值、默认值链路和 0/负数/NaN/Infinity 拒绝 |
| HL-T26 | 绿色（通过） | 普通 PDF 使用 `extract_batch` 异步轮询，保留单一完成结果和配置超时 | `python -m pytest -q tests/test_pdf_hot_loader.py`：新增用例通过 |
| HL-T27 | 绿色（通过） | 大 PDF 按 150 页物理页分批，范围不越界，失败不合并发布并保留批次标记 | `python -m pytest -q tests/test_pdf_hot_loader.py`：新增用例通过 |
| HL-T28 | 绿色（通过） | 热加载临时 Markdown 使用显式路径参与物理页映射，批次标记不进入最终检索文本 | `python -m pytest -q tests/test_page_metadata.py tests/test_pdf_hot_loader.py`：25 passed |
| HL-T29 | 绿色（通过） | 页脚页码识别不得把表格/正文中的孤立数字误判为文档页码 | `python -m pytest -q tests/test_page_metadata.py`：4 passed |
| HL-T30 | 绿色（通过） | 年报常见 `当前页 / 总页数` 格式仅在总页数等于 PDF 物理页数时识别 | `python -m pytest -q tests/test_page_metadata.py`：6 passed；真实 222 页年报识别 222/222 页 |
| HL-T31 | 绿色（通过） | 封面无印刷页码、正文从文档第 1 页开始时保持物理页与文档页的偏移 | `python -m pytest -q tests/test_page_metadata.py`：7 passed；真实电信/移动年报分别识别 217/218、221/222 页 |
| HL-T32 | 绿色（通过） | 真实 PDF 经热加载 worker 完成 MinerU、切分、Embedding、FAISS/BM25、generation 发布并回写 indexed | 临时目录实测：1 discovered、1 processed、0 failed；26 parent、64 child、64/64 Embedding；正式数据未修改 |

### 2026-08-28 增量索引发布首批测试

| ID | 状态 | 测试目标 | 证据 |
|---|---|---|---|
| PUB-T01 | 绿色（通过） | 成功构建写入新 generation，active 指针切换且旧 generation 保留 | `pytest tests/test_index_publication.py -q`：3 passed |
| PUB-T02 | 绿色（通过） | 构建异常不改变旧 active，staging 目录清理 | `pytest tests/test_index_publication.py -q`：3 passed |
| PUB-T03 | 绿色（通过） | active 指针使用原子 JSON 替换，未知公司不猜测版本 | `pytest tests/test_index_publication.py -q`：3 passed |
| PUB-T04 | 绿色（通过） | 旧 ingestion builder 可在不改实现逻辑的前提下写入 staging | `pytest tests/test_index_publication.py -q`：6 passed |
| PUB-T05 | 绿色（通过） | 真实旧索引制品复制到 generation 后，Retriever 可加载 FAISS/BM25/元数据 | 临时目录实测：FAISS 2365 条、1024 维；BM25 2365 条；metadata 2365 条；parent text 888 条 |
| PUB-T06 | 绿色（通过） | 发布前源 PDF 哈希变化会取消发布且不生成 active 指针 | `pytest tests/test_index_publication.py -q`：9 passed |
| PUB-T07 | 绿色（通过） | 仅存在 v7 active 指针、缺少旧式 registry 时 Retriever 可发现已发布公司；无两者时明确失败 | `python -m pytest -q tests/test_index_publication.py`：新增用例通过 |

## M. 可验证多模态财报理解

| ID | 状态 | 测试目标 | 预期 RED 原因 |
|---|---|---|---|
| M-T00 | 绿色（通过） | 分块同时保存 PDF 物理页和直接识别的文档印刷页；物理页缺失时不伪造印刷页 | `python -m pytest -q tests/test_page_metadata.py`：3 passed |
| RENDER-T01 | 绿色（通过） | 页图渲染器以文档版本、源 PDF 哈希、物理页和渲染版本作为缓存键，生成页图/缩略图并拒绝越界页和不安全版本 ID | `python -m pytest -q tests/test_page_image_renderer.py`：RED 2 failed、类型边界 RED 1 failed → GREEN 2 passed |
| MANIFEST-T01 | 绿色（通过） | DocumentAssetManifest 以 v7 SQLite 外键持久化，创建幂等且源哈希、物理页和状态冲突时拒绝静默覆盖 | `python -m pytest -q tests/test_document_asset_manifest_repository.py`：RED 2 failed、冲突边界 RED 1 failed → GREEN 3 passed |
| MANIFEST-T02 | 绿色（通过） | 清单仅在全部 PDF 物理页具备完整页图/缩略图且完整成功解析批次覆盖时标记 complete；缺登记页、文件缺失或批次缺失/失败均持久化为 incomplete 问题 | `python -m pytest tests/test_document_asset_manifest_repository.py -q`：页图 RED 2 failed、批次门禁 RED 1 failed → GREEN 5 passed；真实 5 页 PDF 双门禁临时链路通过 |
| PAGEART-T01 | 绿色（通过） | 页图制品登记必须绑定 matching manifest/document version/物理页，拒绝跨文档、越界和第 0 页 | `python -m pytest -q tests/test_page_artifact_repository.py`：RED 2 failed、页 0 边界 RED 1 failed → GREEN 2 passed |
| REGION-T01 | 绿色（通过） | VisualRegion 只能绑定已完成页图制品，回查 manifest/物理页；仅接受有序的 0–1 非零面积规范化坐标 | `python -m pytest -q tests/test_visual_region_repository.py`：RED 2 failed → GREEN 2 passed；真实 PDF 第 1 物理页临时登记通过 |
| BATCH-T01 | 绿色（通过） | 解析批次以不可重叠的 PDF 物理页段持久化，汇总明确区分缺失、失败和未完成页 | `python -m pytest -q tests/test_parse_batch_repository.py`：RED 2 failed → GREEN 2 passed；真实 5 页 PDF 的 `1–5` 物理页范围验收通过 |
| ARTIFACT-T01 | 绿色（通过） | 六类制品均有 schema 版本；Manifest、Region、ParseBatch、表格、图表和视觉证据状态受限且同事务审计，页图仅凭完整文件创建为 immutable complete | `tests/test_visual_artifact_repository.py`：状态接口 RED 1 failed、schema 列 RED 1 failed → GREEN；`tests/test_parse_batch_repository.py`、manifest/region/page/metadata 关联回归 22 passed |
| COORD-T01 | 绿色（通过） | V7 协调器只能用 document version/blob SHA/物理页数启动，按 manifest 全页渲染并以页图与解析批次双门禁完成 | `python -m pytest -q tests/test_v7_document_processing_coordinator.py`：RED 2 failed → GREEN 2 passed；真实 5 页 blob 临时链路通过 |
| ASSET-T01 | 绿色（通过） | 既有 PDF/Markdown 诊断清单按同名配对统计图片、HTML/Markdown 表格与公式；缺失或越界本地制品标记 incomplete，报告原子写入 | `python -m pytest -q tests/test_document_asset_inventory.py`：RED 2 failed、追加写入 RED 1 failed → GREEN 3 passed |
| M-T01 | 绿色（通过） | 制品清单发现既有 Markdown 图片、HTML/Markdown 表格和公式 | `tests/test_document_asset_inventory.py`（Markdown 图片/HTML 表格/公式资产发现）3 用例通过；历史 RED 原始输出缺失（实现随 document_asset_inventory.py 先行落地），以现状通过为证如实登记 |
| M-T02 | 绿色（通过） | 缺失图片或无法关联页码的制品标记 missing/unresolved | `tests/test_document_asset_inventory.py`（缺失资产标 missing）与 `tests/test_document_asset_manifest_repository.py`（complete 需解析批次覆盖、unresolved 禁止 complete）覆盖，合并 9 passed（短 basetemp）；历史 RED 原始输出缺失，以现状通过为证如实登记 |
| M-T03 | 绿色（通过） | MinerU 失败页批次使文档保持 incomplete | RED 4 failed（`ImportError: cannot import name 'MinerUParseBatchBypass' from 'src.pdf_mineru'`）；GREEN `tests/test_pdf_mineru_parse_batch_bypass.py` 4 passed（成功批次写入/失败页使 coverage.complete=False 且 manifest.asset_status 保持 incomplete/旁路记录失败不影响原解析/单批异常路径记 failed），关联回归 `tests/test_parse_batch_repository.py` + `tests/test_pdf_hot_loader.py` 30 passed（短 basetemp） |
| M-T04 | 绿色（通过） | 相同文档、页码和渲染版本复用页图 artifact ID | `tests/test_page_image_renderer.py`（同页渲染命中内容哈希缓存返回相同 artifact）与 `tests/test_page_artifact_repository.py`（注册链接 manifest 页身份）覆盖，22 passed（短 basetemp）；历史 RED 原始输出缺失，以现状通过为证如实登记 |
| M-T05 | 绿色（通过） | 旋转页 bbox 与前端高亮使用同一规范化坐标 | `tests/test_multimodal_candidate_inventory.py`：RED 1 failed（90° 页直接按旋转后尺寸归一化得到错误坐标）→ GREEN 5 passed；检测器未旋转 bbox 先经 `page.rotation_matrix` 转换到页图空间后再归一化，未旋转页契约保持通过 |
| M-T06 | 绿色（通过） | 有文本层的普通页面不调用视觉模型 | RED 1 collection error（`ModuleNotFoundError: No module named 'src.page_router'`，4 用例）；GREEN `tests/test_page_router.py` 4 passed（五类型区分/纯文本页 use_vision=False 且理由可审计/scan·chart·mixed 请求视觉而 table 按复杂度门禁另行决策/低字符文本页不误判 scan），全新独立模块无既有调用方，回归范围即本套件（短 basetemp） |
| M-T07 | 绿色（通过） | 视觉模型未配置时明确 unavailable 且不静默文本回退 | `tests/test_vision_provider.py`：RED 2 failed（`ModuleNotFoundError: src.vision_provider`）→ GREEN 3 passed；未启用、缺 API key/model 或能力未声明均返回 `unavailable`，不会调用文本 Provider |
| M-T08 | 绿色（通过） | BaseLLMProvider.chat 保持纯文本契约 | 同套件调用既有 `BaseLLMProvider.chat([{role, content}])` 仍抛出原有 `NotImplementedError`；视觉模块独立、未导入或包装 `BaseLLMProvider`，与多 Agent/路由/M2.1～M2.3 关联回归 78 passed |
| M-T09 | 绿色（通过） | MinerU HTML 表格保留多级表头和 row/colspan | RED 1 collection error（`ModuleNotFoundError: No module named 'src.table_structure'`，4 用例）；GREEN `tests/test_table_structure.py` 4 passed（HTML colspan 表头网格展开且原始值/题注保留、rowspan 多级表头跨行关系与被覆盖格保留、Markdown 表格保留空单元格/单位/期间/原始文本、模块命名空间零导入 src.retrieval 且排版符号原样保留），关联回归 `tests/test_source_excerpt.py` + `tests/test_page_router.py` 10 passed |
| M-T10 | 绿色（通过） | 表格事实不从 preprocess_table_text 扁平结果反推 | `src/table_structure.py` 结构化真值链直接解析 MinerU HTML/Markdown 原文（标准库 HTMLParser，无第三方依赖），经测试证明模块命名空间无任何来自 src.retrieval 的符号导入，且含排版符号与空值的原始单元格值原样保留（同上 4 passed） |
| M-T11 | 绿色（通过） | 跨页续表只在标题、表头、列结构和相邻页均兼容时合并 | `tests/test_cross_page_table_continuation.py`：RED 1 collection error（`ImportError: cannot import name 'TablePage'`）→ GREEN 3 passed；相邻页、题注、表头、列结构全部兼容才返回 `confirmed`，不修改原表格真值 |
| M-T12 | 绿色（通过） | 条件不足的跨页表格保持分离并标记候选关系 | 同一套件验证题注、表头或列结构冲突与非相邻页均返回 `candidate`、`requires_review=True`，不自动合并；与 M2.1/M2.2 关联回归 17 passed |
| M-T55 | 绿色（通过） | 复杂表格视觉结果携带结构化表格、置信度、模型、用量和区域；高低置信均只进入 candidate，不可用或缺审计字段为 incomplete | `tests/test_complex_table_vision.py`：RED 2 failed（`ModuleNotFoundError: src.complex_table_vision`）→ GREEN 2 passed；视觉/表格/制品/事实关联回归 17 passed，未写入 verified 事实 |
| M-T13 | 绿色（通过） | 图表提取标题、图例、轴、单位、期间、系列和区域 | `tests/test_chart_understanding.py`：RED 1 collection error（`ModuleNotFoundError: src.chart_understanding`）→ GREEN 3 passed；候选结果保留 manifest/视觉区域、标题、图例、轴、单位、期间与系列，且不写入 verified 事实 |
| M-T14 | 绿色（通过） | 只能判断趋势时不伪造精确数据点 | 同一套件验证数值置信度 0.42 时清空 data_points、仅保留趋势候选；置信度阈值默认 0.85，全部成功输出保持 candidate/review_required |
| M-T15 | 绿色（通过） | 扫描页低置信数字不能进入 verified 事实 | `tests/test_visual_fact_candidate_repository.py`：RED 2 failed（`ModuleNotFoundError: src.visual_fact_candidate_repository`）→ GREEN 2 passed；扫描候选外键绑定 manifest/页制品、默认 pending_review，低置信拒绝准入，高置信仍须显式 verified 后才能保存并关联事实 |
| M-T56 | 绿色（通过） | 视觉候选事实的准入服务同时要求置信度达标与人工审核通过 | `tests/test_visual_fact_admission.py`：RED 1 collection error（`ModuleNotFoundError: src.visual_fact_admission`）→ GREEN 2 passed；低置信即使标记 verified 仍不调用事实仓储，candidate 同样拒绝，高置信 verified 才保存 |
| M-T16 | 绿色（通过） | 视觉数字复用统一单位、期间和币种归一器 | `tests/test_visual_fact_normalizer.py`：RED 4 failed（`ModuleNotFoundError: src.visual_fact_normalizer`）→ GREEN 4 passed；候选仓储注册强制调用既有金额归一器和 FinancialFact 契约，保存归一值/单位/换算轨迹，拒绝未知单位、非法币种和非法期间 |
| M-T17 | 绿色（通过） | 正文与图表同口径冲突进入统一冲突引擎 | `tests/test_visual_fact_conflict_bridge.py`：RED 1 failed（`ModuleNotFoundError: src.visual_fact_conflict_bridge`）→ GREEN 1 passed；已审核且已关联事实的视觉候选调用既有 FinancialFactConflictService，超阈值 VALUE_CONFLICT 写入既有冲突仓储 |
| M-T18 | 绿色（通过） | 图片/OCR 等不可信视觉内容被隔离进只读上下文，不能改变系统指令、工具权限、审批、能力或预算 | `tests/test_vision_security_boundaries.py`：RED 3 failed（`src.vision_security` 不存在）→ GREEN；`VisionSafetyGuard` HTML 转义并封装不可信内容，`BaseVisionProvider` 仅向具体 Provider 传递已冻结请求 |
| M-T19 | 绿色（通过） | `SourceInfo` 可选视觉字段不改变旧 API JSON；仅 complete 制品可带 manifest/page/region/bbox 定位 | `tests/test_source_info_visual_locator.py`：RED 1 failed（定位字段丢弃）→ 后端兼容定向回归 8 passed；前端 241 passed、生产构建通过 |
| M-T20 | 绿色（通过） | EvidencePanel 显示页图、区域高亮和 incomplete 警告 | `tests/test_source_info_visual_locator.py` RED 1 failed（缺失状态字段）→ 后端来源定向回归 4 passed；`SourceCard.test.tsx` RED 1 failed（提示未显示）→ GREEN 5 passed，确认 incomplete 不请求页图 |
| M-T21 | 绿色（通过） | 删除 PDF 同步清理清单、页图、视觉事实和索引 | 完整链路已闭环：未发布版本清理服务（M-T36）；已索引版本经删除协调器推进——`delete_pdf(filename, deletion_coordinator=...)` 为同名全部未删除版本幂等创建删除请求（M3.6.a），排除重建与 PublicationSet CAS 发布（M-T44/M3.10.b）、`cleanup_request` 事实失效/stale 传播/blob 回收（M-T41/M3.11）、旧代际回收（M1.10）；页图 `.deleting` 受限清理（M-T28/M-T37/M-T38）。`tests/test_v7_delete_pdf_integration.py`：RED 3 failed（`deletion_coordinator` 参数与 `request_deletion_by_original_filename` 不存在）→ GREEN 4 passed，关联回归 46 passed（7 套件）；不注入协调器时 V7 表零触碰，与现状完全一致 |
| M-T22 | 🔴 RED | 多模态索引不降低批准的纯文本检索与问答基线 | 尚未运行集成回归 |
| M-T23 | 🔴 RED | 同一视觉区域命中缓存时不重复调用模型 | 视觉缓存和调用账本不存在 |
| M-T24 | 绿色（通过） | 伪造 PNG/JPEG、异常像素、文件大小、调用次数或预估 Token 超限时在具体 Provider 调用前停止，并返回 explicit incomplete | `tests/test_vision_security_boundaries.py`：首轮 3 failed（模块不存在），追加 Provider 调用隔离 RED 1 failed（安全异常直接冒泡）→ GREEN 4 passed；M3 视觉服务关联回归 16 passed |
| M-T25 | 🔴 RED | manifest 原子写入失败时不得推进 complete | 制品状态存储不存在 |
| M-T26 | 🔴 RED | 视觉 embedding 失败不写零向量且标记 incomplete | 索引 strict 模式不存在 |
| M-T27 | 绿色（通过） | 页图端点仅解析同 manifest 下合法且 complete 的已登记 artifact ID，拒绝路径遍历、未知 ID、跨 manifest 和默认关闭路径 | `tests/test_page_artifact_access.py`：RED 2 failed（访问服务不存在）、端点 RED 1 failed（接口不存在）→ 关联回归 16 passed；应用级 API key 不构成文档级 ACL |
| M-T28 | 🟡 部分通过 | 删除中断后保持 deleting 并可幂等续清理 | 页图根目录的 `.deleting` 文件可受限幂等清理，并已收敛到 V7 处理协调器实际输出目录（M-T37/M-T38）；尚未接入应用启动或后台调度 |
| M-T29 | 绿色（通过） | 同源页面或裁剪变体不能跨开发集和冻结留出集 | 区域级样本强制提供 PDF SHA-256 和物理页；`tests/test_multimodal_evaluation_coverage.py` RED 1 failed（只报样本数量不足）→ 覆盖/候选关联回归 7 passed，跨不同 document ID 的同 hash 页被拒绝 |
| M-T30 | 🔴 RED | 高风险视觉数字误入 verified 时无视平均分直接失败 | 高风险硬门禁不存在 |
| M-T31 | 🔴 RED | 多模态报告包含路由、缓存、调用、失败和 P95 | 成本观测字段不存在 |
| M-T32 | 🔴 RED | 页图高亮可键盘操作且表格/图表有文本等价说明 | 前端可访问性尚未实现 |
| M-T33 | 🔴 RED | staging 索引构建失败不改变 active publication | 索引代际管理器不存在 |
| M-T34 | 🔴 RED | 新代际校验后与文档/制品/事实整组发布且可回滚 | PublicationSet 不存在 |
| M-T35 | 绿色（通过） | complete `visual_locator` 经统一 Bearer 请求读取 Blob 页图，并按 bbox 显示高亮；请求 URL 不包含密钥 | `SourceCard.test.tsx` RED 1 failed（未显示页图）→ 来源卡与服务层定向回归 8 passed；全量前端 242 passed、生产构建通过 |
| M-T36 | 绿色（通过） | 未发布且未进入索引代际的 V7 文档删除会同步清理 manifest、解析批次、页图文件、视觉区域、表图制品和视觉证据；索引代际引用明确拒绝 | `tests/test_v7_document_deletion.py` RED 2 failed（模块不存在）→ GREEN 2 passed；与页图、制品仓储、manifest 关联回归 14 passed |
| M-T37 | 绿色（通过） | 删除中断遗留的页图 `.deleting` 文件只可在调用方明确指定的制品根目录内幂等清理 | `tests/test_v7_document_deletion.py` RED 1 failed（恢复接口不存在）→ GREEN 3 passed，目录外同名文件保持不变 |
| M-T38 | 绿色（通过） | V7 处理协调器恢复页图删除时仅使用其 PageImageRenderer 配置的输出根目录 | `tests/test_v7_document_processing_coordinator.py` RED 1 failed（协调器接口不存在）→ 与删除服务回归 6 passed |
| M-T39 | 绿色（通过） | 区域级源页身份字段在 JSON Schema 与运行时模型中同名、同约束，避免 `additionalProperties=false` 拒绝有效样本 | `tests/test_multimodal_evaluation_coverage.py` RED 1 failed（Schema 缺字段）→ 与评测质量门禁回归 24 passed |
| M-T44 | 绿色（通过） | 已索引文档只能通过排除后的候选 generation 退出未来发布集；构建候选不会原地改变当前 active 文档或 active publication，并记录排除审计 | `tests/test_v7_generation_migration.py`：RED 1 failed（接口不存在）→ generation、PublicationSet、删除关联回归 16 passed |
| M-T45 | 绿色（通过） | staging generation 制品验证成功后，PublicationSet 只进入 prepared 并带构建开始时的 CAS 基线；不会自动切换 active publication | `tests/test_v7_generation_publication_coordinator.py`：RED 1 failed（协调器模块不存在）→ generation、PublicationSet、legacy staging 关联回归 25 passed |
| M-T51 | 绿色（通过） | 实际 `IndexPublicationManager` 发布出的 staging generation 制品被注册为 V7 candidate 的不可变 hash/size manifest 绑定；绑定失败不创建 PublicationSet 且 active publication 不变；manifest 与发布结果不一致先于验证被拒绝 | `tests/test_v7_index_generation_binding.py`：RED 3 failed（绑定模块不存在）→ 绑定、协调器、回收定向回归 9 passed，generation/publication/legacy 关联回归 33 passed |
| M-T52 | 绿色（通过） | 协调器提供受控显式 CAS 激活入口：基线匹配时切换 active 并置 published；基线过期得到 superseded 且 active 保持不变，绝不读取 legacy JSON active 指针 | `tests/test_v7_generation_publication_coordinator.py`：RED 2 failed（激活入口不存在）→ 三套件定向回归 9 passed，关联回归 33 passed |
| M-T53 | 绿色（通过） | 旧 generation 回收只记录资格审计（无 active publication 引用、无在途请求引用、保留期已过、Windows 制品未被打开锁定），绝不物理删除；历史 publication 引用仅记入明细不阻塞；锁定文件释放后资格恢复 True | `tests/test_v7_generation_retirement.py`：RED 3 failed（回收模块不存在）→ 三套件定向回归 9 passed，关联回归 33 passed；锁定探测原用重命名到自身无法感知 CPython 共享打开，改为 Windows 独占打开探测后 GREEN |
| M-T54 | 绿色（通过） | 端到端编排收口：排除文档候选 → 实际构建发布 → 绑定 → CAS 准备 → 显式激活 → 旧代际回收资格；激活后旧代际合格、整组回滚后重新失格；并发基线覆盖时后激活者 superseded、回滚恢复旧代际且候选与制品不被物理删除；V7 激活不读/不改 legacy JSON 指针 | `tests/test_v7_generation_publication_e2e.py`：集成验证组合既有分段能力（M-T44～M-T53），无新增生产代码故无 RED 缺口，不作伪造 → 2 passed，七套件关联回归 35 passed |
| M-T46 | 绿色（通过） | 单次请求始终读取同一 publication：请求内激活新 publication 不影响本请求，end_request/request_scope 后释放，无 active 时返回 None | `tests/test_publication_set.py`：RED 1 failed（`AttributeError: 'PublicationResolver' object has no attribute 'begin_request'`）→ 新增 2 用例 GREEN；resolver 用 ContextVar 保存请求快照实现请求级固定 |
| M-T47 | 绿色（通过） | 激活后 RAGGenerator、RetrieveTool、CompareTool 新请求均刷新 publication，结果携带 publication_id，请求结束后快照释放；未注入 resolver 时三工具行为与现状完全一致 | `tests/test_v7_publication_resolver_wiring.py`：RED 4 failed（HybridRetriever/RetrieveTool/CompareTool/RAGGenerator 各 1 个 `TypeError: unexpected keyword argument`）→ HybridRetriever 快照代际优先 + 三工具接线后 4 用例 GREEN；关联回归 14 passed（generation/publication E2E、retrieve/compare quick、agent tools） |
| M-T48 | 绿色（通过） | Windows 打开旧索引时不会被回收或替换 | `tests/test_v7_generation_retirement_execution.py`：RED 3 failed（`ImportError: cannot import name 'V7GenerationRetirementExecutor'`）→ 执行器 GREEN：合格代际制品物理删除+候选置 retired+retirement_executed 审计；不合格（active 引用/在途/保留期/锁定任一）绝不删除并记 retirement_skipped；锁定句柄期间回收跳过、释放后重新执行成功；active publication 全程不变。资格评估原 3 用例 + 关联回归 20 passed（migration/coordinator/e2e/publication_set） |
| M-T49 | 🔴 RED | multimodal_enabled 关闭时旧上传、索引和来源响应完全不变 | 多模态开关不存在 |
| M-T50 | 🔴 RED | 相同内容哈希重复上传幂等返回同一文档版本 | 文档版本模型不存在 |
| M-T40 | 绿色（通过） | 同名不同内容创建新版本且完整前不替换 active | `tests/test_v7_document_version_promotion.py`：RED 3 failed（`AttributeError`：promote_document_version_to_active / get_active_document_version 不存在）→ 仓储新增两方法后 GREEN：同 key 不同 hash 登记新版本为 pending_index 且 active 不变，唯一激活入口 promote 原子降级旧 active 为 superseded 并激活目标；GREEN 验证 12 passed（promotion 3 + m0 兼容 4 + repository 5），关联回归 23 passed |
| M-T57 | 绿色（通过） | 索引回调明确成功并返回 generation 身份后才调用文档版本提升 | `tests/test_v7_document_index_promotion_coordinator.py`：RED 2 failed（`ModuleNotFoundError`）→ GREEN 2 passed；索引失败/缺 generation 保持旧 active，成功后才显式 promote |
| M-T58 | 绿色（通过） | 旧 generation 批处理只选择 `validated` 状态，遵守稳定顺序和单轮 batch 上限；在途 generation 由既有执行器保留制品、状态并留下跳过审计 | `tests/test_v7_generation_retirement_scheduler.py`：RED 2 failed（`ModuleNotFoundError`）→ 批处理与资格/执行器关联 GREEN 8 passed |
| M-T41 | 绿色（通过） | 文档级 deleting 线性化点后新查询不再取得该版本，旧查询快照保持固定；blob ID 解析拒绝 deleting 版本；active publication 包含 deleting 文档时，新 V7 请求 fail-closed，不回退 legacy generation；活动请求租约在 begin/end 间持久化，删除请求明确返回等待 lease 或重建 generation 状态；`rebuild_required` 删除请求可构建排除 deleting 版本的候选代际，经制品绑定与 PublicationSet CAS 发布使替代 publication 生效，重建不触碰 deleting 版本本体；过期租约不再阻塞删除进度，`advance_request()` 按租约与替代 publication 状态推进到 `cleanup_ready` 稳定终态（schema v22），`cleanup_request()` 完成事实可见性失效、stale 传播软失效审计与共享 blob 引用分层回收 | `tests/test_v7_document_deletion_visibility.py`、`tests/test_v7_document_deletion_coordinator.py`：RED 分别为 2 failed、1 failed（模块不存在）→ 删除协调、可见性、PublicationResolver、metadata 关联 GREEN；`tests/test_v7_deletion_rebuild_publication.py`：RED 1 failed（`GenerationMigrationError: 待移除文档版本不是 active 状态`）→ `build_candidate_excluding_document` 接受 `deleting` 线性化状态后 GREEN；租约等待/过期治理与 `advance_request()` 首轮 GREEN 前命中旧 CHECK 约束（status 不含 `cleanup_ready`）→ schema v22 重建表放宽约束后 coordinator 专测 9 passed；`cleanup_request()` 首轮 `FOREIGN KEY constraint failed`（deleting 版本行外键仍引用 blob 登记行）→ 引用计数排除 `deleting`、仅全部版本行物理移除才删登记行的分层设计后 GREEN；软失效审计按 `reason='document_cleanup'` 精确断言（主键为 (document_version_id, reason)，删除请求与清理动作各有记录）；并发引用插入经 `BEGIN IMMEDIATE` 写锁串行化后回收基于最新引用判定；十文件定向回归 47 passed（deletion coordinator/repository、provenance、deletion、rebuild publication、deletion visibility、metadata store、publication set、generation migration、generation publication e2e） |
| M-T42 | 绿色（通过） | 删除完成后 artifact API 和新索引均不可访问派生数据 | 索引层：重建候选排除 deleting 版本（M-T44/M-T41 链，`tests/test_v7_deletion_rebuild_publication.py`）；artifact 层：页图端点对 deleting 版本 fail-closed 拒绝读取（M-T60，`tests/test_artifact_endpoint_auth.py`）；页图文件物理清理调度接线仍属 M-T28 范围 |
| M-T43 | 🔴 RED | 旧在途请求与新代际激活遵守明确快照语义 | 文档版本与 generation 固定未集成 |
| M-T59 | 绿色（通过） | delete_pdf 经注入协调器为同名全部未删除版本幂等创建删除请求且先于文件删除，不注入时 V7 表零触碰；索引 metadata 链条件透传 artifact_refs，未携带不新增字段 | `tests/test_v7_delete_pdf_integration.py`：RED 3 failed（`deletion_coordinator` 参数与 `request_deletion_by_original_filename` 不存在）→ GREEN 4 passed；`tests/test_ingestion_strict_and_artifact_refs.py`：RED 3 failed（strict 与 `EmbeddingIncompleteError` 不存在）→ GREEN 4 passed（M-T26 strict 语义共用此证据）；7 套件关联回归 46 passed |
| M-T60 | 绿色（通过） | 页图端点受端点级 API key 保护（路径不在免认证白名单，缺头/错 key 返回 401 且下游不被调用）；制品目录不公开静态挂载、页图路由为受控 APIRoute；关联 document version 为 deleting 或缺失时页图读取 fail-closed 拒绝；仅承诺单用户/单租户端点级认证，不构成文档级多租户 ACL（M3.9/M3.9.1/S-T26 边界） | `tests/test_artifact_endpoint_auth.py`：RED 1 failed（`resolve_image` 不校验版本可见性，DID NOT RAISE）→ JOIN `v7_document_versions.index_status` 校验后 GREEN 3 passed（认证与挂载两条为钉住既有行为的回归）；9 套件关联回归 52 passed |
| M-T61 | 绿色（通过） | M3.1–M3.5 与 M3.10–M3.12 的已实现本地链路可共同回归，短临时目录不受 Windows 中文长路径影响 | `$env:TEMP` 下短 `--basetemp` 执行 24 个 M3 相关套件：85 passed；仅 4 条既有第三方弃用警告。 |
| M-T62 | 绿色（通过） | 可选 `visual_chart` 不破坏旧 `SourceInfo`；证据分组与链节点能区分回答、检索、视觉证据，并对缺少完整页图定位的视觉制品标记 incomplete | 前端 RED：4 个定向文件失败（`VisualChartEvidence` 不存在、bundle/chain/panel 无视觉语义）；GREEN：5 文件 20 tests passed；全量前端 46 文件 248 tests passed。 |
| M-T63 | 绿色（通过） | 证据面板和证据链图将视觉类别与不完整状态以可访问文本明确呈现；既有页图 Blob 预览、bbox 高亮与键盘触发语义保持复用 | `EvidenceContent.test.tsx`、`EvidenceChainGraph.test.tsx`、`SourceCard.test.tsx` 定向 GREEN；全量前端 46 文件 248 tests passed。 |
| M-T64 | 绿色（通过） | 识别图表仅在数值置信度不少于 0.85 且拥有 complete 页图定位时复用 `ChartContainer` 展示；否则拒绝绘制数值图，仅显示不完整警告和趋势候选 | `VisualChartEvidence.test.tsx` RED（模块不存在）→ GREEN（高置信+定位可绘制，低置信/无定位不绘制）; 全量前端 46 文件 248 tests passed，lint/build 通过。 |
| M-T65 | 绿色（通过） | M4.4 准入报告在证据缺失时 fail-closed；只接受已 verified 的区域样本、与当前 holdout 完全一致的冻结运行记录、合法视觉运行账本、零高风险误入 verified 及完整成本批准记录 | `tests/test_m4_multimodal_readiness.py`：RED 4 failed（模块不存在）→ GREEN 4 passed；与既有多模态覆盖和评测质量门禁回归共 28 passed。当前 385 条 pending_review 候选实跑报告为 No-Go，不作为发布证据。 |
| M-T66 | 绿色（通过） | 人工复核候选抽样按整份文档/公司隔离 development 与 holdout，同源页只保留一条，轮转文档抽样，候选状态强制为 pending_review；公司跨分区、源页不足或输出非 pending_review 均拒绝 | `tests/test_multimodal_candidate_inventory.py`：RED 3 failed（抽样/写包函数不存在）→ GREEN；与区域级评测覆盖回归共 12 passed。真实包 `multimodal_review_packet_tables_20260830.jsonl` 为 30 development + 10 holdout，0 重复源页、0 hash/页/bbox 校验失败。 |
| C1-T01 | 绿色（通过） | ResearchTask 的 task_id 映射稳定 C0 run_id，DAG 节点直接映射 C0 step_id/lease；任务状态与 revision 仅来自 C0，且不新增任务状态表、不替换 AgentMemory | `tests/test_research_task_adapter.py`：RED 3 failed（适配模块不存在）→ GREEN；与 `tests/test_durable_execution.py` 共 16 passed。 |
| C1-T02 | 绿色（通过） | 等待审批、暂停、恢复和取消命令均复用 C0 transition/revision/CAS；重复 command_id 幂等，过期 revision 被拒绝 | `tests/test_research_task_adapter.py`：RED 1 failed（命令方法不存在）→ GREEN；与 C0 回归共 17 passed。 |
| C1-T03 | 绿色（通过） | 研究检查点具 schema_version，仅含 task/run、DAG、依赖版本、制品/事实稳定 ID，拒绝不可 JSON 序列化对象 | `tests/test_research_task_adapter.py`：RED 1 failed（构造器不存在）→ GREEN；与 C0 回归共 18 passed。 |
| C1-T04 | 绿色（通过） | 研究步骤提交将版本化 checkpoint 与 invocation 委托 C0 `commit_step` 的同一事务；保留 C0 租约、revision/CAS 与晚到结果门禁，不新增任务表 | `tests/test_research_task_adapter.py`：RED 1 failed（提交方法不存在）→ GREEN；与 C0 回归共 19 passed。 |
| C1-T05 | 绿色（通过） | 研究任务仅以 `task_id` 在运行时关联既有 `AgentMemory` 实例，复用其原上下文生成，不改写工作记忆、会话持久化或数据库 | `tests/test_research_task_adapter.py`：RED 1 failed（关联方法不存在）→ GREEN；与 C0 和 AgentMemory 回归共 27 passed。 |
| C1-T06 | 绿色（通过） | 恢复只复用检查点依赖版本完全一致、且当前步骤幂等键对应成功调用的步骤；版本变化必须明确拒绝复用 | `tests/test_research_task_adapter.py`：RED 1 failed（恢复决策方法不存在）→ GREEN；与 C0 回归共 21 passed。 |
| C1-T07 | 绿色（通过） | 临时错误只在有限次数内允许重试；批准类错误等待审批，未知或输入错误失败；超时只标记尝试，仍由 C0 拒绝晚到结果 | `tests/test_research_task_adapter.py`：RED 1 failed（失败决策方法不存在）→ GREEN；与 C0 回归共 22 passed。 |
| C1-T08 | 绿色（通过） | 研究任务在 Planner 产出、编排启动、DAG 领取/提交和超时边界均委托 C0；超时不把运行或底层调用写为已停止 | `tests/test_research_task_adapter.py`：RED 1 failed（编排模块不存在）→ GREEN；与 C0 和 Planner 回归共 23 passed。 |
| C1-T09 | 绿色（通过） | 任务事件使用 C0 持久自增 ID，按保留期裁剪；显式数值游标早于最旧保留事件时返回重同步，不静默漏事件 | `tests/test_research_task_adapter.py`：RED 1 failed（事件流模块不存在）→ GREEN；与 C0 回归共 24 passed。 |
| C1-T10 | 绿色（通过） | 新研究任务事件流使用 fetch 和 `Authorization` 头；密钥不进入 URL，端点不进入 APIAuthMiddleware 免鉴权白名单 | 前端 `researchTaskStream.test.ts`：RED（模块不存在）→ GREEN 1 passed；后端鉴权回归 4 passed；前端生产构建通过。 |

> 编号勘误（2026-08-29）：本段原 M-T35～M-T39 五条 RED 与上方已完成条目编号重复，现重编为 M-T46～M-T50；已完成条目 M-T35～M-T39 含义不变。新增测试 ID 自 M-T51 起分配。

## C1. 可恢复研究任务产品化

| ID | 状态 | 测试目标 | 预期 RED 原因 |
|---|---|---|---|
| C-T01 | 🔴 RED | 合法任务状态迁移成功 | 状态机不存在 |
| C-T02 | 🔴 RED | 非法状态迁移被拒绝 | 状态守卫不存在 |
| C-T03 | 🔴 RED | 步骤结果与检查点原子提交 | Checkpoint Store 不存在 |
| C-T04 | 🔴 RED | 检查点写入失败时步骤不标记完成 | 事务边界不存在 |
| C-T05 | 🔴 RED | 幂等键对同输入稳定 | 幂等模块不存在 |
| C-T06 | 🔴 RED | 参数变化产生不同幂等键 | 规范化输入不存在 |
| C-T07 | 🔴 RED | 进程重启恢复最近有效步骤 | 恢复器不存在 |
| C-T08 | 🔴 RED | 已成功有副作用调用不重复 | 调用账本不存在 |
| C-T09 | 🔴 RED | 暂时性错误有限重试 | 错误分类和重试不存在 |
| C-T10 | 🔴 RED | 权限或校验错误不自动重试 | 重试策略不存在 |
| C-T11 | 🔴 RED | SSE 按事件 ID 补发 | 事件存储不存在 |
| C-T12 | 🔴 RED | 新任务层不改变 AgentMemory 既有会话行为 | 集成尚未实现 |
| C-T13 | 🔴 RED | 检查点拒绝任意不可序列化运行时对象 | schema 不存在 |
| C-T14 | 🔴 RED | 持久任务失败时不静默切换执行路径 | 新任务执行器不存在 |
| C-T15 | 🔴 RED | 旧即时问答 API 响应保持兼容 | 新集成尚未实现 |
| C-T16 | 🔴 RED | 持久任务流必须鉴权且不接受 URL 长期 API Key | 新流式端点不存在 |
| C-T17 | 🔴 RED | 事件游标早于保留窗口时要求快照重同步 | 事件保留策略不存在 |
| C-T18 | 绿色（通过） | 前端按 revision 忽略旧状态事件：乱序/重放旧 revision 或相同 revision 事件不回退状态且返回原引用；run_created 初始化 pending；resumed 标记仅在 paused→running 迁移为 true；window_end 与未知事件类型不参与状态合并；多任务状态隔离且 resetTask 可移除；状态标签覆盖七类状态中文展示与恢复提示 | `frontend/src/services/__tests__/researchTaskState.test.ts`、`frontend/src/stores/__tests__/researchTaskStore.test.ts`、`frontend/src/components/chat/__tests__/ResearchTaskStatusTag.test.tsx`：RED 3 个文件收集失败（`@/services/researchTaskState` 等模块不存在）→ GREEN 14 passed；`node node_modules/typescript/bin/tsc -b` 类型检查通过。实现记录见文末 2026-08-30 C2.8 段。 |
| C-T19 | 🔴 RED | 现有线程 timeout 不被误判为底层调用已取消 | 晚到结果隔离尚未接入编排器 |
| C-T20 | 🔴 RED | waiting_approval 依赖变化后不能沿用旧审批 | 审批版本绑定未集成 |
| C-T21 | 绿色（通过） | 六端点 API（创建/查询/事件流/暂停/恢复/取消）：控制命令携带 command_id/expected_revision，重复命令幂等回放，过期 revision 返回 409 与当前 revision，缺失任务 404，请求体校验 422；事件流输出 SSE 帧与 window_end 游标帧，游标早于保留窗口时返回 resync_required 帧而非静默跳过 | `tests/test_research_task_api.py`：RED 14 failed（`src.research_task_api` 不存在）→ GREEN 14 passed；定向回归（adapter/stream_auth/durable/api）39 passed。实现记录见文末 2026-08-30 C2.6 段。 |
| C-T22 | 绿色（通过） | 路由决策持久化与重试守卫：选定路径只追加且同路径幂等，异路径改道抛 RoutePathConflictError，未知路径 ValueError；失败记录保存 category/action/retry_count/max_retries 且选定路径不变；重试新建 `{task_id}-retry-N` 全新 run（原 run 保持 failed），新任务继承选定路径并写入 retry 决策（detail 含 new_task_id）；未记录路径或未 failed 拒绝重试 | `tests/test_research_task_route_persistence.py`：RED 7 failed（adapter 缺少 record_route_selection 等方法与 RoutePathConflictError）→ GREEN 7 passed；定向回归（adapter/metadata_store/durable/api/stream_auth/route_persistence）51 passed。实现记录见文末 2026-08-30 C2.7 段。 |
| C-T23 | 绿色（通过） | 五类故障演练：Worker 异常（重试型失败保持运行且失败只追加记录，重试耗尽迁移 failed、选定路径不变、晚到结果被丢弃、显式重试新建 retry-1 run 并继承路径、改道被拒）；进程中断（同一数据库重建执行环境后按依赖版本复用已完成步骤与成功调用、版本变化拒绝复用、重复有副作用调用被调用账本主键阻止）；并发控制命令（同一 revision 竞争只有一个 CAS 成功、败者收到当前 revision、胜者命令重放幂等且不追加事件）；超时晚到结果（attempt 记为 timed_out 而非取消、晚到提交 discarded 不写检查点与调用账本、新 attempt 接管后正常提交）；断线重连（游标之后只补发新事件不重复推送、游标早于保留窗口返回 resync_required） | `tests/test_research_task_fault_drills.py`：RED 3 failed（orchestrator 缺少 handle_step_failure/recover_interrupted_task；断线演练时间基准修正后 5 用例全绿）→ GREEN 5 passed；定向回归（adapter/drills/durable/api/route_persistence/stream_auth）51 passed，零回归。实现记录见文末 2026-08-30 C2.9 段。 |

## D. 安全、审计与成本治理

| ID | 状态 | 测试目标 | 预期 RED 原因 |
|---|---|---|---|
| D-T01 | 绿色（通过） | 只读与计算工具按策略自动执行 | `python -m pytest -q tests/test_governance_tool_policy.py`：GREEN 4 passed（无副作用自动放行、外部写/特权需审批、未注册默认拒绝、重复注册拒绝） |
| D-T02 | 绿色（通过） | 关键冲突裁决或正式报告签发无审批时阻止 | `python -m pytest -q tests/test_governance_approval.py`：RED 2 failed（AuditRecord 缺便捷属性）→ GREEN 14 passed 含参数化（missing 门禁） |
| D-T03 | 绿色（通过） | 审批参数变化后失效 | 同 approval 测试（params_changed 门禁语义） |
| D-T04 | 绿色（通过） | 检索文档中的指令不能触发工具越权 | `python -m pytest -q tests/test_governance_security.py`：GREEN 7 passed（结束标记转义、参数注入拒绝、保留控制键拒绝、干净参数放行） |
| D-T05 | 绿色（通过） | 上游 Agent 指令不能污染下游 | 同 security 测试（跨 Agent 纯文本载荷拒绝） |
| D-T06 | 绿色（通过） | 敏感字段在持久化前脱敏 | `python -m pytest -q tests/test_governance_redaction.py`：GREEN 4 passed（嵌套/列表脱敏、原结构不变、审计持久化边界脱敏） |
| D-T07 | 绿色（通过） | 审计事件可重建任务关键路径 | `python -m pytest -q tests/test_governance_audit.py`：GREEN 4 passed（回放重建、只追加、任务隔离、空 action 拒绝） |
| D-T08 | 绿色（通过） | 软预算产生预警 | `python -m pytest -q tests/test_governance_budget.py`：GREEN 4 passed（soft_warning 状态与成本快照） |
| D-T09 | 绿色（通过） | 硬预算暂停并保存检查点 | `python -m pytest tests/test_research_budget_pause.py tests/test_research_task_adapter.py tests/test_governance_budget.py -q --basetemp=C:/Users/111/AppData/Local/Temp/dt09green`：RED 模块不存在→GREEN 16 passed；C0 同一事务写检查点、释放租约、暂停运行并记录命令。 |
| D-T10 | 绿色（通过） | 路由记录质量、风险与成本理由 | `python -m pytest -q tests/test_governance_routing_rationale.py`：GREEN 3 passed（质量成本比、高复杂度/高风险质量优先、理由经审计持久化） |
| D-T11 | 绿色（通过） | task revision、事实/制品或索引代际变化使审批失效 | 同 approval 测试（dependencies_changed 门禁语义，参数化覆盖依赖变化） |
| D-T12 | 绿色（通过） | 状态迁移、审批消费和审计事件同事务提交 | 同 approval 测试（BEGIN IMMEDIATE 原子提交与业务失败全回滚断言） |

## E. 研究交付

| ID | 状态 | 测试目标 | 预期 RED 原因 |
|---|---|---|---|
| E-T01 | 绿色（通过） | 显式计划字段创建研究任务时生成并持久化计划和预算快照，创建响应与详情均可读取 | `python -m pytest tests/test_research_task_api.py tests/test_research_delivery_models.py tests/test_v7_metadata_store.py -q --basetemp=C:/Users/111/AppData/Local/Temp/et01green`：RED 1 failed（响应缺少 `plan`）→ GREEN 25 passed；迁移 27 的 `v7_research_plans` 只追加保存计划版本与 Decimal 预算文本。旧调用不提供完整计划字段时保持 C2.6 兼容。 |
| E-T10 | 绿色（通过） | ResearchPlan、Claim、ResearchReport 以稳定 ID、预算快照、声明依据与明确审核状态表达研究交付模型 | `python -m pytest tests/test_research_delivery_models.py -q --basetemp=C:/Users/111/AppData/Local/Temp/e11green2`：RED 收集失败（模块不存在）→ GREEN 4 passed；编译通过 |
| E-T11 | 绿色（通过） | 研究任务列表仅返回 `research:` 前缀的 C0 运行，并以稳定任务 ID 排序 | `python -m pytest tests/test_research_task_api.py -q --basetemp=C:/Users/111/AppData/Local/Temp/e12green`：RED 1 failed（GET `/api/research/tasks` 返回 405）→ GREEN 15 passed；与模型/适配层回归共 30 passed |
| E-T12 | 绿色（通过） | 研究任务页复用 PageShell、DAG、证据和图表组件；无持久 DAG/报告数据时明确展示空态 | `npm run test -- --run src/pages/__tests__/ResearchTasksPage.test.tsx src/pages/__tests__/DagBoardPage.test.tsx src/components/layout/__tests__/HeaderBar.test.tsx`：RED 0 test（页面不存在）→ GREEN 14 passed；`npm run build`、`npm run lint` 通过 |
| E-T14 | 绿色（通过） | 前端报告服务请求任务最新报告；任务详情展示报告版本和声明依据，报告缺失时保持明确空态 | 测试先行；当前 worktree 初次 RED 因无 `node_modules` 仅报 `vitest: command not found`，不伪造业务失败。临时复用原项目已安装依赖后，`npm run test -- --config vitest.worktree.config.mjs --configLoader native --run src/services/__tests__/apiClient.test.ts src/pages/__tests__/ResearchTasksPage.test.tsx`：GREEN 9 passed；`npm run build -- --configLoader native` 通过。 |
| E-T15 | 绿色（通过） | 创建报告必须绑定任务当前持久化计划，服务端生成连续版本、待审核状态和稳定报告 ID；缺任务或缺计划明确拒绝，输入无依据声明不得落库 | `python -m pytest tests/test_research_task_api.py::test_create_report_uses_persisted_plan_and_generates_immutable_versions tests/test_research_task_api.py::test_create_report_rejects_unknown_task_or_task_without_persisted_plan tests/test_research_task_api.py::test_create_report_rejects_claim_without_auditable_support -q --basetemp=C:/Users/111/AppData/Local/Temp/e15red`：RED 3 failed（POST 返回 405）→ `--basetemp=C:/Users/111/AppData/Local/Temp/e15green`：GREEN 3 passed；关联回归 28 passed。2026-09-12 补充 `pending` 状态断言：已有计划的任务可创建待审核草稿；任何 `completed` 门禁都必须由独立产品决策和 OpenSpec 变更引入。 |
| E-T16 | 绿色（通过） | 仅后端登记任务—冲突的事实、制品和索引版本上下文；审批服务从当前 run revision、完整计划哈希和该上下文生成绑定，缺上下文明确拒绝 | `python -m pytest tests/test_research_conflict_governance.py -q --basetemp=C:/Users/111/AppData/Local/Temp/e16red`：RED 3 failed（模块不存在）；补充过期审批 RED 为 1 failed（未拒绝）→ `--basetemp=C:/Users/111/AppData/Local/Temp/e16final`：GREEN 4 passed。2026-09-11 追加 RED：已审批 `step_inputs` 或 `step_bindings` 改变后哈希不变，旧审批可错误复用；GREEN：哈希纳入两类规范化字段，冲突治理/裁决 API 回归 13 passed。 |
| E-T17 | 绿色（通过） | 仅在部署方配置独立审批密钥与审批主体后可授予冲突审批；身份、过期时间和版本绑定由服务端生成，伪造的 `approver` 或绑定字段必须被请求 schema 拒绝 | `python -m pytest tests/test_research_conflict_approval_api.py -q --basetemp=C:/Users/111/AppData/Local/Temp/e17red`：RED 3 failed（端点返回 404）→ `--basetemp=C:/Users/111/AppData/Local/Temp/e17final`：GREEN 3 passed；关联冲突治理/裁决/审批/任务 API 回归完成，`compileall`、限定差异和 UTF-8 U+FFFD 扫描通过。 |
| E-T18 | 绿色（通过） | 任务仅能读取可信上下文关联的冲突和历史；批准/驳回在服务端重建当前绑定并消费匹配审批，保持未决不消费审批 | `tests/test_research_conflict_review_api.py`：RED 3 failed（端点 404）→ `--basetemp=C:/Users/111/AppData/Local/Temp/e18green`：GREEN 3 passed；关联回归 26 passed。 |
| E-T19 | 绿色（通过） | 研究任务页展示可信冲突与裁决历史，无冲突明确空态；浏览器不持有部署审批密钥 | 前端 RED 1 failed（冲突面板缺失）→ 工作区临时依赖配置下 GREEN `ResearchTasksPage` 5 passed；生产构建被共享依赖的 TypeScript 增量缓存写权限阻断，未伪称通过。 |
| E-T20 | 绿色（通过） | 首次部署按配置初始化管理员；合法凭据产生 HttpOnly 会话，当前身份仅返回角色与用户名，审批端点拒绝非 approver | `python -m pytest tests/test_research_identity_api.py tests/test_research_conflict_approval_api.py tests/test_research_conflict_review_api.py tests/test_research_conflict_governance.py tests/test_research_conflict_review.py -q --basetemp=C:/Users/111/AppData/Local/Temp/e20final`：GREEN 14 passed；初始 RED 2 failed（登录端点不存在）。 |
| E-T21 | 🟢 GREEN | 有效研究会话可通过全局 API 门禁，旧 Bearer API Key 继续兼容，无凭据仍拒绝，审批角色检查不放宽 | 独立 RED：从 `1428ef6` 只读基线副本运行 E-T21 测试探针，旧 `api_service` 缺少 `_research_session_is_valid`，得到 **1 failed**；当前实现 GREEN：`python -m pytest tests/test_research_session_auth.py tests/test_research_identity_api.py tests/test_artifact_endpoint_auth.py -q --basetemp=C:/Users/111/AppData/Local/Temp/e21-green-20260901` 得到 **6 passed**。此前“测试与实现同次加入、RED 遗漏”的记录已补正，不将当前 GREEN 倒推为 RED。 |
| E-T22 | 绿色（通过） | 页头仅通过 HttpOnly 会话调用登录、当前身份与登出 API；未登录有明确登录入口，登录后显示用户名和角色，登出后回到未登录态 | `frontend/src/services/__tests__/researchAuthService.test.ts` 与 `HeaderBar.test.tsx`：独立 RED 为认证服务模块不存在、页头缺登录入口（2 files failed，既有 9 passed）→ GREEN 13 passed；关联服务/任务页回归 23 passed。 |
| E-T23 | 绿色（通过） | 仅当前会话有 approver 角色时展示批准、驳回和保持未决按钮；批准/驳回必须先由服务端授予审批再提交裁决，普通用户无裁决入口 | `ResearchTasksPage.test.tsx`：独立 RED 2 failed（裁决服务与角色受控按钮不存在，既有 5 passed）→ GREEN 7 passed；与认证服务、页头和 apiClient 关联回归 25 passed。 |
| E-T23.1 | 🟢 GREEN | 驳回冲突不得选择事实；前端应以 `selected_fact_id=null` 请求并提交服务端审批 | RED：驳回沿用首个事实 ID，服务端返回 422，页面显示通用失败提示；GREEN：按动作区分参数，`ResearchTasksPage.test.tsx` 12 passed。 |
| E-T24 | 绿色（通过） | 正式报告签发先取得与当前报告、计划、任务版本绑定的 approver 审批；未裁决关键冲突必须被服务端拒绝，签发仅追加记录；同一报告不得被第二个有效审批重复签发 | 初始 `python -m pytest tests/test_research_report_signoff_api.py -q --basetemp=C:/Users/111/AppData/Local/Temp/e24red`：RED 2 failed（签发审批端点不存在）→ `--basetemp=C:/Users/111/AppData/Local/Temp/e24green`：GREEN 2 passed。续审新增重复签发用例：RED 为 `sqlite3.IntegrityError: UNIQUE constraint failed ... report_id`，GREEN 为 `python -m pytest -q tests/test_research_report_signoff_api.py tests/test_research_identity_api.py tests/test_research_session_auth.py tests/test_research_report_repository.py tests/test_research_task_api.py`：29 passed；已签发报告返回 409，未使用审批仍为 granted。 |
| E-T25 | 🟢 GREEN | 任务页仅向 approver 展示报告签发入口；先申请签发审批再签发，刷新从服务端只读签发记录显示状态，普通用户无入口 | RED：后端读取签发状态为 405、前端找不到“正式签发报告”；GREEN：后端 `tests/test_research_report_signoff_api.py` 2 passed，任务页 9 passed；关联后端 47 passed、前端 27 passed。 |
| E-T26 | 🟢 GREEN | 登录可由键盘提交，登录、冲突裁决与报告签发失败均有辅助技术可宣布的错误提示 | RED：键盘提交登录后无法找到 `role="alert"`；GREEN：登录失败改为 Ant `Alert`，页头 12 passed；报告签发原生按钮可由 Enter 触发且失败 `Alert` 可读取，任务页与页头 22 passed；前端关联回归 29 passed。冲突裁决既有失败路径已使用同一 Ant `Alert` 组件。 |
| E-T28.1 | 🟢 GREEN | 在研究任务页完成登录或登出后，页面无需刷新即可重新读取当前会话，正确显示或隐藏 approver 签发入口 | RED：`ResearchTasksPage` 新增用例派发登录完成事件后仍找不到“正式签发报告”；GREEN：认证服务导出统一事件名，页头登录/登出后派发事件，任务页监听后重读 `auth/me`，`npm run test -- --run src/pages/__tests__/ResearchTasksPage.test.tsx src/components/layout/__tests__/HeaderBar.test.tsx`：23 passed。 |
| E-T28.2 | 🟡 后续无障碍验收 | 真实屏幕阅读器应验证登录、冲突裁决和报告签发的朗读与错误宣布 | 用户于 2026-08-31 确认其不再阻塞当前发布。保留 E-T26 的自动化 `role="alert"`/键盘覆盖和已完成的真实 Tab/Enter 证据；当前环境未检测到可用读屏工具，不能标记为通过。 |
| E-T29 | 🟢 GREEN | 从回答级证据链定位来源时，来源卡片直接展开摘要、视觉定位和评分详情，避免评分字段仅存在于二次点击后的隐藏区域 | RED：`highlighted` 来源未展示“评分详情”及 `hybrid/rerank` 明细；GREEN：`SourceCard` 由定位状态初始化并自动展开，`SourceCard.test.tsx` 6 passed。 |
| E-T30 | 🟢 GREEN | 知识库文档的 `indexed` 布尔值与清单 `index_status` 一致；无清单时保持旧向量目录兼容 | RED：清单状态为 `indexed` 但文档 `indexed` 为 `False`；GREEN：清单状态优先、旧目录作为无清单回退，`test_pdf_hot_loading.py` 13 passed。 |
| E-T31 | 🟢 GREEN | 有效 researcher 会话创建任务后产生 submitted 记录；仅 approver 可批准并启动或驳回，重复/过期决策必须拒绝 | RED：匿名创建返回 200、审批端点为 404；GREEN：`test_research_task_submission_api.py` 2 passed，研究任务/冲突/签发关联回归共 28 passed。 |
| E-T32 | 🟢 GREEN | 研究任务页向研究员提供最小提交入口并显示 submitted/approved/rejected；审批人可批准执行或驳回 | RED：页面和服务不存在；GREEN：研究员提交范围/预算，审批人批准并执行的页面测试通过，`ResearchTasksPage.test.tsx` 13 passed；`npm run build`、`npm run lint` 通过。 |
| E-T33 | 🟢 GREEN | 批准后的最小执行器在外部计算前领取步骤租约，计算期间续租，异常时释放尝试并追加审计；依次完成 `plan → retrieve → review → report`，仅有来源证据时写入待审核报告，并在全部检查点成功后迁移为 completed；其他工作者持有有效步骤租约时不得调用外部查询或将任务误标为 failed | 初始 RED：`ResearchTaskExecutor` 模块不存在，2 failed；初始 GREEN：成功路径生成一条 `source` 依据声明并 completed，无来源路径 failed 且无报告，`test_research_task_execution.py` 2 passed。续审 RED：竞争租约下仍调用查询且任务被误迁移 `failed`；GREEN：执行前领取、长查询续租、异常释放与租约竞争 `tests/test_durable_execution.py tests/test_research_task_execution.py` 20 passed，任务保持 `running` 且无 failure 决策。 |
| E-T34 | 🟢 GREEN | API 启动时装配真实查询函数，批准后调度执行；查询或报告生成异常必须被审计并将任务转为 failed，禁止无产物长期停留 running | RED：测试装配调用 `configure_research_task_query` 时属性不存在；GREEN：审批路由以后台任务执行，测试读取 completed 与报告；正式 HTTP 创建 `manual-execution-e2e-20260901` 后 20 秒为 completed，报告 1 条且支持类型为 source。 |
| E-T35 | 🟢 GREEN | 任务详情公开只读执行进度：已完成步骤、当前步骤、终态完成时间与经脱敏的失败原因；页面据此展示 DAG 节点状态；运行中任务必须自动刷新并在终态停止刷新 | 初始 RED：执行摘要路由返回 404，页面没有“执行进度”；初始 GREEN：`GET /execution` 从 C0 检查点、终态更新时间和失败决策构造只读摘要，页面按摘要渲染 DAG。续审新增自动刷新用例 RED：运行中任务 5 秒后任务列表和执行摘要调用次数仍为 1；GREEN：加入 5 秒轮询，完成/失败/取消后停止，研究页 18 passed；研究前端定向集合 61 passed、lint/build 通过。 |
| E-T36 | 🟢 GREEN | 仅 approver 能以 CAS 处置无活动执行证据的遗留 `running` 任务；处置仅追加失败原因并迁移为 failed，存在 lease、checkpoint 或调用记录时拒绝 | `tests/test_research_task_legacy_disposition_api.py`：RED 2 failed（处置端点 404）→ GREEN 2 passed；处置在同一 `BEGIN IMMEDIATE` 事务检查执行证据、写入 C0 failed 命令/事件和只追加 failure 决策。 |
| E-T37 | 🟢 GREEN | 最终报告、最终步骤 checkpoint/调用记录、租约释放和 `completed` 迁移必须同一事务提交；报告写入失败时不得留下任一最终状态制品 | `tests/test_research_task_execution.py`：RED 模拟 `append_in_transaction` 失败时任务仍为 completed → GREEN 断言报告与 report checkpoint 均不存在、任务为 failed；研究任务/执行/C0 关联回归 53 passed。 |
| E-T38 | 🟢 GREEN | approver 只能以 CAS 从 failed 且有计划的历史任务创建 `-retry-N` pending 任务；原任务保持 failed，新任务复制计划并重新 submitted，重复 command_id 幂等 | `tests/test_research_task_legacy_disposition_api.py`：RED 1 failed（retry 端点 404）→ GREEN 4 passed；覆盖计划复制、原任务保持 failed、新任务 pending/submitted、重复 command_id 返回同一任务、过期 revision 和缺计划拒绝。 |
| E-T39 | 🟢 GREEN | 每个研究步骤绑定已注册 Agent 及允许工具；执行校验绑定，C0 调用账本保存 Agent、工具、状态和脱敏结果摘要，执行摘要/任务页可只读查看 | RED：`ResearchTaskExecutor` 不接受 `agent_registry`，3 项执行轨迹/绑定测试失败；GREEN：新增 `ResearchStepBinding`、schema 33 计划快照字段、执行器注册表校验和安全轨迹，`tests/test_research_task_trace.py` 8 passed（含受控 HTTP 提交→审批→执行→摘要链路）；研究任务 API/执行/遗留处置/重规划回归 48 passed；页面测试 15 passed，前端全量 52 文件/285 项通过，lint/build 通过。正式服务只读 HTTP 已读取旧无绑定任务与完成报告；正式库无已执行绑定任务，故正式绑定执行仍仅有受控 HTTP 证据。 |
| E-T40 | 🟢 GREEN | 绑定 `retrieve` 的研究步骤必须通过注入 `ToolRegistry` 实际调用，并在 C0 调用账本保存安全的工具调用摘要；旧无绑定计划继续使用通用查询函数 | RED：`ResearchTaskExecutor` 不接受 `tool_registry`，新测试构造失败；GREEN：绑定检索调用实际 `ToolRegistry.execute("retrieve")`，不回退通用查询，调用账本只保存工具名、状态及来源数量/回答存在性，正文和参数均不持久化；未装配工具注册表时任务失败且无报告。`test_research_task_trace.py` 与执行器回归 13 passed，关联研究任务回归 48 passed，后端全量 700 passed、1 skipped，前端全量 52 文件/285 项、lint/build 通过。 |
| E-T41.1 | 🟢 GREEN | 绑定 `DataAgent + retrieve` 且已注入 `LLMProvider` 的研究步骤必须实际运行 `DataAgent`，由其调用受控 `RetrieveTool`；C0 调用账本仅保存 Agent 名称、状态、步数、来源数量和回答存在性，不保存提示词、查询参数、来源正文或模型原始输出 | RED：执行器尚不接受 `llm_provider`，新测试构造失败；GREEN：以脚本化 Provider 驱动 DataAgent 的 `retrieve → Final Answer` 两步 ReAct，确认复用注入工具、通用查询函数未被调用，账本只保存脱敏 `worker_call` 和工具摘要。定向 `test_research_task_trace.py` 与执行器回归 14 passed。 |
| E-T41.2 | 🟢 GREEN | 绑定 `VerifyAgent + verify` 且已注入 `LLMProvider` 的 `review` 步骤必须实际运行 VerifyAgent；它仅可见 `verify` 工具，使用本次检索的声明和来源正文，且必须产生 `valid=True` 的结构化审核结论。C0 仅保存有效性、置信度、统计和 Worker 步数，不保存声明、来源正文、提示词或模型原始输出 | RED：任务 completed 但测试的 verify 工具调用为 0；GREEN：VerifyAgent 可按绑定仅注册 verify，执行器从真实 verify 工具观察结果解析并校验结构化结论，未调用/无结论/非 `valid=True` 时失败。脚本化 Provider 验证 DataAgent 两步 + VerifyAgent 两步、实际 verify 输入、脱敏账本，轨迹与执行器定向 15 passed。 |
| E-T41.3a | 🟢 GREEN | CalcAgent 必须只接受计划快照中经审批持久化的 calculator 结构化参数；缺失、未知字段或从 objective/来源正文推断参数均被拒绝，实际 Worker 只可调用 calculator | RED 1：实际 calculator 已调用但 calculate 步 C0 轨迹仅有通用 `planned_step_count`。RED 2：未知操作、缺失/额外字段、布尔数值均可进入计划。GREEN：步骤输入经 schema 34/Repository/API 保存，计划创建时按 operation 校验精确字段/有限数值，CalcAgent 只注册 calculator，执行器校验实际 `action_input` 与审批快照完全相等，C0 只保存 operation、结果存在性和步数。后端全量 707 passed、1 skipped。 |
| E-T41.3b | 🟢 GREEN | CompareAgent 必须只接受计划快照中经审批持久化的 compare 结构化参数；缺失、未知字段或从 objective/来源正文推断公司/指标均被拒绝，实际 Worker 只可调用 compare | RED：非法公司数、年份、top_n 和额外字段均可进入计划。GREEN：计划创建时校验精确 companies/metric/year/top_n，CompareAgent 仅注册 compare，实际 `action_input` 必须与快照相等；完整 `retrieve → compare → review → report` 任务确认 compare C0 仅保留 metric/结果存在性/步数，不保留公司或年份。关联 56 passed、后端全量 713 passed、1 skipped。 |
| E-T41.3c | 🟢 GREEN | ChartAgent 必须只接受计划快照中经审批持久化的 chart 结构化参数；缺失、未知字段或从 objective/来源正文推断图表数据均被拒绝，实际 Worker 只可调用 chart | RED：空数据、非法类型、非有限数值及额外字段均可进入计划。GREEN：计划创建时校验 data、`bar/line/pie/hbar` 和可选文本字段；ChartAgent 仅注册 chart，实际 `action_input` 必须与快照相等；完整 `retrieve → chart → review → report` 任务确认 chart C0 仅保留 chart_type/结果存在性/步数，不保留图表数据。关联 61 passed、后端全量 718 passed、1 skipped。 |
| E-T41.4 | 🟢 GREEN | 绑定 `PlanAgent + []` 的 `plan` 步必须实际运行无工具 Worker，仅确认已审批计划快照；模型不得生成、修改或替换计划，C0 不得保存目标、风险、提示词或模型原文 | RED：执行器无 `_plan`，PlanAgent 绑定任务失败（2 failed）。GREEN：新增无工具 PlanAgent，Worker 读取计划快照但其最终答案不参与计划变更；C0 仅保存 plan_version、scope_count、step_count、acknowledged 与总步数。完整 `plan → retrieve → review → report` 任务确认无目标/风险泄露；旧未绑定及历史 DataAgent plan 绑定保留直接提交兼容。关联 63 passed、后端全量 720 passed、1 skipped。 |
| E-T41.5 | 🟢 GREEN | 绑定 `ReportAgent + []` 的 `report` 步必须实际运行无工具 Worker，仅确认已审核、不可变报告草稿；模型不得新增或改写声明，C0 不得保存声明正文、来源、提示词或模型原文 | RED：report C0 仍含 report_id，缺少 Worker 确认摘要（1 failed）。GREEN：新增无工具 ReportAgent，先复用原有来源链构造报告，再仅向 Worker 提供草稿确认；模型输出不参与声明写入。完整任务确认 C0 只保存 report_version、claim_count、review_status、acknowledged 和总步数。关联 64 passed、后端全量 721 passed、1 skipped。 |
| E-T42 | 🟢 GREEN | 失败任务页只向 approver 展示“创建重试任务”入口；操作必须携带当前 revision 与新 command_id，并只创建新的 submitted 任务，不在浏览器伪造状态或改写原失败任务 | GREEN：页面调用既有 retry API，成功后仅选中新 pending 任务；测试确认 approver 请求携带原 revision，页面展示新 run。页面 16 passed，前端 build 通过。 |
| E-T43 | 🟢 GREEN | 遗留 `running` 任务页只向 approver 展示审计处置入口；必须提交原因、当前 revision 与新 command_id，并调用既有 legacy-disposition API，禁止浏览器直接删除、重启或改写记录 | GREEN：页面仅在 approver 查看 running 任务时显示原因输入与“标记为失败并保留审计”操作；测试确认调用服务端处置 API 并刷新任务摘要。页面 17 passed，前端 build 通过。此项为补充页面回归，未补造 RED 证据。 |
| E-T44 | 🟢 GREEN | 绑定 DataAgent 的 Worker 查询必须携带审批快照中的 objective 与完整 scope，避免研究范围仅持久化而未参与检索；旧未绑定路径保持兼容 | RED：新增 scope 契约断言发现 DataAgent 输入只有 objective（1 failed）。GREEN：新增 `_data_agent_query()`，将 objective 与规范化 scope 组合后传给 Worker；实际绑定 Worker 回归验证 scope 进入首条用户上下文，研究执行与轨迹相关测试 **24 passed**。 |
| E-T45 | 🟢 GREEN | 绑定 VerifyAgent 必须使用本次检索的完整进程内来源正文和执行器声明；回答级摘要保持兼容，Worker action input 不得替换审核输入，C0 只保留脱敏审核摘要；年报 HTML 表格的裸数字必须读取邻近金额单位上下文 | RED：来源只保留 200 字符且 Worker 可提交自带 `source_text`，完整来源契约测试 **1 failed**。GREEN：检索来源保留短摘要并附进程内 `verification_text`，执行器用受控工具适配器固定 canonical 声明/来源；新增 `test_verify_tool_table_context.py` 首次 **1 failed**，修复后通过；真实中国移动 2024 年报片段中“人民币百万元”与 `1,040,759` 可正确匹配 `10,408 亿元`。完整来源/单位/工具/研究执行关联回归 **43 passed**，后端全量 **724 passed、1 skipped、112 warnings**，未改变 C0 字段。隔离分支提交 `d0498b1`，仅包含本轮源码与测试。 |
| E-T46 | 🟢 GREEN | 人工创建待审核报告必须要求当前会话具有 `researcher` 角色；服务端继续确定报告 ID、版本和 `pending_review` 状态，暂不擅自增加 `completed` 状态限制 | RED：移除 `researcher` 角色后旧端点仍返回 200；GREEN：补充匿名访问 401 用例，研究任务 API、身份、报告、执行和 C0 关联回归 **104 passed**，确认匿名用户和角色不足用户均被拒绝且既有 pending 报告创建兼容用例保持通过。 |
| E-GATE-1 | 🟢 GREEN | 计划、审批、执行、审核与报告闭环在受控本地环境可回归 | 2026-09-12：研究后端集合 **117 passed**，覆盖提交、审批、执行、检查点、报告、签发及失败处置；不替代真实 Provider 或远端 CI。 |
| E-GATE-2 | 🟢 GREEN | 关键声明必须有事实、计算、来源或分析判断标识 | `test_research_delivery_models.py` 纳入 117 passed；无可审计依据的声明被拒绝。 |
| E-GATE-3 | 🟢 GREEN | 事实修订仅使依赖声明/报告失效 | `test_research_report_invalidation.py` 纳入 117 passed；失效传播保留声明级关联。 |
| E-GATE-4 | 🟢 GREEN | 根聊天和其他页面不因研究工作台引入而回归 | 前端路由、页头、研究页 a11y/交互与认证集合 **5 文件、40 passed**；根路由保持 ChatPage。真实读屏另行验收。 |
| E1.10-A11Y | 🟢 GREEN | 研究任务工作台必须暴露带名称的主地标、研究工作台区域和所有异步动作的稳定可读操作名；空态仍可被辅助技术读取 | RED：`ResearchTasksPage` 无带名称的 `main`，修复后加载态刷新按钮名称暴露为 `loading 刷新`；追加 RED：提交任务加载态名称暴露为 `loading 提交研究任务`；再追加 RED：审批、重试、遗留处置和报告签发加载态分别暴露为 `loading 批准并执行`、`loading 创建重试任务`、`loading 标记为失败并保留审计`、`loading 正式签发报告`。GREEN：为上述四个异步按钮增加稳定 `aria-label`，新增 a11y 契约共 **6 passed**；研究页/a11y/页头串行回归 **35 passed**，前端全量 **53 个文件/293 passed**。该契约不等同于真实屏幕阅读器验收。 |
| E1.10-PACKAGE | 🟢 GREEN | 完整研究交付闭包必须能在不含无关变更的独立 Git 副本中构建、回归并形成可审计提交 | 基于 `d0498b1` 的独立副本迁入 60 个明确归属文件；研究后端 **119 passed**、E-T21 认证/身份/artifact **6 passed**，前端研究集合 **7 个测试文件/49 passed**，lint/build/compileall/diff/乱码门禁通过；隔离分支 `codex/research-e110-isolated-20260901` 已形成可审计提交，最终提交 SHA 见交接文档。当前仓库因 `.git/FETCH_HEAD` 和 ref lock 无写权限，不能导入分支引用；真实屏幕阅读器验收仍未完成，因此 E1.10 聚合任务保持未勾选。 |
| A3.1/0.5 复核 | 🔴 RED | 干净依赖、真实基线与真实读屏前置 | 2026-09-13：隔离 Python 3.11 环境以 `requirements.lock` 完整安装后 `pip check` 为通过，`compileall` 与 CI 指定后端集合为 32 passed；隔离便携 Node 20.19.5 副本以 `npm ci` 完整安装，`npm run build` 通过，单一 Vitest 文件为 19 passed。完整 `npm test` 在 Windows 本机于 Vitest 启动后不输出任何用例结论，单 worker forks 全量运行亦未在合理时限完成，不能冒充 CI 通过；需修复该本机测试执行问题或取得 Linux CI 的完整结果。真实 v5.19 基线及最新候选真实读屏仍未完成；服务器隔离栈仍为 `5e17993`，早于本地候选，不能用于当前研究工作台验收。 |
| E-T02 | 绿色（通过） | 执行前修改范围时，只重算直接受影响步骤及其下游依赖步骤和预算；无关步骤成本保持不变，任务启动后拒绝调整 | `python -m pytest tests/test_research_plan_replanning.py tests/test_research_delivery_models.py tests/test_research_task_adapter.py tests/test_research_task_api.py -q --basetemp=C:/Users/111/AppData/Local/Temp/e14verify`：RED 收集失败（`ResearchPlanReplanner` 不存在）→ GREEN 34 passed；覆盖范围依赖、下游闭包、预算重算、pending 门禁与 DAG/预算一致性拒绝。 |
| E-T03 | 绿色（通过） | 未裁决关键冲突阻止正式报告签发 | E-T24：可信上下文冲突无裁决或最新裁决为保持未决时，签发返回 409，且不消费审批；已裁决状态才可继续检查签发审批。 |
| E-T04 | 绿色（通过） | 用户可查看原冲突的双方事实 ID，并批准、驳回或保持未决；批准/驳回仅在匹配的冲突审批有效时消费审批并追加裁决历史 | `python -m pytest tests/test_research_conflict_review.py tests/test_governance_approval.py tests/test_financial_fact_conflict_repository.py -q --basetemp=C:/Users/111/AppData/Local/Temp/e15verify`：RED 收集失败（模块不存在）→ GREEN 18 passed；同秒历史回放改按 SQLite 插入顺序，避免随机 ID 颠倒审计时间线。 |
| E-T05 | 🟢 GREEN | 关键声明关联事实、计算或分析标签 | 历史 RED 原因“报告模型不存在”已过期。`Claim.create` 拒绝无依据声明，并要求事实、计算、来源或明确分析标签；本轮隔离副本执行 `tests/test_research_delivery_models.py tests/test_research_report_export.py` 为 17 passed。 |
| E-T06 | 绿色（通过） | 事实修订只使依赖该事实的声明进入待复核，并创建可比较的新报告版本；无关声明保持原状态 | `python -m pytest tests/test_research_report_invalidation.py tests/test_research_delivery_models.py tests/test_research_report_export.py -q --basetemp=C:/Users/111/AppData/Local/Temp/e17green`：RED 收集失败（服务不存在）→ GREEN 7 passed。 |
| E-T07 | 绿色（通过） | Markdown/HTML 导出保留报告、计划、数据版本、声明 ID 及其事实、计算、来源或分析依据；HTML 必须转义不可信文本 | `python -m pytest tests/test_research_report_export.py tests/test_research_delivery_models.py -q --basetemp=C:/Users/111/AppData/Local/Temp/e16green`：RED 收集失败（导出器不存在）→ GREEN 6 passed。 |
| E-T08 | 🟢 GREEN | 新任务页复用现有主题与证据组件 | 历史 RED 原因“前端页面未实现”已过期。`ResearchTasksPage` 复用 `PageShell`、`DagFlow`、`EvidenceContent` 和 `ChartContainer`；本轮隔离副本研究页、可访问性与页头定向回归为 35 passed，生产构建通过。 |
| E-T09 | 🟢 GREEN | 旧聊天页与现有路由保持可用 | 新增 `frontend/src/__tests__/AppRoutes.test.tsx` 直接锁定根路由仍渲染 `ChatPage`，且仅 `/research` 渲染研究页；本轮 2 passed。研究页、可访问性、页头与路由合计 37 passed，生产构建通过。 |

## 全局回归

| ID | 状态 | 测试目标 | 预期 RED 原因 |
|---|---|---|---|
| G-T01 | 🔴 RED | 后端完整回归保持现有基线 | 尚未运行实施后回归 |
| G-T02 | 🔴 RED | 前端完整回归和生产构建通过 | 尚未运行实施后回归 |
| G-T03 | 🔴 RED | OpenSpec 文档、任务和 TDD 状态一致 | 尚未进入实施 |
| G-T04 | 🔴 RED | 中文 UTF-8 与乱码扫描通过 | 尚未进入实施 |
| G-T05 | 🔴 RED | 完整金融评测达到批准阈值 | 尚无 v7.0 结果 |
| G-T06 | 🔴 RED | GitHub 远端门禁与发布 SHA 可验证 | 尚未推送实施版本 |

## 每项转绿必须记录

- 首次 RED 命令与关键失败原因。
- 最小实现对应文件。
- GREEN 命令与通过数量。
- 是否执行相关回归。
- 提交 SHA。
- 如果修改阈值，记录原值、新值、依据和批准人。

## 2026-08-28 A 阶段首批实现记录

- 首次 RED：`python -m pytest tests/test_evaluation_quality_gate.py -q`，因 `src.evaluation` 不存在而收集失败。
- 最小实现：`src/evaluation/`、`evals/schema/case.schema.json`、`evals/datasets/core.jsonl`、`evals/fixtures/offline-core.json`。
- GREEN：同一命令 16 passed；`python -m compileall -q src/evaluation tests/test_evaluation_quality_gate.py` 通过。
- CLI 冒烟：`python -m src.evaluation.cli --dataset evals/datasets/core.jsonl --fixtures evals/fixtures/offline-core.json --output-dir .tmp/evaluation-smoke` 生成 JSON/Markdown 报告并通过种子门禁。
- 评测数据当前只有 1 条种子样本，A1.4/A1.5/A1.7 与 A 包退出条件尚未完成；不以种子结果代表 v5.19 全量质量。

## 2026-09-12 v5.19 配置基线指纹记录

- 首次 RED：`python -m pytest -q tests/test_v519_compatibility_manifest.py`，因 `evals/fixtures/v5.19-compatibility-manifest.json` 不存在而 **2 failed**。
- 最小实现：`evals/fixtures/v5.19-compatibility-manifest.json` 只保存 v5.19 提交、`.env.example` 与三份已跟踪配置的 Git blob 指纹；不复制可能含敏感值的配置正文。`tests/test_v519_compatibility_manifest.py` 校验标签、提交与 blob 一致，并拒绝将未跟踪索引数据或未导出 OpenAPI 标为已冻结。
- GREEN：同一命令 **2 passed**。这只完成 0.10 的配置指纹子集，不代表 v5.19 OpenAPI、关键 JSON、company_registry/metadata 或无 v7 数据库行为已完成基线冻结。

## 2026-09-12 v5.19 无 Key API 指纹记录

- 首次 RED：`python -m pytest -q tests/test_v519_compatibility_manifest.py`，因 `isolated_openapi_fingerprint` 和后续候选兼容记录缺失，分别出现 **1 failed**。
- 最小实现：从 `v5.19` Git archive 创建不含 `.git` 和 `data/v7` 的临时副本，清空 Provider/LangSmith 变量并禁用 tracing 后只导入应用、生成 OpenAPI 和调用无副作用端点；夹具记录 17 条路径、关键 JSON 指纹，以及源提交 `9e4f135` 的候选 39 路径与旧路径零缺失。
- GREEN：`python -m pytest -q tests/test_v519_compatibility_manifest.py tests/test_evaluation_quality_gate.py tests/test_financial_fact_compatibility.py` 为 **30 passed**；未启动服务、未调用 Provider、未使用生产数据或密钥。完整 OpenAPI 正文、认证成功响应、运行时索引数据和无 v7 数据库夹具继续保持未完成。

## 2026-09-12 v5.19 字段级 OpenAPI 兼容记录

- 首次 RED：`python -m pytest -q tests/test_v519_compatibility_manifest.py`，因 `field_level_openapi_compatibility` 缺失而 **1 failed**。
- 最小实现：比较 v5.19 与候选隔离 OpenAPI 的旧路径操作签名（方法、参数、请求体、内容类型、响应码和直接 JSON schema 引用），并比较 v5 已有组件 schema。只记录哈希、字段名和可选扩展，不保存完整 schema 或响应正文。
- GREEN：`python -m pytest -q tests/test_v519_compatibility_manifest.py tests/test_evaluation_quality_gate.py tests/test_financial_fact_compatibility.py` 为 **31 passed**；旧操作签名哈希相同，旧组件零缺失。认证成功响应、深层 schema 语义、运行时索引数据和无 v7 数据库夹具仍未完成。

## 2026-09-12 v5.19 无 Key 响应正文兼容记录

- 首次 RED：`python -m pytest -q tests/test_v519_compatibility_manifest.py`，因 `no_key_response_compatibility` 缺失而 **1 failed**。
- 最小实现：在无 Key、禁用 tracing 的 v5.19/候选临时 archive 中，对 14 个不触发写入、Provider 或真实数据访问的请求记录状态、顶层字段和正文哈希；仅 `vector_db_dir` 按路径占位规则脱敏，避免临时目录差异造成假回归。
- GREEN：`python -m pytest -q tests/test_v519_compatibility_manifest.py tests/test_evaluation_quality_gate.py tests/test_financial_fact_compatibility.py` 为 **32 passed**。认证成功响应、携带有效请求的业务端点、运行时索引数据和无 v7 数据库夹具仍未覆盖。

## 2026-09-12 流式端点历史鉴权债务记录

- 复用 v5.19 `p0_fixes_manual.py` 的错误 Bearer Key 输入，在无 Key、禁用 tracing 的 v5.19/候选隔离副本中验证：5 个普通受保护端点返回相同 401 正文；带有效 query 的 `/api/agent/stream` 无 Key 或错误 Key 均进入路由并返回 503，而不是中间件 401。
- 该行为与 v5.19 一致，候选当时没有引入回归；但它是 API Key 中间件未覆盖 SSE 路由的安全债务，不属于可接受的发布结论。
- 后续独立变更 `fix-agent-stream-authentication` 已移除 `/api/agent/stream` 静态白名单，`tests/test_agent_stream_auth.py` 验证无 Key/错误 Key 在下游前为 401，正确 Bearer Key 与有效研究会话仍透传。兼容清单将历史 503 指纹保留为 `remediated_security_exception`，不再声称此项与 v5.19 行为一致；相关定向回归 **36 passed**。完整 OpenAPI 正文、认证成功响应、未跟踪运行时索引数据和无 v7 数据库夹具仍待补齐。

## 2026-08-28 B2.5 声明级 EvidenceBundle 实现记录

- 首次 RED：`python -m pytest tests/test_evidence_bundle.py -q --basetemp=.tmp/pytest-b25`，5 failed，关键失败原因均为 `ModuleNotFoundError: No module named 'src.evidence_bundle'`。
- 最小实现：`src/evidence_bundle.py`（`EvidenceBundle` 不可变模型 + `EvidenceBundleRepository`）；`src/v7_metadata_store.py` 追加 migration 10（`v7_claims`、`v7_evidence_bundles`，claim 外键 `ON DELETE RESTRICT`）。
- GREEN：同一命令 5 passed；`python -m compileall -q src/evidence_bundle.py src/v7_metadata_store.py tests/test_evidence_bundle.py` 通过。
- 兼容性回归：`python -m pytest tests/test_v7_metadata_store.py tests/test_financial_fact_vertical_slice.py tests/test_financial_fact_registry_provider.py tests/test_financial_fact_registry_adapter.py tests/test_verified_financial_facts.py -q`：23 passed。
- B 包定向回归：14 个 B 阶段测试文件（含 `test_evidence_bundle.py`）共 55 passed，零回归。
- 兼容边界：证据包仅新增可选 `to_response()` 载荷；既有比较响应与旧来源字段未改动，由 `test_existing_comparison_response_stays_unchanged_when_bundle_created` 固定。
- 环境说明：pytest 默认临时目录 `C:\Users\111\AppData\Local\Temp\pytest-of-111` 出现 Windows 权限错误（WinError 5），本轮起统一使用 `--basetemp=.tmp/pytest-*` 项目内目录。
- 提交 SHA：未提交；工作区存在大量未提交改动，等待用户明确授权后统一提交。

## 2026-08-30 C2.6 研究任务六端点 API 实现记录（C-T21）

- 首次 RED：`python -m pytest tests/test_research_task_api.py -q --basetemp=.tmp/pytest-red-c26`，14 failed，关键失败原因均为 `ModuleNotFoundError: No module named 'src.research_task_api'`（或 ImportError）。
- 最小实现：`src/research_task_api.py`（APIRouter 六端点 + `configure_research_task_store` 注入口 + C0 异常到 HTTP 语义映射：KeyError→404、RevisionConflictError→409 带 current_revision、InvalidRunTransitionError→409、sqlite3.IntegrityError（重复创建）→409、负游标/非法保留期→422）；`src/api_service.py` 在图表静态挂载后 `app.include_router`，事件流端点不加免鉴权白名单（由既有 C-T16 回归钉住）。
- SSE 契约：逐事件 `data:` 帧（event_id/event_type/revision + payload 展开）+ 终帧 `window_end`（next_event_id/oldest_event_id/resync_required）；游标早于保留窗口时只发 `resync_required=true` 的 window_end 帧，不静默漏事件，与 C2.4 重同步语义一致。
- GREEN：同一命令 14 passed。
- 回归：`python -m pytest tests/test_research_task_adapter.py tests/test_research_task_stream_auth.py tests/test_durable_execution.py tests/test_research_task_api.py -q --basetemp=.tmp/pytest-reg-c26` 共 39 passed，零回归；旧即时问答 API 零改动（未触碰既有路由与响应模型，C-T15 兼容回归在 C2.10 全量回归时验证）。
- 提交 SHA：6a87782（feat(tasks): productize durable research execution）。

## 2026-08-30 C2.7 路由决策持久化与重试守卫实现记录（C-T22）

- 设计依据：design.md C0/C1 段“持久任务一旦选择 single 或 multi 路径，失败时不得静默切换路径，必须保存失败并由显式重试或重新规划处理”；C0 状态机 failed 为终态（ALLOWED_TRANSITIONS 空集合），因此重试不回迁状态，而是新建 `{task_id}-retry-N` 任务与 `research:{task_id}-retry-N` run，路径决策只追加。
- 首次 RED：`python -m pytest tests/test_research_task_route_persistence.py -q --basetemp=.tmp/pytest-red-c27`，7 failed，失败原因均为 adapter 缺少 `record_route_selection`/`route_selection`/`route_decisions`/`record_failure`/`retry_task` 方法与 `RoutePathConflictError` 异常。
- 最小实现：
  - `src/v7_metadata_store.py` 新增 migration 23：只追加表 `v7_task_route_decisions`（decision_type CHECK 限定 selected/failure/retry，selected_path CHECK 限定 single/multi）+ 索引 `idx_v7_route_decisions_task(task_id, decision_id)`，禁止覆盖历史。
  - `src/research_task_adapter.py` 新增 `RoutePathConflictError`、`RouteDecision` 只读数据类与五个方法：`record_route_selection`（同路径幂等返回既有记录、异路径抛冲突、未知路径 ValueError）、`route_selection`（读最近 selected 决策，未记录抛 ValueError）、`route_decisions`（按 decision_id 升序全量返回）、`record_failure`（写入 category/action/retry_count/max_retries，不动选定路径）、`retry_task`（先校验路径一致与 run 为 failed，再新建 retry run、继承选定路径、写 retry 决策 detail 含 new_task_id/command_id）。
  - 重试编号按原始基线推导：剥离 `-retry-N` 后缀得到 base，扫描 base 系列全部 retry 决策取最大编号 +1，重试链沿 `base-retry-N` 连续编号。
- GREEN：同一命令 7 passed。
- 回归：`python -m pytest tests/test_research_task_adapter.py tests/test_v7_metadata_store.py tests/test_durable_execution.py tests/test_research_task_api.py tests/test_research_task_stream_auth.py tests/test_research_task_route_persistence.py -q --basetemp=.tmp/pytest-reg-c27` 共 51 passed，零回归（含 migration 23 迁移与 schema_version 动态断言）。
- 提交 SHA：未提交；按计划在 C2.10 统一提交 `feat(tasks): productize durable research execution` 后回填。

## 2026-08-30 C2.8 前端按 revision 合并事件实现记录（C-T18）

- 设计依据：design.md C-T18 语义——事件乱序、重放或重连补发时，只有严格更新的 revision 才应用，旧事件不得回退前端状态；`resumed` 标记仅由 paused→running 迁移产生；`window_end` 游标帧与未知事件类型不参与状态合并。
- 首次 RED：`npm run test -- --run src/services/__tests__/researchTaskState.test.ts src/stores/__tests__/researchTaskStore.test.ts src/components/chat/__tests__/ResearchTaskStatusTag.test.tsx`，3 个文件收集失败，失败原因为 `@/services/researchTaskState`、`@/stores/researchTaskStore`、`@/components/chat/ResearchTaskStatusTag` 模块不存在。
- 最小实现：
  - `frontend/src/services/researchTaskState.ts`：纯合并逻辑——`ResearchTaskStatus` 七类状态类型、`createResearchTaskState`（初始 unknown/revision -1）、`applyResearchTaskEvent`（run_created 初始化 pending；run_transitioned 仅在 revision 严格更新时应用并计算 resumed；旧 revision/同 revision 重放返回原状态引用；window_end 与未知事件忽略）。
  - `frontend/src/stores/researchTaskStore.ts`：Zustand store 按任务 ID 隔离状态，`applyEvent` 委托纯合并函数，状态引用不变时不触发渲染；`resetTask` 移除指定任务。
  - `frontend/src/components/chat/ResearchTaskStatusTag.tsx`：订阅 store 展示七类状态中文标签（等待开始/运行中/等待审批/已暂停/失败/已取消/已完成，unknown 显示未开始），resumed 时追加“已恢复”标签；未知任务显示“未开始”。
- GREEN：同一命令 14 passed（7 + 4 + 3）。
- 类型检查：`node node_modules/typescript/bin/tsc -b` 通过（exit 0）。
- 说明：npx 直调会被沙箱拦截 npm cache 日志写入，类型检查统一使用项目内本地 TypeScript 二进制。
- 提交 SHA：未提交；按计划在 C2.10 统一提交 `feat(tasks): productize durable research execution` 后回填。

## 2026-08-30 C2.9 五类故障演练实现记录（C-T23）

- 设计依据：design.md C1-GATE-1 要求五类故障演练全部达到预期状态——Worker 异常（failure_decision 分类 + record_failure 只追加 + retry 不迁移状态/failed 迁移终态/waiting_approval 迁移等待审批）、进程中断（同一 SQLite 重建执行环境后 recovery_decision 按依赖版本与幂等键复用，重复有副作用调用被 `v7_execution_invocations.idempotency_key TEXT PRIMARY KEY` 唯一约束拒绝）、并发控制命令（同 revision CAS 竞争唯一胜者 + command_id 重放幂等不追加事件）、超时晚到结果（timed_out 不写检查点与调用账本，新 attempt 接管后正常提交且原 attempt 保持 timed_out）、断线重连（游标之后只补发新事件，游标早于保留窗口时 resync_required）。
- 首次 RED：`python -m pytest tests/test_research_task_fault_drills.py -q --basetemp=.tmp/pytest-red-c29`，3 failed——orchestrator 缺少 `handle_step_failure` 与 `recover_interrupted_task`（预期失败）；另断线演练首跑 `cursor is None`：事件真实 created_at（2026）早于演练假定读取时间（2030）减保留期 3600 秒，保留窗口裁剪全部事件，需在读取前 `UPDATE v7_task_events SET created_at` 归一化到演练时钟附近。
- 最小实现：
  - `tests/test_research_task_fault_drills.py`（新建，5 用例）：`_harness(tmp_path)` 构造 DurableExecutionStore + ResearchTaskAdapter + ResearchTaskOrchestrator；五演练分别覆盖 Worker 异常晚到门禁与改道冲突、进程中断复用与重复副作用拒绝、并发 CAS 与幂等重放、超时晚到隔离与新 attempt 接管、断线重连补发与 resync 标记；`RoutePathConflictError` 从 `src.research_task_adapter` 模块级导入。
  - `src/research_task_orchestrator.py`（新增两方法，保留既有方法未动）：`handle_step_failure` 先 `failure_decision` 分类再 `record_failure` 只追加持久化，随后按动作分支——retry 返回当前快照（任务保持 running 等待重新领取步骤）、failed 走 `fail_task` CAS 终态、waiting_approval 走 `wait_for_approval`；`recover_interrupted_task` 委托 `recovery_decision` 推导可复用步骤与成功调用。
- GREEN：`python -m pytest tests/test_research_task_fault_drills.py -q --basetemp=.tmp/pytest-green-c29b`，5 passed（首跑曾 2 failed，均为测试自身问题：`RoutePathConflictError` 误作 adapter 类属性、恢复断言应为两步均完成可复用 `("analyze", "fetch")`，已修正）。
- 定向回归：`python -m pytest tests/test_research_task_adapter.py tests/test_research_task_fault_drills.py tests/test_durable_execution.py tests/test_research_task_api.py tests/test_research_task_route_persistence.py tests/test_research_task_stream_auth.py -q --basetemp=.tmp/pytest-reg-c29`，51 passed 零回归。
- 提交 SHA：6a87782（feat(tasks): productize durable research execution）。

## 2026-08-30 D 包治理模块实现记录（D-T01~D-T12）

- 设计依据：design.md D 段——五级工具风险（read_only/compute/external_read/external_write/privileged），有副作用才审批；审批绑定 task_revision/plan_hash/fact_version/artifact_version/index_generation 五维度与参数哈希，expires_at 时效，消费后不可复用；审计账本只追加；同事务原子性避免"已执行但无审计"或"已审计但未执行"；持久化前脱敏；提示词注入隔离；用量度量与预算控制；路由质量—成本比决策留痕。
- 首次 RED：`python -m pytest tests/test_governance_tool_policy.py tests/test_governance_audit.py tests/test_governance_approval.py tests/test_governance_redaction.py tests/test_governance_security.py tests/test_governance_metrics.py tests/test_governance_budget.py tests/test_governance_routing_rationale.py -q --basetemp=C:/Users/111/AppData/Local/Temp/pytest-dred`，首批 13 failed（src/governance 模块不存在，预期失败）。
- 最小实现（src/governance/ 九个模块 + src/v7_metadata_store.py 迁移 24/25）：
  - `tool_policy.py`（D1.1）：五级 ToolRisk；ToolPolicyEngine 注册/校验，未注册默认拒绝，重复注册拒绝；无副作用（read_only/compute/external_read）自动放行，external_write/privileged 返回 required_approval。
  - `audit.py`（D1.4）：GovernanceAuditStore 只追加事件（迁移 24 v7_governance_audit_events），append/replay_by_task；AuditRecord 提供 event 与便捷属性双访问；_insert 持久化前经 redact_sensitive_fields 脱敏 detail，原始事件对象不变。
  - `approval.py`（D1.2/D1.2.1/D1.3/D1.4.1）：ApprovalBinding 五维度结构化绑定；digest = SHA-256(canonical[subject, subject_id, params_hash, binding_json])；check_gate 依次判 missing/params_changed/expired/dependencies_changed；consume_in_transaction 以 BEGIN IMMEDIATE 将审批消费、审计事件与 business_transition 放入同一事务，异常全回滚；三类 subject（冲突裁决/报告签发/工具执行）。
  - `redaction.py`（D1.5）：键名规范化（小写、连字符转下划线）后子串匹配敏感标记；递归处理 dict/list/tuple 返回新结构，REDACTED_VALUE = "[REDACTED]"。
  - `security.py`（D1.6）：不可信内容隔离块标记 + 结束标记转义（<<<ESCAPED_END_UNTRUSTED>>>）；validate_tool_params 顶层键白名单 + 递归保留控制键拒绝（system/system_prompt/instructions/developer/role/messages）；ensure_structured_payload 跨 Agent 仅接受 dict/list。
  - `metrics.py`（D1.7）：UsageTracker 按任务/模型累计调用次数、token、延迟与成本估算，task_summary/model_breakdown 只读聚合。
  - `budget.py`（D1.8）：BudgetPolicy(soft_cost, hard_cost) 两级阈值；evaluate 返回 ok/soft_warning，超硬预算抛 BudgetExceededError 携带成本快照与硬预算。
  - `routing_rationale.py`（D1.9）：compare_routes 高复杂度/高风险质量优先，其余按 quality/cost 比值；save_routing_rationale 经审计账本持久化 route_selected 事件（含 chosen_path/reason/complexity/risk/alternatives）。
  - 迁移 24（审计事件表）与 25（审批表）以部分暂存方式进入本提交（工作区 B2.5 未授权迁移 12-22 不混入）。
- GREEN：同命令 `--basetemp=C:/Users/111/AppData/Local/Temp/pytest-dfinal`，43 passed。两轮修复：D1.2 首轮 2 failed（审批测试直接访问 record.action 而 AuditRecord 无该属性，补充便捷属性委托 event）；D1.5-D1.9 首轮 2 failed（UsageTracker.task_summary 误调用 self._aggregate，改为模块级 _Aggregate 类）。
- 全量回归：`python -m pytest tests/ -q --basetemp=C:/Users/111/AppData/Local/Temp/pytest-d1verify`，641 passed + 1 skipped；首轮 19 failed 全部为 pymupdf 无法写中文路径临时目录的环境问题（FzErrorSystem: cannot open file），改用 ASCII basetemp 后视觉模块 29 passed 全绿，非 D 包改动导致。
- 遗留：D-T09 的"超预算暂停并保存检查点"需 E 包任务状态机接入 BudgetExceededError 后才能转绿；审批门禁与冲突裁决/报告签发的实际编排接入在 E 包完成。
- 提交 SHA：1428ef6（feat(governance): add agent policy audit and budgets）。
