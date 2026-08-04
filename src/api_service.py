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
import re
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, List, Optional, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from .retrieval import RAGGenerator, HybridRetriever, COMPANY_ABBREV_MAP
from .query_processor import QueryProcessor
from .conversation import ConversationManager
from .agent_core import ReActAgent
from .agent_memory import AgentMemory
from .tools import ToolRegistry
from .tools.retrieve_tool import RetrieveTool
from .tools.calculator_tool import CalculatorTool
from .tools.compare_tool import CompareTool
from .tools.chart_tool import ChartTool
from .tools.verify_tool import VerifyTool
from .planner import TaskPlanner
from .reflector import AnswerReflector

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
# query_processor 使用可变容器存放，避免 @asynccontextmanager 破坏 global 声明的问题
_shared_state: dict = {"query_processor": None}

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
        # reflector 默认配置
        "enable_verification": True,
        "enable_hallucination_check": True,
        "auto_correct": True,
        "hallucination_threshold": 0.05,
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
        reflector_cfg = config.get("reflector", {})
        memory_cfg = config.get("memory", {})
        api_cfg = config.get("api", {})

        if not agent_cfg:
            logger.warning("[config_loader] agent 配置节为空 | 使用默认配置")

        result = {}
        for key, default_val in default_config.items():
            # reflector 开头的 key 从 reflector 配置节读取
            if key in ("enable_verification", "enable_hallucination_check",
                       "auto_correct", "hallucination_threshold"):
                val = reflector_cfg.get(key, default_val)
                source = "文件[reflector]" if key in reflector_cfg else "默认"
            else:
                val = agent_cfg.get(key, default_val)
                source = "文件[agent]" if key in agent_cfg else "默认"
            result[key] = val
            logger.info("[config_loader] %s=%s | 来源=%s | 默认=%s",
                         key, val, source, default_val)

        # memory 配置
        result["memory_working_memory_limit"] = memory_cfg.get("working_memory_limit", 10)
        result["memory_episodic_memory_turns"] = memory_cfg.get("episodic_memory_turns", 5)
        result["memory_enable_long_term"] = memory_cfg.get("enable_long_term", False)
        logger.info("[config_loader] memory: working_limit=%d, episodic_turns=%d, long_term=%s",
                     result["memory_working_memory_limit"],
                     result["memory_episodic_memory_turns"],
                     result["memory_enable_long_term"])

        # api 配置
        result["api_key"] = api_cfg.get("key", "no-key-needed")
        result["api_max_steps_hard_limit"] = api_cfg.get("max_steps_hard_limit", 15)
        logger.info("[config_loader] api: key=%s, max_steps_hard_limit=%d",
                     "***" if result["api_key"] != "no-key-needed" else "no-key-needed",
                     result["api_max_steps_hard_limit"])

        # 检查是否有未识别的配置项
        unexpected_agent = set(agent_cfg.keys()) - set(default_config.keys())
        unexpected_reflector = set(reflector_cfg.keys()) - set(default_config.keys())
        if unexpected_agent:
            logger.warning("[config_loader] 未识别的 agent 配置项将被忽略 | keys=%s", unexpected_agent)
        if unexpected_reflector:
            logger.warning("[config_loader] 未识别的 reflector 配置项将被忽略 | keys=%s", unexpected_reflector)

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

# API 鉴权配置（在 _init_globals() 中设置）
_api_key: str = ""
_max_steps_hard_limit: int = 15


# ==================== 请求模型 ====================

class QueryRequest(BaseModel):
    """RAG 问答请求"""
    query: str = Field(..., description="查询文本")
    company_name: Optional[str] = Field(None, description="限定公司名（可选）")
    top_n: int = Field(5, description="重排后返回条数", ge=1, le=20)
    conversation_id: Optional[str] = Field(None, description="对话ID（可选，不提供则自动生成）")
    enable_rewrite: bool = Field(True, description="是否启用意图识别与Query改写")


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
    company_name: Optional[str] = None
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
    filter_enabled: bool = False
    filter_config_loaded: bool = False


# ==================== Agent 模式请求/响应 ====================

class AgentQueryRequest(BaseModel):
    """Agent 查询请求"""
    query: str = Field(..., description="查询文本")
    max_steps: int = Field(5, description="Agent 最大推理步数", ge=1, le=100)
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

