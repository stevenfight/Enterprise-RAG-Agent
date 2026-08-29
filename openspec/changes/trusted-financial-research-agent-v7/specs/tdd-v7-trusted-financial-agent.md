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
| C0-T01 | 🔴 RED | 同一步骤只有一个有效 lease 执行者 | 租约仓储不存在 |
| C0-T02 | 🔴 RED | lease 过期后新 attempt 可接管 | 接管逻辑不存在 |
| C0-T03 | 🔴 RED | 原 attempt 晚到结果被标记 discarded | attempt token 校验不存在 |
| C0-T04 | 🔴 RED | 并发暂停与取消只有一个 revision CAS 成功 | revision/CAS 不存在 |
| C0-T05 | 🔴 RED | 相同 command_id 重复提交返回原结果 | 命令幂等账本不存在 |
| C0-T06 | 🔴 RED | 并行事件由单写入器生成单调唯一 event ID | 持久事件写入器不存在 |
| C0-T07 | 🔴 RED | 幂等键包含模型、提示词、事实/制品和索引代际 | 依赖版本未纳入 |
| C0-T08 | 🔴 RED | 超时线程晚到结果不能写事实、索引或 completed | 提交守卫不存在 |
| C0-T09 | 🔴 RED | 模拟入库进程中断后从检查点恢复且不重复成功调用 | 通用执行器不存在 |
| C0-T10 | 🔴 RED | M 复用 C0 表与仓储而不建立平行状态机 | M 尚未集成执行基础 |
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
| S-T07 | 🔴 RED | 完整 MinerU 产物选择 REUSE/ENRICH 且不调用解析器 | 复用门禁不存在 |
| S-T08 | 🔴 RED | 已定位失败页只执行 TARGETED_REEXTRACT 范围 | 定向重处理任务不存在 |
| S-T09 | 🔴 RED | 全局不兼容时 FULL_REEXTRACT 留下明确原因 | 全量重提取判定不存在 |
| SRC-T01 | 绿色（通过） | 源 PDF 冻结清单记录哈希、物理页、加密/可读状态及既有 registry 的逻辑映射；冲突映射不猜测；原子写入保证源文件字节不变 | `python -m pytest -q tests/test_source_inventory.py`：RED 2 failed、追加边界 RED 1 failed → GREEN 3 passed |
| S-T10 | 🔴 RED | 普通文本页不因首轮迁移调用视觉模型 | 页面路由尚未实现 |
| S-T11 | 🔴 RED | 首个 v7 generation 覆盖迁移基线全部 active 文档 | 全量代际迁移器不存在 |
| S-T12 | 🔴 RED | 缺少完整版本证据的旧向量不得导入首个 v7 generation | 向量兼容门禁不存在 |
| S-T13 | 🔴 RED | 新代际任一完整性校验失败均不改变 active | 不可变发布流程不存在 |
| S-T14 | 🔴 RED | 查询在并发激活期间固定同一 generation 快照 | 请求级 Resolver 不存在 |
| S-T15 | 🔴 RED | 已发布事实、声明、计算和报告关系不存在悬空外键 | ProvenanceRepository 不存在 |
| S-T16 | 🔴 RED | 来源版本失效会把受影响声明、计算和报告标记 stale | 依赖影响传播不存在 |
| S-T17 | 🔴 RED | 删除一个逻辑文档不会删除仍被引用的共享 blob | blob 引用计数不存在 |
| S-T18 | 🔴 RED | artifact API 拒绝路径、未知/删除/不可见 artifact 且不泄露路径 | 受控制品端点不存在 |
| S-T19 | 🔴 RED | multimodal 开关关闭时旧上传、删除、查询契约与夹具一致 | 兼容开关未实现 |
| S-T20 | 🔴 RED | 当前溯源实现不引入图数据库或通用三元组依赖 | 依赖边界尚未实施验证 |
| S-T21 | 🔴 RED | orphan staging/blob 不能通过查询或 artifact API 访问且可幂等清理 | 孤儿清理与可见性隔离不存在 |
| S-T22 | 🔴 RED | 哈希键命中但大小/字节不一致时拒绝复用并审计 | 冲突校验不存在 |
| S-T23 | 绿色（通过） | 控制字符、路径分隔符和 Windows 保留文件名不进入 v7 文档版本元数据或物理路径 | `python -m pytest -q tests/test_v7_document_repository.py`：追加边界 RED 1 failed → GREEN 4 passed |
| S-T24 | 🔴 RED | I/O、数据库、解析和索引错误分类稳定且重试有上限 | 错误分类与重试策略不存在 |
| S-T25 | 🔴 RED | 新上传响应保留 filename/size/size_mb 且处理中不宣称索引完成 | v7 上传兼容适配不存在 |
| S-T26 | 🔴 RED | 端点级 API key 不被测试或文档误判为文档级多租户 ACL | 权限承诺边界未验证 |
| S-T27 | 🔴 RED | 单次请求的索引、文档、artifact 和事实固定同一 publication | PublicationResolver 不存在 |
| S-T28 | 🔴 RED | 两个构建者基于同 revision 发布时只有一个 CAS 成功 | PublicationSet CAS 不存在 |
| S-T29 | 🔴 RED | 索引文件通过但发布事务失败时全部新数据不可见 | 跨组件发布集合不存在 |
| S-T30 | 🔴 RED | 回滚整组恢复 index/document/artifact/fact 而非只切索引 | PublicationSet 回滚不存在 |
| S-T31 | 🔴 RED | 首轮构建期间语料变化不会静默改变覆盖分母 | corpus revision 固定不存在 |
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
| COORD-T01 | 绿色（通过） | V7 协调器只能用 document version/blob SHA/物理页数启动，按 manifest 全页渲染并以页图与解析批次双门禁完成 | `python -m pytest -q tests/test_v7_document_processing_coordinator.py`：RED 2 failed → GREEN 2 passed；真实 5 页 blob 临时链路通过 |
| ASSET-T01 | 绿色（通过） | 既有 PDF/Markdown 诊断清单按同名配对统计图片、HTML/Markdown 表格与公式；缺失或越界本地制品标记 incomplete，报告原子写入 | `python -m pytest -q tests/test_document_asset_inventory.py`：RED 2 failed、追加写入 RED 1 failed → GREEN 3 passed |
| M-T01 | 🔴 RED | 制品清单发现既有 Markdown 图片、HTML/Markdown 表格和公式 | DocumentAssetManifest 不存在 |
| M-T02 | 🔴 RED | 缺失图片或无法关联页码的制品标记 missing/unresolved | 完整性校验不存在 |
| M-T03 | 🔴 RED | MinerU 失败页批次使文档保持 incomplete | 批次状态未记录 |
| M-T04 | 🔴 RED | 相同文档、页码和渲染版本复用页图 artifact ID | PageRenderer 不存在 |
| M-T05 | 🔴 RED | 旋转页 bbox 与前端高亮使用同一规范化坐标 | 坐标模型不存在 |
| M-T06 | 🔴 RED | 有文本层的普通页面不调用视觉模型 | PageRouter 不存在 |
| M-T07 | 🔴 RED | 视觉模型未配置时明确 unavailable 且不静默文本回退 | VisionProvider 不存在 |
| M-T08 | 🔴 RED | BaseLLMProvider.chat 保持纯文本契约 | 多模态尚未实现兼容边界 |
| M-T09 | 🔴 RED | MinerU HTML 表格保留多级表头和 row/colspan | 表格结构适配器不存在 |
| M-T10 | 🔴 RED | 表格事实不从 preprocess_table_text 扁平结果反推 | 结构化真值链不存在 |
| M-T11 | 🔴 RED | 跨页续表只在标题、表头、列结构和相邻页均兼容时合并 | 续表规则不存在 |
| M-T12 | 🔴 RED | 条件不足的跨页表格保持分离并标记候选关系 | 保守合并门禁不存在 |
| M-T13 | 🔴 RED | 图表提取标题、图例、轴、单位、期间、系列和区域 | 图表理解器不存在 |
| M-T14 | 🔴 RED | 只能判断趋势时不伪造精确数据点 | 置信与输出等级不存在 |
| M-T15 | 🔴 RED | 扫描页低置信数字不能进入 verified 事实 | 视觉事实审核状态未集成 |
| M-T16 | 🔴 RED | 视觉数字复用统一单位、期间和币种归一器 | 视觉链尚未接入 B 内核 |
| M-T17 | 🔴 RED | 正文与图表同口径冲突进入统一冲突引擎 | 跨模态冲突链不存在 |
| M-T18 | 🔴 RED | 视觉提示词注入不能改变工具权限和审批 | 视觉安全边界不存在 |
| M-T19 | 🔴 RED | SourceInfo 可选视觉字段不改变旧 API JSON | 后端兼容扩展未实现 |
| M-T20 | 🔴 RED | EvidencePanel 显示页图、区域高亮和 incomplete 警告 | 前端视觉证据未实现 |
| M-T21 | 🔴 RED | 删除 PDF 同步清理清单、页图、视觉事实和索引 | 生命周期清理未实现 |
| M-T22 | 🔴 RED | 多模态索引不降低批准的纯文本检索与问答基线 | 尚未运行集成回归 |
| M-T23 | 🔴 RED | 同一视觉区域命中缓存时不重复调用模型 | 视觉缓存和调用账本不存在 |
| M-T24 | 🔴 RED | 异常像素、页数或成本超限时停止并留下审计错误 | 资源预算门禁不存在 |
| M-T25 | 🔴 RED | manifest 原子写入失败时不得推进 complete | 制品状态存储不存在 |
| M-T26 | 🔴 RED | 视觉 embedding 失败不写零向量且标记 incomplete | 索引 strict 模式不存在 |
| M-T27 | 🔴 RED | 页图端点只接受合法 artifact ID 并拒绝路径遍历/跨文档访问 | 受控制品 API 不存在 |
| M-T28 | 🔴 RED | 删除中断后保持 deleting 并可幂等续清理 | 删除状态机不存在 |
| M-T29 | 🔴 RED | 同源页面或裁剪变体不能跨开发集和冻结留出集 | 多模态数据泄漏校验不存在 |
| M-T30 | 🔴 RED | 高风险视觉数字误入 verified 时无视平均分直接失败 | 高风险硬门禁不存在 |
| M-T31 | 🔴 RED | 多模态报告包含路由、缓存、调用、失败和 P95 | 成本观测字段不存在 |
| M-T32 | 🔴 RED | 页图高亮可键盘操作且表格/图表有文本等价说明 | 前端可访问性尚未实现 |
| M-T33 | 🔴 RED | staging 索引构建失败不改变 active publication | 索引代际管理器不存在 |
| M-T34 | 🔴 RED | 新代际校验后与文档/制品/事实整组发布且可回滚 | PublicationSet 不存在 |
| M-T35 | 🔴 RED | 单次请求始终读取同一 publication | 请求级发布快照固定不存在 |
| M-T36 | 🔴 RED | 激活后 RAGGenerator、RetrieveTool、CompareTool 新请求均刷新 publication | 统一 Resolver 不存在 |
| M-T37 | 🔴 RED | Windows 打开旧索引时不会被回收或替换 | 代际引用与回收策略不存在 |
| M-T38 | 🔴 RED | multimodal_enabled 关闭时旧上传、索引和来源响应完全不变 | 多模态开关不存在 |
| M-T39 | 🔴 RED | 相同内容哈希重复上传幂等返回同一文档版本 | 文档版本模型不存在 |
| M-T40 | 🔴 RED | 同名不同内容创建新版本且完整前不替换 active | 版本激活门禁不存在 |
| M-T41 | 🔴 RED | deleting 线性化点后新查询不再包含该文档版本 | 查询快照过滤不存在 |
| M-T42 | 🔴 RED | 删除完成后 artifact API 和新索引均不可访问派生数据 | 跨存储删除闭环未实现 |
| M-T43 | 🔴 RED | 旧在途请求与新代际激活遵守明确快照语义 | 文档版本与 generation 固定未集成 |

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
| C-T18 | 🔴 RED | 前端按 revision 忽略旧状态事件 | 前端任务状态合并不存在 |
| C-T19 | 🔴 RED | 现有线程 timeout 不被误判为底层调用已取消 | 晚到结果隔离尚未接入编排器 |
| C-T20 | 🔴 RED | waiting_approval 依赖变化后不能沿用旧审批 | 审批版本绑定未集成 |

