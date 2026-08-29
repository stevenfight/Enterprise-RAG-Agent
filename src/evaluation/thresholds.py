"""评测门禁阈值配置加载。

B2.7 起 thresholds.yaml 由评测平面真实消费；
A2.8 预留的声明级证据门禁在 B 阶段按该配置启用。
"""

from pathlib import Path
from typing import Any

import yaml

DEFAULT_THRESHOLDS_PATH = Path("evals/config/thresholds.yaml")

# 声明级证据门禁的合法取值：disabled_until_b 为 A 阶段预留值，B 阶段切换为 enabled。
_CLAIM_EVIDENCE_MODES = {"enabled", "disabled", "disabled_until_b"}


def load_thresholds(path: str | Path = DEFAULT_THRESHOLDS_PATH) -> dict[str, Any]:
    """加载并校验门禁阈值配置；非法配置直接失败，不做静默回退。"""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("门禁阈值配置必须是键值映射")
    mode = raw.get("claim_level_evidence_support")
    if mode not in _CLAIM_EVIDENCE_MODES:
        raise ValueError(f"claim_level_evidence_support 取值非法: {mode}")
    minimum_pass_rate = raw.get("minimum_pass_rate")
    if (
        isinstance(minimum_pass_rate, bool)
        or not isinstance(minimum_pass_rate, (int, float))
        or not 0 < float(minimum_pass_rate) <= 1
    ):
        raise ValueError("minimum_pass_rate 必须在 (0, 1] 区间")
    high_risk_failure_limit = raw.get("high_risk_failure_limit", 0)
    if (
        isinstance(high_risk_failure_limit, bool)
        or not isinstance(high_risk_failure_limit, int)
        or high_risk_failure_limit < 0
    ):
        raise ValueError("high_risk_failure_limit 必须是非负整数")
    return {
        "minimum_pass_rate": float(minimum_pass_rate),
        "high_risk_failure_limit": high_risk_failure_limit,
        "claim_level_evidence_support": mode,
    }
