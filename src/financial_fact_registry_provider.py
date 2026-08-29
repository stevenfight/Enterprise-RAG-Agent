# -*- coding: utf-8 -*-
"""按 V7 功能开关提供已核验财务事实注册表。"""

from pathlib import Path
from threading import RLock

from .v7_feature_flags import V7FeatureFlags
from .verified_financial_facts import VerifiedFinancialFactRegistry


_REGISTRY_INITIALIZATION_LOCK = RLock()


def get_verified_financial_fact_registry(
    *,
    flags: V7FeatureFlags,
    metadata_database_path: str | Path,
):
    """关闭时保持 legacy 注册表；开启时才创建 V7 事实链。"""
    if not isinstance(flags, V7FeatureFlags):
        raise TypeError("flags 必须是 V7FeatureFlags")

    legacy_registry = VerifiedFinancialFactRegistry()
    if not flags.financial_trust_enabled:
        return legacy_registry

    from .fact_calculation_repository import FactCalculationRepository
    from .financial_fact_conflict_repository import FinancialFactConflictRepository
    from .financial_fact_registry_adapter import FinancialFactRegistryAdapter
    from .financial_fact_repository import FinancialFactRepository
    from .v7_metadata_store import V7MetadataStore

    with _REGISTRY_INITIALIZATION_LOCK:
        store = V7MetadataStore(metadata_database_path)
        adapter = FinancialFactRegistryAdapter(
            legacy_registry=legacy_registry,
            repository=FinancialFactRepository(store),
            calculation_repository=FactCalculationRepository(store),
            conflict_repository=FinancialFactConflictRepository(store),
        )
        adapter.import_registered_revenue_facts()
    return adapter
