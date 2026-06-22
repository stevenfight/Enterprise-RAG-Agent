# 任务清单: 长期记忆 JSON 文件持久化

> 编码: UTF-8 | 日期: 2026-06-22

---

## 任务

- [x] 1.1 修改 `AgentMemory.__init__`：新增 `session_id`、`persist_dir` 参数
- [x] 1.2 实现 `_load_persisted()`：从 JSON 文件加载最近 N 轮情景记忆
- [x] 1.3 实现 `_save_persisted()`：将情景记忆全量写入 JSON 文件
- [x] 1.4 在 `summarize_to_episodic()` 末尾调用 `_save_persisted()`
- [x] 1.5 更新 `app_streamlit.py`：`AgentMemory()` 传入 session_id
- [x] 1.6 更新 `config/agent_config.json`：开启 enable_long_term
- [x] 1.7 运行现有测试，确认无回归（27 PASS, 0 FAIL）
- [x] 1.8 更新文章 `03-三层记忆系统设计.md`：长期记忆状态改为已实现
