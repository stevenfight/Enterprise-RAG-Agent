# TDD 台账

| 编号 | 初始状态 | 契约 | 验证证据 |
| --- | --- | --- | --- |
| S-T1 | GREEN | 跨源 SSE 必须携带 HttpOnly 研究会话，且 URL 不含会话或 API Key | 先运行 RED：期望凭据但收到 `undefined`；恢复后 `chatService/apiClient` 定向回归 7 passed |
| S-T2 | GREEN | `react-router-dom` 与 `react-router` 必须回到 7.18.3 锁定基线 | `npm ci --ignore-scripts` 后 `npm ls` 输出两个包均为 7.18.3；源码与锁文件相对 HEAD 无差异 |
| S-T3 | GREEN | 本变更不得触及后端、部署、真实凭据或路由行为 | `npm run lint`、`npm run build`、`git diff --check` 通过；未执行后端、部署或远程操作 |
