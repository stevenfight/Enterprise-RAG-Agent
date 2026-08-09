# 变更提案: 长期记忆 JSON 文件持久化

> 编码: UTF-8 | 日期: 2026-06-22 | 状态: 已完成

---

## 动机

当前长期记忆 (`long_term_memory`) 仅在内存中存储静态公司简介字典，进程重启后丢失。文章《三层记忆系统设计》中描述"长期记忆：跨会话持久化"与代码现状不符，需要实现真正的持久化。

## 目标

- 每个 session 写入独立的 JSON 文件（`data/long_term_memory/{session_id}.json`）
- `summarize_to_episodic()` 时同步追加写入 JSON 文件
- `AgentMemory` 初始化时自动从 JSON 文件加载最近 N 轮情景记忆
- 多个 session 天然隔离，无并发冲突

## 技术路线

- 纯 JSON 文件读写（`json.dump` / `json.load`），不引入外部依赖
- 存储路径: `data/long_term_memory/`
- 初始化时若 JSON 文件存在则加载，否则从空列表开始

## 影响范围

| 文件 | 变更类型 |
|------|----------|
| `src/agent_memory.py` | 核心变更：新增持久化读写方法 |
| `app_streamlit.py` | 调用侧：传入 session_id |
| `config/agent_config.json` | 配置：开启 long_term |
| `tests/test_agent_memory.py` | 新增持久化测试用例 |
