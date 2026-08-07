# SDD: 步骤 1.1 DataAgent

> 编码: UTF-8 | 变更: multi-agent-step04

---

## 1. 架构设计

```
ReActAgent (src/agent_core.py)           ← 步骤 0.1 已改造
  │
  ├── 继承：_call_llm()       （llm_provider 双路径）
  ├── 继承：_parse_response() （Thought/Action/Action Input 解析）
  ├── 继承：_execute_action() （工具执行 + sources 收集）
  ├── 继承：_build_system_prompt() （YAML 模板加载）
  ├── 继承：run()            （ReAct 推理循环）
  │
  └── DataAgent (src/worker_agents/data_agent.py)  ← 本次新增
        │
        ├── 定制：prompt_name="data_agent"
        │        → 加载 agent_prompts.yaml data_agent 节
        │        → 只含安全规则 + 检索规则 1/2/3/4/5/6/7/9/10/11
        │        → 不含规则 8（图表展示）
        │
        ├── 定制：max_steps=3
        │        → 检索一般 1-3 步（检索→追加检索→回答）
        │
        ├── 定制：temperature=0.2
        │        → 检索不需要创造性，需要稳定输出
        │
        ├── 定制：model="qwen-turbo"
        │        → 简单查询意图理解，turbo 即可
        │
        └── 工具注册：ToolRegistry().register(retrieve_tool)
                 → 只注册 retrieve 一个工具
                 → 每个 DataAgent 实例独立 ToolRegistry
```

## 2. DataAgent 规则集 vs Default 规则集

| 规则编号 | 内容 | default | data_agent |
|:--:|------|:--:|:--:|
| 1 | 每步只能调用一个工具 | + | + |
| 2 | 数据不充分时继续检索 | + | + |
| 3 | 数字必须标注来源 | + | + |
| 4 | 空结果时调整查询角度 | + | + |
| 5 | 单位换算 | + | + |
| 6 | 禁止汇率换算 | + | + |
| 7 | 优先人民币数据 | + | + |
| 8 | 图表展示 | + | - |
| 9 | 优先年报来源 | + | + |
| 10 | 年报检索强化 | + | + |
| 11 | 同源对比原则 | + | + |
| -- | 职责：只检索不做分析 | - | + |

> DataAgent 移除规则 8（图表展示），新增第三条职责定义"只返回检索到的原始数据，不要解读或计算"。

## 3. 模型分配

| Agent | 模型 | 温度 | 原因 |
|------|------|:--:|------|
| DataAgent | qwen-turbo | 0.2 | 只做检索，不需要复杂推理。用 max 浪费（简单查询降本约 60%） |

## 4. 工具配置

| Agent | 持有工具 | 工具来源 | 说明 |
|------|:--:|------|------|
| DataAgent | retrieve | 共享 | 内部 HybridRetriever 加载向量库，`search()` 是无状态调用，可并行安全 |

## 5. 与后续步骤的依赖

```
步骤 1.1 DataAgent（本次）
  │
  ├── 被步骤 2.1 依赖: AgentRegistry 会注册 DataAgent 的能力描述
  ├── 被步骤 2.3 依赖: DelegateTool 会通过 AgentRegistry 获取 DataAgent 实例
  └── 被步骤 2.4 依赖: OrchestratorAgent 会通过 delegate 工具委派 DataAgent
```

## 6. 不改动保证

| 层级 | 文件 | 说明 |
|------|------|------|
| Agent 核心 | `src/agent_core.py` | 只继承不改动 |
| 任务规划 | `src/planner.py` | 不依赖 planner |
| API 服务 | `src/api_service.py` | 步骤 1.1 不接入 API 端点 |
| 路由 | `src/router.py` | 不依赖路由 |
| Prompt | `config/agent_prompts.yaml` | data_agent 节已在步骤 0.2 定义 |
| 工具 | 所有工具文件 | 直接复用 retrieve |
| 测试 | `tests/` 所有现有测试 | 100% 通过 |
