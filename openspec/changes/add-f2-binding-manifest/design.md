# 设计：评测数据绑定清单

## 清单格式

绑定清单使用 UTF-8 JSON，最小字段如下：

```json
{
  "schema_version": 1,
  "dataset_path": "evals/datasets/core.jsonl",
  "dataset_sha256": "...",
  "source_inventory_path": "data/stock_data/pdf_source_inventory.json",
  "source_inventory_sha256": "..."
}
```

路径按 POSIX 分隔符比较，并与 CLI 实际传入路径的规范化相对路径比较；哈希按文件内容计算。绑定清单本身不要求记录来源根目录，因为来源根目录可以是本地或隔离服务器上的显式装配位置。

## 运行时行为

- 新增 `--source-binding-manifest`，传入后先审计数据集和来源清单的路径、存在性及 SHA-256。
- 绑定报告写入 `metadata.source_binding`。
- 绑定清单错误使 CLI 返回非零，但不阻止生成报告。
- 未传入该参数时不新增失败条件，兼容现有无绑定清单运行。

## 安全边界

审计器只读取清单和文件哈希，不复制、覆盖、删除或修改评测集、来源清单及 PDF。
