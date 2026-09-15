# 设计：F2 来源完整性绑定审计

1. `src/evaluation/source_integrity.py` 接收已解析评测样本、显式来源根目录和 JSON 清单路径，输出来源文件数量、清单缺失、来源缺失、SHA-256/大小/物理页漂移和 `ready` 状态。
2. 相对来源文件名只在显式来源根目录中解析；同一文件在多个根目录中按第一个存在文件使用，清单以 `filename` 建立绑定索引，`relative_source_path` 作为保留元数据，不改变样本声明的文件名。
3. PDF 物理页数复用 PyMuPDF 读取；读取失败或页数不一致均为失败，不自动降级为“仅文件存在”。
4. `src/evaluation/cli.py` 新增 `--source-inventory`。未提供该参数时继续使用现有存在性审计；提供后将完整性结果写入 `metadata.source_integrity`，任何不一致使 CLI 返回 1。
5. 审计器保持纯只读，不写来源根目录，不改变候选集状态；测试使用临时 PDF 和临时清单验证漂移边界。
