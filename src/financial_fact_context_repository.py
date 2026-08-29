# -*- coding: utf-8 -*-
"""FinancialFact 上下文的 V7 SQLite 仓储。"""

import json

from .financial_fact_context import FinancialFactSource, FinancialPeriod, FinancialScope
from .v7_metadata_store import V7MetadataStore


class FinancialFactContextConflictError(RuntimeError):
    """同一上下文 ID 对应的既有审计证据不一致。"""


class FinancialFactContextRepository:
    """在同一 V7 数据库持久化期间、口径和真实文档版本来源。"""

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store

    def save_period(self, period: FinancialPeriod) -> None:
        self._save("v7_financial_periods", "INSERT INTO v7_financial_periods VALUES (?, ?, ?, ?, ?)", (period.period_id, period.period_start.isoformat(), period.period_end.isoformat(), period.fiscal_year, period.period_type))

    def save_scope(self, scope: FinancialScope) -> None:
        self._save("v7_financial_scopes", "INSERT INTO v7_financial_scopes VALUES (?, ?, ?, ?)", (scope.scope_id, scope.consolidation, scope.accounting_standard, int(scope.audited)))

    def save_source(self, source: FinancialFactSource) -> None:
        self._save("v7_financial_fact_sources", "INSERT INTO v7_financial_fact_sources VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (source.source_id, source.logical_document_id, source.document_version_id, source.source_file, json.dumps(source.physical_pages), source.excerpt, source.source_type, source.authority_level))

    def get_source(self, source_id: str) -> FinancialFactSource | None:
        self.store.initialize()
        with self.store.connect() as connection:
            row = connection.execute("SELECT * FROM v7_financial_fact_sources WHERE source_id = ?", (source_id,)).fetchone()
        if row is None:
            return None
        return FinancialFactSource.create(source_id=row[0], logical_document_id=row[1], document_version_id=row[2], source_file=row[3], physical_pages=tuple(json.loads(row[4])), excerpt=row[5], source_type=row[6], authority_level=row[7])

    def _save(self, table: str, statement: str, values: tuple) -> None:
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                key_column = {
                    "v7_financial_periods": "period_id",
                    "v7_financial_scopes": "scope_id",
                    "v7_financial_fact_sources": "source_id",
                }[table]
                existing = connection.execute(
                    f"SELECT * FROM {table} WHERE {key_column} = ?",
                    (values[0],),
                ).fetchone()
                if existing is not None:
                    connection.commit()
                    if tuple(existing) != values:
                        raise FinancialFactContextConflictError("上下文 ID 与既有证据不一致")
                    return
                connection.execute(statement, values)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
