"""D1.1 工具权限策略测试：风险等级、权限策略与默认拒绝边界（D-T01）。

规格依据：spec-governance-operations.md「工具权限」——只读检索与纯计算工具
按策略自动执行并记录审计事件；外部写入与特权操作必须获得审批；未注册工具
默认拒绝，防止未分类能力绕过治理边界。
"""

from __future__ import annotations

import pytest

from src.governance.tool_policy import (
    PolicyDecision,
    ToolDescriptor,
    ToolPolicy,
    ToolRiskLevel,
)


def _policy() -> ToolPolicy:
    """构造覆盖四类风险等级的注册表，external_read 由独立用例覆盖。"""
    return ToolPolicy(
        tools=[
            ToolDescriptor(name="retrieve_financial_fact", risk_level=ToolRiskLevel.READ_ONLY),
            ToolDescriptor(name="calculator", risk_level=ToolRiskLevel.COMPUTE),
            ToolDescriptor(name="publish_index", risk_level=ToolRiskLevel.EXTERNAL_WRITE),
            ToolDescriptor(name="grant_role", risk_level=ToolRiskLevel.PRIVILEGED),
        ]
    )


def test_read_only_and_compute_tools_auto_execute() -> None:
    """D-T01：只读检索与纯计算工具按策略自动执行。"""
    policy = _policy()
    read_only = policy.evaluate("retrieve_financial_fact")
    compute = policy.evaluate("calculator")
    assert read_only.decision is PolicyDecision.AUTO_EXECUTE
    assert compute.decision is PolicyDecision.AUTO_EXECUTE
    assert read_only.risk_level is ToolRiskLevel.READ_ONLY


def test_external_write_and_privileged_require_approval() -> None:
    """外部写入与特权操作有副作用，必须获得审批后才能执行。"""
    policy = _policy()
    assert policy.evaluate("publish_index").decision is PolicyDecision.APPROVAL_REQUIRED
    assert policy.evaluate("grant_role").decision is PolicyDecision.APPROVAL_REQUIRED


def test_unregistered_tool_denied_by_default() -> None:
    """默认拒绝边界：未注册工具一律拒绝，不能隐式继承低风险待遇。"""
    evaluation = _policy().evaluate("unknown_tool")
    assert evaluation.decision is PolicyDecision.DENIED
    assert evaluation.risk_level is None
    assert evaluation.reason != ""


def test_duplicate_tool_registration_rejected() -> None:
    """同名工具重复注册视为配置错误，防止策略被静默覆盖。"""
    with pytest.raises(ValueError):
        ToolPolicy(
            tools=[
                ToolDescriptor(name="calculator", risk_level=ToolRiskLevel.COMPUTE),
                ToolDescriptor(name="calculator", risk_level=ToolRiskLevel.READ_ONLY),
            ]
        )
