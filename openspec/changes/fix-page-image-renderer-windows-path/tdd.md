# TDD 记录

- [RED] `test_page_renderer_uses_short_png_temporary_name_for_deep_output_paths`：旧实现缺少短临时路径生成器，测试因 `AttributeError` 失败。
- [GREEN] 新临时路径为 `.<uuid>.png`，不包含最终长哈希文件名或 `.thumbnail` 标记；页图、视觉制品仓库和发布集定向回归 **24 passed**，`compileall` 与严格 OpenSpec 校验通过。
