# 任务清单: RAG 管道升级为 RAG-Agent 智能体

> 编码: UTF-8
> 每个阶段完成后运行 `python tests/tdd_all_optimizations.py` 确保管道回归通过

---

## 阶段零：基础准备（已完成）

- [x] 0.1 项目目录规范化，清理非工程文件
- [x] 0.2 创建 `docs/系统设计决策记录.md`（继承 RAG 阶段技术约束）
- [x] 0.3 更新 `.gitignore`（排除 `_local/`）
- [x] 0.4 创建 `openspec/changes/rag-to-agent/` 规范文档

---

## 阶段一：Agent 核心框架

- [x] 1.1 创建 `config/agent_config.json` - Agent 行为配置
- [x] 1.2 实现 `src/tools/__init__.py` - 工具基类 + 注册框架
- [x] 1.3 实现 `src/agent_memory.py` - 三层记忆系统
- [x] 1.4 实现 `src/agent_core.py` - ReAct 循环主控制器
- [x] 1.5 运行管道回归测试，确保无影响

---

## 阶段二：工具实现

- [x] 2.1 实现 `src/tools/retrieve_tool.py` - 封装现有混合检索
- [x] 2.2 实现 `src/tools/calculator_tool.py` - 财务指标计算
- [x] 2.3 实现 `src/tools/compare_tool.py` - 多公司对比分析
- [x] 2.4 实现 `src/tools/chart_tool.py` - 图表生成
- [x] 2.5 实现 `src/tools/verify_tool.py` - 数值验证
- [x] 2.6 运行管道回归测试，确保无影响

---

## 阶段三：反思与规划

- [x] 3.1 实现 `src/reflector.py` - 答案质量验证与修正
- [x] 3.2 实现 `src/planner.py` - 复杂查询任务拆解
- [x] 3.3 Agent 生成过程日志记录（每步 Thought/Action/Observation）
- [x] 3.4 运行管道回归测试，确保无影响

---

## 阶段四：界面与服务集成

- [x] 4.1 更新 `src/__init__.py` - 导出 Agent 模块
- [x] 4.2 `src/api_service.py` 新增 `POST /api/agent/query` 端点
- [x] 4.3 `app_streamlit.py` 新增 Agent 模式（开关 + 推理链展示）
- [x] 4.4 保留 `/api/query` 作为管道降级方案
- [x] 4.5 运行管道回归测试，确保无影响

---

## 阶段五：对话记忆升级

- [x] 5.1 扩展 `src/conversation.py` 支持 Agent 记忆结构
- [x] 5.2 对话历史与 Agent 推理链的关联存储
- [x] 5.3 运行管道回归测试，确保无影响

---

## 阶段六：测试与验证

- [x] 6.1 编写 `tests/test_agent_core.py`
- [x] 6.2 编写 `tests/test_agent_tools.py`
- [x] 6.3 编写 `tests/test_agent_memory.py`
- [x] 6.4 编写 `tests/test_reflector.py`
- [x] 6.5 全量回归测试（管道模式 + Agent 模式）
- [x] 6.6 端到端测试：单公司查询、多公司对比、趋势分析、域外拦截

---

## 阶段七：文档更新

- [x] 7.1 更新 `README.md` - 新增 Agent 模式说明
- [x] 7.2 更新 `docs/快速上手指南_新开发者.md` - 新增 Agent 开发指南
- [x] 7.3 更新 `docs/上线部署清单.md` - 新增 Agent 部署检查项
- [x] 7.4 归档本次变更到 `openspec/changes/`
