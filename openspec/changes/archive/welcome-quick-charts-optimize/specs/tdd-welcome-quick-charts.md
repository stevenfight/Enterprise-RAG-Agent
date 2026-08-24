# TDD 测试用例: 欢迎页 + 快捷指令 + 图表优化

> 编码: UTF-8
> 图例: 红色 = 未验证（待实现）, 绿色 = 已通过
> 验证方式: Vitest + React Testing Library

---

## 模块 W: 欢迎页 + 快捷指令

| ID | 测试用例 | 操作 | 期望 | 状态 |
|----|---------|------|------|:--:|
| WQ-01 | 传入 quickCommands 时渲染快捷指令胶囊 | 空消息态 + quickCommands 传入 | 渲染对应文本的胶囊按钮 | 绿色 |
| WQ-02 | 点击胶囊直接发送问题 | 点击胶囊 | onSend 被调用且参数为问题文本 | 绿色 |
| WQ-03 | 未传入 quickCommands 时不渲染 | 空消息态 + 不传 prop | 无快捷指令区域 | 绿色 |
| WQ-04 | 有消息时隐藏快捷指令区 | 非空消息态 + quickCommands 传入 | 快捷指令区不出现 | 绿色 |
| WQ-05 | 快捷指令胶囊样式为马卡龙色 | 检查胶囊元素 class/style | 含马卡龙描边色或 hover 样式类 | 绿色 |

## 模块 G: 图表暗色适配

| ID | 测试用例 | 操作 | 期望 | 状态 |
|----|---------|------|------|:--:|
| GC-01 | 默认亮色标题颜色不变 | 渲染 ChartContainer 不传 dark | option 标题颜色为 #3D3554 | 绿色 |
| GC-02 | dark=true 标题颜色切换 | 传 dark=true | option 标题颜色为 #e8e8e8 | 绿色 |
| GC-03 | dark=true 坐标轴文字颜色切换 | 传 dark=true | axisLabel 颜色为 #8c8c8c | 绿色 |
| GC-04 | dark=true 容器卡片为暗色背景 | 传 dark=true | 容器背景为 #1f1f1f | 绿色 |
| GC-05 | 亮色容器卡片背景不变 | 不传 dark | 容器背景为 #ffffff | 绿色 |

> 说明: 模块 G 的测试通过 spy `ReactEChartsCore` 或断言渲染 DOM 背景样式完成；现有 22 个图表测试保持不破坏。
