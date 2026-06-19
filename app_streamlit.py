# -*- coding: utf-8 -*-
"""
企业知识库智能问答系统 - Streamlit Web 界面

运行方式: streamlit run app_streamlit.py
"""

import json
import logging
import sys
import time
from pathlib import Path

import streamlit as st

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root / "src"))

from retrieval import RAGGenerator, HybridRetriever, COMPANY_ABBREV_MAP
from query_processor import QueryProcessor, OUT_OF_DOMAIN_REPLY
from conversation import ConversationManager

logger = logging.getLogger("streamlit_app")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)

st.set_page_config(
    page_title="企业知识库智能问答",
    layout="wide",
    initial_sidebar_state="expanded",
)

VECTOR_DB_DIR = project_root / "data" / "stock_data" / "databases" / "vector_dbs"

INTENT_LABELS = {
    "financial_data": ("财务数据", ""),
    "business_analysis": ("业务分析", ""),
    "comparison": ("对比分析", ""),
    "trend": ("趋势预测", ""),
    "general": ("通用问答", ""),
    "out_of_domain": ("域外问题", ""),
}

CONFIDENCE_STYLES = {
    "high": ("高", ""),
    "medium": ("中", ""),
    "low": ("低", ""),
}


def init_session_state():
    if "rag_generator" not in st.session_state:
        st.session_state.rag_generator = None
    if "query_processor" not in st.session_state:
        st.session_state.query_processor = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "conversation_manager" not in st.session_state:
        st.session_state.conversation_manager = ConversationManager()
    if "initialized" not in st.session_state:
        st.session_state.initialized = False
    if "agent_mode" not in st.session_state:
        st.session_state.agent_mode = False
    if "agent" not in st.session_state:
        st.session_state.agent = None
    if "agent_registry" not in st.session_state:
        st.session_state.agent_registry = None


def load_components():
    if st.session_state.initialized:
        return True

    with st.spinner("正在加载模型和索引，请稍候..."):
        try:
            st.session_state.rag_generator = RAGGenerator(str(VECTOR_DB_DIR))
            st.session_state.query_processor = QueryProcessor()
            st.session_state.initialized = True
            return True
        except Exception as e:
            st.error(f"初始化失败: {str(e)}")
            return False


def _init_agent_mode():
    """初始化 Agent 模式的工具注册表、Agent 实例"""
    if st.session_state.agent_registry is not None:
        return  # 已初始化

    from tools import ToolRegistry
    from tools.retrieve_tool import RetrieveTool
    from tools.calculator_tool import CalculatorTool
    from tools.compare_tool import CompareTool
    from tools.chart_tool import ChartTool
    from tools.verify_tool import VerifyTool
    from agent_core import ReActAgent
    from agent_memory import AgentMemory

    registry = ToolRegistry()
    registry.register(RetrieveTool())
    registry.register(CalculatorTool())
    registry.register(CompareTool())
    registry.register(ChartTool())
    registry.register(VerifyTool())

    st.session_state.agent_registry = registry
    st.session_state.agent = ReActAgent(
        tool_registry=registry,
        memory=AgentMemory(),
        max_steps=5,
        temperature=0.3,
        model="qwen-max",
    )
    logger.info("[Streamlit] Agent 模式初始化完成, 模型: qwen-max, tools=%d",
                 len(registry._tools))


def get_companies():
    if not st.session_state.rag_generator:
        return []
    try:
        retriever = st.session_state.rag_generator._get_retriever()
        if not retriever._company_registry:
            retriever._load_company_registry()
        return list(retriever._company_registry.get("companies", {}).keys())
    except Exception:
        return []