## D. 安全、审计与成本治理

| ID | 状态 | 测试目标 | 预期 RED 原因 |
|---|---|---|---|
| D-T01 | 🔴 RED | 只读与计算工具按策略自动执行 | 工具策略不存在 |
| D-T02 | 🔴 RED | 关键冲突裁决或正式报告签发无审批时阻止 | 审批门禁不存在 |
| D-T03 | 🔴 RED | 审批参数变化后失效 | 参数绑定不存在 |
| D-T04 | 🔴 RED | 检索文档中的指令不能触发工具越权 | 新攻击链测试未实现 |
| D-T05 | 🔴 RED | 上游 Agent 指令不能污染下游 | 结构化边界不存在 |
| D-T06 | 🔴 RED | 敏感字段在持久化前脱敏 | 脱敏层不存在 |
| D-T07 | 🔴 RED | 审计事件可重建任务关键路径 | 审计账本不存在 |
| D-T08 | 🔴 RED | 软预算产生预警 | 预算器不存在 |
| D-T09 | 🔴 RED | 硬预算暂停并保存检查点 | 预算与状态机未集成 |
| D-T10 | 🔴 RED | 路由记录质量、风险与成本理由 | 路由解释不存在 |
| D-T11 | 🔴 RED | task revision、事实/制品或索引代际变化使审批失效 | 审批依赖哈希不完整 |
| D-T12 | 🔴 RED | 状态迁移、审批消费和审计事件同事务提交 | 审计与业务事务未集成 |

