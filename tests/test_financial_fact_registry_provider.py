"""B0.5 已核验比较 API 的 V7 功能开关契约。"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

from src.v7_feature_flags import V7FeatureFlags


def _assert_legacy_comparison_fields_preserved(enriched, legacy):
    """B2.6 声明级可选载荷扩展后，旧比较响应字段必须逐项保持。"""
    for key in ("available", "metric_key", "fiscal_year", "unit", "fact_ids"):
        assert enriched[key] == legacy[key]
    for enriched_item, legacy_item in zip(enriched["items"], legacy["items"]):
        for key, value in legacy_item.items():
            assert enriched_item[key] == value


def test_financial_trust_disabled_returns_legacy_registry_without_creating_database(tmp_path):
    from src.financial_fact_registry_provider import get_verified_financial_fact_registry
    from src.verified_financial_facts import VerifiedFinancialFactRegistry

    database_path = tmp_path / "v7_metadata.sqlite3"
    registry = get_verified_financial_fact_registry(
        flags=V7FeatureFlags(), metadata_database_path=database_path
    )

    assert type(registry) is VerifiedFinancialFactRegistry
    assert database_path.exists() is False


def test_financial_trust_enabled_uses_v7_adapter_and_preserves_comparison_contract(tmp_path):
    from src.financial_fact_registry_provider import get_verified_financial_fact_registry
    from src.verified_financial_facts import VerifiedFinancialFactRegistry

    database_path = tmp_path / "v7_metadata.sqlite3"
    registry = get_verified_financial_fact_registry(
        flags=V7FeatureFlags(financial_trust_enabled=True),
        metadata_database_path=database_path,
    )

    comparison = registry.get_comparison(
        "operating_revenue", 2024, ["中国移动", "中国联通", "中国电信"]
    )

    assert type(registry).__name__ == "FinancialFactRegistryAdapter"
    assert database_path.exists() is True
    # B2.6 后注入仓储的适配器会追加可选证据载荷，因此校验旧字段逐项保持而非整体相等。
    _assert_legacy_comparison_fields_preserved(
        comparison,
        VerifiedFinancialFactRegistry().get_comparison(
            "operating_revenue", 2024, ["中国移动", "中国联通", "中国电信"]
        ),
    )


def test_api_registry_factory_keeps_legacy_path_closed_without_v7_database(tmp_path, monkeypatch):
    from src import api_service
    from src.verified_financial_facts import VerifiedFinancialFactRegistry

    monkeypatch.setattr(api_service, "project_root", tmp_path)
    registry = api_service._get_verified_financial_fact_registry(
        {"v7_feature_flags": V7FeatureFlags()}
    )

    assert type(registry) is VerifiedFinancialFactRegistry
    assert not (tmp_path / "data" / "stock_data" / "v7_metadata.sqlite3").exists()


def test_api_registry_factory_uses_v7_adapter_only_when_enabled(tmp_path, monkeypatch):
    from src import api_service
    from src.verified_financial_facts import VerifiedFinancialFactRegistry

    monkeypatch.setattr(api_service, "project_root", tmp_path)
    registry = api_service._get_verified_financial_fact_registry(
        {"v7_feature_flags": V7FeatureFlags(financial_trust_enabled=True)}
    )

    assert type(registry).__name__ == "FinancialFactRegistryAdapter"
    assert (tmp_path / "data" / "stock_data" / "v7_metadata.sqlite3").exists()
    # B2.6 后注入仓储的适配器会追加可选证据载荷，因此校验旧字段逐项保持而非整体相等。
    _assert_legacy_comparison_fields_preserved(
        registry.get_comparison("operating_revenue", 2024, ["中国移动"]),
        VerifiedFinancialFactRegistry().get_comparison("operating_revenue", 2024, ["中国移动"]),
    )


def test_public_comparison_api_uses_legacy_when_closed_and_v7_when_enabled(tmp_path, monkeypatch):
    from src import api_service

    monkeypatch.setattr(api_service, "project_root", tmp_path)
    database_path = tmp_path / "data" / "stock_data" / "v7_metadata.sqlite3"
    monkeypatch.setattr(
        api_service,
        "_load_agent_config",
        lambda: {"v7_feature_flags": V7FeatureFlags()},
    )
    closed = asyncio.run(
        api_service.api_verified_comparison("operating_revenue", 2024, "中国移动")
    )
    assert closed["available"] is True
    assert database_path.exists() is False

    monkeypatch.setattr(
        api_service,
        "_load_agent_config",
        lambda: {"v7_feature_flags": V7FeatureFlags(financial_trust_enabled=True)},
    )
    enabled = asyncio.run(
        api_service.api_verified_comparison("operating_revenue", 2024, "中国移动")
    )
    # B2.6 后 V7 分支会追加可选证据载荷，因此校验旧字段逐项保持而非整体相等。
    _assert_legacy_comparison_fields_preserved(enabled, closed)
    assert database_path.exists() is True


def test_invalid_v7_flag_configuration_is_loaded_as_closed(tmp_path, monkeypatch):
    from src import api_service

    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "agent_config.json").write_text(
        json.dumps({"v7_feature_flags": {"financial_trust_enabled": "true"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(api_service, "project_root", tmp_path)

    config = api_service._load_agent_config()

    assert config["v7_feature_flags"] == V7FeatureFlags()


def test_public_chart_projection_preserves_verified_facts_when_enabled(tmp_path, monkeypatch):
    from src import api_service

    chart_path = tmp_path / "charts"
    chart_path.mkdir()
    (chart_path / "operator_revenue.json").write_text(
        json.dumps(
            {
                "chart_type": "bar",
                "title": "2024年三大运营商营业收入对比",
                "labels": ["中国移动", "中国联通", "中国电信"],
                "values": [1, 2, 3],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(api_service, "project_root", tmp_path)
    monkeypatch.setattr(api_service, "_charts_dir", chart_path)
    monkeypatch.setattr(
        api_service,
        "_load_agent_config",
        lambda: {"v7_feature_flags": V7FeatureFlags(financial_trust_enabled=True)},
    )

    charts = asyncio.run(api_service.api_charts_list())["charts"]

    assert charts[0]["labels"] == ["中国移动", "中国联通", "中国电信"]
    assert charts[0]["values"] == [10408, 3896, 5236]


def test_concurrent_enabled_registry_creation_is_idempotent(tmp_path):
    from src.financial_fact_registry_provider import get_verified_financial_fact_registry

    database_path = tmp_path / "v7_metadata.sqlite3"
    flags = V7FeatureFlags(financial_trust_enabled=True)

    def load_revenue():
        registry = get_verified_financial_fact_registry(
            flags=flags, metadata_database_path=database_path
        )
        return registry.get_comparison("operating_revenue", 2024, ["中国移动"])

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: load_revenue(), range(4)))

    assert all(result["available"] is True for result in results)
    assert all(result["items"][0]["value"] == 10408 for result in results)
