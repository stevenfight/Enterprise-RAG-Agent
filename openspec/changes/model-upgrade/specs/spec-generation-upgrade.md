# 需求规格: 生成模型升级

> 编码: UTF-8
> 变更: model-upgrade
> 状态: 待审核

---

## SPEC-G1: 答案生成模型从 qwen-plus 升级到 qwen-max

### 描述

将 RAG 答案生成的 LLM 模型从 `qwen-plus` 升级为 `qwen-max`,提升指令遵循能力和幻觉抑制效果。意图识别和查询改写仍保持 `qwen-plus`。

### 前置条件

- DashScope API Key 已配置
- `qwen-max` 模型在 DashScope 平台可用

### 功能需求

| ID | 需求 | 优先级 |
|----|------|--------|
| G1-F1 | `RAGGenerator.GENERATION_MODEL` 从 `qwen-plus` 改为 `qwen-max` | P0 |
| G1-F2 | `QueryProcessor.MODEL_NAME` 保持 `qwen-plus` 不变 | P0 |
| G1-F3 | `_llm_rerank` 中的模型不再使用 qwen-plus(已替换为 gte-rerank) | P0 |
| G1-F4 | 验证 qwen-max 的 max_tokens 参数兼容性(当前设为 2048) | P1 |

### 非功能需求

| ID | 需求 |
|----|------|
| G1-N1 | 生成答案中数据引用必须与检索结果一致,不得编造数字 |
| G1-N2 | 单次生成耗时不超过 15 秒 |
| G1-N3 | qwen-max 的 API 调用格式与 qwen-plus 兼容(均使用 dashscope.Generation.call) |

### 场景

#### 场景 G1-S1: 财务数据查询生成

```
给定: 查询 "中芯国际2024年营收" 和包含营收数据的检索结果
当: 调用 RAGGenerator.query
那么: 生成的答案中营收数字与检索结果一致
且: 答案标注了来源引用 [来源1]
且: 不包含检索结果中未出现的数字
```

#### 场景 G1-S2: 对比分析生成

```
给定: 查询 "三家运营商2024年营收对比" 和三家公司的检索结果
当: 调用 RAGGenerator.query (intent=comparison)
那么: 生成的答案以表格或结构化格式展示三家数据
且: 每家数据标注来源
且: 缺失数据明确说明"未在检索结果中找到"
```

#### 场景 G1-S3: 信息不足场景

```
给定: 查询 "中芯国际2026年营收预测" 但检索结果中只有2024年数据
当: 调用 RAGGenerator.query
那么: 答案明确说明"检索结果中未包含2026年数据"
且: 不编造2026年预测数字
```

### 涉及文件

- `src/retrieval.py` (第896行 `GENERATION_MODEL` 常量)
- `src/query_processor.py` (第30行 `MODEL_NAME` 常量, 保持不变)
