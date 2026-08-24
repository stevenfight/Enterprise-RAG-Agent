# 设计方案：知识库页面 KPI 概览

在知识库页面标题下、上传区域前增加四张统计卡片：文档总数、已索引、待索引、索引完成率。

统计数据直接由现有 `documents` 数组计算：

- 总数：`documents.length`
- 已索引：`documents.filter(document => document.indexed).length`
- 待索引：总数减已索引
- 完成率：已索引 / 总数，空列表显示 `0%`

使用现有 `page-card` 和页面主题变量。桌面端四列，中等屏幕两列，移动端单列。上传和文档表格保持原有逻辑。
