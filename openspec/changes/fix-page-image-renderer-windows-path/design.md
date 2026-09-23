# 设计

`PageImageRenderer._save_pixmap_atomic()` 在最终文件同目录创建短 UUID 临时 PNG，格式为 `.<uuid>.png`。PyMuPDF 仍可依据 `.png` 后缀写入；写入成功后继续通过 `os.replace()` 原子替换最终路径，`finally` 块继续删除残留临时文件。

这将临时文件名与最终制品的 64 位哈希和 `.thumbnail` 后缀解耦，缩短深路径下的实际写入路径。
