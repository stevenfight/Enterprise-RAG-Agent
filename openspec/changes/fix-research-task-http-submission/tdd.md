# TDD：HTTP 研究任务提交修复

| ID | 状态 | 测试目标 | RED 原因 |
| --- | --- | --- | --- |
| RTH-T01 | 绿色（通过） | 缺少 `crypto.randomUUID` 的 HTTP 环境仍可提交任务 | RED：`ResearchTasksPage.test.tsx` 在 `crypto={}` 时未调用提交服务；GREEN：定向套件 24 passed。 |
| RTH-T02 | 绿色（通过） | 服务端 422 原因展示给用户 | 变更前捕获分支固定显示泛化提示；GREEN：模拟 `detail.message` 后页面展示服务端原因，定向套件 24 passed。 |
| RTH-T03 | 绿色（通过） | 缺少 `crypto.randomUUID` 时批准待审批任务仍能发出命令 | RED：`E-T32` 在 `crypto={}` 时批准服务未被调用；GREEN：统一客户端标识生成后定向套件 24 passed，lint 与 build 通过。 |

## 验证记录

- `npm test -- --run src/pages/__tests__/ResearchTasksPage.test.tsx`：24 passed。
- `npm run lint`：通过。
- `npm run build`：通过；仅保留既有大产物体积警告。
