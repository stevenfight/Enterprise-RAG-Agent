# 任务清单: ReAct 空结果安全阀

> 编码: UTF-8

---

## 阶段一: 空结果检测增强

- [x] 1.1 `_is_empty_result()` 新增 `[工具执行失败]` 前缀判定
- [x] 1.2 `_is_empty_result()` 新增 `未检索到相关数据` 关键词判定
- [x] 1.3 判定分支添加 INFO 级日志（空字符串 / 失败前缀 / 具体标记）
- [x] 1.4 运行 `python tests/test_agent_mock_boundary.py` 验证 13 个标记

## 阶段二: 计数器与日志

- [x] 2.1 `empty_result_count` 累加逻辑保持不变
- [x] 2.2 `empty_result_count` 重置时新增 INFO 日志"计数器已重置为0"
- [x] 2.3 运行 `python tests/test_agent_mock_boundary.py` 验证计数器全状态

## 阶段三: 强制降级修复

- [x] 3.1 `_generate_forced_answer` 方法签名增加 `reasoning_chain` 参数
- [x] 3.2 `run()` 调用点传入 `reasoning_chain`
- [x] 3.3 运行 `python tests/test_agent_mock_boundary.py` 验证无 NameError
- [x] 3.4 运行 `python tests/test_agent_boundary_verify.py` 验证合成空结果触发 forced_stop

## 阶段四: 端到端验证

- [x] 4.1 真实 LLM 查询域外公司，验证是否触发空结果路径
- [x] 4.2 monkey-patch `_execute_action` 全部返回 `[工具执行失败]`，验证降级答案非空
- [x] 4.3 运行全量回归测试，确保无影响

## 阶段五: 文档与引流

- [x] 5.1 博客文章精简"坑 3"为 8 行列表，与坑 1/坑 2 风格对齐
- [x] 5.2 效果验证表新增"空结果强制终止"行
- [x] 5.3 经验总结新增第 6 条"罕见路径必须测试"
- [x] 5.4 引流汇总修正 max_steps=10→5、行数 200→500、新增坑 3 钩子
