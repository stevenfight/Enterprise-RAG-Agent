# TDD：前端工作台整体一致性收口

本文件与 `spec.md` 对照维护。初始用例先标记为 RED，实施并核查通过后改为 GREEN。

| 用例 | 初始状态 | 验收 | 状态 |
| --- | --- | --- | --- |
| FWC-T01 | 非聊天页面布局 | 非聊天路由的主内容区保留 `overflow: auto` 且页面级 `padding` 为 0 | GREEN |
| FWC-T02 | 研究任务顶栏 | `/research` 显示“研究任务” | GREEN |
| FWC-T03 | 页面容器 | `PageShell` 居中且保留唯一响应式内边距职责 | GREEN |
| FWC-T04 | 主题浏览器表面 | 全局样式提供 `selection` 与可见 `focus-visible` 规则并引用主题变量 | GREEN |
| FWC-T05 | 侧栏表面 | 亮色侧栏使用中性 `pageSidebarLight`，不使用早期装饰性渐变 | GREEN |
| FWC-T06 | 研究任务空态 | 无选中任务时，详情区域提供真实空态说明 | GREEN |
| FWC-T07 | 回归验证 | 全量测试、lint、构建、检测和桌面/移动视觉核查无阻断项 | GREEN |

## 核查记录

- RED 阶段确认了双层内边距、研究页标题回退、亮色侧栏渐变、主题浏览器表面缺失及任务详情空白画布五项缺口。
- 定向测试：8 个文件、60 项通过。
- `npm run lint`：通过；`npm run build`：通过，仅保留既有大 chunk 提示。
- impeccable detector：共享布局、标题栏、侧栏、页面容器与研究任务页返回空结果。
- 桌面与移动端本地浏览器：研究页标题正确，空任务时有任务详情说明；移动端 `documentScrollWidth === viewport`，无页面级横向溢出。
- 2026-09-22 全量 Vitest：54 个测试文件、305 项通过；`npm run lint` 和 `npm run build` 通过。构建仅保留既有大 chunk 提示；测试日志中的 Ant Design 弃用提示、React `act` 提示和 jsdom 伪元素提示均未造成失败。
