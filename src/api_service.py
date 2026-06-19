# -*- coding: utf-8 -*-
"""
FastAPI API 服务模块

将 RAG 检索流程封装为 REST API 接口，提供：
  - POST /api/query    - 完整 RAG 问答（检索+生成）
  - POST /api/retrieve - 仅检索（不生成）
  - GET  /api/companies - 获取可用公司列表
  - GET  /api/health    - 健康检查

运行方式: uvicorn src.api_service:app --host 0.0.0.0 --port 8000
"""

import logging
import json
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from retrieval import RAGGenerator, HybridRetriever, COMPANY_ABBREV_MAP
from query_processor import QueryProcessor
from conversation import ConversationManager
from agent_core import ReActAgent
from agent_memory import AgentMemory
from tools import ToolRegistry
from tools.retrieve_tool import RetrieveTool
from tools.calculator_tool import CalculatorTool
from tools.compare_tool import CompareTool
from tools.chart_tool import ChartTool
from tools.verify_tool import VerifyTool
from planner import TaskPlanner
from reflector import AnswerReflector

logger = logging.getLogger("api_service")
logger.setLevel(logging.INFO)

if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)

project_root = Path(__file__).resolve().parent.parent
vector_db_dir = project_root / "data" / "stock_data" / "databases" / "vector_dbs"

rag_generator: Optional[RAGGenerator] = None
query_processor: Optional[QueryProcessor] = None

# ==================== 会话管理 ====================

class ConversationStore:
    """会话存储 (企业级封装: 容量上限 + 淘汰逻辑)

    替代模块级全局 dict, 提供封装的会话生命周期管理。
    """

    def __init__(self, max_conversations: int = 100):
        self._store: dict = {}
        self.max_conversations = max_conversations
        logger.info("[ConversationStore] 初始化完成 | max_conversations=%d | 状态=空存储",
                     max_conversations)

    def get(self, conversation_id: str) -> Optional[ConversationManager]:
        """获取已有会话, 不存在返回 None"""
        result = self._store.get(conversation_id)
        if result is not None:
            logger.debug("[ConversationStore] get 命中 | conversation_id=%s | store_size=%d",
                         conversation_id, len(self._store))
        else:
            logger.debug("[ConversationStore] get 未命中 | conversation_id=%s | store_size=%d",
                         conversation_id, len(self._store))
        return result

    def get_or_create(self, conversation_id: str) -> ConversationManager:
        """获取或新建会话, 超容量上限时自动淘汰最早会话

        企业级内存保护: 当 _store 超过 max_conversations 时,
        自动淘汰最早创建的会话, 防止服务长期运行导致 OOM。
        """
        # 路径A: 已有会话直接返回
        if conversation_id in self._store:
            logger.info("[ConversationStore] 复用已有会话 | conversation_id=%s | store_size=%d/%d",
                         conversation_id, len(self._store), self.max_conversations)
            return self._store[conversation_id]

        # 路径B: 新建会话 (可能触发淘汰)
        before_count = len(self._store)
        evicted_count = 0

        # 容量上限检查: 超过时循环淘汰最早会话
        while len(self._store) >= self.max_conversations:
            if not self._store:
                logger.warning("[ConversationStore] 淘汰循环中断 | 原因=存储意外为空 | max=%d",
                               self.max_conversations)
                break
            oldest_id = next(iter(self._store))
            del self._store[oldest_id]
            evicted_count += 1
            logger.info("[ConversationStore] 淘汰最早会话 | conversation_id=%s | "
                         "淘汰序号=%d/%d | store_size_after=%d/%d",
                         oldest_id, evicted_count, before_count,
                         len(self._store), self.max_conversations)

        # 创建新会话
        self._store[conversation_id] = ConversationManager()
        after_count = len(self._store)
        logger.info("[ConversationStore] 新建会话完成 | conversation_id=%s | "
                     "before=%d | evicted=%d | after=%d/%d | usage=%.0f%%",
                     conversation_id, before_count, evicted_count,
                     after_count, self.max_conversations,
                     (after_count / max(self.max_conversations, 1)) * 100)
        return self._store[conversation_id]

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: str) -> bool:
        return key in self._store


