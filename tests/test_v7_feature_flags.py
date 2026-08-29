"""v7 功能开关严格配置的确定性测试。"""

import pytest


def test_v7_feature_flags_default_to_all_disabled():
    from src.v7_feature_flags import V7FeatureFlags

    flags = V7FeatureFlags.from_mapping(None)

    assert flags.financial_trust_enabled is False
    assert flags.durable_execution_enabled is False
    assert flags.multimodal_enabled is False
    assert flags.research_tasks_enabled is False


@pytest.mark.parametrize("feature", ["multimodal_enabled", "research_tasks_enabled"])
def test_v7_dependent_feature_fails_closed_without_required_flags(feature: str):
    from src.v7_feature_flags import FeatureFlagConfigurationError, V7FeatureFlags

    with pytest.raises(FeatureFlagConfigurationError, match="financial_trust_enabled"):
        V7FeatureFlags.from_mapping({feature: True})


def test_v7_feature_flags_reject_unknown_and_non_boolean_values():
    from src.v7_feature_flags import FeatureFlagConfigurationError, V7FeatureFlags

    with pytest.raises(FeatureFlagConfigurationError, match="未知"):
        V7FeatureFlags.from_mapping({"unknown_flag": True})
    with pytest.raises(FeatureFlagConfigurationError, match="布尔"):
        V7FeatureFlags.from_mapping({"financial_trust_enabled": "true"})


def test_v7_multimodal_and_research_tasks_accept_explicit_dependencies():
    from src.v7_feature_flags import V7FeatureFlags

    flags = V7FeatureFlags.from_mapping(
        {
            "financial_trust_enabled": True,
            "durable_execution_enabled": True,
            "multimodal_enabled": True,
            "research_tasks_enabled": True,
        }
    )

    assert flags.multimodal_enabled is True
    assert flags.research_tasks_enabled is True
