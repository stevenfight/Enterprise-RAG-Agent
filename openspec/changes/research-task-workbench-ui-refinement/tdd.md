# TDD：研究任务工作台界面收口

本文件与 `spec.md` 对照维护。初始用例先标记为 RED，实施并核查通过后改为 GREEN。

| 用例 | 初始状态 | 验收 | 状态 |
| --- | --- | --- | --- |
| RTW-T01 | 页面有任务列表 | 显示“任务列表（N）”或等价的真实数量，且任务按钮仍能选择任务 | GREEN |
| RTW-T02 | 页面选中任务 | 任务导航和任务详情分别处于 `research-task-list-panel`、`research-task-details` 结构中 | GREEN |
| RTW-T03 | 页面有报告 | 报告详情保留报告版本、声明依据和既有签发操作 | GREEN |
| RTW-T04 | 页面没有报告 | 报告详情、证据和图表仅显示真实空态，不出现推测内容 | GREEN |
| RTW-T05 | 无任务页面 | 主地标、工作台区域、刷新按钮和空态可访问名称保持稳定 | GREEN |
| RTW-T06 | 研究员提交任务 | 研究目标、范围、预算字段和提交 API 参数不变 | GREEN |
| RTW-T07 | 审批人处理任务 | 批准、驳回、重试、遗留任务处置、冲突裁决和报告签发入口不变 | GREEN |
| RTW-T08 | 样式构建 | 生产构建、lint 和 impeccable detector 不产生阻断错误 | GREEN |

## 核查记录

- 定向页面与可访问性测试：2 个文件、27 项通过。
- 前端全量测试：54 个文件、299 项通过。
- `npm run lint`：通过。
- `npm run build`：通过；仅保留既有大 chunk 提示，不属于本次页面改动阻断。
- impeccable detector：`frontend/src/pages/ResearchTasksPage.tsx` 返回空结果。
- 本地浏览器：桌面空态可视核查通过；移动视口测得 `document.body.scrollWidth === window.innerWidth`，未发现页面级横向溢出；本地后端未启动，因此未将空数据页面冒充为真实报告数据验收。
