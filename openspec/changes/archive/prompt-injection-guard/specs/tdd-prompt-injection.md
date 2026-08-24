# TDD: 提示词注入防护

> 编码: UTF-8 | 变更: prompt-injection-guard | 规则: 全线 GREEN (+P1 规则过滤器)

---

## P0 测试状态登记

| 测试ID | 状态 | 描述 |
|:---:|:---:|------|
| PI-G01 | GREEN | INTENT_PROMPT_TEMPLATE 含 `<用户输入>` 标签 |
| PI-G02 | GREEN | REWRITE_PROMPT_TEMPLATE 含 `<用户输入>` 标签 |
| PI-G03 | GREEN | INTENT_PROMPT_TEMPLATE 含边界声明 |
| PI-G04 | GREEN | REWRITE_PROMPT_TEMPLATE 含边界声明 |
| PI-G05 | GREEN | agent_core 用户消息含 `<user_query>` 标签 |
| PI-G06 | GREEN | agent_core system prompt 含标签边界声明 |
| PI-G07 | GREEN | retrieval _build_prompt 含 `<用户问题>` 标签 |
| PI-G08 | GREEN | retrieval _build_comparison_prompt 含 `<用户问题>` 标签 |
| PI-G09 | GREEN | retrieval _build_financial_data_prompt 含 `<用户问题>` 标签 |
| PI-G10 | GREEN | agent_core system prompt 含安全规则区块 |
| PI-G11 | GREEN | retrieval 生成 prompt 含防注入声明 |
| PI-G12 | GREEN | 正常查询回归验证 |

## P1 规则过滤器验证结果

| 验证项 | 结果 | 描述 |
|:---:|:---:|------|
| RF-V01 | PASS | domain_filter.yaml 配置加载正常 |
| RF-V02 | PASS | 天气闲聊 ("今天天气真好啊") → 规则拦截 |
| RF-V03 | PASS | 人身攻击 ("傻逼") → 规则拦截 |
| RF-V04 | PASS | 正常查询 ("中芯国际2024年营收") → 未命中 |
| RF-V05 | PASS | mode=log 时不拦截 |
| RF-V06 | PASS | enabled=false 时跳过规则检查 |
| RF-V07 | PASS | 配置文件不存在时优雅降级为仅 LLM 分类 |

---

## 版本记录

| 版本 | 日期 | 作者 | 变更内容 |
|:---:|------|------|---------|
| v1.0 | 2026-07-09 | AI Agent | 初始版本，全线 RED |
| v1.1 | 2026-07-09 | AI Agent | 全部 12 项 P0 测试通过，全线 GREEN |
| v1.2 | 2026-07-09 | AI Agent | P1 规则过滤器追加，7 项额外验证全通过 |
