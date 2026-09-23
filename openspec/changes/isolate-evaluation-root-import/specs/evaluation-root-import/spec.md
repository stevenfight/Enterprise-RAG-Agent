## ADDED Requirements

### Requirement: 评测模块 SHALL 避免不必要的根包初始化副作用

评测 schema、数据集和 CLI 的导入 SHALL 不主动初始化 RAG/Agent 监控或模型依赖；既有根包公开导出 SHALL 保持按需兼容。

#### Scenario: 导入评测 schema

- **WHEN** 在独立 Python 进程中导入 `src.evaluation.schema`
- **THEN** 导入成功
- **AND** 不输出监控初始化日志

#### Scenario: 访问既有根包导出

- **WHEN** 调用 `from src import RAGGenerator, AgentResult, ToolRegistry`
- **THEN** 三个名称均可成功解析
- **AND** 未知名称仍抛出 `AttributeError`
