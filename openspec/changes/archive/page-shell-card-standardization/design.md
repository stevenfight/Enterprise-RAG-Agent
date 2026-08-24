# 设计方案：页面容器与卡片规范统一

## 1. 统一设计令牌

在全局 CSS 中增加页面级语义类：

- `.page-shell`：页面内容根容器，最大宽度 1200px，水平居中，统一桌面端内边距。
- `.page-header`：标题区，统一标题、描述和底部间距。
- `.page-card`：普通业务卡片，使用主题背景、边框、圆角和轻阴影。
- `.page-card--section`：页面区块卡片，保留 Ant Design Card 的内容和标题能力。
- `.page-stack`：页面区块垂直间距。

具体尺寸：

- 桌面端最大宽度：1200px。
- 桌面端水平内边距：32px。
- 平板端水平内边距：20px。
- 移动端水平内边距：16px。
- 页面标题区底部间距：24px。
- 页面区块间距：24px。
- 普通卡片圆角：14px。
- 卡片边框使用现有 `theme.ts` 的 border token 对应色值。

## 2. 组件设计

新增 `frontend/src/components/common/PageShell.tsx`：

- `PageShell` 负责页面最大宽度和内边距。
- `PageHeader` 负责统一页面图标、标题和描述。
- 两个组件只负责结构和 className，不承载业务逻辑。
- 主题颜色通过 CSS 变量和 Ant Design token 继承，不新增状态管理。

## 3. 页面迁移

- `DagBoardPage`：替换根容器和标题区，查询卡片及图例卡片增加统一 `page-card` class。
- `ChartsPage`：替换根容器和标题区，筛选卡片和图表卡片使用统一卡片规范。
- `KnowledgePage`：替换根容器和标题区，上传区域和表格保持功能不变，仅统一外层卡片与间距。
- `SettingsPage`：替换根容器和标题区，现有配置卡片统一间距和圆角。
- `AppLayout`：保留聊天页铺满逻辑，非聊天路由继续保留内容区滚动，不重复增加全局 padding。

## 4. 兼容性

- 不引入新的 npm 依赖。
- 不改变 API、SSE、Zustand 或页面业务逻辑。
- 移动端通过 `responsive.css` 调整 `.page-shell` 内边距和卡片间距。
- 通过 `prefers-reduced-motion` 不在本次新增持续动画。
