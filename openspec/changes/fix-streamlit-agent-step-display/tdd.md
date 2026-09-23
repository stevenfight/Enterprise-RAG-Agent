# TDD 记录

- [GREEN] `python -m compileall -q app_streamlit.py`：通过。
- [GREEN] `src/agent_core.py` 的 reasoning step 字段核对为 `step`。
- [GREEN] Streamlit 适配映射核对为 `s.get("step", "?")`，不再读取不存在的 `s["step_number"]`。