def _load_agent_config() -> dict:
    """加载 Agent 配置文件, 带默认值回退

    Returns:
        dict with keys: max_steps, llm_timeout, temperature, model, max_retries
    """
    default_config = {
        "max_steps": 5,
        "llm_timeout": 60,
        "tool_timeout": 30,
        "temperature": 0.3,
        "model": "qwen-max",
        "max_retries": 1,
    }
    config_path = project_root / "config" / "agent_config.json"
    logger.info("[config_loader] 开始加载 Agent 配置 | 路径=%s", config_path)

    if not config_path.exists():
        logger.warning("[config_loader] 配置文件不存在 | 路径=%s | 使用默认配置 | keys=%s",
                       config_path, list(default_config.keys()))
        return default_config

    try:
        logger.debug("[config_loader] 配置文件存在, 开始读取 | 大小=%d bytes",
                     config_path.stat().st_size)
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        agent_cfg = config.get("agent", {})

        if not agent_cfg:
            logger.warning("[config_loader] agent 配置节为空 | 使用默认配置")

        result = {}
        for key, default_val in default_config.items():
            val = agent_cfg.get(key, default_val)
            result[key] = val
            source = "文件" if key in agent_cfg else "默认"
            logger.info("[config_loader] %s=%s | 来源=%s | 默认=%s",
                         key, val, source, default_val)

        # 检查是否有未识别的配置项
        unexpected = set(agent_cfg.keys()) - set(default_config.keys())
        if unexpected:
            logger.warning("[config_loader] 未识别的配置项将被忽略 | keys=%s", unexpected)

        logger.info("[config_loader] 配置加载完成 | 有效项=%d/%d",
                     len(result), len(default_config))
        return result

    except json.JSONDecodeError as e:
        logger.error("[config_loader] JSON 解析失败 | 路径=%s | 错误=%s | 使用默认配置",
                     config_path, e)
        return default_config
    except Exception as e:
        logger.error("[config_loader] 读取失败 | 路径=%s | 错误=%s | 使用默认配置",
                     config_path, e)
        return default_config


# Agent 模式全局实例
agent: Optional[ReActAgent] = None
agent_registry: Optional[ToolRegistry] = None
agent_planner: Optional[TaskPlanner] = None
agent_reflector: Optional[AnswerReflector] = None
conversation_store: ConversationStore = ConversationStore(max_conversations=100)


# ==================== 请求模型 ====================

class QueryRequest(BaseModel):
    """RAG 问答请求"""
    query: str = Field(..., description="查询文本")
    company_name: Optional[str] = Field(None, description="限定公司名（可选）")
    top_n: int = Field(5, description="重排后返回条数", ge=1, le=20)
    conversation_id: Optional[str] = Field(None, description="对话ID（可选，不提供则自动生成）")


class RetrieveRequest(BaseModel):
    """仅检索请求"""
    query: str = Field(..., description="查询文本")
    company_name: Optional[str] = Field(None, description="限定公司名（可选）")
    top_n: int = Field(5, description="重排后返回条数", ge=1, le=20)


# ==================== 响应模型 ====================

class SourceInfo(BaseModel):
    """来源信息"""
    index: int
    source_file: str
    pages: List[int]
    company_name: str
    scores: dict


class QueryResponse(BaseModel):
    """RAG 问答响应"""
    answer: str
    sources: List[SourceInfo]
    query: str
    company_name: Optional[str]
    retrieved_count: int
    context_used_count: Optional[int] = None
    processing_time: float = 0.0
    conversation_id: Optional[str] = None


class RetrieveResultItem(BaseModel):
    """单条检索结果"""
    parent_text: str
    source_file: str
    pages: List[int]
    company_name: str
    child_id: Optional[str] = None
    parent_key: Optional[str] = None
    scores: dict


class RetrieveResponse(BaseModel):
    """仅检索响应"""
    results: List[RetrieveResultItem]
    query: str
    company_name: Optional[str]
    total_count: int


class CompanyInfo(BaseModel):
    """公司信息"""
    name: str
    display_name: str


class CompaniesResponse(BaseModel):
    """可用公司列表响应"""
    companies: List[CompanyInfo]
    total_count: int


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    vector_db_dir: str
    rag_generator_loaded: bool
    agent_loaded: bool = False


