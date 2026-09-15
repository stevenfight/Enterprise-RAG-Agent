# 设计：F2 来源证据审计

1. `src/evaluation/source_audit.py` 提供纯函数式只读审计，输入已解析样本和来源根目录，输出检查数量、缺失文件和 `ready` 状态。
2. 相对来源文件名只在显式来源根目录下解析；绝对路径只检查其自身，不进行网络访问或路径写入。
3. `src/evaluation/cli.py` 的 `--source-root` 可重复传入多个目录。审计结果写入 JSON/Markdown 评测报告元数据；来源缺失直接导致 CLI 返回 1。
4. 未传入 `--source-root` 时不改变现有 offline-core 夹具行为，避免把无密钥 CI 误变成必须携带历史 PDF 的门禁。
