# 任务

- [x] RPT-1 记录 RED：干净部署 archive 的完整后端集合因运行时图表 JSON 与 Git 前置失败，不能视为业务回归。
- [x] RPT-2 将图表金额单位断言迁移到既有已核验事实投影契约，不读取运行时目录。
- [x] RPT-3 将 v5.19 Git 指纹断言限定为具备 Git 前置的工作树；archive 中明确 skip。
- [x] RPT-4 在候选 Git 工作树运行两个受影响测试并复核无 Git 环境的 skip 行为（Git 工作树 8 passed；最小 archive 6 passed、1 skipped）。
- [x] RPT-5 在含 `.git`、`v5.19` 标签和锁定依赖的干净 Python 3.11 环境复跑完整后端集合（592 passed、1 skipped、退出码 0）。