def render_sidebar():
    with st.sidebar:
        st.markdown("## 系统设置")

        companies = get_companies()
        selected_company = st.selectbox(
            "选择公司",
            options=["全部公司"] + companies,
            index=0,
            help="限定检索范围，选择'全部公司'将检索所有公司数据",
        )

        company_name = None if selected_company == "全部公司" else selected_company

        top_n = st.slider(
            "检索返回条数",
            min_value=1,
            max_value=10,
            value=5,
            step=1,
            help="重排后返回的文档片段数量",
        )

        enable_rewrite = st.checkbox(
            "启用意图识别与查询改写",
            value=True,
            help="使用思维链模式对查询进行意图识别和改写，提升检索精度",
        )

        st.markdown("---")
        st.markdown("### 模式切换")

        agent_mode = st.toggle(
            "Agent 推理模式",
            value=st.session_state.agent_mode,
            help="启动后 LLM 将自主决策调用多个工具（检索/计算/对比/图表/验证），"
                 "支持多步推理。关闭后使用传统管道模式。",
        )
        if agent_mode != st.session_state.agent_mode:
            st.session_state.agent_mode = agent_mode
            if agent_mode:
                _init_agent_mode()
            st.rerun()

        st.markdown("---")
        st.markdown("### 系统状态")

        if st.session_state.initialized:
            st.success("系统已就绪")
            if companies:
                st.info(f"已加载 {len(companies)} 家公司索引")
                for c in companies:
                    st.markdown(f"- {c}")
        else:
            st.warning("系统未初始化")

        st.markdown("---")
        st.markdown("### 示例问题")
        examples = [
            "中芯国际2024年营收情况",
            "中国电信的5G业务发展如何",
            "中国移动和中国联通的营收对比",
            "中芯国际的产能利用率趋势",
            "中国联通的云计算业务收入",
        ]
        for ex in examples:
            if st.button(ex, key=f"ex_{ex}", use_container_width=True):
                st.session_state.example_query = ex

        st.markdown("---")
        if st.button("清空对话历史", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()

        st.markdown("---")
        st.markdown("### 对话管理")
        turn_count = len(st.session_state.conversation_manager.messages) // 2
        st.info(f"当前对话轮数: {turn_count}")

        if st.button("新对话", use_container_width=True, type="primary"):
            st.session_state.conversation_manager.clear()
            st.session_state.chat_history = []
            st.rerun()

        return company_name, top_n, enable_rewrite


def render_chat_history():
    for item in st.session_state.chat_history:
        role = item["role"]
        if role == "user":
            with st.chat_message("user"):
                st.markdown(item["content"])
        elif role == "assistant":
            with st.chat_message("assistant"):
                render_answer(item)


def render_answer(item):
    answer = item.get("answer", "")
    sources = item.get("sources", [])

    # ---- Agent 推理链展示 ----
    if item.get("agent_mode") and item.get("reasoning_chain"):
        with st.expander("推理过程 (ReAct Agent)", expanded=False):
            for step in item["reasoning_chain"]:
                step_num = step.get("step_number", "?")
                thought = step.get("thought", "")
                action = step.get("action", "?")
                obs = step.get("observation", "")[:200]
                elapsed = step.get("elapsed_ms", 0)

                st.markdown(f"**Step {step_num}** ({elapsed:.0f}ms)")
                st.markdown(f"> Action: `{action}`")
                if thought:
                    st.info(f"Thought: {thought}")
                if obs:
                    st.code(obs[:300], language="json")

        # 反思结果
        reflection = item.get("reflection")
        if reflection:
            with st.expander("反思验证 (Reflection)", expanded=False):
                cols = st.columns(4)
                with cols[0]:
                    st.metric("置信度", f"{reflection.get('overall_confidence', 0):.0%}")
                with cols[1]:
                    st.metric("幻觉数", f"{reflection.get('hallucination_count', 0)}/{reflection.get('total_datapoints', 0)}")
                with cols[2]:
                    st.metric("来源完整性", f"{reflection.get('source_completeness', 0):.0%}")
                with cols[3]:
                    st.metric("回答完整性", f"{reflection.get('answer_completeness', 0):.0%}")
                if reflection.get("suggestions"):
                    st.warning("\n".join(reflection["suggestions"]))

    query_info = item.get("query_info", None)

    if query_info:
        with st.expander("查询分析", expanded=False):
            intent = query_info.get("intent", "general")
            intent_conf = query_info.get("intent_confidence", 0)
            rewritten = query_info.get("rewritten_query", "")
            sub_queries = query_info.get("sub_queries", [])
            extracted_companies = query_info.get("extracted_companies", [])
            extracted_years = query_info.get("extracted_years", [])
            cot = query_info.get("cot_reasoning", "")

            intent_label, _ = INTENT_LABELS.get(intent, ("未知", ""))

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("意图分类", intent_label)
            with col2:
                st.metric("分类置信度", f"{intent_conf:.0%}")
            with col3:
                st.metric("子问题数", len(sub_queries))

            if rewritten:
                st.markdown(f"**改写后查询:** {rewritten}")
            if sub_queries:
                st.markdown("**拆解子问题:**")
                for sq in sub_queries:
                    st.markdown(f"  - {sq}")
            if extracted_companies:
                st.markdown(f"**识别公司:** {', '.join(extracted_companies)}")
            if extracted_years:
                st.markdown(f"**识别年份:** {', '.join(extracted_years)}")
            if cot:
                st.markdown("**思维链推理:**")
                st.text(cot)

    st.markdown(answer)

    if sources:
        with st.expander(f"来源信息（{len(sources)} 条）", expanded=False):
            for s in sources:
                idx = s.get("index", 0)
                source_file = s.get("source_file", "未知")
                pages = s.get("pages", [])
                company = s.get("company_name", "未知")
                scores = s.get("scores", {})
                confidence = scores.get("confidence", "unknown")

                conf_label, _ = CONFIDENCE_STYLES.get(confidence, ("未知", ""))

                pages_str = ""
                if pages:
                    if len(pages) >= 2:
                        pages_str = f"第{pages[0]}-{pages[-1]}页"
                    else:
                        pages_str = f"第{pages[0]}页"

                header = f"**[来源{idx}]** {company} | {source_file}"
                if pages_str:
                    header += f" | {pages_str}"
                header += f" | 置信度: {conf_label}"

                st.markdown(header)

                detail_cols = st.columns(4)
                with detail_cols[0]:
                    st.caption(f"Hybrid: {scores.get('hybrid', 0):.4f}")
                with detail_cols[1]:
                    st.caption(f"Rerank: {scores.get('rerank', 0):.1f}")
                with detail_cols[2]:
                    if "vector" in scores:
                        st.caption(f"Vector: {scores.get('vector', 0):.4f}")
                with detail_cols[3]:
                    if "bm25" in scores:
                        st.caption(f"BM25: {scores.get('bm25', 0):.4f}")



def main():
    init_session_state()

    if not load_components():
        st.stop()

    company_name, top_n, enable_rewrite = render_sidebar()

    st.markdown("# 企业知识库智能问答系统")
    st.markdown("基于 RAG 技术的企业年报智能问答，支持混合检索 + gte-rerank-v2 重排 + 意图识别")

    render_chat_history()

    example_query = st.session_state.pop("example_query", None)

    if prompt := st.chat_input("请输入您的问题...") or example_query:
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        st.session_state.conversation_manager.add_message("user", prompt)

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            # ---- Agent 模式分支 ----
            if st.session_state.agent_mode:
                _run_agent_query(prompt)
            else:
                _run_pipeline_query(prompt, company_name, top_n, enable_rewrite)


def _run_agent_query(prompt):
    """Agent 模式: ReAct 推理 + 工具调用 + 反思验证"""
    from planner import TaskPlanner
    from reflector import AnswerReflector

    # 显示任务规划
    planner = TaskPlanner()
    plan = planner.plan(prompt)

    with st.status(f"Agent 推理中... (策略: {plan.category.category}, {len(plan.subtasks)}个子任务)",
                   expanded=True) as status:
        try:
            t0 = time.time()
            result = st.session_state.agent.run(prompt)
            elapsed = time.time() - t0
            status.update(label=f"Agent 推理完成 ({elapsed:.1f}s, {result.total_steps}步)",
                          state="complete")
        except Exception as e:
            status.update(label=f"Agent 推理失败: {str(e)}", state="error")
            result = type("AgentResult", (), {
                "answer": f"抱歉，Agent 推理出现错误: {str(e)}",
                "success": False,
                "reasoning_chain": [],
                "total_steps": 0,
                "total_elapsed_ms": 0,
                "forced_stop": False,
                "error": str(e),
            })()

    # 反思验证
    reflection = None
    if result.success:
        reflector = AnswerReflector()
        sources = []
        for step in result.reasoning_chain:
            obs = step.get("observation", "")
            if obs and "results" in str(obs):
                try:
                    import json as _json
                    obs_data = _json.loads(obs) if isinstance(obs, str) else obs
                    if isinstance(obs_data, dict) and "results" in obs_data:
                        sources.extend(obs_data["results"])
                except Exception:
                    pass
        ref_result = reflector.verify(result.answer, sources, prompt)
        reflection = {
            "has_hallucination": ref_result.has_hallucination,
            "hallucination_count": ref_result.hallucination_count,
            "total_datapoints": ref_result.total_datapoints,
            "source_completeness": ref_result.source_completeness,
            "answer_completeness": ref_result.answer_completeness,
            "overall_confidence": ref_result.overall_confidence,
            "suggestions": ref_result.suggestions,
        }

    # 渲染答案
    item = {
        "role": "assistant",
        "answer": result.answer,
        "sources": [],
        "agent_mode": True,
        "reasoning_chain": [
            {
                "step_number": s["step_number"],
                "thought": s.get("thought", ""),
                "action": s.get("action", "?"),
                "observation": s.get("observation", "")[:300],
                "elapsed_ms": s.get("elapsed_ms", 0),
            }
            for s in result.reasoning_chain
        ],
        "reflection": reflection,
    }
    render_answer(item)

    st.session_state.chat_history.append(item)
    answer_summary = result.answer[:200] + "..." if len(result.answer) > 200 else result.answer
    st.session_state.conversation_manager.add_message("assistant", answer_summary)


def _run_pipeline_query(prompt, company_name, top_n, enable_rewrite):
    """管道模式: 意图识别 + 检索 + 生成"""
    query_info = None
    search_query = prompt
    actual_company = company_name
    extracted_companies = []
    extracted_years = []
    intent = None
    conversation_context = st.session_state.conversation_manager.get_context_string()

    # ── 1. 意图识别 + 查询改写 ──
    if enable_rewrite:
        with st.status("查询分析中...", expanded=False) as status:
            try:
                qp = st.session_state.query_processor
                intent, intent_conf, cot_reasoning = qp._classify_intent(prompt)

                if intent == "out_of_domain":
                    status.update(label="域外问题已拦截", state="complete")
                    item = {
                        "role": "assistant",
                        "answer": OUT_OF_DOMAIN_REPLY,
                        "sources": [],
                        "query_info": {
                            "intent": intent,
                            "intent_confidence": intent_conf,
                            "cot_reasoning": cot_reasoning,
                        },
                    }
                    render_answer(item)
                    st.session_state.chat_history.append(item)
                    st.session_state.conversation_manager.add_message("assistant", OUT_OF_DOMAIN_REPLY[:200])
                    return

                rewritten, sub_queries, extracted_companies, extracted_years, _ = \
                    qp._rewrite_query(prompt, conversation_context)
                search_query = rewritten
                if extracted_companies and not actual_company:
                    actual_company = extracted_companies[0]

                query_info = {
                    "intent": intent,
                    "intent_confidence": intent_conf,
                    "rewritten_query": search_query,
                    "sub_queries": sub_queries,
                    "extracted_companies": extracted_companies,
                    "extracted_years": extracted_years,
                    "cot_reasoning": cot_reasoning,
                }
                status.update(label="查询分析完成: {}".format(intent), state="complete")
            except Exception as e:
                logger.warning("查询分析失败，使用原始查询: %s", e)

    # ── 2. 检索 + 生成 ──
    with st.spinner("检索并生成回答中..."):
        try:
            result = st.session_state.rag_generator.query(
                query=search_query,
                company_name=actual_company,
                top_n=top_n,
                mentioned_companies=extracted_companies,
                intent=intent,
                extracted_years=extracted_years,
            )
        except Exception as e:
            logger.exception("管道查询失败")
            result = {
                "answer": "抱歉，查询处理出现错误: {}".format(str(e)),
                "sources": [],
            }

    # ── 3. 渲染回答 ──
    item = {
        "role": "assistant",
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "query_info": query_info,
    }
    render_answer(item)
    st.session_state.chat_history.append(item)
    answer_summary = result.get("answer", "")[:200]
    st.session_state.conversation_manager.add_message("assistant", answer_summary)


if __name__ == "__main__":
    main()
