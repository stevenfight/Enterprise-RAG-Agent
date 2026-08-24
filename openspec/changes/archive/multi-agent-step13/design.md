# 设计文档: SSE 流式一致性优化（阶段十三）

> 编码: UTF-8

---

## 一、问题链路

### 1.1 单 Agent 缺少流式答案

```
_stream_single_agent()
  └─ for event in agent.run_stream(...):   # 转发 thought/action/observation/answer
       └─ answer 一次性输出，无 answer_chunk 打字机效果
```

对比多 Agent：

```
_stream_multi_agent()
  └─ answer_chunk(N 次按句拆分) → answer（完整）
```

### 1.2 完成事件冗余

```
DelegateTool._run_worker_task()
  ├─ run() 内部 StepCallback.on_done → worker_done（前端消费）✓
  ├─ 成功路径 put_nowait(worker_complete)   ← 前端不识别，冗余
  └─ 失败路径 put_nowait(worker_complete)   ← 前端不识别，冗余

_stream_multi_agent()
  └─ workers_done 推送（前端 default 忽略，冗余）
```

## 二、修复设计

### 2.1 提取拆句纯函数

```python
def _split_answer_chunks(text: str) -> list:
    """按中文句末标点拆句，用于 answer_chunk 流式推送"""
    if not text:
        return []
    sentences = re.split(r'([。\n；;])', text)
    chunks = []
    for i in range(0, len(sentences), 2):
        chunk = sentences[i]
        if i + 1 < len(sentences):
            chunk += sentences[i + 1]
        if chunk.strip():
            chunks.append(chunk.strip())
    return chunks
```

### 2.2 单 Agent 补 answer_chunk

在 `_stream_single_agent` 循环中，当 `event_type == "answer"` 时，先按句推送 `answer_chunk`，再转发 `answer`：

```python
if event_type == "answer":
    final_answer = event.get("content", "") or event.get("answer", "")
    for chunk in _split_answer_chunks(final_answer):
        yield f"data: {json.dumps({'type': 'answer_chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
        await _asyncio.sleep(0)
    # 再推 answer
```

### 2.3 清理 DelegateTool 完成事件

- 成功路径：删除 `worker_complete` 推送（`run()` 已通过 `on_done` 推 `worker_done`）。
- 失败路径：把 `worker_complete` 改为 `worker_done`，字段对齐 `StepCallback.on_done`（`success=False`）。

### 2.4 删除 workers_done

删除 `_stream_multi_agent` 中的 `workers_done` 推送，前端类型同步清理。

## 三、测试设计

### SP13-A: `_split_answer_chunks`（3 项）
1. 空串 → `[]`
2. 单句无标点 → 单元素
3. 多句含标点 → 按句拆分

### SP13-B: 单 Agent 流式推 answer_chunk（1 项）
mock `agent.run_stream` 返回固定 `answer` 事件，断言 `answer_chunk` 在 `answer` 之前出现。

### SP13-C: DelegateTool 完成事件清理（2 项）
1. 成功路径：event_queue 无 `worker_complete` 事件
2. 失败路径：event_queue 有 `worker_done(success=False)` 事件

### SP13-D: 删除 workers_done（1 项）
静态断言 `src/api_service.py` 源码不含 `workers_done` 字符串。

## 四、一致性保证

- 单 Agent 与多 Agent 均通过 `answer_chunk` → `answer` 的时序流式输出答案。
- 多 Agent 完成事件统一为 `worker_done`（由 `StepCallback.on_done` 或 DelegateTool 失败兜底推送）。
