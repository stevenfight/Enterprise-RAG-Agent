# 任务清单: 步骤 0.1 多 Agent 基础能力搭建

> 编码: UTF-8 | 变更: multi-agent-step01
>
> 完成日期: 2026-08-06

---

## 实施任务

- [x] 1. 新增 `src/llm_provider.py` (R-02)
  - [x] 1.1 创建 LLMUsage dataclass
  - [x] 1.2 创建 LLMResponse dataclass
  - [x] 1.3 创建 BaseLLMProvider 抽象基类
  - [x] 1.4 创建 DashScopeProvider 实现
  - [x] 1.5 创建 OpenAICompatibleProvider 占位

- [x] 2. 新增 `src/step_callback.py` (R-06, R-07)
  - [x] 2.1 创建 StepCallback 类
  - [x] 2.2 实现 on_step 方法
  - [x] 2.3 实现 on_done 方法

- [x] 3. 新增 `src/worker_tool_factory.py` (M-45)
  - [x] 3.1 创建 WorkerToolFactory 类
  - [x] 3.2 实现 create_registry 方法

- [x] 4. 修改 `src/agent_core.py` (R-01/02/04/05, M-35/36/41/44/46)
  - [x] 4.1 顶部新增 import (yaml, Template)
  - [x] 4.2 AgentResult 新增 3 字段
  - [x] 4.3 ReActAgent.__init__ 新增 3 参数
  - [x] 4.4 _default_system_prompt 改为 $variable 语法
  - [x] 4.5 新增 _load_prompt_template 方法
  - [x] 4.6 升级 _build_system_prompt 方法
  - [x] 4.7 升级 _call_llm 双路径
  - [x] 4.8 run() 签名扩展 + sources/tokens 重置 + 返回值填充
  - [x] 4.9 run_stream() 同 4.8 + step_callback 插入
  - [x] 4.10 _execute_action 收集 sources

- [x] 5. 修改 `src/api_service.py` (R-02)
  - [x] 5.1 _init_globals 新增 LLMProvider 初始化
  - [x] 5.2 _create_per_request_agent 新增 llm_provider/prompt_name 参数
  - [x] 5.3 _load_agent_config 新增 models/multi_agent 配置节读取
  - [x] 5.4 所有调用 _create_per_request_agent 的地方传 llm_provider

- [x] 6. 修改 `src/tools/retrieve_tool.py` (M-45)
  - [x] 6.1 新增 import threading
  - [x] 6.2 新增 _init_lock 类变量
  - [x] 6.3 _get_retriever 添加 double-check locking

- [x] 7. 修改 `config/agent_config.json` (R-02)
  - [x] 7.1 新增 agent.models 配置节
  - [x] 7.2 新增 multi_agent 配置节

## 验证任务

- [x] 8. 运行 TDD 测试
  - [x] 8.1 编写 tdd_multi_agent_step01.py 测试脚本
  - [x] 8.2 逐项运行，标绿通过的测试
  - [x] 8.3 确保所有 64 项测试通过

- [ ] 9. 回归验证
  - [ ] 9.1 运行现有测试确保无回归
  - [ ] 9.2 验证 /api/agent/query 行为不变
