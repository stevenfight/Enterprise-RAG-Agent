# TDD 台账

| 编号 | 初始状态 | 契约 | 验证证据 |
| --- | --- | --- | --- |
| V-T1 | GREEN | M0/M1 纵向链路必须保留文档、页面制品、视觉定位和访问边界 | 24 个 M0/M1、页面制品与视觉测试文件共 80 passed；API/检索交叉回归 78 passed |
| V-T2 | GREEN | 视觉 Provider、缓存和事实准入不得泄露凭据或伪造视觉证据 | 视觉 Provider/安全/事实/图表表格扫描页测试在 80 passed 中通过；未调用真实 Provider |
| V-T3 | GREEN | 发布集提升、解析、退休和删除必须保持 generation 一致性 | 19 个发布集测试文件 72 passed，索引发布额外 11 passed |
| V-T4 | GREEN | 验收不得将 `data/v7`、临时目录或真实 Provider 调用纳入提交 | `data/v7/` 已加入 `.gitignore` 并由 `git check-ignore` 验证；无真实 Provider 调用 |
