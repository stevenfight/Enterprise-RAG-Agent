# TDD: 长期记忆 JSON 文件持久化

> 编码: UTF-8 | 变更: long-term-memory-persistence
> 
> 标记规则: RED = 未实现/未通过 | GREEN = 已实现且通过

---

## 测试状态登记表

| 用例编号 | 测试名称 | 状态 | 说明 |
|----------|----------|------|------|
| TC-LT01 | 初始化加载已存在的 JSON 文件 | GREEN | session_id 非空且 enable_long_term=True 时从 JSON 加载 |
| TC-LT02 | JSON 文件不存在时初始化为空 | GREEN | 文件不存在不报错，episodic_memory 为空 |
| TC-LT03 | summarize_to_episodic 写入 JSON 文件 | GREEN | 写入后 JSON 文件包含摘要数据 |
| TC-LT04 | 多次写入追加不覆盖 | GREEN | 连续 3 次 summarize 后 JSON 有 3 条记录 |
| TC-LT05 | session_id 为空时不持久化 | GREEN | 不回写 JSON，不读取 JSON |
| TC-LT06 | 加载时只保留最近 N 轮 | GREEN | JSON 有 10 条记录，episodic_memory 仅加载最近 5 条 |
| TC-LT07 | 多 session 数据隔离 | GREEN | s1 和 s2 互相不可见 |
| TC-LT08 | Unicode 中文正确读写 | GREEN | 中文 query/answer 写入 JSON 后读取不乱码 |
