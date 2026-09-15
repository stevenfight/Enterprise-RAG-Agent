# 设计

1. 图表金额单位测试直接构造最小的旧表格图表对象，调用既有 `VerifiedFinancialFactRegistry.project_chart_artifact()`，断言已登记的三大运营商收入投影仍把中国移动写为 `10,408` 亿元。测试不读取 `data/charts/`。
2. v5.19 指纹测试只在仓库存在 `.git` 且系统可执行 `git` 时运行；缺任一前置时使用 pytest 的明确 skip 原因。skip 不表示兼容性通过。
3. 不改业务实现。定向测试在 Git 工作树中必须通过；无 Git archive 环境应显示一项明确 skip，其他可运行测试继续执行。
