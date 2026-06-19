# 需求规格: 重排模型替换

> 编码: UTF-8
> 变更: model-upgrade
> 状态: 待审核

---

## SPEC-R1: 重排从 LLM 逐条调用替换为 gte-rerank 批量调用

### 描述

将 LLM 重排逻辑从 `qwen-plus` 逐条调用(18次API调用,30-60秒)替换为 `gte-rerank` 专用重排模型批量调用(1次API调用,2-3秒),提升重排准确度和速度。

### 前置条件

- DashScope API Key 已配置
- `gte-rerank` 模型在 DashScope 平台可用
- DashScope Python SDK 支持 `TextReRank` API

### 功能需求

| ID | 需求 | 优先级 |
|----|------|--------|
| R1-F1 | `_llm_rerank` 方法改为使用 `dashscope.TextReRank.call()` | P0 |
| R1-F2 | 重排输入为 query + 候选文档列表,输出为排序后的文档列表及分数 | P0 |
| R1-F3 | 重排分数归一化到 0-10 范围,与现有置信度计算逻辑兼容 | P0 |
| R1-F4 | 保留 rerank_reasoning 和 rerank_key_info 字段(从 gte-rerank 结果中提取或置空) | P1 |
| R1-F5 | 候选列表为空时返回 ([], []),统一返回类型(修复 ISSUE-004) | P1 |
| R1-F6 | 重排 API 调用失败时,回退到 hybrid 分数排序 | P1 |

### 非功能需求

| ID | 需求 |
|----|------|
| R1-N1 | 单次重排耗时不超过 5 秒(20个候选) |
| R1-N2 | 重排 API 调用次数从 N 次降为 1 次 |
| R1-N3 | 重排分数范围 0-10,与现有 _compute_confidence 逻辑兼容 |

### 场景

#### 场景 R1-S1: 正常重排流程

```
给定: 查询 "中芯国际2024年营收" 和 20 个候选文档
当: 调用 _llm_rerank
那么: 使用 gte-rerank 批量重排
且: 返回 top 5 结果,每个结果包含 rerank 分数(0-10)
且: 耗时不超过 5 秒
```

#### 场景 R1-S2: 对比查询重排

```
给定: 查询 "中国移动和中国联通和中国电信2024年营收对比" 和 18 个候选文档(3家公司各6个)
当: 调用 _llm_rerank
那么: gte-rerank 在同一上下文中对 18 个文档打分
且: 三家公司的营收数据块均应获得较高分数(>=5.0)
```

#### 场景 R1-S3: API 调用失败回退

```
给定: gte-rerank API 调用失败(网络错误/限流)
当: 调用 _llm_rerank
那么: 回退到按 hybrid 分数排序
且: 日志记录回退原因
且: 不抛出异常,保证查询流程不中断
```

#### 场景 R1-S4: 候选列表为空

```
给定: 候选列表为空
当: 调用 _llm_rerank
那么: 返回 ([], [])
且: 不调用任何 API
```

### 涉及文件

- `src/retrieval.py` (`_llm_rerank` 方法, 第479-554行)
- `src/retrieval.py` (`_compute_confidence` 方法, 第558-568行, 验证兼容性)
