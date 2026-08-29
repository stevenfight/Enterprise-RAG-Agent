# -*- coding: utf-8 -*-
"""可追溯 FinancialFact 计算结果的 V7 SQLite 仓储。"""

import json

from .fact_calculation_service import FactCalculationResult
from .v7_metadata_store import V7MetadataStore


class FactCalculationConflictError(RuntimeError):
    """同一计算 ID 对应的公式、输入或结果证据不一致。"""


class FactCalculationRepository:
    """保存公式版本、输入事实 ID 与确定性计算明细。"""

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store

    def save(self, calculation_id: str, result: FactCalculationResult) -> None:
        if not isinstance(calculation_id, str) or not calculation_id.strip():
            raise ValueError("calculation_id 不能为空")
        self.store.initialize()
        values = (
            calculation_id, result.operation, result.formula_version,
            json.dumps(result.input_fact_ids), json.dumps(result.details, ensure_ascii=False, sort_keys=True),
        )
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    "SELECT operation, formula_version, input_fact_ids_json, details_json FROM v7_fact_calculations WHERE calculation_id = ?",
                    (calculation_id,),
                ).fetchone()
                if existing is not None:
                    connection.commit()
                    existing_result = FactCalculationResult(
                        existing[0], existing[1], tuple(json.loads(existing[2])), json.loads(existing[3])
                    )
                    if existing_result != result:
                        raise FactCalculationConflictError("calculation_id 与既有计算证据不一致")
                    return
                connection.execute("INSERT INTO v7_fact_calculations VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", values)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def get(self, calculation_id: str) -> FactCalculationResult | None:
        self.store.initialize()
        with self.store.connect() as connection:
            row = connection.execute("SELECT operation, formula_version, input_fact_ids_json, details_json FROM v7_fact_calculations WHERE calculation_id = ?", (calculation_id,)).fetchone()
        if row is None:
            return None
        return FactCalculationResult(row[0], row[1], tuple(json.loads(row[2])), json.loads(row[3]))

    def list_by_fact_ids(self, fact_ids: tuple[str, ...]) -> tuple[tuple[str, FactCalculationResult], ...]:
        """返回输入事实与给定 fact_ids 存在交集的计算，按 calculation_id 稳定排序。"""
        if not fact_ids:
            return ()
        self.store.initialize()
        wanted = set(fact_ids)
        with self.store.connect() as connection:
            rows = connection.execute(
                "SELECT calculation_id, operation, formula_version, input_fact_ids_json, details_json FROM v7_fact_calculations ORDER BY calculation_id"
            ).fetchall()
        matched = []
        for row in rows:
            input_fact_ids = tuple(json.loads(row[3]))
            if wanted.isdisjoint(input_fact_ids):
                continue
            matched.append((row[0], FactCalculationResult(row[1], row[2], input_fact_ids, json.loads(row[4]))))
        return tuple(matched)
