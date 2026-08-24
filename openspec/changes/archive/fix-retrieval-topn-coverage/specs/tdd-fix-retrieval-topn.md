# TDD 测试用例: 修复多公司检索 top_n 过小

> 编码: UTF-8
> 图例: 红色 = 未验证（待实现）, 绿色 = 已通过
> 验证方式: unittest（`python tests/tdd_retrieval_topn_fix.py`）

---

| ID | 测试用例 | 输入 | 期望输出 | 状态 |
|----|---------|------|---------|:--:|
| TC-01 | 多公司 + top_n 偏小 | `top_n=3, companies=[移动,电信,联通,中芯国际]` | `4` | 绿色 |
| TC-02 | 多公司 + top_n 充足 | `top_n=5, companies=[移动,电信,联通]` | `5` | 绿色 |
| TC-03 | 单公司不扩容 | `top_n=3, companies=[移动]` | `3` | 绿色 |
| TC-04 | 空公司列表 | `top_n=3, companies=[]` | `3` | 绿色 |
| TC-05 | top_n 等于公司数 | `top_n=4, companies=[移动,电信,联通,中芯国际]` | `4` | 绿色 |
| TC-06 | top_n=1 多公司 | `top_n=1, companies=[移动,电信]` | `2` | 绿色 |
