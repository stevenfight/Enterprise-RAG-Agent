# 任务清单: Planner 运营商别名识别（三大运营商）

> 编码: UTF-8

- [x] 1. 创建 OpenSpec 变更文档 (proposal + spec + tdd + tasks)
- [x] 2. 编写 TDD 测试（标红）并确认失败
- [x] 3. planner.py 新增 COMPANY_ALIASES 与 _extract_companies
- [x] 4. 运行 TDD 测试标绿
- [x] 5. 重启后端并验证 /api/agent/plan 返回正确公司
- [x] 6. 更新文档状态
- [x] 7. 增强 _build_multi_compare: 涨幅/图表关键词 → 追加 calculator/chart 子任务 (AL-06~AL-09)
- [x] 8. 多公司优先分类调整 + CHART_KEYWORDS 新增 (AL-10 验证趋势不回归)
- [x] 9. multi_compare 增加前置 retrieve 检索节点, 链路: retrieve→compare→(calc)→(chart)→verify
- [x] 10. COMPARE_KEYWORDS 移除连接词"和/与/及/以及"防单公司误判; trend 分类放宽为"图表且(计算或公司)" (AL-11)
