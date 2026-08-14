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
from .orchestrator_agent import OrchestratorAgent

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

        # ---- 新增：读取多 Agent 模型分配配置 ----
        result["models"] = agent_cfg.get("models", {})
        if result["models"]:
            logger.info("[config_loader] models 配置已加载: %s", list(result["models"].keys()))

        # ---- 新增：读取多 Agent 容错与超时配置 ----
        multi_agent_cfg = config.get("multi_agent", {})
        result["multi_agent"] = multi_agent_cfg
        if multi_agent_cfg:
            logger.info("[config_loader] multi_agent 配置已加载: %s", list(multi_agent_cfg.keys()))

        # 检查是否有未识别的配置项
        # models 是 agent 节内的嵌套配置，已被单独读取，不视为未识别项
        unexpected_agent = set(agent_cfg.keys()) - set(default_config.keys()) - {"models"}
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
    tags: List[str] = []
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
    company_name: Optional[str] = Field(None, description="限定公司名（可选）")
    max_steps: int = Field(5, description="Agent 最大推理步数", ge=1, le=100)
    temperature: float = Field(0.3, description="LLM 温度", ge=0.0, le=2.0)
    conversation_id: Optional[str] = Field(None, description="对话ID (可选, 不提供则自动生成)")
    mode: str = Field("auto", description="模式: auto / single / multi")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """验证 mode 取值必须在 auto/single/multi 中"""
        if v not in ("auto", "single", "multi"):
            raise ValueError(f"mode 必须是 auto / single / multi，当前值: {v}")
        return v


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


# ==================== 知识库管理 & 系统状态模型 ====================

class KnowledgeDocument(BaseModel):
    """知识库文档信息"""
    filename: str
    size: int
    size_mb: float
    upload_time: str
    indexed: bool


class KnowledgeListResponse(BaseModel):
    """知识库文档列表响应"""
    documents: list = []
    total: int = 0


class KnowledgeUploadResponse(BaseModel):
    """上传响应"""
    success: bool = True
    filename: str = ""
    size: int = 0
    size_mb: float = 0.0


class SystemStatusResponse(BaseModel):
    """系统状态响应"""
    model: dict = {}
    vector_db: dict = {}
    memory: dict = {}
    monitoring: dict = {}
    tools: dict = {}


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

    # ---- 新增：LLMProvider 初始化 ----
    from src.llm_provider import DashScopeProvider
    from src.utils import get_api_key
    api_key_for_agent = get_api_key()
    llm_provider = DashScopeProvider(api_key=api_key_for_agent)
    _shared_state["llm_provider"] = llm_provider
    logger.info("[api_service] DashScopeProvider 初始化完成")

    # ---- 新增：QueryRouter 初始化（步骤 0.3） ----
    from src.router import QueryRouter
    # DashScopeProvider 已在上方导入，此处复用同一 import 创建 router 独立实例
    router_llm = DashScopeProvider(api_key=api_key_for_agent)
    query_router = QueryRouter(turbo_llm=router_llm)
    _shared_state["query_router"] = query_router
    logger.info("[api_service] QueryRouter 初始化完成")

    # ---- 步骤 2.1：AgentRegistry 初始化（多 Agent 组件） ----
    from src.agent_registry import AgentRegistry, AgentCapability
    from src.shared_memory import SharedMemory

    agent_registry = AgentRegistry()
    agent_registry.register(AgentCapability(
        name="DataAgent",
        description="从向量数据库精确检索财务数据，支持指定公司名称",
        tools=["retrieve"],
        max_parallel=3,
        llm_model="qwen-turbo",
    ))
    _shared_state["agent_registry"] = agent_registry
    _shared_state["has_multi_agent"] = True

    # ---- 阶段三：注册其余 Worker Agent 能力 ----
    agent_registry.register(AgentCapability(
        name="CalcAgent",
        description="财务计算专家：执行增长率/CAGR/利润率计算，输入来自上游数据",
        tools=["calculator", "retrieve"],
        max_parallel=2,
        llm_model="qwen-plus",
    ))
    agent_registry.register(AgentCapability(
        name="CompareAgent",
        description="财务对比分析专家：多公司横向对比，输出 Markdown 表格",
        tools=["compare", "retrieve"],
        max_parallel=2,
        llm_model="qwen-max",
    ))
    agent_registry.register(AgentCapability(
        name="ChartAgent",
        description="图表渲染专家：从上游数据提取结构化数值并生成图表",
        tools=["chart"],
        max_parallel=2,
        llm_model="qwen-max",
    ))
    agent_registry.register(AgentCapability(
        name="VerifyAgent",
        description="财务数据审核专家：验证数字准确性和来源支撑关系",
        tools=["verify", "retrieve"],
        max_parallel=2,
        llm_model="qwen-plus",
    ))
    logger.info("[api_service] AgentRegistry 注册完成: %d 个 Worker", len(agent_registry.list_all()))

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
    # M6 修复: 清理 _shared_state 中的组件
    _shared_state.clear()
    logger.info("[api_service] _shared_state 已清理")
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

    # 无需鉴权的路径（精确匹配）
    SKIP_PATHS = {
        "/api/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        # 前端页面内部接口：EventSource / 原生 fetch 无法携带鉴权头
        "/api/agent/stream",
        "/api/agent/plan",
        "/api/charts/list",
    }

    # 无需鉴权的路径前缀（动态资源，如前端展示的图表图片）
    SKIP_PREFIXES = ("/api/charts/images/",)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # 健康检查、文档接口及前端内部接口无需鉴权
        if path in self.SKIP_PATHS or path.startswith(self.SKIP_PREFIXES):
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

