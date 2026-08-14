# TDD 测试用例: SSE 流式一致性优化（阶段十三）

> 编码: UTF-8
> 约定: <span style="color:red">红色</span> = 未通过, <span style="color:green">绿色</span> = 已通过

---

## 一、测试文件规划

| 文件 | 测试范围 |
|------|---------|
| `tests/tdd_multi_agent_step13.py` | SP13-A / SP13-B / SP13-C / SP13-D（Python unittest，不依赖 LLM API） |

---

## 二、测试用例

### SP13-A: `_split_answer_chunks` 拆句函数

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-13-A-01 | 空串 | 调用 `_split_answer_chunks("")` | 返回 `[]` | <span style="color:green">GREEN</span> |
| TC-13-A-02 | 单句无标点 | 调用 `_split_answer_chunks("营收100亿元")` | 返回 `["营收100亿元"]` | <span style="color:green">GREEN</span> |
| TC-13-A-03 | 多句含标点 | 调用 `_split_answer_chunks("中国移动营收最高。其次是中国电信。")` | 返回按句拆分结果 | <span style="color:green">GREEN</span> |

---

### SP13-B: 单 Agent 流式推 answer_chunk

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-13-B-01 | answer_chunk 先于 answer | mock `run_stream` 返回 answer 事件，收集生成器事件 | `answer_chunk` 出现在 `answer` 之前 | <span style="color:green">GREEN</span> |

---

### SP13-C: DelegateTool 完成事件清理

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-13-C-01 | 成功路径无 worker_complete | mock Worker run 成功，带 event_queue 调用 `_run_worker_task` | event_queue 无 `worker_complete` 事件 | <span style="color:green">GREEN</span> |
| TC-13-C-02 | 失败路径推 worker_done | mock Worker run 抛异常，max_retries=0 | event_queue 有 `worker_done` 且 success=False | <span style="color:green">GREEN</span> |

---

### SP13-D: 删除 workers_done

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-13-D-01 | 无 workers_done 残留 | 静态读取 `src/api_service.py` 源码 | 不含 `workers_done` 字符串 | <span style="color:green">GREEN</span> |

---

## 三、测试统计

| 规范 | 测试用例数 | 已通过 | 未通过 |
|------|:--:|:--:|:--:|
| SP13-A | 3 | 3 | 0 |
| SP13-B | 1 | 1 | 0 |
| SP13-C | 2 | 2 | 0 |
| SP13-D | 1 | 1 | 0 |
| **合计** | **7** | **7** | **0** |
