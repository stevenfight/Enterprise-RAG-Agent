# Spec: 长期记忆 JSON 文件持久化

> 编码: UTF-8 | 变更: long-term-memory-persistence

---

## 概述

将 `AgentMemory` 的情景记忆从纯内存扩展到支持 JSON 文件持久化，使 `enable_long_term=True` 的会话在进程重启后能恢复历史会话摘要。

---

## Requirement: JSON 文件持久化写入

### Scenario: summarize_to_episodic 同步写文件
- **WHEN** `enable_long_term=True` 且 `session_id` 非空
- **AND** 调用 `summarize_to_episodic(query, answer)`
- **THEN** 情景摘要同时追加写入 `{persist_dir}/{session_id}.json`
- **AND** JSON 文件包含 `timestamp`、`query`、`answer_preview`、`steps_count`、`tools_used` 字段

### Scenario: JSON 文件自动创建
- **WHEN** `persist_dir` 或 JSON 文件不存在
- **THEN** 自动创建目录和文件

---

## Requirement: JSON 文件持久化加载

### Scenario: 初始化时从 JSON 加载
- **WHEN** `AgentMemory(session_id="abc", enable_long_term=True)` 初始化
- **AND** `data/long_term_memory/abc.json` 存在且包含 10 条记录
- **THEN** `self.episodic_memory` 初始化为最近 `episodic_memory_turns` 轮（默认 5 轮）
- **AND** 日志输出加载的轮数

### Scenario: JSON 文件不存在时优雅处理
- **WHEN** `AgentMemory(session_id="abc", enable_long_term=True)` 初始化
- **AND** `data/long_term_memory/abc.json` 不存在
- **THEN** `self.episodic_memory` 初始化为空列表
- **AND** 不抛异常

---

## Requirement: 向后兼容

### Scenario: session_id 为空时不做持久化
- **WHEN** `AgentMemory()` 或 `AgentMemory(session_id="")` 初始化
- **THEN** 不读取任何 JSON 文件
- **AND** `summarize_to_episodic` 不写入 JSON 文件
- **AND** 行为与旧版完全一致

---

## Requirement: 多 session 隔离

### Scenario: 不同 session_id 读写不同文件
- **WHEN** 两个 AgentMemory 实例分别使用 session_id="s1" 和 "s2"
- **THEN** s1 写入 `s1.json`，s2 写入 `s2.json`
- **AND** s1 的 episodic_memory 不影响 s2