# 静态文件服务：挂载图表图片目录，前端可通过 /api/charts/images/{filename} 访问
# 使用 /api/charts/images 子路径，避免与 /api/charts/list 等 API 路由冲突
_charts_dir = project_root / "data" / "charts"
_charts_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/charts/images", StaticFiles(directory=str(_charts_dir)), name="charts")


def _extract_markdown_tables(answer: str, query: str) -> int:
    """从 LLM 回答中提取 markdown 表格，保存为 chart 条目（chart_type=table）

    返回保存的表格数量。
    """
    saved_count = 0
    # 匹配 markdown 表格：连续的 |...| 行
    lines = answer.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not (line.startswith("|") and line.endswith("|")):
            i += 1
            continue

        # 找到表格开头
        header_line = line
        header_cells = [c.strip() for c in header_line.split("|")[1:-1]]
        if len(header_cells) < 2:
            i += 1
            continue

        # 下一行应该是分隔行
        if i + 1 >= len(lines):
            i += 1
            continue
        sep_line = lines[i + 1].strip()
        if not (sep_line.startswith("|") and all(c.strip() in ("---", ":---", "---:", ":---:") for c in sep_line.split("|")[1:-1])):
            i += 1
            continue

        # 收集数据行
        rows = []
        j = i + 2
        while j < len(lines):
            row_line = lines[j].strip()
            if not (row_line.startswith("|") and row_line.endswith("|")):
                break
            row_cells = [c.strip() for c in row_line.split("|")[1:-1]]
            if len(row_cells) == len(header_cells):
                rows.append(row_cells)
            j += 1

        if rows:
            # 构建文件路径
            safe_query = re.sub(r'[^\u4e00-\u9fff\w\-]', '_', query[:30]).strip('_')
            ts = int(time.time() * 1000)
            file_name = f"table_{safe_query}_{ts}.json"
            json_path = _charts_dir / file_name

            table_data = {
                "chart_type": "table",
                "title": query[:60] + ("..." if len(query) > 60 else ""),
                "columns": header_cells,
                "rows": rows,
                "file_name": file_name,
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            json_path.write_text(json.dumps(table_data, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("[api_service] 表格已保存到图表模块: %s (%d列 x %d行)", file_name, len(header_cells), len(rows))
            saved_count += 1

        i = j

    return saved_count


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

        # 提取回答中的 markdown 表格，保存到数据图表模块
        table_count = _extract_markdown_tables(answer, request.query)
        if table_count > 0:
            result["table_count"] = table_count  # 告知前端有表格可查看

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

def _create_per_request_agent(memory: AgentMemory, max_steps: int, temperature: float,
                               llm_provider: Optional[Any] = None) -> ReActAgent:
    """为每个请求创建独立的 Agent 实例（并发安全）

    Args:
        memory: 会话独立的 AgentMemory 实例
        max_steps: 请求的 max_steps（会被硬上限截断）
        temperature: LLM 温度
        llm_provider: LLM 提供者实例（可选，用于多 Agent 模式）

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
        llm_provider=llm_provider,
        prompt_name="default",
    )


async def _handle_multi_agent_query(
    request: AgentQueryRequest,
    cm: ConversationManager,
    conversation_id: str,
    route_result: Optional[Any] = None,
) -> AgentQueryResponse:
    """处理多 Agent 查询请求（阶段四提取为独立函数）

    支持 mode="multi" 显式调用和 auto 模式下 router 自动分派。

    Args:
        request: Agent 查询请求（含 mode/company_name）
        cm: 会话管理器
        conversation_id: 会话ID
        route_result: 路由结果（auto 模式下由 router 提供，multi 模式下为 None）

    Returns:
        AgentQueryResponse 响应对象
    """
    import asyncio
    from src.shared_memory import SharedMemory
    from src.tools.delegate_tool import DelegateTool

    shared_memory = SharedMemory()
    shared_memory.set_task_context("query", request.query)
    if route_result and route_result.category:
        shared_memory.set_task_context("companies", route_result.category.company_names)
    # 传递 company_name（阶段四新增）
    if request.company_name:
        shared_memory.set_task_context("company_name", request.company_name)

    agent_registry = _shared_state.get("agent_registry")
    delegate_tool = DelegateTool(
        agent_registry=agent_registry,
        shared_memory=shared_memory,
    )
    orchestrator = OrchestratorAgent(
        delegate_tool=delegate_tool,
        agent_registry=agent_registry,
        llm_provider=_shared_state.get("llm_provider"),
        shared_memory=shared_memory,
    )

    # 执行多 Agent 推理（阶段四新增 company_name 传递，H3 超时保护）
    _agent_cfg = _load_agent_config()
    _orchestrator_timeout = _agent_cfg.get("orchestrator_timeout",
        _agent_cfg.get("multi_agent", {}).get("orchestrator_timeout", 300))
    loop = asyncio.get_event_loop()
    try:
        # run(self, query, conversation_history="", company_name=None, shared_context="")
        result = await asyncio.wait_for(
            loop.run_in_executor(None, orchestrator.run,
                                 request.query,
                                 cm.get_context_string(max_turns=3),
                                 request.company_name),
            timeout=_orchestrator_timeout,
        )
    except asyncio.TimeoutError:
        logger.error("[api_service] 多 Agent 执行超时 (%.1fs), 将回退到单Agent", _orchestrator_timeout)
        return None
    except Exception as e:
        logger.error("[api_service] 多 Agent 执行异常: %s, 将回退到单Agent", str(e))
        return None

    # Reflector 反思（使用 SharedMemory 聚合的来源）
    reflection = None
    reflector = _shared_state.get("reflector")
    if reflector and result.answer:
        try:
            sources = shared_memory.get_all_sources()
            ref_result = reflector.verify(result.answer, sources, request.query)
            reflection = {
                "score": ref_result.overall_confidence,
                "issues": ref_result.suggestions,
                "corrected_answer": ref_result.corrected_answer if ref_result.corrected_answer else None,
            }
        except Exception as re:
            logger.warning("[api_service] reflection 异常(非致命): %s", re)
            reflection = None

    # 构建响应
    response = AgentQueryResponse(
        success=result.success,
        answer=result.answer,
        total_steps=result.total_steps,
        total_elapsed_ms=result.total_elapsed_ms,
        forced_stop=result.forced_stop,
        error=result.error,
        reasoning_chain=result.reasoning_chain if result.reasoning_chain else [],
        reflection=reflection,
    )
    logger.info("[api_service] 多 Agent 执行完成: success=%s, workers=%d, total_tokens=%d",
                 result.success, len(shared_memory.agent_outputs),
                 getattr(result, "total_tokens", 0))

    # 记录对话历史
    cm.add_message("user", request.query)
    cm.add_message("assistant", result.answer)
    return response


def _split_answer_chunks(text: str) -> list:
    """将完整答案按句拆分，用于 answer_chunk 流式推送（单/多 Agent 复用）

    以句号、换行、中文/英文分号作为切分点，保留分隔符附于前一 chunk。
    空串返回空列表。
    """
    if not text:
        return []
    parts = re.split(r'([。\n；;])', text)
    chunks = []
    for i in range(0, len(parts), 2):
        chunk = parts[i]
        if i + 1 < len(parts):
            chunk += parts[i + 1]
        if chunk.strip():
            chunks.append(chunk.strip())
    return chunks


async def _stream_single_agent(
    agent: ReActAgent,
    query: str,
    company_name: Optional[str],
    cm: ConversationManager,
):
    """单 Agent 流式 SSE 事件生成器

    事件序列: connected → thought → action → observation → answer → reflection → done
    注意：router 决策已在上层 event_generator() 完成，此函数不重复查询。
    """
    import asyncio as _asyncio

    # 发送 connected 事件
    yield f"data: {json.dumps({'type': 'connected', 'timestamp': int(time.time() * 1000)}, ensure_ascii=False)}\n\n"
    await _asyncio.sleep(0)

    final_answer = ""
    has_error = False
    try:
        for event in agent.run_stream(query, company_name=company_name):
            event_type = event.get("type", "")
            if event_type == "answer":
                final_answer = event.get("content", "") or event.get("answer", "")
                # answer 前逐句推送 answer_chunk，与多 Agent 保持一致的打字机效果
                for chunk in _split_answer_chunks(final_answer):
                    yield f"data: {json.dumps({'type': 'answer_chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
                    await _asyncio.sleep(0)
            event_json = json.dumps(event, ensure_ascii=False, default=str)
            yield f"data: {event_json}\n\n"
            await _asyncio.sleep(0)
    except Exception as e:
        has_error = True
        logger.error("[api_service] _stream_single_agent 异常: %s", str(e))
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    # ---- 事件: reflection (阶段四对齐，H1-H2 修复) ----
    if not has_error and final_answer:
        reflector = _shared_state.get("reflector")
        if reflector:
            try:
                ref_result = reflector.verify(final_answer, [], query)
                reflection_event = {
                    "type": "reflection",
                    "score": ref_result.overall_confidence,
                    "issues": ref_result.suggestions,
                    "corrected_answer": ref_result.corrected_answer if ref_result.corrected_answer else None,
                    "timestamp": int(time.time() * 1000),
                }
                yield f"data: {json.dumps(reflection_event, ensure_ascii=False, default=str)}\n\n"
            except Exception as re:
                logger.warning("[api_service] reflection 验证异常(非致命): %s", re)

    # ---- 事件: done (H1 修复: 前端依赖此事件判定流结束) ----
    yield f"data: {json.dumps({'type': 'done', 'timestamp': int(time.time() * 1000)}, ensure_ascii=False)}\n\n"

    # ---- 对话历史写入 (H2 修复: 确保 single 模式流式请求更新会话记忆) ----
    cm.add_message("user", query)
    if final_answer:
        cm.add_message("assistant", final_answer)


async def _stream_multi_agent(
    query: str,
    company_name: Optional[str],
    cm: ConversationManager,
):
    """多 Agent 流式 SSE 事件生成器（阶段四提取为独立函数）

    事件序列: connected → orchestrator_start → delegating
              → worker_step(N次) → worker_done(N次)
              → answer_chunk(N次) → answer → reflection → done
    """
    import asyncio as _asyncio
    import queue
    import threading
    from src.shared_memory import SharedMemory
    from src.tools.delegate_tool import DelegateTool

    shared_memory = SharedMemory()
    shared_memory.set_task_context("query", query)
    if company_name:
        shared_memory.set_task_context("company_name", company_name)

    agent_registry = _shared_state.get("agent_registry")
    event_queue = queue.Queue()

    delegate_tool = DelegateTool(
        agent_registry=agent_registry,
        shared_memory=shared_memory,
        event_queue=event_queue,
    )
    orchestrator = OrchestratorAgent(
        delegate_tool=delegate_tool,
        agent_registry=agent_registry,
        llm_provider=_shared_state.get("llm_provider"),
        shared_memory=shared_memory,
    )

    # ---- 事件1: connected ----
    yield f"data: {json.dumps({'type': 'connected', 'timestamp': int(time.time() * 1000)}, ensure_ascii=False)}\n\n"
    await _asyncio.sleep(0)

    # ---- 事件2: orchestrator_start ----
    agent_list = agent_registry.list_all() if agent_registry else []
    yield f"data: {json.dumps({'type': 'orchestrator_start', 'registered_agents': agent_list, 'timestamp': int(time.time() * 1000)}, ensure_ascii=False)}\n\n"

    # ---- 事件3: delegating（阶段四新增）----
    yield f"data: {json.dumps({'type': 'delegating', 'batch': 0, 'agents': agent_list, 'timestamp': int(time.time() * 1000)}, ensure_ascii=False)}\n\n"

    # 在独立线程中执行 Orchestrator
    final_result = [None]
    orchestrator_error = [None]

    def _run_orchestrator():
        try:
            final_result[0] = orchestrator.run(
                query=query,
                company_name=company_name,  # 阶段四新增
                conversation_history=cm.get_context_string(max_turns=3),
            )
        except Exception as e:
            orchestrator_error[0] = str(e)
            logger.error("[api_service] Orchestrator 执行异常: %s", str(e))

    orchestrator_thread = threading.Thread(target=_run_orchestrator, daemon=True)
    orchestrator_thread.start()

    # 轮询 Worker 步骤事件（H3 超时保护）
    orchestrator_done = False
    _start_ts = time.time()
    _ss_timeout = _load_agent_config().get("orchestrator_timeout",
        _load_agent_config().get("multi_agent", {}).get("orchestrator_timeout", 300))
    while not orchestrator_done:
        try:
            while True:
                event = event_queue.get_nowait()
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        except queue.Empty:
            pass

        orchestrator_thread.join(timeout=0.1)
        orchestrator_done = not orchestrator_thread.is_alive()
        if not orchestrator_done and (time.time() - _start_ts) > _ss_timeout:
            logger.error("[api_service] _stream_multi_agent 执行超时 (%.1fs)", _ss_timeout)
            yield f"data: {json.dumps({'type': 'error', 'content': f'多Agent执行超时({_ss_timeout}s)'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'timestamp': int(time.time() * 1000)}, ensure_ascii=False)}\n\n"
            return
        await _asyncio.sleep(0.05)

    # 收集剩余事件
    try:
        while True:
            event = event_queue.get_nowait()
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
    except queue.Empty:
        pass

    # ---- 完成信号统一由 worker_done 事件承载（每 Worker 一个）----

    # 判断执行结果
    worker_count = len(shared_memory.agent_outputs)
    if orchestrator_error[0]:
        yield f"data: {json.dumps({'type': 'error', 'content': orchestrator_error[0]}, ensure_ascii=False)}\n\n"
    elif final_result[0]:
        result = final_result[0]

        # ---- 新增事件: answer_chunk（按句子拆分）----
        for chunk in _split_answer_chunks(result.answer or ""):
            yield f"data: {json.dumps({'type': 'answer_chunk', 'content': chunk}, ensure_ascii=False)}\n\n"

        # ---- 事件: answer ----
        yield f"data: {json.dumps({'type': 'answer', 'content': result.answer, 'workers': worker_count, 'total_tokens': shared_memory.get_total_tokens()}, ensure_ascii=False, default=str)}\n\n"

        # ---- 新增事件: reflection（独立事件，阶段四新增）----
        reflector = _shared_state.get("reflector")
        if reflector and result.answer:
            sources = shared_memory.get_all_sources()
            ref_result = reflector.verify(result.answer, sources, query)
            reflection_event = {
                "type": "reflection",
                "score": ref_result.overall_confidence,
                "issues": ref_result.suggestions,
                "corrected_answer": ref_result.corrected_answer if ref_result.corrected_answer else None,
                "timestamp": int(time.time() * 1000),
            }
            yield f"data: {json.dumps(reflection_event, ensure_ascii=False, default=str)}\n\n"

    # ---- 事件: done ----
    yield f"data: {json.dumps({'type': 'done', 'timestamp': int(time.time() * 1000)}, ensure_ascii=False)}\n\n"

    # 记录对话历史
    cm.add_message("user", query)
    if final_result[0]:
        cm.add_message("assistant", final_result[0].answer)


@app.post("/api/agent/query", response_model=AgentQueryResponse,
          summary="Agent 模式查询 (ReAct 推理 + 工具调用)")
async def api_agent_query(request: AgentQueryRequest):
    logger.info("=" * 60)
    logger.info("[api_service] 收到 /api/agent/query 请求")
    logger.info("[api_service] Agent 查询: '%s', max_steps=%d, temperature=%.2f, mode=%s",
                 request.query, request.max_steps, request.temperature, request.mode)

    if not _shared_state.get("agent_initialized"):
        logger.error("[api_service] Agent 未初始化，无法处理请求")
        raise HTTPException(status_code=503, detail="Agent 未初始化，服务暂不可用")

    # ---- 会话隔离: 每个 conversation_id 持有独立的 AgentMemory ----
    conversation_id = request.conversation_id or str(uuid.uuid4())
    cm = _ensure_conversation(conversation_id)
    if cm.agent_memory is None:
        cm.link_memory(AgentMemory())
    per_request_memory = cm.agent_memory  # 会话独立的 memory

    # ---- mode 路由（阶段四新增）----
    effective_mode = request.mode  # auto / single / multi

    # mode="multi": 直接走多 Agent 链路，不通过 router
    if effective_mode == "multi":
        logger.info("[api_service] mode=multi，直接执行多 Agent 链路")
        try:
            multi_result = await _handle_multi_agent_query(request, cm, conversation_id)
            if multi_result is not None:
                return multi_result
            logger.warning("[api_service] 多Agent执行失败，回退到单Agent")
        except Exception as e:
            logger.warning("[api_service] 多Agent异常，回退到单Agent: %s", e)
        # fallthrough 到单Agent

    # mode="auto": 通过 router 自动判断
    if effective_mode == "auto":
        from src.router import RouteResult
        router = _shared_state.get("query_router")
        route_result: Optional[RouteResult] = None
        if router:
            conv_context = cm.get_context_string(max_turns=3)
            route_result = router.route(request.query, context=conv_context)
            logger.info(
                "[api_service] 路由决策: mode=%s, trace=%s, reasoning=%s",
                route_result.mode, route_result.trace, route_result.reasoning,
            )

            if route_result.mode == "multi_agent":
                logger.info("[api_service] 路由为 multi_agent，执行多 Agent 链路")
                try:
                    multi_result = await _handle_multi_agent_query(
                        request, cm, conversation_id,
                        route_result=route_result,
                    )
                    if multi_result is not None:
                        return multi_result
                    logger.warning("[api_service] auto→multi 执行失败，回退到单Agent")
                except Exception as e:
                    logger.warning("[api_service] auto→multi 异常，回退到单Agent: %s", e)
                # fallthrough 到单Agent

    # mode="single" 或 auto 下非 multi_agent: 走单 Agent 流程（现有逻辑不变）
    # ===== 以下为原有单 Agent 代码 =====

    # 为每个请求创建独立 Agent 实例（并发安全）
    agent = _create_per_request_agent(
        memory=per_request_memory,
        max_steps=request.max_steps,
        temperature=request.temperature,
        llm_provider=_shared_state.get("llm_provider"),
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
                step_number=s["step"],
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


@app.get("/api/agent/stream", summary="Agent SSE 流式推理 (Phase 4)")
async def api_agent_stream(
    query: str,
    mode: str = "auto",
    company_name: Optional[str] = None,
    max_steps: int = 5,
    temperature: float = 0.3,
    conversation_id: Optional[str] = None,
):
    """Agent 流式推理 SSE 端点

    使用 Server-Sent Events (SSE) 协议实时推送 Agent 推理的中间步骤。

    - **query**: 查询文本 (必填)
    - **mode**: 推理模式 auto/single/multi (默认 auto)
    - **company_name**: 指定公司名 (可选)
    - **max_steps**: 最大推理步数 (默认5, 范围1-20)
    - **temperature**: LLM 温度 (默认0.3)
    - **conversation_id**: 会话ID (可选, 用于记忆隔离)
    """
    # 参数校验 (M5 修复)
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="query 参数不能为空")
    if max_steps < 1 or max_steps > 100:
        raise HTTPException(status_code=400, detail="max_steps 必须在 1-100 之间")
    if temperature < 0.0 or temperature > 2.0:
        raise HTTPException(status_code=400, detail="temperature 必须在 0.0-2.0 之间")
    if mode not in ("auto", "single", "multi"):
        raise HTTPException(status_code=400, detail="mode 必须是 auto/single/multi 之一")

    logger.info("=" * 60)
    logger.info("[api_service] 收到 /api/agent/stream 请求")
    logger.info("[api_service] SSE 查询: '%s', max_steps=%d, mode=%s", query, max_steps, mode)

    if not _shared_state.get("agent_initialized"):
        logger.error("[api_service] Agent 未初始化，无法处理 SSE 请求")
        raise HTTPException(status_code=503, detail="Agent 未初始化，服务暂不可用")

    # 会话隔离
    conv_id = conversation_id or str(uuid.uuid4())
    cm = _ensure_conversation(conv_id)
    if cm.agent_memory is None:
        cm.link_memory(AgentMemory())
    per_request_memory = cm.agent_memory

    # ---- 预创建 Agent 实例（仅在非 multi 模式下使用）----
    single_agent = _create_per_request_agent(
        memory=per_request_memory,
        max_steps=max_steps,
        temperature=temperature,
        llm_provider=_shared_state.get("llm_provider"),
    )
    logger.info("[api_service] SSE Agent 实例已创建 (per-request): max_steps=%d", single_agent.max_steps)

    async def event_generator():
        """异步事件生成器，根据 mode 分派到对应流式函数（阶段四重构）"""
        import asyncio as _asyncio

        effective_mode = mode

        # mode="multi": 直接走多 Agent 流式
        if effective_mode == "multi":
            logger.info("[api_service] SSE mode=multi，执行多 Agent 流式链路")
            async for event in _stream_multi_agent(query, company_name, cm):
                yield event
            return

        # mode="auto": 通过 router 自动判断
        if effective_mode == "auto":
            router = _shared_state.get("query_router")
            if router:
                conv_context = cm.get_context_string(max_turns=3)
                route_result = router.route(query, context=conv_context)
                logger.info(
                    "[api_service] SSE 路由决策: mode=%s, trace=%s",
                    route_result.mode, route_result.trace,
                )
                yield f"data: {json.dumps({'type': 'router_decision', **route_result.to_dict()}, ensure_ascii=False, default=str)}\n\n"

                if route_result.mode == "multi_agent":
                    logger.info("[api_service] SSE 路由为 multi_agent")
                    async for event in _stream_multi_agent(query, company_name, cm):
                        yield event
                    return

        # mode="single" 或 auto 下非 multi_agent: 单 Agent 流式
        async for event in _stream_single_agent(single_agent, query, company_name, cm):
            yield event

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
                data["image_url"] = "/api/charts/images/%s" % json_file.with_suffix(".png").name
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

    if not _shared_state.get("agent_initialized"):
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
        per_request_memory = cm.agent_memory

        # 每请求创建独立 Agent 实例（并发安全，与 /api/agent/query 一致）
        per_request_agent = _create_per_request_agent(
            memory=per_request_memory,
            max_steps=10,
            temperature=0.3,
            llm_provider=_shared_state.get("llm_provider"),
        )

        # 调用 Agent 推理
        result = per_request_agent.run(user_message)
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

    if not _shared_state.get("agent_initialized"):
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
        per_request_memory = cm.agent_memory

        # 每请求创建独立 Agent 实例（并发安全，与 /api/agent/query 一致）
        per_request_agent = _create_per_request_agent(
            memory=per_request_memory,
            max_steps=10,
            temperature=0.3,
            llm_provider=_shared_state.get("llm_provider"),
        )

        # 调用 Agent 推理
        result = per_request_agent.run(user_message)
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


# ==================== 知识库管理 & 系统状态 API ====================

from .knowledge_service import get_documents, upload_pdf, delete_pdf


@app.get("/api/knowledge/documents",
         response_model=KnowledgeListResponse,
         summary="获取知识库文档列表")
async def api_knowledge_documents():
    """返回 PDF 文档列表，包含索引状态"""
    logger.info("[api_service] 收到 /api/knowledge/documents 请求")
    docs = get_documents()
    return {"documents": docs, "total": len(docs)}


@app.post("/api/knowledge/upload",
          response_model=KnowledgeUploadResponse,
          summary="上传 PDF 文档")
async def api_knowledge_upload(request: Request):
    """上传 PDF 文件到知识库（最大 50MB）"""
    logger.info("[api_service] 收到 /api/knowledge/upload 请求")
    try:
        # 粗略大小检查（在读取文件内容之前）
        content_length = request.headers.get("content-length")
        if content_length:
            cl = int(content_length)
            logger.info("[api_service] 上传 Content-Length: %d bytes (%.2f MB)",
                         cl, cl / 1024 / 1024)
            if cl > 50 * 1024 * 1024:
                logger.warning("[api_service] 上传被拒绝: Content-Length 超过 50MB 限制 | Content-Length: %d", cl)
                raise HTTPException(
                    status_code=413,
                    detail="文件过大，最大允许 50 MB")
        else:
            logger.info("[api_service] 上传请求无 Content-Length 头")

        form = await request.form()
        file = form.get("file")
        if file is None:
            logger.warning("[api_service] 上传失败: form 中缺少 file 字段")
            raise HTTPException(status_code=400, detail="缺少文件")
        content = await file.read()
        filename = file.filename or "unnamed.pdf"
        logger.info("[api_service] 文件读取完成 | 文件名: %s | 实际大小: %d bytes",
                     filename, len(content))
        result = upload_pdf(content, filename)
        logger.info("[api_service] 上传处理完成 | 文件名: %s | 大小: %.2f MB",
                     result["filename"], result["size_mb"])
        return {"success": True, **result}
    except ValueError as e:
        logger.warning("[api_service] 上传参数错误: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/knowledge/documents/{filename}",
            summary="删除 PDF 文档")
async def api_knowledge_delete(filename: str):
    """删除指定的 PDF 文档"""
    logger.info("[api_service] 收到 DELETE /api/knowledge/documents/%s",
                 filename)
    from urllib.parse import unquote
    decoded = unquote(filename)
    if decoded != filename:
        logger.info("[api_service] 文件名已 URL 解码: %s -> %s",
                     filename, decoded)
    filename = decoded
    if not delete_pdf(filename):
        logger.warning("[api_service] 删除失败: 文档不存在 | 文件名: %s",
                        filename)
        raise HTTPException(status_code=404,
                            detail=f"文档不存在: {filename}")
    logger.info("[api_service] 删除成功 | 文件名: %s", filename)
    return {"success": True, "filename": filename}


@app.get("/api/system/status",
         response_model=SystemStatusResponse,
         summary="获取系统状态")
async def api_system_status():
    """返回系统运行状态（只读监控数据）"""
    from .monitoring import (LANGSMITH_ENABLED, LANGSMITH_PROJECT,
                              LANGSMITH_ENDPOINT)

    # --- 模型状态 ---
    agent_cfg = _load_agent_config()
    model_status = {
        "name": agent_cfg.get("model", "qwen-max"),
        "status": "loaded" if rag_generator is not None else "not_loaded",
        "temperature": agent_cfg.get("temperature", 0.3),
        "max_steps": agent_cfg.get("max_steps", 5),
    }

    # --- 向量数据库状态 ---
    vb_counts = 0
    if vector_db_dir.exists():
        vb_counts = sum(1 for d in vector_db_dir.iterdir() if d.is_dir())
    vector_db_status = {
        "path": str(vector_db_dir),
        "status": "available" if vector_db_dir.exists() else "unavailable",
        "company_count": vb_counts,
    }

    # --- 长期记忆状态 ---
    memory_status = {
        "long_term_enabled":
            agent_cfg.get("memory_enable_long_term", False),
        "working_memory_limit":
            agent_cfg.get("memory_working_memory_limit", 10),
    }

    # --- LangSmith 监控状态 ---
    monitoring_status = {
        "langsmith_available": LANGSMITH_ENABLED,
        "langsmith_project": LANGSMITH_PROJECT,
        "langsmith_endpoint": LANGSMITH_ENDPOINT,
    }

    # --- 工具列表（当前全部启用，只读） ---
    tools_status = {
        "retrieve": True,
        "calculator": True,
        "compare": True,
        "chart": True,
        "verify": True,
        "delegate": True,
    }

    return {
        "model": model_status,
        "vector_db": vector_db_status,
        "memory": memory_status,
        "monitoring": monitoring_status,
        "tools": tools_status,
    }
