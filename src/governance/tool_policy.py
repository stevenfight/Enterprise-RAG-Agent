"""D1.1 工具权限策略：风险等级、权限策略与默认拒绝边界。

设计依据：design.md D 段与「有副作用才审批」原则——
- 只读检索、纯计算与外部读取无副作用，按策略自动执行并记录审计事件；
- 外部写入与特权操作必须获得与规范化参数绑定的有效审批；
- 未注册工具一律默认拒绝，防止未分类能力绕过治理边界；
- 审批优先落在关键冲突裁决、正式报告签发和未来真实写操作上，
  当前版本不新增虚构的危险工具。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class ToolRiskLevel(str, Enum):
    """工具风险等级，与 design.md D 段五级分类一致。"""

    READ_ONLY = "read_only"
    COMPUTE = "compute"
    EXTERNAL_READ = "external_read"
    EXTERNAL_WRITE = "external_write"
    PRIVILEGED = "privileged"


class PolicyDecision(str, Enum):
    """策略裁决结果：自动执行、需审批、默认拒绝。"""

    AUTO_EXECUTE = "auto_execute"
    APPROVAL_REQUIRED = "approval_required"
    DENIED = "denied"


# 无副作用等级：可自动执行（执行方仍需记录审计事件）。
_AUTO_EXECUTE_LEVELS = frozenset(
    {ToolRiskLevel.READ_ONLY, ToolRiskLevel.COMPUTE, ToolRiskLevel.EXTERNAL_READ}
)
# 有副作用等级：必须先获得有效审批。
_APPROVAL_LEVELS = frozenset({ToolRiskLevel.EXTERNAL_WRITE, ToolRiskLevel.PRIVILEGED})


@dataclass(frozen=True)
class ToolDescriptor:
    """工具注册项：名称与风险等级由部署配置显式声明。"""

    name: str
    risk_level: ToolRiskLevel
    description: str = ""


@dataclass(frozen=True)
class PolicyEvaluation:
    """单次策略评估结果，携带风险等级与裁决原因供审计记录。"""

    tool_name: str
    decision: PolicyDecision
    risk_level: ToolRiskLevel | None
    reason: str


class ToolPolicy:
    """工具权限策略：注册表驱动，未注册工具默认拒绝。"""

    def __init__(self, tools: Iterable[ToolDescriptor]) -> None:
        registry: dict[str, ToolDescriptor] = {}
        for descriptor in tools:
            if descriptor.name in registry:
                raise ValueError(f"工具 {descriptor.name} 重复注册，禁止静默覆盖策略")
            registry[descriptor.name] = descriptor
        self._tools = registry

    def evaluate(self, tool_name: str) -> PolicyEvaluation:
        """评估工具调用请求并返回裁决。

        - 注册且无副作用：auto_execute；
        - 注册且有副作用：approval_required；
        - 未注册：denied（默认拒绝边界）。
        """
        descriptor = self._tools.get(tool_name)
        if descriptor is None:
            return PolicyEvaluation(
                tool_name=tool_name,
                decision=PolicyDecision.DENIED,
                risk_level=None,
                reason="工具未注册，按默认拒绝边界处理",
            )
        if descriptor.risk_level in _AUTO_EXECUTE_LEVELS:
            return PolicyEvaluation(
                tool_name=tool_name,
                decision=PolicyDecision.AUTO_EXECUTE,
                risk_level=descriptor.risk_level,
                reason="无副作用工具按策略自动执行，执行方需记录审计事件",
            )
        if descriptor.risk_level in _APPROVAL_LEVELS:
            return PolicyEvaluation(
                tool_name=tool_name,
                decision=PolicyDecision.APPROVAL_REQUIRED,
                risk_level=descriptor.risk_level,
                reason="有副作用工具必须获得与规范化参数绑定的有效审批",
            )
        raise ValueError(f"工具 {tool_name} 的风险等级 {descriptor.risk_level} 未纳入策略裁决")
