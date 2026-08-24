# TDD 测试用例: P0 关键缺陷修复 (v5.1)

> 编码: UTF-8
> 约定: <span style="color:red">红色</span> = 未通过, <span style="color:green">绿色</span> = 已通过

---

## 一、测试文件规划

| 文件 | 测试范围 |
|------|---------|
| `tests/test_p0_fixes.py` | 所有 SP0-01 ~ SP0-05 的 TDD 测试用例 |

---

## 二、测试用例

### SP0-01: empty_result_count 重置逻辑

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-P0-01-01 | 连续空结果后有效结果计数器归零 | 1. 模拟 empty_result_count=3<br>2. 调用一个返回有效结果的工具<br>3. 检查 empty_result_count | `empty_result_count == 0` | <span style="color:green">GREEN</span> |
| TC-P0-01-02 | 连续空结果后仍空结果计数器递增 | 1. 模拟 empty_result_count=2<br>2. 调用一个返回空结果的工具<br>3. 检查 empty_result_count | `empty_result_count == 3` | <span style="color:green">GREEN</span> |
| TC-P0-01-03 | 空结果计数器不影响工具调用本身 | 1. 计数空结果到阈值附近<br>2. 验证工具调用结果与正常无异 | 工具返回结果不受计数器影响 | <span style="color:green">GREEN</span> |
| TC-P0-01-04 | 边界: count 从 0 开始递增后归零 | 1. count=0 → 空结果 → count=1<br>2. 空结果 → count=2<br>3. 有效结果 → count=0 | `count == 0`（不是 1） | <span style="color:green">GREEN</span> |

---

### SP0-02: run_stream 强制答案传入正确推理链

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-P0-02-01 | 强制答案时推理链非空 | 1. 设置 max_steps=1<br>2. 调用 run_stream()<br>3. 收集 yield 的事件 | 强制答案事件中 reasoning_chain 不为空列表 | <span style="color:green">GREEN</span> |
| TC-P0-02-02 | 推理链包含正确步数 | 1. 设置 max_steps=2<br>2. Agent 执行 2 步后强制回答<br>3. 检查 reasoning_chain 长度 | `len(reasoning_chain) == 2` | <span style="color:green">GREEN</span> |
| TC-P0-02-03 | 正常完成(非 max_steps)不受影响 | 1. 设置 max_steps=5<br>2. 查询简单问题在 2 步内完成<br>3. 收集 yield 的事件 | 正常完成，无强制答案事件 | <span style="color:green">GREEN</span> |

---

### SP0-03: memory 配置生效

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-P0-03-01 | enable_long_term=True 时启用长期记忆 | 1. 配置中 memory.enable_long_term=true<br>2. startup() 加载<br>3. 检查 AgentMemory 实例 | `memory.enable_long_term == True` | <span style="color:green">GREEN</span> |
| TC-P0-03-02 | working_memory_limit 从配置读取 | 1. 配置中 memory.working_memory_limit=10<br>2. startup() 加载<br>3. 检查 AgentMemory 实例 | `memory.working_memory_limit == 10` | <span style="color:green">GREEN</span> |
| TC-P0-03-03 | episodic_memory_turns 从配置读取 | 1. 配置中 memory.episodic_memory_turns=5<br>2. startup() 加载<br>3. 检查 AgentMemory 实例 | `memory.episodic_memory_turns == 5` | <span style="color:green">GREEN</span> |
| TC-P0-03-04 | 缺少 memory 段时使用默认值 | 1. config 中删除 memory 段<br>2. startup() 加载<br>3. 检查 AgentMemory 实例 | 使用默认值: limit=10, turns=5, long_term=False | <span style="color:green">GREEN</span> |

---

### SP0-04: Agent per-request 创建

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-P0-04-01 | 两个请求使用不同的 AgentMemory | 1. 以 session_id=A 发送请求<br>2. 以 session_id=B 发送请求<br>3. 检查两次推理是否互相干扰 | 两个请求使用不同的 memory 实例，结果隔离 | <span style="color:green">GREEN</span> |
| TC-P0-04-02 | Agent 实例创建不增加显著延迟 | 1. 测量 Agent 创建耗时<br>2. 对比阈值 | `ReActAgent.__init__` 耗时 < 5ms | <span style="color:green">GREEN</span> |
| TC-P0-04-03 | 工具注册表全请求共享 | 1. 检查多个请求使用的 tool_registry | 同一个 tool_registry 实例（id 相同）| <span style="color:green">GREEN</span> |

---

### SP0-05: API Key 鉴权

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-P0-05a-01 | 无 API Key 请求被拒绝 | 1. 不带 Authorization Header 请求 `/api/chat`<br>2. 检查响应 | 401, detail 含"未授权" | <span style="color:green">GREEN</span> |
| TC-P0-05a-02 | 错误的 API Key 被拒绝 | 1. 带 `Bearer wrong-key` 请求 `/api/chat`<br>2. 检查响应 | 401, detail 含"未授权" | <span style="color:green">GREEN</span> |
| TC-P0-05a-03 | 正确的 API Key 放行 | 1. 带 `Bearer correct-key` 请求 `/api/chat`<br>2. 检查响应 | 200 或正常业务响应 | <span style="color:green">GREEN</span> |
| TC-P0-05a-04 | /api/health 无需鉴权 | 1. 不带 Header 请求 `/api/health`<br>2. 检查响应 | 200, 正常返回健康状态 | <span style="color:green">GREEN</span> |
| TC-P0-05b-01 | max_steps 超上限被截断 | 1. 请求中 max_steps=100<br>2. 检查实际使用的 max_steps | 实际 max_steps = 15（硬上限） | <span style="color:green">GREEN</span> |
| TC-P0-05b-02 | max_steps 未超上限正常使用 | 1. 请求中 max_steps=5<br>2. 检查实际使用的 max_steps | 实际 max_steps = 5 | <span style="color:green">GREEN</span> |

---

## 三、测试统计

| 规范 | 测试用例数 | 已通过 | 未通过 |
|------|:--:|:--:|:--:|
| SP0-01 | 4 | 4 | 0 |
| SP0-02 | 3 | 3 | 0 |
| SP0-03 | 4 | 4 | 0 |
| SP0-04 | 3 | 3 | 0 |
| SP0-05 | 6 | 6 | 0 |
| **合计** | **20** | **20** | **0** |
