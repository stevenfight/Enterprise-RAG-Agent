# -*- coding: utf-8 -*-
"""
LangSmith 监控模块

为自研 ReAct Agent 框架提供 LangSmith 在线追踪和监控能力。
本模块框架无关，不依赖 LangChain，直接使用 langsmith SDK 的 @traceable 装饰器和 Client API。

特性：
  - traceable 装饰器工厂：langsmith 可用时返回真实追踪装饰器，不可用时返回透传
  - Client 单例管理：延迟初始化，避免重复创建连接
  - Windows 注册表回退：环境变量读取失败时从注册表兜底
  - 优雅降级：未安装包或未配置 API Key 时所有功能静默降级

环境变量：
  LANGSMITH_API_KEY       - LangSmith API 密钥（从 https://smith.langchain.com 获取）
  LANGCHAIN_TRACING_V2    - 设置为 "true" 启用追踪
  LANGCHAIN_PROJECT       - 项目名称（可选，默认 "financial-rag-agent"）
  LANGCHAIN_ENDPOINT      - 自定义端点（可选，默认 https://api.smith.langchain.com）

参考项目: CASE-投顾AI助手（效果评估）/1-hybrid_wealth_advisor_langgraph_langsmith.py
"""

import logging
import os
import sys

logger = logging.getLogger("monitoring")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)


def _get_env_with_fallback(key: str, default: str = "") -> str:
    """读取环境变量，优先从进程环境读取，兜底从 Windows 注册表读取

    参考投顾AI助手项目的实现，确保在 Windows 系统环境变量设置后
    新启动的进程也能获取到。

    Args:
        key: 环境变量名
        default: 默认值（环境变量不存在时返回）

    Returns:
        环境变量值或默认值
    """
    value = os.getenv(key)
    if value is not None:
        return value
    # 进程环境变量未设置时，尝试从 Windows 注册表读取
    if os.name == "nt":
        try:
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(hive, r"Environment") as reg_key:
                        value, _ = winreg.QueryValueEx(reg_key, key)
                        if value:
                            # 同步注入到当前进程环境变量
                            os.environ[key] = value
                            logger.info(
                                "[monitoring] 从 Windows 注册表读取环境变量 %s (hive=%s)",
                                key, "HKCU" if hive == winreg.HKEY_CURRENT_USER else "HKLM"
                            )
                            return value
                except (FileNotFoundError, OSError):
                    continue
        except Exception as e:
            logger.debug("[monitoring] 注册表读取失败: %s", str(e))
    return default


# ---- 环境变量读取 ----
LANGSMITH_API_KEY = _get_env_with_fallback("LANGSMITH_API_KEY")
LANGSMITH_TRACING_V2 = _get_env_with_fallback("LANGCHAIN_TRACING_V2", "")
LANGSMITH_PROJECT = _get_env_with_fallback("LANGCHAIN_PROJECT") or "financial-rag-agent"
LANGSMITH_ENDPOINT = _get_env_with_fallback("LANGCHAIN_ENDPOINT") or "https://api.smith.langchain.com"

# ---- 可用性检测 ----
_LANGSMITH_AVAILABLE = False
_traceable = None

try:
    from langsmith import Client as _LangSmithClient
    from langsmith import traceable as _ls_traceable
    _LANGSMITH_AVAILABLE = True
    logger.info("[monitoring] langsmith 包导入成功，版本可用")
except ImportError:
    logger.info("[monitoring] langsmith 包未安装，追踪功能不可用。安装命令: python -m pip install langsmith")

# ---- 启用状态 ----
LANGSMITH_ENABLED = (
    _LANGSMITH_AVAILABLE
    and LANGSMITH_TRACING_V2.lower() == "true"
    and bool(LANGSMITH_API_KEY)
)
logger.info(
    "[monitoring] LangSmith 状态: available=%s, tracing_v2=%s, api_key=%s, enabled=%s",
    _LANGSMITH_AVAILABLE,
    LANGSMITH_TRACING_V2,
    "已配置" if LANGSMITH_API_KEY else "未配置",
    LANGSMITH_ENABLED,
)

# ---- Client 单例 ----
_client = None


def get_client():
    """获取 LangSmith Client 单例

    延迟初始化，首次调用时创建 Client 实例。
    未启用或不满足条件时返回 None。

    Returns:
        langsmith.Client | None: Client 实例或 None
    """
    global _client
    if not LANGSMITH_ENABLED:
        return None
    if _client is None:
        try:
            _client = _LangSmithClient(
                api_key=LANGSMITH_API_KEY,
                api_url=LANGSMITH_ENDPOINT,
            )
            logger.info(
                "[monitoring] LangSmith Client 初始化成功, project=%s, endpoint=%s",
                LANGSMITH_PROJECT, LANGSMITH_ENDPOINT
            )
        except Exception as e:
            logger.error("[monitoring] LangSmith Client 初始化失败: %s", str(e))
            return None
    return _client


def traceable(name=None, **kwargs):
    """traceable 装饰器工厂函数

    LangSmith 可用时返回真实的追踪装饰器，不可用时返回透传装饰器。
    调用方代码不需要任何条件判断，统一使用此函数即可。

    Usage:
        from src.monitoring import traceable

        @traceable(name="react-loop")
        def run(self, query):
            ...

    Args:
        name: 追踪名称（在 LangSmith Dashboard 中显示）
        **kwargs: 传递给 langsmith.traceable 的额外参数

    Returns:
        装饰器函数
    """
    if not LANGSMITH_ENABLED:
        # 返回不做任何追踪的透传装饰器
        def passthrough(func):
            return func
        return passthrough
    return _ls_traceable(name=name, project_name=LANGSMITH_PROJECT, **kwargs)


def is_available() -> bool:
    """检查 LangSmith 是否可用

    同时满足以下条件才返回 True:
      1. langsmith 包已安装
      2. LANGCHAIN_TRACING_V2 设置为 "true"
      3. LANGSMITH_API_KEY 已配置

    Returns:
        bool: LangSmith 是否可用
    """
    return LANGSMITH_ENABLED


def init_langsmith():
    """初始化 LangSmith Client（供 API 服务启动时调用）

    如果未启用，仅记录日志；如果已在配置文件中禁用，同样跳过。
    此函数可安全重复调用，已初始化时不会重复创建。

    Returns:
        bool: 是否成功初始化
    """
    if not LANGSMITH_ENABLED:
        logger.info("[monitoring] LangSmith 未启用，跳过初始化")
        return False
    client = get_client()
    if client is not None:
        logger.info("[monitoring] LangSmith 初始化完成, 项目: %s", LANGSMITH_PROJECT)
        return True
    return False


# ---- 模块加载时日志 ----
if LANGSMITH_ENABLED:
    logger.info(
        "[monitoring] LangSmith 已启用 | 项目=%s | 端点=%s | "
        "查看追踪: https://smith.langchain.com",
        LANGSMITH_PROJECT, LANGSMITH_ENDPOINT
    )
else:
    logger.info(
        "[monitoring] LangSmith 未启用 | 原因: %s | "
        "启用方法: 设置 LANGSMITH_API_KEY + LANGCHAIN_TRACING_V2=true",
        "langsmith 未安装" if not _LANGSMITH_AVAILABLE else (
            "LANGSMITH_API_KEY 未配置" if not LANGSMITH_API_KEY else "LANGCHAIN_TRACING_V2 未设为 true"
        )
    )
