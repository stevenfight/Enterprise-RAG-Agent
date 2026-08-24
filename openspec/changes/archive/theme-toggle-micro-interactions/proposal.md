# 变更提案: 主题切换按钮 + 消息动效微交互

> 编码: UTF-8

## 背景

当前暗色/亮色主题切换基础设施已完备（appStore + useTheme hook + ConfigProvider 动态绑定），但用户缺少直观的切换入口。同时，消息气泡缺少复制、重新生成等常用微交互，入场动画也不够精致。

## 目标

1. **主题切换按钮**：在顶部栏右侧添加太阳/月亮图标按钮，一键切换亮/暗主题，localStorage 持久化已就绪。
2. **消息 hover 微交互**：AI 消息气泡 hover 时显示复制、重新生成按钮。
3. **入场动画增强**：气泡淡入上滑更平滑，增加 stagger 延迟感。

## 方案

### B. 主题切换
- HeaderBar 右侧添加 `Button type="text"`，图标根据 `isDark` 切换 `SunOutlined` / `MoonOutlined`
- 点击调用 `toggleTheme()`，localStorage 自动持久化

### C. 消息动效 + 微交互
- MessageBubble 外层包裹 hover 状态，hover 时在气泡右上角显示操作按钮行（复制、重新生成）
- 复制按钮：点击后将消息内容写入剪贴板，显示 Toast 提示
- 重新生成按钮：点击后触发父组件的 `onRegenerate` callback
- 入场动画：增强 `fade-in-up` 为 `fade-in-up-smooth`，增加 cubic-bezier 缓动

## 非目标
- 不修改后端 API
- 不改主题 token 配置（lightTheme/darkTheme 已完备）
- 不引入额外动画库
