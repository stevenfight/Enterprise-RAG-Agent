# 任务清单：F2 评测数据绑定清单

- [x] 1.1 先新增清单缺失、路径漂移、哈希漂移和成功绑定的 RED 测试。
- [x] 1.2 实现只读绑定清单审计器。
- [x] 1.3 将 `--source-binding-manifest` 接入评测 CLI，并保持未传参兼容。
- [x] 1.4 生成候选种子评测集的绑定清单；不生成或复制完整评测集与 PDF。
- [x] 1.5 运行绑定、来源、评测、OpenSpec、编译、UTF-8 和乱码回归。（绑定测试 5 passed；关联回归合计 54 passed；OpenSpec 18 passed、0 failed；compileall、diff check 通过。）
- [x] 1.6 更新 v7 tasks/TDD、文件化计划和交接文档；不提升发布状态、不推送远端。