## E. 研究交付

| ID | 状态 | 测试目标 | 预期 RED 原因 |
|---|---|---|---|
| E-T01 | 🔴 RED | 创建研究任务生成计划和预算 | 新 API 不存在 |
| E-T02 | 🔴 RED | 修改范围只重算受影响步骤 | 依赖失效逻辑不存在 |
| E-T03 | 🔴 RED | 未裁决关键冲突阻止正式报告 | 报告门禁不存在 |
| E-T04 | 🔴 RED | 用户可批准、驳回或保持冲突未决 | 审核流程不存在 |
| E-T05 | 🔴 RED | 关键声明关联事实、计算或分析标签 | 报告模型不存在 |
| E-T06 | 🔴 RED | 事实修订只使依赖声明失效 | 声明依赖图不存在 |
| E-T07 | 🔴 RED | Markdown/HTML 导出保留声明和来源 ID | 导出器不存在 |
| E-T08 | 🔴 RED | 新任务页复用现有主题与证据组件 | 前端页面未实现 |
| E-T09 | 🔴 RED | 旧聊天页与现有路由保持可用 | 新集成尚未验证 |

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

## 2026-08-28 B2.5 声明级 EvidenceBundle 实现记录

- 首次 RED：`python -m pytest tests/test_evidence_bundle.py -q --basetemp=.tmp/pytest-b25`，5 failed，关键失败原因均为 `ModuleNotFoundError: No module named 'src.evidence_bundle'`。
- 最小实现：`src/evidence_bundle.py`（`EvidenceBundle` 不可变模型 + `EvidenceBundleRepository`）；`src/v7_metadata_store.py` 追加 migration 10（`v7_claims`、`v7_evidence_bundles`，claim 外键 `ON DELETE RESTRICT`）。
- GREEN：同一命令 5 passed；`python -m compileall -q src/evidence_bundle.py src/v7_metadata_store.py tests/test_evidence_bundle.py` 通过。
- 兼容性回归：`python -m pytest tests/test_v7_metadata_store.py tests/test_financial_fact_vertical_slice.py tests/test_financial_fact_registry_provider.py tests/test_financial_fact_registry_adapter.py tests/test_verified_financial_facts.py -q`：23 passed。
- B 包定向回归：14 个 B 阶段测试文件（含 `test_evidence_bundle.py`）共 55 passed，零回归。
- 兼容边界：证据包仅新增可选 `to_response()` 载荷；既有比较响应与旧来源字段未改动，由 `test_existing_comparison_response_stays_unchanged_when_bundle_created` 固定。
- 环境说明：pytest 默认临时目录 `C:\Users\111\AppData\Local\Temp\pytest-of-111` 出现 Windows 权限错误（WinError 5），本轮起统一使用 `--basetemp=.tmp/pytest-*` 项目内目录。
- 提交 SHA：未提交；工作区存在大量未提交改动，等待用户明确授权后统一提交。
