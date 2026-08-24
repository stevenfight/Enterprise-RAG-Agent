# 技术设计: 多 Agent 回答来源标注具体页码（阶段十一）

> 编码: UTF-8

---

## 1. 问题链路

```
RetrieveTool._format_results
  pages [23,24,25] → "第23-25页"   （已存在，注入 Observation）
        ↓
LLM 读取 Observation
        ↓
Prompt 规则：只要求「标注来源」 ← 缺陷点：未要求「标注页码」
        ↓
Final Answer 来源列表缺页码
```

---

## 2. 修复设计

### 2.1 prompt 规则强化

把「标注来源」相关规则统一强化为「标注来源及具体页码」，并给出格式示例。

| 节 | 原规则 | 新规则 |
|----|--------|--------|
| `default` 规则 3 | 回答中涉及的数字必须标注来源 | 回答中涉及的数字必须标注来源及具体页码（格式如「中国移动2024年度报告 第23页」） |
| `data_agent` 规则 3 | 回答中涉及的数字必须标注来源 | 同上（加页码） |
| `compare_agent` 规则 3 | 对比结果中涉及的数字必须标注来源 | 同上（加页码） |
| `verify_agent` 规则 3 | 审核报告中涉及的数字必须标注来源 | 同上（加页码） |
| `orchestrator` Final Answer | 汇总的最终答案，包含来源引用 | 汇总的最终答案，包含来源引用（含具体页码） |

### 2.2 fallback 一致性

`src/agent_core.py` 的 `_default_system_prompt` 规则 3 同步更新，与 `config/agent_prompts.yaml` 的 `default` 节保持一致（项目约定见 yaml 文件头注释）。

---

## 3. 测试设计

测试文件 `tests/tdd_multi_agent_step11.py`：

### SP11-A 页码格式化回归（3 项）
直接实例化 `RetrieveTool` 调用 `_format_results`，输入不同 `pages` 断言输出：
- `[]` → `页码未知`
- `[23]` → `第23页`
- `[23,24,25]` → `第23-25页`

### SP11-B prompt 页码规则静态断言（5 项）
读取 `config/agent_prompts.yaml`，断言 `default / data_agent / compare_agent / verify_agent / orchestrator` 各节 `template` 含「页码」关键词。

---

## 4. 影响面

- 仅影响 LLM 输出风格（来源带页码），不影响检索、路由、计算逻辑。
- 不改变 SSE 事件协议、前端渲染。
- 不引入新的运行依赖。
