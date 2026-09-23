# 修复 Streamlit Agent 推理步骤展示

## 背景

`ReActAgent` 的 `AgentResult.reasoning_chain` 使用 `step` 字段表示步骤序号，而 Streamlit 适配层仍读取旧的 `step_number`，导致 Agent 查询成功后渲染推理链时触发 KeyError。

## 目标

保持现有聊天和推理链展示结构，只修正适配层的字段读取并对缺失字段提供安全默认值。

## 非目标

- 不改变 Agent 推理、工具调用、Provider 或 API 行为。
- 不修改前端 React 页面、部署配置或服务器。
