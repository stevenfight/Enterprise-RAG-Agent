# 修复 Agent 工具契约测试的包导入边界

## 背景

`tests/test_agent_tools.py` 以顶层 `tools.verify_tool` 导入带有 `..financial_unit_rules` 相对导入的模块，会在脚本直跑或 pytest 环境中触发 `attempted relative import beyond top-level package`。

## 目标

让契约测试通过 `src.tools` 包边界加载 VerifyTool，并保留直接执行测试脚本时的项目根路径。

## 非目标

- 不改变任何 Agent 工具实现或运行时导出。
- 不修改依赖、部署、凭据、服务器或主分支。
