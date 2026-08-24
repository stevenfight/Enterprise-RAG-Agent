# 需求规格: 财务指标卡片化 + Markdown 表格美化

> 编码: UTF-8

---

## 1. Markdown 表格美化

### 1.1 表头样式
- 背景：`linear-gradient(135deg, #B8A9C9 0%, #9B8EC4 100%)`（马卡龙紫渐变）
- 文字：白色 `#FFFFFF`，字号 13px，font-weight 600
- 内边距：`10px 14px`
- 等宽字体：`JetBrains Mono` 族（用于数字列）

### 1.2 数据行样式
- 斑马纹：奇数行 `#FFFFFF`，偶数行 `#FAF8FC`
- 暗色模式：奇数行 `#252236`，偶数行 `#2A2740`
- 行 hover：背景色过渡到 `rgba(184,169,201,0.08)`，transition 0.2s
- 内边距：`8px 14px`
- 字号：13px

### 1.3 数字列处理
- 自动检测：单元格内容匹配 `/^[\d,\.\-%\s]+$/`（纯数字/百分比/货币）
- 对齐方式：右对齐 `text-align: right`
- 字体：等宽字体 `monoFont`
- 颜色：正值绿色 `#7ECB9A`，负值红色 `#E88B8B`

### 1.4 表格外框
- 圆角：`border-radius: 12px`
- 阴影：`0 2px 12px rgba(0,0,0,0.06)`
- 边框折叠：`border-collapse: separate`（配合圆角）
- 溢出隐藏：`overflow: hidden`
- 外边距：`margin: 12px 0`

---

## 2. 财务 KPI 卡片自动提取

### 2.1 提取规则

| 指标名 | 正则模式 | 示例匹配 |
|--------|---------|---------|
| 营业收入 | `营收[收入]?[：:]?\s*(\d[\d,.]+)\s*亿元` | "营收 1,234.5 亿元" |
| 净利润 | `净利润[：:]?\s*(\d[\d,.]+)\s*亿元` | "净利润 567.8 亿元" |
| 同比增长 | `同比[增长]?[：:]?\s*([+-]?\d[\d,.]+)\s*%` | "同比增长 5.6%" |
| 净利润增长 | `净利润.*同比[增长]?[：:]?\s*([+-]?\d[\d,.]+)\s*%` | "净利润同比增长 8.2%" |
| ROE | `ROE[：:]?\s*(\d[\d,.]+)\s*%` | "ROE 12.5%" |
| 毛利率 | `毛利率[：:]?\s*(\d[\d,.]+)\s*%` | "毛利率 35.2%" |

### 2.2 卡片渲染
- 布局：水平排列，flex wrap，gap 12px
- 单卡片：圆角 12px，padding 14px 18px，背景 `#FFFFFF`，阴影 `0 2px 8px rgba(0,0,0,0.06)`
- 暗色模式：背景 `#252236`，阴影 `0 2px 8px rgba(0,0,0,0.2)`
- 内容结构：
  - 顶部：图标（Ant Design icon）+ 指标名称（12px，灰色）
  - 中部：大数字（24px，等宽字体，font-weight 700）
  - 底部：单位/变化趋势（12px，带颜色）

### 2.3 图标映射

| 指标 | 图标 |
|------|------|
| 营收/收入 | DollarOutlined |
| 净利润 | RiseOutlined |
| 增长率 | ArrowUpOutlined / ArrowDownOutlined |
| ROE | PercentageOutlined |
| 毛利率 | PieChartOutlined |

### 2.4 显示条件
- 当 `extractFinancialKPIs(text)` 返回非空数组时，在 Markdown 内容上方渲染 KPI 区域
- 最多显示 6 个 KPI 卡片
- 无匹配时不渲染（不破坏现有布局）

---

## 3. 兼容性

- 亮/暗色主题自动适配（通过 `useTheme` hook 读取 `isDark`）
- 不影响现有消息渲染流程（只在 AI 消息中生效）
- 与 @ant-design/x Bubble 组件无冲突
