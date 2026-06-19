# 需求规格: Embedding 模型升级

> 编码: UTF-8
> 变更: model-upgrade
> 状态: 待审核

---

## SPEC-E1: Embedding 模型从 v1 升级到 v3

### 描述

将 DashScope Embedding 模型从 `text-embedding-v1` (1536维) 升级为 `text-embedding-v3` (1024维),提升中文财报文本的语义理解能力。

### 前置条件

- DashScope API Key 已配置
- `text-embedding-v3` 模型在 DashScope 平台可用

### 功能需求

| ID | 需求 | 优先级 |
|----|------|--------|
| E1-F1 | `src/retrieval.py` 中 `EMBEDDING_MODEL` 常量从 `text-embedding-v1` 改为 `text-embedding-v3` | P0 |
| E1-F2 | `src/retrieval.py` 中 `EMBEDDING_DIM` 常量从 `1536` 改为 `1024` | P0 |
| E1-F3 | `src/ingestion.py` 中 `EMBEDDING_MODEL` 常量从 `text-embedding-v1` 改为 `text-embedding-v3` | P0 |
| E1-F4 | `src/ingestion.py` 中 `EMBEDDING_DIM` 常量从 `1536` 改为 `1024` | P0 |
| E1-F5 | 重建所有公司的 FAISS 索引,使用新模型生成 Embedding | P0 |
| E1-F6 | 重建后验证向量检索功能正常 | P0 |

### 非功能需求

| ID | 需求 |
|----|------|
| E1-N1 | 旧索引文件在重建前应备份 |
| E1-N2 | 重建过程中 Embedding API 调用失败时应有重试机制(已有) |
| E1-N3 | 新索引的向量维度必须为 1024 |

### 场景

#### 场景 E1-S1: 正常升级流程

```
给定: 当前使用 text-embedding-v1 (1536维) 的 FAISS 索引
当: 修改 EMBEDDING_MODEL 和 EMBEDDING_DIM 常量并执行 python src/ingestion.py --rebuild
那么: 所有公司索引使用 text-embedding-v3 (1024维) 重建
且: 检索功能正常工作
```

#### 场景 E1-S2: 维度不匹配检测

```
给定: EMBEDDING_DIM 设为 1024 但 FAISS 索引仍是 1536 维
当: 执行向量检索
那么: 应报错提示维度不匹配,而非静默失败
```

#### 场景 E1-S3: 表格数据检索提升验证

```
给定: 新索引已构建
当: 查询 "中国电信2024年营业收入"
那么: 包含 "5,236亿元" 营收数据的文档块应出现在向量检索 top 10 结果中
且: 该结果在旧索引中可能不在 top 30
```

### 涉及文件

- `src/retrieval.py` (第45-46行, 第156行)
- `src/ingestion.py` (第37-38行, 第92行, 第273行, 第333行)
