"""B2.1 可追溯计算结果持久化测试。"""

import pytest


def test_calculation_repository_persists_formula_inputs_and_details(tmp_path):
    from src.fact_calculation_repository import FactCalculationRepository
    from src.fact_calculation_service import FactCalculationResult
    from src.v7_metadata_store import V7MetadataStore

    repository = FactCalculationRepository(V7MetadataStore(tmp_path / "metadata.sqlite3"))
    result = FactCalculationResult(
        operation="yoy_growth", formula_version="calculator-yoy-v1",
        input_fact_ids=("revenue-2024", "revenue-2023"),
        details={"growth_rate": 0.1},
    )

    repository.save("calc-revenue-yoy-2024", result)

    stored = repository.get("calc-revenue-yoy-2024")
    assert stored.formula_version == "calculator-yoy-v1"
    assert stored.input_fact_ids == ("revenue-2024", "revenue-2023")
    assert stored.details == {"growth_rate": 0.1}


def test_calculation_repository_replays_same_evidence_and_rejects_conflict(tmp_path):
    from src.fact_calculation_repository import FactCalculationConflictError, FactCalculationRepository
    from src.fact_calculation_service import FactCalculationResult
    from src.v7_metadata_store import V7MetadataStore

    repository = FactCalculationRepository(V7MetadataStore(tmp_path / "metadata.sqlite3"))
    result = FactCalculationResult("yoy_growth", "calculator-yoy-v1", ("a", "b"), {"growth_rate": 0.1})
    repository.save("calc-1", result)
    repository.save("calc-1", result)
    with pytest.raises(FactCalculationConflictError):
        repository.save("calc-1", FactCalculationResult("yoy_growth", "calculator-yoy-v1", ("a", "b"), {"growth_rate": 0.2}))
