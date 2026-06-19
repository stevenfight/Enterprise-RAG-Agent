# -*- coding: utf-8 -*-
"""
Agent 工具系统

提供工具统一接口、注册框架和结果包装：
  - ToolResult: 工具执行结果的数据类
  - BaseTool: 所有工具的抽象基类
  - ToolRegistry: 工具注册、查找、调用分发

对应 SDD: openspec/changes/rag-to-agent/specs/spec-tools.md
"""

import json
import logging
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("tools")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)


@dataclass
class ToolResult:
    """工具执行结果

    Attributes:
        success: 工具是否执行成功
        data: 工具返回的数据（任意类型）
        error: 错误信息（success=False 时填充）
    """
    success: bool
    data: Any = None
    error: str = ""

    def to_observation(self) -> str:
        """将执行结果转换为 Observation 文本，供 Agent 理解"""
        if not self.success:
            logger.warning("[ToolResult] 生成失败 Observation: %s", self.error)
            return f"[工具执行失败] {self.error}"
        if self.data is None:
            logger.info("[ToolResult] 生成空结果 Observation")
            return "[工具返回空结果]"
        if isinstance(self.data, str):
            return self.data
        if isinstance(self.data, dict):
            return json.dumps(self.data, ensure_ascii=False, indent=2)
        return str(self.data)


class BaseTool:
    """工具基类

    所有业务工具必须继承此类并实现 run 方法。

    Attributes:
        name: 工具唯一名称（Agent 通过此名称调用）
        description: 工具功能描述（提供给 LLM 理解）
        parameters: 工具参数说明（dict 格式）
    """

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    def run(self, **kwargs) -> ToolResult:
        """执行工具逻辑

        Args:
            **kwargs: 工具参数，由 Agent 根据 parameters 传入

        Returns:
            ToolResult: 工具执行结果

        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError(f"工具 {self.name} 未实现 run 方法")

    def _validate_params(self, required: List[str], **kwargs) -> Optional[str]:
        """校验必填参数

        Args:
            required: 必填参数名列表
            **kwargs: 实际传入的参数

        Returns:
            str: 如果校验失败返回错误信息，成功返回 None
        """
        missing = [p for p in required if p not in kwargs or kwargs[p] is None]
        if missing:
            msg = f"缺少必填参数: {', '.join(missing)}"
            logger.warning("[%s] 参数校验失败: %s", self.name, msg)
            return msg
        logger.debug("[%s] 参数校验通过, 参数: %s", self.name, kwargs)
        return None


class ToolRegistry:
    """工具注册表

    管理所有可用工具的注册、查找和描述生成。

    Usage:
        registry = ToolRegistry()
        registry.register(MyTool())
        tool = registry.get("my_tool")
        result = registry.execute("my_tool", param1="value1")
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        logger.info("[ToolRegistry] 初始化工具注册表")

    def register(self, tool: BaseTool) -> None:
        """注册一个工具

        Args:
            tool: 工具实例（继承自 BaseTool）

        Raises:
            ValueError: 工具名已存在时抛出
        """
        if tool.name in self._tools:
            msg = f"工具 {tool.name} 已注册，不可重复注册"
            logger.error("[ToolRegistry] %s", msg)
            raise ValueError(msg)
        self._tools[tool.name] = tool
        logger.info("[ToolRegistry] 注册工具: %s (%s)", tool.name, tool.description)

    def get(self, name: str) -> Optional[BaseTool]:
        """根据名称获取工具

        Args:
            name: 工具名称

        Returns:
            BaseTool 或 None（工具不存在时）
        """
        tool = self._tools.get(name)
        if tool is None:
            logger.warning("[ToolRegistry] 工具 '%s' 未注册，可用工具: %s", name, self.list_all())
        return tool

    def list_all(self) -> List[str]:
        """列出所有已注册工具的名称"""
        return list(self._tools.keys())

    def execute(self, name: str, **kwargs) -> ToolResult:
        """执行指定工具

        Args:
            name: 工具名称
            **kwargs: 传递给工具 run 方法的参数

        Returns:
            ToolResult: 工具执行结果
        """
        logger.info("[ToolRegistry] 执行工具: %s, 参数: %s", name, kwargs)

        tool = self.get(name)
        if tool is None:
            logger.error("[ToolRegistry] 工具 '%s' 未注册", name)
            return ToolResult(
                success=False,
                error=f"工具 '{name}' 未注册。可用工具: {self.list_all()}"
            )

        try:
            result = tool.run(**kwargs)
            logger.info("[ToolRegistry] 工具 '%s' 执行成功", name)
            return result
        except TypeError as e:
            logger.error("[ToolRegistry] 工具 '%s' 参数错误: %s", name, str(e))
            return ToolResult(
                success=False,
                error=f"工具 '{name}' 参数错误: {str(e)}"
            )
        except Exception as e:
            logger.error("[ToolRegistry] 工具 '%s' 执行异常: %s", name, str(e))
            return ToolResult(
                success=False,
                error=f"工具 '{name}' 执行异常: {str(e)}"
            )

    def get_tool_descriptions(self) -> str:
        """生成 LLM 可用的工具描述文本

        Returns:
            格式化后的工具列表说明
        """
        if not self._tools:
            logger.info("[ToolRegistry] 生成工具描述: 无可用工具")
            return "(无可用工具)"

        lines = []
        for tool in self._tools.values():
            param_desc = ""
            if tool.parameters and "properties" in tool.parameters:
                props = tool.parameters["properties"]
                param_desc = ", ".join(
                    f"{k}({v.get('description', '')})" for k, v in props.items()
                )
            lines.append(f"- {tool.name}: {tool.description}" +
                         (f" [参数: {param_desc}]" if param_desc else ""))

        desc = "\n".join(lines)
        logger.info("[ToolRegistry] 生成工具描述，共 %d 个工具", len(self._tools))
        return desc
