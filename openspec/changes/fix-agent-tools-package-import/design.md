# 设计

测试入口在 `sys.path` 中显式加入项目根目录，并将 VerifyTool 的导入从顶层 `tools.verify_tool` 改为包内 `src.tools.verify_tool`。其余工具导入保持现状，避免扩大测试改动范围。
