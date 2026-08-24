# 变更提案: RAG 管道升级为 RAG-Agent 智能体

> 编码: UTF-8
> 状态: 已完成

---

## 1. 变更背景

当前系统是典型的管道式 RAG 架构，核心流程为：

```
用户提问 → 意图识别 → Query改写 → BM25+向量混合检索 → gte-rerank-v2重排 → Qwen-Max生成 → 返回答案
```

该系统在企业年报智能问答场景下已经验证有效（端到端耗时 ~20s，TDD 测试通过率 97.7%），但存在以下不足：

- **单次检索 → 单次生成**：无自主推理能力，无法对复杂问题拆解多步执行
- **无工具调用机制**：无法进行财务计算、图表生成、数值验证等操作
- **无自我修正**：生成结果没有验证环节，无法自动发现和修正错误
- **对话记忆简单**：仅支持 5 轮上下文，无结构化记忆

本变更将系统从"管道式 RAG"升级为"Agent 式 RAG"，在保留全部原有能力的基础上，增加自主推理、工具调用、自我反思等智能体核心能力。

---

## 2. 变更目标

| 目标 | 衡量标准 |
|------|---------|
| 新增 Agent 自主推理 | 支持复杂查询的多步拆解与执行（ReAct 模式） |
| 新增工具调用系统 | 支持检索、计算、对比、图表、验证等至少 5 个工具 |
| 新增答案质量验证 | 生成答案经过数值验证和幻觉检测 |
| 保留原有管道能力 | 原有 RAG 管道作为降级方案，100% 可用 |
| 原有 TDD 回归通过 | 现有测试全部通过，不引入回归 |

---

## 3. 变更范围

### 3.1 新增模块

| 模块 | 文件名 | 职责 |
|------|--------|------|
| Agent 核心 | `src/agent_core.py` | ReAct 循环控制器 |
| Agent 记忆 | `src/agent_memory.py` | 三层记忆（工作/情景/长期） |
| 任务规划器 | `src/planner.py` | 复杂查询拆解为子任务 |
| 反思模块 | `src/reflector.py` | 答案质量验证、幻觉检测 |
| 工具注册 | `src/tools/__init__.py` | 工具基类与注册框架 |
| 检索工具 | `src/tools/retrieve_tool.py` | 封装现有混合检索 |
| 计算工具 | `src/tools/calculator_tool.py` | 财务指标计算 |
| 对比工具 | `src/tools/compare_tool.py` | 多公司结构化对比 |
| 图表工具 | `src/tools/chart_tool.py` | 财务趋势图表生成 |
| 验证工具 | `src/tools/verify_tool.py` | 数值验证反幻觉 |
| Agent 配置 | `config/agent_config.json` | Agent 行为参数 |

### 3.2 修改模块

| 模块 | 文件 | 修改内容 |
|------|------|---------|
| API 服务 | `src/api_service.py` | 新增 `/api/agent/query` 端点 |
| Web 界面 | `app_streamlit.py` | 新增 Agent 模式、推理链展示 |
| 对话管理 | `src/conversation.py` | 扩展为支持 Agent 记忆结构 |
| 入口文件 | `src/__init__.py` | 导出 Agent 相关模块 |

### 3.3 保留不变（数据管道 + 核心检索）

- `src/pdf_mineru.py` - PDF 解析
- `src/text_splitter.py` - 文本分块
- `src/ingestion.py` - 索引构建
- `src/retrieval.py` - 混合检索+生成（封装为工具）
- `src/query_processor.py` - 意图识别+改写
- `src/utils.py` - 公共工具
- 全部 `config/` 和 `data/` 文件

---

## 4. Agent 架构设计概要

### 4.1 ReAct 模式

采用 ReAct (Reasoning + Acting) 模式，核心循环：

```
while step < max_steps and not answer_found:
    thought = LLM.think(context, tools, memory)  # 推理
    action = thought.action                       # 行动
    observation = execute_tool(action)            # 观察
    memory.add(thought, action, observation)      # 记忆
    step += 1
```

### 4.2 工具系统

所有工具实现统一接口：`Tool.run(params) → ToolResult`

| 工具 | 输入 | 输出 |
|------|------|------|
| retrieve | query, company_name, top_n | 检索结果列表 + 来源 |
| calculate | expression / metric_name, company_data | 计算结果 |
| compare | companies[], metrics[], year | 结构化对比表 |
| chart | data, chart_type | 图表文件路径 |
| verify | claim, source_text | 验证结果 + 置信度 |

### 4.3 记忆系统

| 层级 | 存储内容 | 生命周期 |
|------|---------|---------|
| 工作记忆 | 当前任务的 Thought/Action/Observation | 单次查询 |
| 情景记忆 | 历史对话摘要 | 会话级 |
| 长期记忆 | 公司知识图谱、财务术语 | 持久化 |

---

## 5. 技术决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| Agent 框架 | 自研 ReAct（不引入 LangChain 等） | 保持轻量，复用 DashScope Qwen 系列原生能力 |
| 大模型 | Qwen-Max (生成) + Qwen-Plus (意图) | 与 RAG 阶段一致，不增加新依赖 |
| 原有管道 | 保留作为降级方案 | API 新增 `/api/agent/query`，原有 `/api/query` 不变 |
| Streamlit | 新增 Agent 模式开关 | 用户可切换管道模式 / Agent 模式 |

---

## 6. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| LLM 调用次数增加 | Agent 多步推理可能 5-10 次 LLM 调用 | 保留管道模式，Agent 模式可选 |
| 工具调用失败 | 单步失败影响整体答案 | 每步超时+重试，失败时跳过继续 |
| 原有功能回归 | 修改可能影响管道 | 管道代码完全不改，Agent 是叠加层 |
| API 成本增加 | 多次 LLM 调用 | 配置 max_steps=5，可调 |

---

## 7. 前置工作（已完成）

- 项目目录规范化，清理非工程文件
- 提取 RAG 阶段技术约束到 `docs/系统设计决策记录.md`
- 更新 `.gitignore` 排除本地文档目录

---

## 8. 受影响的规范

- `openspec/changes/model-upgrade/` - 模型配置继承
- `openspec/changes/quality-robustness-enhancement/` - 健壮性能力继承
