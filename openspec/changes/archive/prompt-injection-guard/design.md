# Design: 提示词注入防护

> 编码: UTF-8 | 变更: prompt-injection-guard

---

## 架构概览

```
用户输入
  ↓
【注入标记层】── 在所有 prompt 模板中用 XML 标签包裹用户输入
  │  query_processor.py: INTENT_PROMPT_TEMPLATE / REWRITE_PROMPT_TEMPLATE
  │  agent_core.py:      用户消息追加
  │  retrieval.py:       三个 _build_*_prompt
  ↓
【LLM 防御层】── 在 system prompt / 生成 prompt 中嵌入安全规则
  │  agent_core.py:      _default_system_prompt 追加安全规则
  │  retrieval.py:       三个 _build_*_prompt 加入防注入声明
  ↓
LLM
```

---

## 关键设计决策

### 决策 1: XML 标签作为定界符

**决策**: 使用 `<用户输入>`、`<user_query>`、`<用户问题>` 三种 XML 标签包裹用户原始输入。

**理由**:
- LLM 在预训练中大量接触 XML/HTML 标签，天然理解其作用域和边界语义
- 不需要外部依赖，纯 prompt 工程方案
- 不修改用户输入内容（不转义、不过滤），保持信息完整性

### 决策 2: 三种不同标签名适配不同上下文

**决策**: 在不同模块使用不同的标签名，而非统一标签。

**理由**:
- query_processor 中 prompt 使用中文风格（`<用户输入>`），与现有中文 prompt 模板风格一致
- agent_core 中消息使用英文风格（`<user_query>`），与 ReAct prompt 英文混合风格一致
- retrieval 中 prompt 使用中文风格（`<用户问题>`），与现有 prompt 中文风格一致
- 标签名语义对应上下文角色，提高 LLM 理解准确性

### 决策 3: 安全规则注入位置

**决策**: 安全规则放在 prompt 最前端的独立区块中。

**理由**:
- 用户在阅读时，越先看到的信息权重越高（LLM 的 recency/primacy 效应）
- 独立区块用 `===` 分隔符突出，增强视觉和语义权重
- 放在所有工具指令和用户输入之前

### 决策 4: 不改动用户输入内容

**决策**: 不在注入标记层做字符级过滤、转义或截断。

**理由**:
- 第一层（规则过滤）留待 P1 实施，保持 P0 改动最小化
- 不做内容级别处理，避免误杀正常查询（如用户讨论"忽略某个指标"）
- LLM 在标记边界内自行判断，降低误报率

### 决策 5: retrieval.py 三个 prompt 模板统一改造

**决策**: 三个 `_build_*_prompt` 方法统一追加相同的安全声明，统一将 `用户问题：{query}` 改为 `<用户问题>\n{query}\n</用户问题>`。

**理由**:
- 三个方法的结构高度相似（系统指令 + 上下文 + 用户问题 + 检索结果 + 最终指令）
- 统一切入点降低遗漏风险
- 后续维护改动只需在一处模板

---

## 测试验证

| 文件 | 目的 |
|------|------|
| `tests/test_prompt_injection_guard.py` | 验证注入标记存在性 + system prompt 安全规则完整性 |
| `tests/tdd_all_optimizations.py` | 回归验证（确保正常查询不受影响） |
