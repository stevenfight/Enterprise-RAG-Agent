# TDD 测试用例：统一 API 会话记忆创建入口

| 用例编号 | 测试目标 | 初始状态 | 通过标准 |
| --- | --- | --- | --- |
| TC-MEM-01 | 统一入口读取 memory 配置 | <span style="color:green">绿</span> | 实例参数与配置一致 |
| TC-MEM-02 | 统一入口传入 conversation_id | <span style="color:green">绿</span> | `AgentMemory.session_id` 等于会话 ID |
| TC-MEM-03 | 同一会话复用已有记忆 | <span style="color:green">绿</span> | 不重复创建实例 |
| TC-MEM-04 | 不同会话保持记忆隔离 | <span style="color:green">绿</span> | 两个会话使用不同实例和 session_id |
| TC-MEM-05 | 四个 API 不再直接使用默认 AgentMemory | <span style="color:green">绿</span> | 源码扫描确认仅统一辅助入口创建 |
| TC-MEM-06 | 既有后端回归测试无新增失败 | <span style="color:green">绿</span> | 冒烟 4/4 通过；相关后端测试 13 项通过 |
