# 设计方案: ReAct 空结果安全阀

> 编码: UTF-8

---

## 1. 核心思路

在 ReAct 主循环的每一步工具执行后，增加"空结果检测 → 计数器累加/重置 → 步数耗尽强制降级"的三层安全阀。

```
每步执行完工具 →
  _is_empty_result(observation)?
    ├─ 是 → empty_result_count += 1
    └─ 否 → empty_result_count = max(0, count - 1)
              若归零 → 输出 INFO 日志"计数器已重置为0"

  检查 max_steps?
    └─ 达到 → _generate_forced_answer() → forced_stop=True
```

## 2. 关键技术决策

### 2.1 标记清单（8 + 2 个）

| 类型 | 标记 | 来源 |
|------|------|------|
| 前缀 | `[错误]` | 工具层报错 |
| 前缀 | `[工具执行失败]` | ToolResult.success=False → to_observation() |
| 关键词 | `未检索到相关数据` | RetrieveTool 空结果分支 |
| 关键词 | `未找到相关数据` | 通用空结果文案 |
| 关键词 | `无数据` / `没有检索到` / `没有找到` | 各工具多样性覆盖 |
| 关键词 | `无有效数值` / `来源文本不足` | 数据质量问题 |
| 关键词 | `unavailable` | 英文来源兼容 |

判定顺序：空字符串 → 前缀匹配（O(1)）→ 关键词遍历（O(n)）

### 2.2 计数器行为

- 连续空 → 累加，>=2 输出 WARNING
- 有结果 → 减 1 退回（防抖动，不惩罚"偶然搜不到再搜到"）
- 与 max_steps 解耦：计数器只做检测和预警，强制降级由 max_steps 触发

### 2.3 强制降级

- `success=True`：避免上层认为是系统故障
- `forced_stop=True`：明确标记"这是降级答案"
- 降级答案由 LLM 基于已收集的部分信息生成，至少说明"哪些信息缺失"
- 兜底文案："抱歉，推理超时，未能生成有效答案。请尝试简化您的问题。"

### 2.4 NameError 修复

`_generate_forced_answer` 原代码隐式引用 `run()` 局部变量 `reasoning_chain`。
修复：改为方法签名显式接收 `reasoning_chain` 参数。

```python
def _generate_forced_answer(self, messages, reasoning_chain):  # 显式传参
    for step_info in reasoning_chain:  # 不再依赖外部作用域
        ...
```

## 3. 测试策略

| 测试类型 | 文件 | 覆盖点 |
|----------|------|--------|
| 纯 Mock 单元测试 | `test_agent_mock_boundary.py` | 13 标记 True/False、计数器累加/重置/日志、方法签名、NameError |
| 端到端验证 | `test_agent_boundary_verify.py` | 真实 LLM 空结果、合成 monkey-patch、降级答案非空 |