# ==================== Agent 模式请求/响应 ====================

class AgentQueryRequest(BaseModel):
    """Agent 查询请求"""
    query: str = Field(..., description="查询文本")
    max_steps: int = Field(5, description="Agent 最大推理步数", ge=1, le=20)
    temperature: float = Field(0.3, description="LLM 温度", ge=0.0, le=2.0)
    conversation_id: Optional[str] = Field(None, description="对话ID (可选, 不提供则自动生成)")


class AgentStepInfo(BaseModel):
    """Agent 单步推理信息"""
    step_number: int
    thought: str
    action: Optional[str] = None
    action_input: Optional[dict] = None
    observation: Optional[str] = None
    elapsed_ms: float = 0.0


class AgentQueryResponse(BaseModel):
    """Agent 查询响应"""
    answer: str
    success: bool
    reasoning_chain: List[AgentStepInfo] = []
    total_steps: int = 0
    total_elapsed_ms: float = 0.0
    forced_stop: bool = False
    reflection: Optional[dict] = None
    error: Optional[str] = None


# ==================== 生命周期管理 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化 RAGGenerator，关闭时清理资源"""
    global rag_generator

    logger.info("=" * 60)
    logger.info("[api_service] FastAPI 应用启动中...")
    logger.info("[api_service] 项目根目录: %s", project_root)
    logger.info("[api_service] 向量数据库目录: %s", vector_db_dir)

    if not vector_db_dir.exists():
        logger.warning("[api_service] 向量数据库目录不存在: %s", vector_db_dir)
    else:
        logger.info("[api_service] 向量数据库目录已确认存在")

    logger.info("[api_service] 开始初始化 RAGGenerator 实例...")
    start_time = time.time()
    rag_generator = RAGGenerator(vector_db_dir)
    elapsed = time.time() - start_time
    logger.info("[api_service] RAGGenerator 实例创建完成，耗时: %.2f 秒", elapsed)

    logger.info("[api_service] 开始初始化 QueryProcessor 实例...")
    query_processor = QueryProcessor()
    logger.info("[api_service] QueryProcessor 实例创建完成")

    # ---- Agent 模式初始化 ----
    logger.info("[api_service] 开始初始化 Agent 模式组件...")
    global agent, agent_registry, agent_planner, agent_reflector

    agent_registry = ToolRegistry()
    agent_registry.register(RetrieveTool())
    agent_registry.register(CalculatorTool())
    agent_registry.register(CompareTool())
    agent_registry.register(ChartTool())
    agent_registry.register(VerifyTool())
    logger.info("[api_service] Agent 工具注册完成: %d 个工具", len(agent_registry._tools))

    agent_planner = TaskPlanner()
    agent_reflector = AnswerReflector()
    logger.info("[api_service] Agent 规划器 + 反思器 初始化完成")

    # 从 config 文件加载 Agent 配置参数
    ag_cfg = _load_agent_config()

    # AgentMemory 不再全局共享，改为每个 conversation_id 独立持有
    # 此处传入一个占位 AgentMemory, 每次请求时切换到对应会话的记忆
    agent = ReActAgent(
        tool_registry=agent_registry,
        memory=AgentMemory(),
        max_steps=ag_cfg["max_steps"],
        temperature=ag_cfg["temperature"],
        model=ag_cfg["model"],
        llm_timeout=ag_cfg["llm_timeout"],
        max_retries=ag_cfg["max_retries"],
    )
    logger.info("[api_service] Agent 实例创建完成 (记忆按会话隔离), 配置: %s", ag_cfg)

    logger.info("[api_service] FastAPI 应用启动完成")
    logger.info("=" * 60)

    yield

    logger.info("=" * 60)
    logger.info("[api_service] FastAPI 应用关闭中...")
    rag_generator = None
    agent = None
    logger.info("[api_service] RAGGenerator + Agent 实例已释放")
    logger.info("[api_service] FastAPI 应用已关闭")
    logger.info("=" * 60)


def _ensure_conversation(conversation_id: str) -> ConversationManager:
    """获取或创建会话, 委托给 ConversationStore"""
    return conversation_store.get_or_create(conversation_id)


# ==================== FastAPI 应用 ====================

