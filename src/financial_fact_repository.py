# -*- coding: utf-8 -*-
"""FinancialFact 的 V7 SQLite 不可变仓储。"""

import json
from dataclasses import dataclass
from decimal import Decimal

from .financial_fact import FinancialFact
from .v7_metadata_store import V7MetadataStore


class FinancialFactConflictError(RuntimeError):
    """同一 fact_id 对应的已有证据与新证据不一致。"""


@dataclass(frozen=True)
class FinancialFactSaveResult:
    """事实写入的幂等结果。"""

    fact_id: str
    created: bool


class FinancialFactRepository:
    """把经校验的事实以事实 ID 幂等写入 V7MetadataStore。"""

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store

    def save(self, fact: FinancialFact) -> FinancialFactSaveResult:
        """写入不可变事实；同 ID 仅允许完全相同的证据重放。"""
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    "SELECT * FROM v7_financial_facts WHERE fact_id = ?",
                    (fact.fact_id,),
                ).fetchone()
                if existing is not None:
                    connection.commit()
                    if self._from_row(existing) != fact:
                        raise FinancialFactConflictError("fact_id 与既有事实证据不一致")
                    return FinancialFactSaveResult(fact.fact_id, False)
                connection.execute(
                    """
                    INSERT INTO v7_financial_facts(
                        fact_id, metric_key, company_name, raw_value, raw_unit,
                        normalized_value, normalized_unit, currency, period,
                        scope, source_file, physical_pages_json, excerpt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._to_row_values(fact),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return FinancialFactSaveResult(fact.fact_id, True)

    def get(self, fact_id: str) -> FinancialFact | None:
        """按稳定事实 ID 读取不可变事实。"""
        self.store.initialize()
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT * FROM v7_financial_facts WHERE fact_id = ?",
                (fact_id,),
            ).fetchone()
        return self._from_row(row) if row is not None else None

    @staticmethod
    def _to_row_values(fact: FinancialFact) -> tuple[str, ...]:
        """将 Decimal 和物理页序列序列化为稳定数据库值。"""
        return (
            fact.fact_id,
            fact.metric_key,
            fact.company_name,
            str(fact.raw_value),
            fact.raw_unit,
            str(fact.normalized_value),
            fact.normalized_unit,
            fact.currency,
            fact.period,
            fact.scope,
            fact.source_file,
            json.dumps(fact.physical_pages, ensure_ascii=False),
            fact.excerpt,
        )

    @staticmethod
    def _from_row(row) -> FinancialFact:
        """从数据库行重建领域模型，继续使用统一输入验证。"""
        return FinancialFact.create(
            fact_id=row[0],
            metric_key=row[1],
            company_name=row[2],
            raw_value=Decimal(row[3]),
            raw_unit=row[4],
            normalized_value=Decimal(row[5]),
            normalized_unit=row[6],
            currency=row[7],
            period=row[8],
            scope=row[9],
            source_file=row[10],
            physical_pages=tuple(json.loads(row[11])),
            excerpt=row[12],
        )
