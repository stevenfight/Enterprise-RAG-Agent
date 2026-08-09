# 设计文档: 长期记忆 JSON 文件持久化

> 编码: UTF-8 | 日期: 2026-06-22

---

## 架构概览

```
summarize_to_episodic()
  → self.episodic_memory.append(summary)   # 原有：写内存
  → self._save_persisted()                  # 新增：写 JSON 文件

AgentMemory.__init__(session_id="xxx")
  → self._load_persisted()                  # 新增：从 JSON 文件加载
  → 加载最近 episodic_memory_turns 轮
```

## 存储结构

```
data/long_term_memory/
├── streamlit_session_abc123.json
├── streamlit_session_def456.json
└── ...
```

每个 JSON 文件格式：

```json
[
  {
    "timestamp": "2026-06-22T14:30:00",
    "query": "中芯国际营收是多少？",
    "answer_preview": "中芯国际2024年营收为1250.38亿元",
    "steps_count": "3",
    "tools_used": "retrieve, calculator"
  }
]
```

## 接口变更

`AgentMemory.__init__` 新增可选参数：

```python
def __init__(
    self,
    working_memory_limit: int = 10,
    episodic_memory_turns: int = 5,
    enable_long_term: bool = False,
    session_id: str = "",           # 新增: session 标识
    persist_dir: str = "data/long_term_memory",  # 新增: 持久化目录
):
```

## 向后兼容

- `session_id` 为空字符串时不持久化（行为与旧版完全一致）
- `enable_long_term` 与旧含义一致
- 所有现有测试无需修改（默认不传入 session_id）
