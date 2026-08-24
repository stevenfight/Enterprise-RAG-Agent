# 设计：工作区本地生成物忽略规则

## 方案

仅在根目录 `.gitignore` 新增一个“本地工具与运行产物”分组。规则采用精确路径，避免使用宽泛通配符误伤可提交的源码、测试和文档。

## 验证方式

使用 `git check-ignore -v` 验证每个目标路径命中预期规则，并使用 `git status --porcelain` 确认功能代码、测试、OpenSpec 归档和 `requirements.lock` 仍保持可见。
