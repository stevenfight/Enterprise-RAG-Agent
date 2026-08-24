# 变更提案: Planner 运营商别名识别（三大运营商）

> 编码: UTF-8

## 背景

DAG 看板输入「对比三大运营商2024年的营业收入」时，`TaskPlanner` 返回的规划中 `companies` 为空、compare 任务描述为「对比 各公司: 2024年营收」。

根因：`planner.py` 的 `_classify_query` 仅通过 `COMPANY_NAMES = {中芯国际, 中国移动, 中国联通, 中国电信}` 精确匹配，而用户使用行业称谓「三大运营商」，未命中任何公司名，导致 compare 子任务无法定位目标公司。检索层与编排层均可处理该查询，唯独规划层缺失。

## 目标

1. 查询包含「三大运营商」时，规划器将其展开为 `[中国移动, 中国联通, 中国电信]`。
2. compare 子任务的 `tool_params["companies"]` 包含三家运营商，DAG 展示正确的公司。
3. 不改变既有行为：直接写公司名的查询、模糊查询逻辑保持原样。

## 方案

- `planner.py` 新增 `COMPANY_ALIASES` 映射：`{"三大运营商": ["中国移动", "中国联通", "中国电信"]}`。
- `_classify_query` 提取公司时，先精确匹配 `COMPANY_NAMES`，再按 `COMPANY_ALIASES` 做别名展开并去重追加。
- 抽出处 `_extract_companies(query)` 私有方法，保持 `_classify_query` 现有结构。

## 非目标

- 不改动检索层、编排层、前端 DAG 渲染逻辑。
- 不做通用 NER 实体识别（仅处理明确的运营商别名）。
