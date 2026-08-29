# 源文件、索引与溯源方案：两轮独立审查

## 审查约束

- 审查只以仓库当前代码、现有数据资产和本变更文档为证据，不把规划中的组件当作已实现事实。
- 每轮先记录可复核证据，再给出问题和文档修正；无证据的性能、安全或泛化结论不成立。
- 本文件审查的是规划可实施性，不代表业务代码、测试或发布门禁已经通过。

## 第一轮：输入边界、错误、权限与旧接口回归

### 代码证据

1. `src/knowledge_service.py::upload_pdf()` 第 76-103 行只检查扩展名和大小，随后以 `open(dest_path, "wb")` 直接覆盖同名目标；没有 PDF magic、页数、加密、staging 或不可变版本登记。
2. `src/knowledge_service.py::delete_pdf()` 第 120-146 行的文档字符串明确说明“不清理对应的向量索引数据”，实现只调用 `filepath.unlink()`。
3. `src/pdf_mineru.py::_process_large_pdf()` 第 153-172 行会跳过失败页批次，只要至少一批成功仍写出合并 Markdown 并返回成功。
4. `src/text_splitter.py::build_line_page_map()` 第 148-163 行按 Markdown 字符比例映射 PDF 字符位置，是近似页码，不是 bbox 证据。
5. `src/api_service.py::APIAuthMiddleware` 第 653-671 行使用统一 API key，并对白名单流式端点和图表静态前缀免鉴权；代码没有多租户主体或文档 ACL 证据。

### 发现、修正与结论

1. **边界不足：** 原方案提到 staging，但未覆盖 PDF magic、空文件、加密、截断、Windows 保留名和哈希键异常冲突。已补入 design、规格、M0 任务和 S-T03/S-T22/S-T23。
2. **错误处理不足：** 原方案未区分不可重试输入错误、临时 I/O/数据库错误和解析/索引完整性错误，存在无限重试或错误标 complete 的实现空间。已增加稳定错误分类、有限重试和 S-T24。
3. **半成品权限边界不足：** staging 或数据库登记失败后可能留下孤儿文件，原方案未明确其不可见性。已规定 staging/orphan 不得由查询或 artifact API 访问，并增加幂等回收与 S-T21。
4. **权限结论过度风险：** 现有证据只能支持统一 API key 的端点认证，不能支持多租户或文档级 ACL。已把 v7 权限承诺限定为单用户/单租户，并增加 S-T26；团队多租户仍在延后范围。
5. **回归边界不足：** 开关开启后的上传响应未明确保留旧字段，可能破坏现有调用方。已规定保留 `filename/size/size_mb`，只增加可选状态字段，且处理中不得宣称索引完成，并增加 S-T25。
6. **既有产物不能按“文件存在”复用：** 大 PDF 代码允许部分成功，近似页码也不能证明区域准确。方案已要求页批次、引用和定位证据完整后才 REUSE；否则 ENRICH、定向重提取或全量重提取。

第一轮结论：在上述修正前，方案不能覆盖上传与解析的真实边界，也不能证明权限和旧契约安全；修正后，相关风险均已进入规格、任务和 RED 测试，但尚未实现，不能宣称问题已经在代码中解决。

## 第二轮：并发发布、删除、引用完整性与回滚

### 代码证据

1. `src/ingestion.py::save_registry()` 第 51-54 行直接 `write_text` 覆盖 registry；`main()` 第 383-389 行在 `--rebuild` 时先递归删除旧公司索引目录。当前实现没有 staging generation 或原子发布集合。
2. `src/ingestion.py::build_faiss_index()` 第 225-231 行在 embedding 批次失败后写入零向量；metadata 第 265-276 行只有 chunk/source/pages/company/hash/tags 等字段，registry 虽记录 embedding model 和维度，但没有完整 parser、splitter、preprocess 和 schema 版本，不能证明旧向量可安全导入。
3. `src/retrieval.py::HybridRetriever` 第 440-480 行缓存 registry、向量和 BM25 retriever；`RAGGenerator._get_retriever()` 第 1407-1410 行再缓存 HybridRetriever。`src/tools/retrieve_tool.py` 第 133-152 行和 `src/tools/compare_tool.py` 第 103-115 行还各自延迟缓存独立 HybridRetriever。
4. `src/knowledge_service.py::delete_pdf()` 只删除文件且明确不清理索引，证明文件、索引和业务元数据当前不能用单一文件操作保持一致。
5. 仓库当前不存在 `PublicationSet`、`PublicationResolver` 或 active publication 事务，因此以下内容均是规划要求，不是现有能力。

### 发现、修正与结论

1. **只切索引指针会产生混合快照：** 查询可能读取新索引，却读取旧 artifact/fact 可见性。已用 `PublicationSet` 统一绑定 generation、document versions、artifact/fact 边界和 corpus revision；请求固定 publication，而非只固定 generation。新增 S-T27/S-T29。
2. **并发发布缺少胜者规则：** 两个构建任务可能相互覆盖。已规定 expected active publication/revision 的 SQLite CAS，最多一个发布成功，失败任务标记 superseded。新增 S-T28。
3. **首轮迁移分母可能漂移：** 构建期间上传或删除会让“覆盖全部文档”无法判定。已固定 corpus revision；后续变更进入下一 publication，或重启受影响校验。新增 S-T31。
4. **回滚范围原先过窄：** 只回滚 index pointer 无法恢复同批事实和制品可见性。已改为创建引用上一整组不可变版本的新 publication，新增 S-T30。
5. **共享 blob 存在删除竞态：** 删除检查零引用与并发同 hash 上传若分两步执行，可能误删刚被引用的源。已要求引用增减和删除资格在同一事务串行化，新增 S-T32。
6. **级联物理删除会破坏审计：** 来源失效后仍需解释历史报告。已规定外键 RESTRICT、软失效和 stale 传播；报告保留失效原因，但受保护 artifact 不再开放给新请求。新增 S-T33。
7. **旧代际回收与在途缓存冲突：** 多个独立 Retriever 缓存和 Windows 打开文件使立即删除不安全。已要求 publication 租约、owner token、崩溃超时回收，并增加 S-T34；无活动租约且过保留期前不得物理回收。
8. **旧向量复用没有证据：** 现有 metadata 不足以证明预处理兼容，且失败批次可能含零向量。首轮 v7 继续要求全部重算 embedding；这不是对 MinerU 产物的全量重处理。

第二轮结论：修正前，索引、事实、制品和文档可见性无法形成同一并发快照，回滚和删除也可能跨存储失配；修正后，方案给出了单一发布真值、CAS、请求快照、软失效和共享 blob 事务边界。相关组件当前均不存在，因此结论只能是“规划已覆盖”，不能是“实现已安全”。

## 两轮总判断

- **有证据支持：** 现有上传覆盖、删除不清索引、MinerU 部分成功、页码近似、索引原地删除/直接写、embedding 零向量和多入口缓存都是真实代码行为，规划必须规避。
- **有证据支持：** 当前需求可由明确的文档—制品—事实—声明—计算—报告关系完成；仓库没有多跳图评测证明知识图谱带来必要收益，因此 v7 延后知识图谱是较低风险选择。
- **不能宣称：** 文档通过审查不等于实现通过；所有新增 S/M TDD 仍为 RED，权限只到单用户/单租户端点级，首轮索引质量与成本必须在实施后测量。
- **审查结果：** 两轮共识别并回写 14 类问题。当前文档可作为后续 SDD/TDD 实施依据，未发现仍缺少规格落点的已证实高风险项；是否能开发通过，只能由后续 RED→GREEN 测试和回归证据决定。
