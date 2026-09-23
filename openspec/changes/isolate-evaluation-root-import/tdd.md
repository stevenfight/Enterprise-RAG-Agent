# TDD 记录

- [GREEN] `python -c "import src.evaluation.schema; print('evaluation_import=ok')"`：成功且未出现 `[monitoring]`。
- [GREEN] `python -c "from src import RAGGenerator, AgentResult, ToolRegistry"`：根包公开导出兼容。
- [GREEN] 评测质量门禁、完整数据集、人工签核、财务事实和 Agent 工具定向回归：70 passed。
- [GREEN] `python -m compileall -q src/__init__.py`：通过。
