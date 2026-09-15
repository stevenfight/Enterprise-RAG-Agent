# TDD：F1 测试可复现性

| 用例 | 初始状态 | 期望 |
| --- | --- | --- |
| RPT-S01 | 🟢 GREEN | 图表金额单位测试不依赖 `data/charts/`，而验证已登记图表投影将中国移动营业收入写为 `10,408`。候选 Git 工作树的受影响集合验证为 8 passed。 |
| RPT-S02 | 🟢 GREEN | Git 工作树中 v5.19 指纹测试继续执行；缺 `.git` 或 Git 可执行文件时明确 skip，不将 archive 环境误报为断言失败。最小 archive 验证为 6 passed、1 skipped。 |