app = FastAPI(
    title="企业知识库 RAG API",
    description="基于混合检索与 RAG 生成的企业财报问答服务",
    version="1.0.0",
    lifespan=lifespan,
)


# ==================== API 接口 ====================

@app.post("/api/query", response_model=QueryResponse, summary="完整 RAG 问答（检索+生成）")
async def api_query(request: QueryRequest):
    """
    完整 RAG 问答接口：执行混合检索 + gte-rerank-v2 重排 + 生成答案

    - **query**: 查询文本（必填）
    - **company_name**: 限定公司名（可选，不填则检索所有公司）
    - **top_n**: 重排后返回条数（默认5，范围1-20）
    - **conversation_id**: 对话ID（可选，不提供则自动生成）
    """
    logger.info("=" * 60)
    logger.info("[api_service] 收到 /api/query 请求")
    logger.info("[api_service] 查询: '%s'", request.query)
    logger.info("[api_service] 指定公司: %s", request.company_name or "全部")
    logger.info("[api_service] top_n: %d", request.top_n)

    conversation_id = request.conversation_id or str(uuid.uuid4())
    logger.info("[api_service] 对话ID: %s", conversation_id)

    if rag_generator is None:
        logger.error("[api_service] RAGGenerator 未初始化，无法处理请求")
        raise HTTPException(status_code=503, detail="RAGGenerator 未初始化，服务暂不可用")

    cm = _ensure_conversation(conversation_id)
    logger.info("[api_service] 会话已关联: %s (存储总数: %d)", conversation_id, len(conversation_store))
    rag_generator.conversation_manager = cm

    try:
        start_time = time.time()

        intent = None
        mentioned_companies = None
        extracted_years = None

        if query_processor is not None:
            try:
                qp_result = query_processor.process(request.query)
                intent = qp_result.get("intent")
                mentioned_companies = qp_result.get("extracted_companies")
                extracted_years = qp_result.get("extracted_years")
                logger.info("[api_service] 意图识别: intent=%s, 公司=%s, 年份=%s",
                             intent, mentioned_companies, extracted_years)
                if intent == "out_of_domain" and qp_result.get("should_reject"):
                    elapsed = time.time() - start_time
                    return QueryResponse(
                        answer="抱歉，您的问题不在企业财报分析范围内，我无法回答。",
                        sources=[],
                        retrieved_count=0,
                        processing_time=round(elapsed, 3),
                        conversation_id=conversation_id,
                    )
            except Exception as e:
                logger.warning("[api_service] QueryProcessor 调用失败: %s，继续使用原始查询", str(e))

        if mentioned_companies and len(mentioned_companies) > 1:
            result = rag_generator.query(
                query=request.query,
                mentioned_companies=mentioned_companies,
                intent=intent,
                extracted_years=extracted_years,
                top_n=request.top_n,
            )
        else:
            company = request.company_name
            if not company and mentioned_companies and len(mentioned_companies) == 1:
                company = mentioned_companies[0]
            result = rag_generator.query(
                query=request.query,
                company_name=company,
                intent=intent,
                extracted_years=extracted_years,
                top_n=request.top_n,
            )
        elapsed = time.time() - start_time
        result["processing_time"] = round(elapsed, 3)
        result["conversation_id"] = conversation_id

        # 统一写入对话历史（由 api_service 层管理，RAGGenerator 不再重复写入）
        answer = result.get("answer", "")
        cm.add_message("user", request.query)
        cm.add_message("assistant", answer)
        logger.info("[api_service] 对话历史已更新，当前轮数: %d",
                     len(cm.messages) // 2)

        logger.info("[api_service] /api/query 处理完成，耗时: %.2f 秒", elapsed)
        logger.info("[api_service] 答案长度: %d 字符，来源数: %d",
                     len(result.get("answer", "")), len(result.get("sources", [])))
        return result
    except ValueError as e:
        logger.error("[api_service] /api/query 参数错误: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        logger.error("[api_service] /api/query 文件未找到: %s", str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("[api_service] /api/query 处理异常: %s", str(e))
        raise HTTPException(status_code=500, detail=f"内部服务错误: {str(e)}")


# ============================================================
# Agent 模式 API 端点
# ============================================================

@app.post("/api/agent/query", response_model=AgentQueryResponse,
          summary="Agent 模式查询 (ReAct 推理 + 工具调用)")
async def api_agent_query(request: AgentQueryRequest):
    """
    Agent 模式查询接口: LLM 自主决策调用 tools (retrieve/calculator/compare/chart/verify)

    - **query**: 查询文本 (必填)
    - **max_steps**: 最大推理步数 (默认5, 范围1-20)
    - **temperature**: LLM 温度 (默认0.3, 范围0.0-2.0)

    返回完整的推理链 (Thought → Action → Observation)、最终答案和反思验证结果。
    """
    logger.info("=" * 60)
    logger.info("[api_service] 收到 /api/agent/query 请求")
    logger.info("[api_service] Agent 查询: '%s', max_steps=%d, temperature=%.2f",
                 request.query, request.max_steps, request.temperature)

    if agent is None:
        logger.error("[api_service] Agent 未初始化，无法处理请求")
        raise HTTPException(status_code=503, detail="Agent 未初始化，服务暂不可用")

    # ---- 会话隔离: 每个 conversation_id 持有独立的 AgentMemory ----
    conversation_id = request.conversation_id or str(uuid.uuid4())
    cm = _ensure_conversation(conversation_id)
    if cm.agent_memory is None:
        cm.link_memory(AgentMemory())
    agent.memory = cm.agent_memory  # 切换到当前会话的记忆

    # 更新 Agent 参数 (支持按请求调整)
    agent.max_steps = request.max_steps
    agent.temperature = request.temperature
    logger.info("[api_service] Agent 参数已更新: max_steps=%d, temperature=%.2f",
                 agent.max_steps, agent.temperature)

    try:
        # ---- 1. 任务规划 ----
        if agent_planner is not None:
            logger.info("[api_service] 阶段 1/3: 任务规划")
            plan = agent_planner.plan(request.query)
            logger.info("[api_service] 规划结果: category=%s, subtasks=%d, batches=%d",
                         plan.category.category, len(plan.subtasks), len(plan.execution_order))
        else:
            plan = None

        # ---- 2. Agent 推理 ----
        logger.info("[api_service] 阶段 2/3: Agent ReAct 推理")
        result = agent.run(request.query)
        logger.info("[api_service] Agent 推理完成: success=%s, steps=%d, elapsed=%.1fs",
                     result.success, result.total_steps, result.total_elapsed_ms / 1000)

        # ---- 3. 反思验证 ----
        reflection = None
        if agent_reflector is not None and result.answer:
            logger.info("[api_service] 阶段 3/3: 反思验证")
            # 从推理链提取来源
            sources = []
            for step in result.reasoning_chain:
                obs = step.get("observation", "")
                if obs and "来源" in obs:
                    try:
                        import json as _json
                        obs_data = _json.loads(obs) if isinstance(obs, str) else obs
                        if isinstance(obs_data, dict) and "results" in obs_data:
                            sources.extend(obs_data["results"])
                    except Exception:
                        pass

            ref_result = agent_reflector.verify(result.answer, sources, request.query)
            reflection = {
                "has_hallucination": ref_result.has_hallucination,
                "hallucination_count": ref_result.hallucination_count,
                "total_datapoints": ref_result.total_datapoints,
                "source_completeness": ref_result.source_completeness,
                "answer_completeness": ref_result.answer_completeness,
                "overall_confidence": ref_result.overall_confidence,
                "suggestions": ref_result.suggestions,
                "corrected_answer": ref_result.corrected_answer if ref_result.corrected_answer else None,
            }
        else:
            reflection = {"note": "反思器未启用或答案为空"}

        # ---- 4. 构建响应 ----
        chain = [
            AgentStepInfo(
                step_number=s["step_number"],
                thought=s.get("thought", ""),
                action=s.get("action"),
                action_input=s.get("action_input"),
                observation=s.get("observation", "")[:500] if s.get("observation") else None,
                elapsed_ms=s.get("elapsed_ms", 0),
            )
            for s in result.reasoning_chain
        ]

        logger.info("[api_service] /api/agent/query 处理完成")
        logger.info("[api_service] 推理链: %d 步, 答案: %d 字符, 置信度: %.2f",
                     len(chain), len(result.answer),
                     reflection.get("overall_confidence", 0) if reflection else 0)

        return AgentQueryResponse(
            answer=result.answer,
            success=result.success,
            reasoning_chain=chain,
            total_steps=result.total_steps,
            total_elapsed_ms=result.total_elapsed_ms,
            forced_stop=result.forced_stop,
            reflection=reflection,
            error=result.error,
        )

    except Exception as e:
        logger.error("[api_service] /api/agent/query 处理异常: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Agent 推理错误: {str(e)}")


@app.post("/api/retrieve", response_model=RetrieveResponse, summary="仅检索（不生成）")
async def api_retrieve(request: RetrieveRequest):
    """
    仅检索接口：执行混合检索 + gte-rerank-v2 重排，不生成答案

    - **query**: 查询文本（必填）
    - **company_name**: 限定公司名（可选，不填则检索所有公司）
    - **top_n**: 重排后返回条数（默认5，范围1-20）
    """
    logger.info("=" * 60)
    logger.info("[api_service] 收到 /api/retrieve 请求")
    logger.info("[api_service] 查询: '%s'", request.query)
    logger.info("[api_service] 指定公司: %s", request.company_name or "全部")
    logger.info("[api_service] top_n: %d", request.top_n)

    if rag_generator is None:
        logger.error("[api_service] RAGGenerator 未初始化，无法处理请求")
        raise HTTPException(status_code=503, detail="RAGGenerator 未初始化，服务暂不可用")

    try:
        start_time = time.time()
        retriever = rag_generator._get_retriever()
        results = retriever.search(
            query=request.query,
            company_name=request.company_name,
            top_n=request.top_n,
        )
        elapsed = time.time() - start_time
        logger.info("[api_service] /api/retrieve 处理完成，耗时: %.2f 秒", elapsed)
        logger.info("[api_service] 检索结果数: %d", len(results))

        return {
            "results": results,
            "query": request.query,
            "company_name": request.company_name,
            "total_count": len(results),
        }
    except ValueError as e:
        logger.error("[api_service] /api/retrieve 参数错误: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        logger.error("[api_service] /api/retrieve 文件未找到: %s", str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("[api_service] /api/retrieve 处理异常: %s", str(e))
        raise HTTPException(status_code=500, detail=f"内部服务错误: {str(e)}")


@app.get("/api/companies", response_model=CompaniesResponse, summary="获取可用公司列表")
async def api_companies():
    """获取当前向量数据库中所有可用公司的列表"""
    logger.info("[api_service] 收到 /api/companies 请求")

    if rag_generator is None:
        logger.error("[api_service] RAGGenerator 未初始化，无法处理请求")
        raise HTTPException(status_code=503, detail="RAGGenerator 未初始化，服务暂不可用")

    try:
        retriever = rag_generator._get_retriever()
        if not retriever._company_registry:
            retriever._load_company_registry()

        companies_dict = retriever._company_registry.get("companies", {})
        companies = []
        for name, info in companies_dict.items():
            display_name = info.get("display_name", name) if isinstance(info, dict) else name
            companies.append(CompanyInfo(name=name, display_name=display_name))
            logger.info("[api_service]   公司: %s (显示名: %s)", name, display_name)

        logger.info("[api_service] /api/companies 返回 %d 家公司", len(companies))
        return {
            "companies": companies,
            "total_count": len(companies),
        }
    except FileNotFoundError as e:
        logger.error("[api_service] /api/companies 公司注册表未找到: %s", str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("[api_service] /api/companies 处理异常: %s", str(e))
        raise HTTPException(status_code=500, detail=f"内部服务错误: {str(e)}")


@app.get("/api/health", response_model=HealthResponse, summary="健康检查")
async def api_health():
    """健康检查接口，返回服务状态和基本配置信息"""
    logger.info("[api_service] 收到 /api/health 请求")

    status = "ok" if rag_generator is not None else "not_ready"
    logger.info("[api_service] /api/health 返回状态: %s, RAGGenerator 已加载: %s, Agent 已加载: %s",
                 status, rag_generator is not None, agent is not None)

    return {
        "status": status,
        "vector_db_dir": str(vector_db_dir),
        "rag_generator_loaded": rag_generator is not None,
        "agent_loaded": agent is not None,
    }