def _init_globals():
    """初始化所有全局变量（必须在普通函数中执行，@asynccontextmanager 会破坏 global 声明）"""
    global rag_generator, agent, agent_registry, agent_planner, agent_reflector
    global _api_key, _max_steps_hard_limit

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
    _shared_state["query_processor"] = QueryProcessor()
    logger.info("[api_service] QueryProcessor 实例创建完成")

    # ---- Agent 模式初始化 ----
    logger.info("[api_service] 开始初始化 Agent 模式组件...")

    agent_registry = ToolRegistry()
    agent_registry.register(RetrieveTool())
    agent_registry.register(CalculatorTool())
    agent_registry.register(CompareTool())
    agent_registry.register(ChartTool())
    agent_registry.register(VerifyTool())
    logger.info("[api_service] Agent 工具注册完成: %d 个工具", len(agent_registry._tools))

    agent_planner = TaskPlanner()

    # 从 config 文件加载 Agent 配置参数
    ag_cfg = _load_agent_config()

    agent_reflector = AnswerReflector(
        enable_verification=ag_cfg["enable_verification"],
        enable_hallucination_check=ag_cfg["enable_hallucination_check"],
        auto_correct=ag_cfg["auto_correct"],
        hallucination_threshold=ag_cfg["hallucination_threshold"],
    )
    logger.info("[api_service] Agent 规划器 + 反思器 初始化完成, reflector 配置: %s",
                {k: ag_cfg[k] for k in ("enable_verification", "enable_hallucination_check",
                                         "auto_correct", "hallucination_threshold")})

    # AgentMemory - 从配置读取 memory 参数（OPT-04 修复）
    # 不再创建全局 agent 实例，改为 per-request 创建（并发安全修复）
    # 将共享组件存入 _shared_state
    _shared_state["tool_registry"] = agent_registry
    _shared_state["planner"] = agent_planner
    _shared_state["reflector"] = agent_reflector
    _shared_state["ag_cfg"] = ag_cfg
    _shared_state["agent_initialized"] = True
    logger.info("[api_service] Agent 共享组件初始化完成 (per-request 模式), 配置: %s", ag_cfg)

    # 设置 API 鉴权全局变量
    global _api_key, _max_steps_hard_limit
    _api_key = ag_cfg.get("api_key", "no-key-needed")
    _max_steps_hard_limit = ag_cfg.get("api_max_steps_hard_limit", 15)
    if _api_key == "no-key-needed":
        logger.warning("[api_service] API Key 使用默认值, 请尽快修改!")
    else:
        logger.info("[api_service] API Key 已配置")

    logger.info("[api_service] FastAPI 应用启动完成")
    logger.info("=" * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化 RAGGenerator，关闭时清理资源
    
    注意: @asynccontextmanager 装饰器会将函数转为生成器，导致 Python 的 global 声明失效。
    因此所有 global 变量的赋值必须放在普通同步函数 _init_globals() 中。
    """
    _init_globals()

    yield

    logger.info("=" * 60)
    logger.info("[api_service] FastAPI 应用关闭中...")
    global rag_generator, agent, agent_registry, agent_planner, agent_reflector
    rag_generator = None
    _shared_state["query_processor"] = None
    agent = None
    agent_registry = None
    agent_planner = None
    agent_reflector = None
    logger.info("[api_service] RAGGenerator + QueryProcessor + Agent 实例已释放")
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

# CORS 中间件: 允许前端跨域访问（开发环境 Vite 代理 + 直连双模式）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class APIAuthMiddleware(BaseHTTPMiddleware):
    """API Key 鉴权中间件

    校验所有请求的 Authorization: Bearer <key> 请求头。
    白名单路径无需鉴权: /api/health, /docs, /openapi.json, /redoc
    """

    # 无需鉴权的路径
    SKIP_PATHS = {"/api/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next):
        # 健康检查和文档接口无需鉴权
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        # 从模块级变量读取 API Key
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.warning("[auth] 请求缺少 API Key | path=%s | client=%s",
                           request.url.path, request.client.host if request.client else "unknown")
            return JSONResponse(
                status_code=401,
                content={"detail": "未授权: 缺少 API Key"}
            )

        token = auth_header[len("Bearer "):]
        if token != _api_key:
            logger.warning("[auth] API Key 无效 | path=%s", request.url.path)
            return JSONResponse(
                status_code=401,
                content={"detail": "未授权: API Key 无效"}
            )

        return await call_next(request)


app.add_middleware(APIAuthMiddleware)

# 静态文件服务：挂载图表图片目录，前端可通过 /api/charts/{filename} 访问
_charts_dir = project_root / "data" / "charts"
_charts_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/charts", StaticFiles(directory=str(_charts_dir)), name="charts")


# ==================== API 接口 ====================

@app.post("/api/query", response_model=QueryResponse, summary="完整 RAG 问答（检索+生成）")
async def api_query(request: QueryRequest):
    """
    完整 RAG 问答接口：执行混合检索 + gte-rerank-v2 重排 + 生成答案

    - **query**: 查询文本（必填）
    - **company_name**: 限定公司名（可选，不填则检索所有公司）
    - **top_n**: 重排后返回条数（默认5，范围1-20）
    - **conversation_id**: 对话ID（可选，不提供则自动生成）
    - **enable_rewrite**: 是否启用意图识别与Query改写（默认True）
    """
    logger.info("=" * 60)
    logger.info("[api_service] 收到 /api/query 请求")
    logger.info("[api_service] 查询: '%s'", request.query)
    logger.info("[api_service] 指定公司: %s", request.company_name or "全部")
    logger.info("[api_service] top_n: %d, enable_rewrite: %s", request.top_n, request.enable_rewrite)

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

        if request.enable_rewrite and _shared_state["query_processor"] is not None:
            try:
                qp_result = _shared_state["query_processor"].process(request.query)
                intent = qp_result.get("intent")
                mentioned_companies = qp_result.get("extracted_companies")
                extracted_years = qp_result.get("extracted_years")
                logger.info("[api_service] 意图识别: intent=%s, 公司=%s, 年份=%s",
                             intent, mentioned_companies, extracted_years)
                if intent == "out_of_domain":
                    elapsed = time.time() - start_time
                    logger.info("[api_service] 域外问题拦截成功: intent=%s", intent)
                    return QueryResponse(
                        answer="抱歉，您的问题不在企业财报分析范围内，我无法回答。",
                        sources=[],
                        query=request.query,
                        retrieved_count=0,
                        processing_time=round(elapsed, 3),
                        conversation_id=conversation_id,
                    )
            except Exception as e:
                logger.warning("[api_service] QueryProcessor 调用失败: %s，继续使用原始查询", str(e))
        else:
            logger.info("[api_service] 意图识别已禁用或 QueryProcessor 未初始化, enable_rewrite=%s, qp=%s", request.enable_rewrite, _shared_state["query_processor"] is not None)

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

def _create_per_request_agent(memory: AgentMemory, max_steps: int, temperature: float) -> ReActAgent:
    """为每个请求创建独立的 Agent 实例（并发安全）

    Args:
        memory: 会话独立的 AgentMemory 实例
        max_steps: 请求的 max_steps（会被硬上限截断）
        temperature: LLM 温度

    Returns:
        新创建的 ReActAgent 实例
    """
    ag_cfg = _shared_state["ag_cfg"]
    hard_limit = ag_cfg.get("api_max_steps_hard_limit", 15)
    effective_max_steps = min(max_steps, hard_limit)
    if max_steps > hard_limit:
        logger.warning("[per-request] max_steps 超出硬上限, 已截断: %d -> %d", max_steps, hard_limit)

    return ReActAgent(
        tool_registry=_shared_state["tool_registry"],
        memory=memory,
        max_steps=effective_max_steps,
        temperature=temperature,
        model=ag_cfg["model"],
        llm_timeout=ag_cfg["llm_timeout"],
        max_retries=ag_cfg["max_retries"],
    )


@app.post("/api/agent/query", response_model=AgentQueryResponse,
          summary="Agent 模式查询 (ReAct 推理 + 工具调用)")
async def api_agent_query(request: AgentQueryRequest):
    logger.info("=" * 60)
    logger.info("[api_service] 收到 /api/agent/query 请求")
    logger.info("[api_service] Agent 查询: '%s', max_steps=%d, temperature=%.2f",
                 request.query, request.max_steps, request.temperature)

    if not _shared_state.get("agent_initialized"):
        logger.error("[api_service] Agent 未初始化，无法处理请求")
        raise HTTPException(status_code=503, detail="Agent 未初始化，服务暂不可用")

    # ---- 会话隔离: 每个 conversation_id 持有独立的 AgentMemory ----
    conversation_id = request.conversation_id or str(uuid.uuid4())
    cm = _ensure_conversation(conversation_id)
    if cm.agent_memory is None:
        cm.link_memory(AgentMemory())
    per_request_memory = cm.agent_memory  # 会话独立的 memory

    # 为每个请求创建独立 Agent 实例（并发安全）
    agent = _create_per_request_agent(
        memory=per_request_memory,
        max_steps=request.max_steps,
        temperature=request.temperature,
    )
    logger.info("[api_service] Agent 实例已创建 (per-request): max_steps=%d, temperature=%.2f",
                 agent.max_steps, agent.temperature)

    try:
        # ---- 1. 任务规划 ----
        planner = _shared_state.get("planner")
        if planner is not None:
            logger.info("[api_service] 阶段 1/3: 任务规划")
            plan = planner.plan(request.query)
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
        reflector = _shared_state.get("reflector")
        if reflector is not None and result.answer:
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

            ref_result = reflector.verify(result.answer, sources, request.query)
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
        raise HTTPException(status_code=500, detail="Agent 推理过程发生内部错误")


@app.get("/api/agent/stream", summary="Agent SSE 流式推理 (Phase 2)")
async def api_agent_stream(
    query: str,
    company_name: Optional[str] = None,
    max_steps: int = 5,
    temperature: float = 0.3,
    conversation_id: Optional[str] = None,
):
    """Agent 流式推理 SSE 端点

    使用 Server-Sent Events (SSE) 协议实时推送 Agent 推理的中间步骤。
    事件类型: thought / action / observation / answer / error / done

    - **query**: 查询文本 (必填)
    - **company_name**: 指定公司名 (可选)
    - **max_steps**: 最大推理步数 (默认5, 范围1-20)
    - **temperature**: LLM 温度 (默认0.3)
    - **conversation_id**: 会话ID (可选, 用于记忆隔离)
    """
    logger.info("=" * 60)
    logger.info("[api_service] 收到 /api/agent/stream 请求")
    logger.info("[api_service] SSE 查询: '%s', max_steps=%d", query, max_steps)

    if not _shared_state.get("agent_initialized"):
        logger.error("[api_service] Agent 未初始化，无法处理 SSE 请求")
        raise HTTPException(status_code=503, detail="Agent 未初始化，服务暂不可用")

    # 会话隔离
    conv_id = conversation_id or str(uuid.uuid4())
    cm = _ensure_conversation(conv_id)
    if cm.agent_memory is None:
        cm.link_memory(AgentMemory())
    per_request_memory = cm.agent_memory

    # 为每个请求创建独立 Agent 实例（并发安全）
    agent = _create_per_request_agent(
        memory=per_request_memory,
        max_steps=max_steps,
        temperature=temperature,
    )
    logger.info("[api_service] SSE Agent 实例已创建 (per-request): max_steps=%d", agent.max_steps)

    async def event_generator():
        """异步事件生成器，将 Agent 的同步 yield 转为异步 SSE 流"""
        import asyncio
        try:
            # 立即发送初始连接确认事件，避免浏览器 EventSource 因长时间无数据而超时断开
            yield f"data: {json.dumps({'type': 'connected', 'timestamp': int(time.time() * 1000)}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0)  # 让出事件循环，确保初始事件被发送

            for event in agent.run_stream(query, company_name=company_name):
                event_json = json.dumps(event, ensure_ascii=False, default=str)
                yield f"data: {event_json}\n\n"
                await asyncio.sleep(0)  # 每步让出事件循环，避免阻塞
        except Exception as e:
            logger.error("[api_service] SSE 流异常: %s", str(e))
            error_event = json.dumps({
                "type": "error",
                "content": "流式推理过程发生内部错误",
            }, ensure_ascii=False)
            yield f"data: {error_event}\n\n"

    logger.info("[api_service] SSE 流已建立连接")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
        "filter_enabled": (
            _shared_state["query_processor"] is not None
            and _shared_state["query_processor"]._filter_config is not None
            and _shared_state["query_processor"]._filter_config.get("enabled", False)
        ),
        "filter_config_loaded": (
            _shared_state["query_processor"] is not None
            and _shared_state["query_processor"]._filter_config is not None
        ),
    }



# ==================== 管理员接口: 过滤器配置 ====================

@app.get("/api/admin/filter-status", summary="查看域外过滤器配置状态")
async def api_filter_status():
    """返回域外过滤器的当前配置状态 (规则数量, 启用状态, 模式等)"""
    logger.info("[api_service] 收到 /api/admin/filter-status 请求")

    if _shared_state["query_processor"] is None:
        return {"status": "unavailable", "message": "QueryProcessor 未初始化"}

    config = _shared_state["query_processor"]._filter_config
    if config is None:
        return {
            "status": "disabled",
            "message": "配置文件不存在或加载失败",
            "config_path": str(_shared_state["query_processor"]._FILTER_CONFIG_PATH),
        }

    return {
        "status": "loaded",
        "enabled": config.get("enabled", False),
        "mode": config.get("mode", "reject"),
        "config_path": str(_shared_state["query_processor"]._FILTER_CONFIG_PATH),
        "out_of_domain_rules": len(config.get("out_of_domain_patterns", [])),
        "unsafe_content_rules": len(config.get("unsafe_content_patterns", [])),
        "reject_message_custom": bool(config.get("reject_message", "")),
    }


@app.post("/api/admin/filter-reload", summary="热重载域外过滤器配置")
async def api_filter_reload():
    """重新加载 domain_filter.yaml 配置，无需重启服务"""
    logger.info("[api_service] 收到 /api/admin/filter-reload 请求")

    if _shared_state["query_processor"] is None:
        raise HTTPException(status_code=503, detail="QueryProcessor 未初始化")

    success = _shared_state["query_processor"]._reload_filter_config()

    if success:
        config = _shared_state["query_processor"]._filter_config
        return {
            "status": "reloaded" if config.get("enabled") else "disabled",
            "message": "配置文件热重载成功" if success else "配置文件加载失败",
            "rules": {
                "out_of_domain": len(config.get("out_of_domain_patterns", [])) if config else 0,
                "unsafe_content": len(config.get("unsafe_content_patterns", [])) if config else 0,
            },
            "mode": config.get("mode") if config else "N/A",
        }
    else:
        return {
            "status": "disabled",
            "message": "配置文件不存在或无法解析，过滤器已禁用",
        }

# ==================== Phase 2 新增接口 ====================

@app.get("/api/charts/list", summary="获取所有图表列表（含结构化数据供 ECharts 渲染）")
async def api_charts_list():
    """返回 data/charts/ 目录下所有图表 JSON 文件的列表

    每个条目包含 chart_type, title, labels, values 等结构化数据，
    前端 ChartsPage 可直接用于 ECharts 交互式渲染。
    """
    charts = []
    if _charts_dir.exists():
        for json_file in sorted(_charts_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                data["image_url"] = "/api/charts/%s" % json_file.with_suffix(".png").name
                charts.append(data)
            except Exception as e:
                logger.warning("[api_service] 读取图表 JSON 失败: %s, %s", json_file.name, e)
    return {"charts": charts, "total": len(charts)}


@app.get("/api/agent/plan", summary="获取 Agent 任务规划数据（DAG 结构）")
async def api_agent_plan(query: str):
    """返回 TaskPlanner 对查询的拆解结果，包含子任务和依赖关系

    前端 DagBoardPage 可用于 @antv/g6 渲染 DAG 有向无环图。
    返回结构:
      - nodes: [{id, label, type, description, params, status}]
      - edges: [{source, target}]
      - execution_order: [[task_id, ...], ...]  -- 分批执行计划
    """
    if agent_planner is None:
        raise HTTPException(status_code=503, detail="任务规划器未初始化")

    plan = agent_planner.plan(query)
    if not plan or not plan.valid:
        return {"nodes": [], "edges": [], "execution_order": [], "message": "无法拆解该查询"}

    nodes = []
    edges = []
    for st in plan.subtasks:
        nodes.append({
            "id": st.task_id,
            "label": st.task_id,
            "type": st.task_type.value,
            "description": st.description,
            "tool_name": st.tool_name,
            "tool_params": st.tool_params,
            "status": st.status,
        })
        for dep_id in st.depends_on:
            edges.append({"source": dep_id, "target": st.task_id})

    return {
        "nodes": nodes,
        "edges": edges,
        "execution_order": plan.execution_order,
        "category": plan.category.category if plan.category else "unknown",
        "message": plan.message if plan.message else "",
    }


# ==================== LangBot 兼容接口 ====================

class LangBotRequest(BaseModel):
    """LangBot 自定义 API 请求格式 (OpenAI 兼容)"""
    messages: list = Field(..., description="对话消息列表, 格式: [{\"role\": \"user\", \"content\": \"...\"}]")
    model: Optional[str] = Field(None, description="模型名称 (LangBot 传入, 本接口忽略)")
    stream: bool = Field(False, description="是否流式响应 (暂不支持)")
    conversation_id: Optional[str] = Field(None, description="会话ID (可选, 用于记忆隔离)")


class LangBotResponse(BaseModel):
    """LangBot 自定义 API 响应格式 (OpenAI 兼容)"""
    choices: list
    usage: dict = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


@app.post("/api/langbot/chat", response_model=LangBotResponse,
          summary="LangBot 兼容接口 (企业微信接入)")
async def api_langbot_chat(request: LangBotRequest):
    """LangBot 企业微信接入兼容接口

    接收 OpenAI 兼容格式的请求, 提取用户消息后调用 Agent 查询,
    返回 OpenAI 兼容格式的响应。

    用于 LangBot 的自定义 API 流水线, 实现企业微信 → LangBot → 本服务 的消息链路。
    """
    logger.info("=" * 60)
    logger.info("[api_service] 收到 /api/langbot/chat 请求 (LangBot 兼容)")

    # 提取用户最后一条消息
    user_message = ""
    for msg in reversed(request.messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            user_message = msg.get("content", "")
            break

    if not user_message:
        logger.warning("[api_service] LangBot 请求中无用户消息")
        return LangBotResponse(
            choices=[{"message": {"role": "assistant", "content": "请发送您的问题"}}]
        )

    logger.info("[api_service] LangBot 用户消息: '%s'", user_message)

    if agent is None:
        logger.error("[api_service] Agent 未初始化")
        return LangBotResponse(
            choices=[{"message": {"role": "assistant", "content": "服务暂不可用, 请稍后重试"}}]
        )

    try:
        # 会话隔离
        conversation_id = request.conversation_id or str(uuid.uuid4())
        cm = _ensure_conversation(conversation_id)
        if cm.agent_memory is None:
            cm.link_memory(AgentMemory())
        agent.memory = cm.agent_memory

        # 调用 Agent 推理
        result = agent.run(user_message)
        answer = result.answer if result.answer else "抱歉, 未能找到相关信息。"

        logger.info("[api_service] LangBot 查询完成: success=%s, steps=%d, 答案长度=%d",
                     result.success, result.total_steps, len(answer))

        return LangBotResponse(
            choices=[{"message": {"role": "assistant", "content": answer}}]
        )

    except Exception as e:
        logger.error("[api_service] LangBot 查询异常: %s", str(e))
        return LangBotResponse(
            choices=[{"message": {"role": "assistant", "content": f"查询出错: {str(e)}"}}]
        )


# ==================== OpenAI 兼容接口 (供 LangBot 内置 Agent 调用) ====================

class OpenAIChatMessage(BaseModel):
    """OpenAI 消息格式, 兼容 content 为字符串或多模态数组两种格式"""
    role: str = Field(..., description="消息角色: system / user / assistant")
    content: Any = Field(..., description="消息内容: 字符串 或 多模态数组 [{\"type\":\"text\",\"text\":\"...\"}]")

    @field_validator('content', mode='before')
    @classmethod
    def coerce_content(cls, v):
        """预处理 content 字段: 接受字符串或列表, 统一转为字符串"""
        if isinstance(v, str):
            return v
        if isinstance(v, list):
            # 多模态格式: [{"type": "text", "text": "..."}, ...]
            parts = []
            for item in v:
                if isinstance(item, dict) and item.get('type') == 'text':
                    parts.append(item.get('text', ''))
            return ' '.join(parts) if parts else ''
        return str(v) if v is not None else ''


class OpenAIChatRequest(BaseModel):
    """OpenAI /v1/chat/completions 请求格式"""
    model: str = Field(default="rag-agent", description="模型名称 (LangBot 传入, 本接口忽略)")
    messages: List[OpenAIChatMessage] = Field(..., description="对话消息列表")
    stream: bool = Field(default=False, description="是否流式响应 (暂不支持)")
    temperature: Optional[float] = Field(default=None, description="温度参数 (忽略)")
    max_tokens: Optional[int] = Field(default=None, description="最大 token 数 (忽略)")
    conversation_id: Optional[str] = Field(default=None, description="会话ID (可选, 用于记忆隔离)")


def _strip_markdown_images(text: str) -> str:
    """移除 Markdown 图片语法，企业微信不支持 Markdown 渲染图片"""
    # 移除 ![alt](url) 格式
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # 移除可能残留的空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


@app.post("/v1/chat/completions",
          summary="OpenAI 兼容接口 (供 LangBot 内置 Agent 调用)")
async def api_openai_chat_completions(request: OpenAIChatRequest):
    """OpenAI Chat Completions 兼容接口

    接收标准 OpenAI chat completions 格式的请求,
    提取用户最后一条消息后调用 Agent 推理,
    返回 OpenAI 兼容格式的响应（支持 stream 流式和非流式）。

    用于 LangBot 内置 Agent 的 openai-chat-completions 请求器直接调用本服务。
    """
    import json as json_module

    logger.info("=" * 60)
    logger.info("[api_service] 收到 /v1/chat/completions 请求 (OpenAI 兼容), stream=%s", request.stream)

    # 从 messages 中提取最后一条用户消息
    user_message = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_message = msg.content
            break

    if not user_message:
        logger.warning("[api_service] OpenAI 请求中无用户消息")
        empty_resp = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "请发送您的问题"},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }
        if request.stream:
            return _stream_response(empty_resp)
        return empty_resp

    logger.info("[api_service] OpenAI 用户消息: '%s'", user_message)

    if agent is None:
        logger.error("[api_service] Agent 未初始化")
        err_resp = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "服务暂不可用, 请稍后重试"},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }
        if request.stream:
            return _stream_response(err_resp)
        return err_resp

    try:
        # 会话隔离
        conversation_id = request.conversation_id or str(uuid.uuid4())
        cm = _ensure_conversation(conversation_id)
        if cm.agent_memory is None:
            cm.link_memory(AgentMemory())
        agent.memory = cm.agent_memory

        # 调用 Agent 推理
        result = agent.run(user_message)
        answer = result.answer if result.answer else "抱歉, 未能找到相关信息。"
        # 企业微信不支持 Markdown 图片渲染，移除图片语法
        answer = _strip_markdown_images(answer)

        logger.info("[api_service] OpenAI 查询完成: success=%s, steps=%d, 答案长度=%d",
                     result.success, result.total_steps, len(answer))

        chat_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())

        resp = {
            "id": chat_id,
            "object": "chat.completion",
            "created": created,
            "model": request.model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }

        if request.stream:
            return _stream_response(resp)
        return resp

    except Exception as e:
        logger.error("[api_service] OpenAI 查询异常: %s", str(e))
        exc_resp = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": f"查询出错: {str(e)}"},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }
        if request.stream:
            return _stream_response(exc_resp)
        return exc_resp


def _stream_response(non_stream_resp: dict):
    """将非流式响应转换为 SSE 流式响应"""
    async def generate():
        import json as json_module
        chat_id = non_stream_resp["id"]
        created = non_stream_resp["created"]
        model = non_stream_resp["model"]
        content = non_stream_resp["choices"][0]["message"]["content"]

        # 第一个 chunk: delta.content = 完整内容
        chunk = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {"content": content},
                "finish_reason": None
            }]
        }
        yield f"data: {json_module.dumps(chunk, ensure_ascii=False)}\n\n"

        # 结束 chunk: finish_reason = "stop"
        end_chunk = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json_module.dumps(end_chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
