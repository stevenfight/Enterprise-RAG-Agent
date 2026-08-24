# TDD 测试用例: 主题切换按钮 + 消息动效微交互

> 编码: UTF-8
> 图例: 红色 = 未验证（待实现）, 绿色 = 已通过
> 验证方式: Vitest + React Testing Library

---

## 模块 B: HeaderBar 主题切换

| ID | 测试用例 | 操作 | 期望 | 状态 |
|----|---------|------|------|:--:|
| TB-01 | 渲染主题切换按钮 | 渲染 HeaderBar | 存在按钮含 sun/moon 图标 | 绿色 |
| TB-02 | 点击切换暗色 | 点击按钮 | toggleTheme 被调用 | 绿色 |
| TB-03 | 亮色显示太阳图标 | isDark=false | 显示 SunOutlined | 绿色 |
| TB-04 | 暗色显示月亮图标 | isDark=true | 显示 MoonOutlined | 红色 |

> 注: TB-04 实现代码已支持（HeaderBar.tsx 中条件渲染 MoonOutlined），但测试用例因 mock 简化暂未编写，后续补充。

## 模块 C: MessageBubble 微交互

| ID | 测试用例 | 操作 | 期望 | 状态 |
|----|---------|------|------|:--:|
| MB-01 | hover 显示复制按钮 | hover AI 消息 | 复制按钮出现 | 绿色 |
| MB-02 | 点击复制写入剪贴板 | 点击复制按钮 | navigator.clipboard.writeText 被调用 | 绿色 |
| MB-03 | hover 显示重新生成按钮 | hover AI 消息 | 重新生成按钮出现 | 绿色 |
| MB-04 | 点击重新生成触发回调 | 点击重新生成 | onRegenerate 被调用 | 绿色 |
| MB-05 | 用户消息不显示操作按钮 | hover 用户消息 | 无操作按钮 | 绿色 |
