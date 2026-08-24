# TDD 测试用例: Planner 运营商别名识别（三大运营商）

> 编码: UTF-8
> 图例: 红色 = 未验证（待实现）, 绿色 = 已通过
> 验证方式: python tests/tdd_planner_alias.py (unittest)

---

## 模块 AL: 运营商别名识别

| ID | 测试用例 | 操作 | 期望 | 状态 |
|----|---------|------|------|:--:|
| AL-01 | 别名「三大运营商」展开为三家 | plan("对比三大运营商2024年的营业收入") | company_names = [中国移动, 中国联通, 中国电信] | 绿色 |
| AL-02 | 别名查询分类为 multi_compare | 同 AL-01 | category = multi_compare | 绿色 |
| AL-03 | compare 子任务携带完整公司列表 | 同 AL-01 | tool_params["companies"] = 三家运营商 | 绿色 |
| AL-04 | 精确公司名查询不受影响 | plan("中国移动和中国联通2024年营收对比") | company_names = [中国移动, 中国联通] | 绿色 |
| AL-05 | 模糊查询公司仍为空 | plan("2024年营收增长了么") | company_names 为空，逻辑不变 | 绿色 |
| AL-06 | 多公司+涨幅+图表 → 完整子任务链 | plan("三大运营商2024年营收分别是多少，涨幅是多少，使用图表展示") | category=multi_compare, tool_names=[retrieve, compare, calculator, chart, verify] | 绿色 |
| AL-07 | 涨幅计算子任务参数 | 同 AL-06 | calculator 子任务 operation=yoy_growth | 绿色 |
| AL-08 | 图表子任务参数 | 同 AL-06 | chart 子任务 chart_type=bar | 绿色 |
| AL-09 | 无涨幅无图表对比不回归 | plan("对比三大运营商2024年的营业收入") | tool_names=[retrieve, compare, verify] | 绿色 |
| AL-10 | 单公司+趋势仍按趋势分类 | plan("中国移动2024年营收增长趋势图") | category=trend (多公司优先不误伤) | 绿色 |
| AL-11 | 单公司+变化+图表 → trend | plan("中芯国际近几年主营业务及营收变化，图表展示") | category=trend, tool_names=[retrieve, calculator, chart] | 绿色 |

> 说明: 测试直接调用 `src.planner.TaskPlanner.plan()`，不依赖网络与外部服务。
> 补充: 实现时将 `COMPANY_NAMES` 由 set 改为 list，修复了既有 set 迭代顺序不稳定问题（此前「中国移动和中国联通」可能解析为「中国联通、中国移动」）。
> 补充2: `_build_multi_compare` 增强，新增 `CHART_KEYWORDS`，`CALC_KEYWORDS` 增加"涨幅/增长/同比"；多公司优先分类，涨幅/图表需求由 compare 后的 calculator/chart 子任务承载。
