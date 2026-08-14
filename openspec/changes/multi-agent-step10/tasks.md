# 任务清单: 前端多 Agent 流式可视化（阶段十）

> 编码: UTF-8

---

## 任务列表

| 序号 | 任务 | 产出 | 状态 |
|:--:|------|------|:--:|
| 1 | 创建 OpenSpec 变更记录 | proposal.md / design.md / tasks.md / specs/tdd-step10.md | 已完成 |
| 2 | 编写 TDD 用例规格（全线标红） | specs/tdd-step10.md | 已完成 |
| 3 | 扩展前端类型定义 | frontend/src/types/chat.ts | 已完成 |
| 4 | 实现事件识别 + reducer 纯函数 | frontend/src/utils/agentEvent.ts | 已完成 |
| 5 | 编写 Vitest 单元测试（预期先红） | frontend/src/utils/__tests__/agentEvent.test.ts | 已完成 |
| 6 | 运行测试并转绿 | npm test 输出 | 已完成 |
| 7 | 接入 SSE 事件消费 | ChatPage.tsx + chatStore.ts | 已完成 |
| 8 | 扩展多 Agent 步骤展示 | MessageBubble.tsx | 已完成 |
| 9 | 前端构建验证 | npm run build (tsc) | 已完成（见下方说明） |
| 10 | TDD 转绿 + 更新文档 | specs/tdd-step10.md 状态更新 | 已完成 |

---

## 验收标准

- `frontend/src/utils/__tests__/agentEvent.test.ts` 全部 15 项用例通过：
  - SP10-A 事件类型识别 2 项
  - SP10-B 多 Agent 事件映射 8 项
  - SP10-C 单 Agent 事件回归 5 项
- `npm test` 可运行新测试且无回归（实际：4 个测试文件 62 项用例全部通过）
- `npm run build`（tsc）编译零错误 —— 本次变更未引入任何新增类型错误；仓库中存在 12 项历史遗留 tsc 错误（DagFlow / ChatContainer / KnowledgePage / vite.config.ts 等既有文件），不属于本变更范围
- 后端 `src/`、`config/` 零改动
