# 设计

在 `app_streamlit.py` 的 reasoning chain 适配处读取 `s.get("step", "?")`，将 Agent 内部的 `step` 映射为现有 UI 使用的 `step_number`，其余字段映射保持不变。
