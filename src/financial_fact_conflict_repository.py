# -*- coding: utf-8 -*-
"""未裁决 FinancialFact 冲突的人工确认仓储。"""

import json

from .financial_fact_conflict_service import FinancialFactConflictDecision
from .v7_metadata_store import V7MetadataStore


class FinancialFactConflictConflictError(RuntimeError):
    """同一冲突 ID 对应的待人工复核证据不一致。"""


class FinancialFactConflictRepository:
    """持久化待人工确认的冲突，不修改任一事实。"""

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store

    def save(self, conflict_id: str, decision: FinancialFactConflictDecision) -> None:
        if decision.status != "pending_review" or not decision.conflict_type:
            raise ValueError("只有待人工复核的冲突可以持久化")
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT status, conflict_type, fact_ids_json, relative_difference, preferred_fact_id FROM v7_financial_fact_conflicts WHERE conflict_id = ?",
                    (conflict_id,),
                ).fetchone()
                existing = (
                    FinancialFactConflictDecision(row[0], row[1], tuple(json.loads(row[2])), row[3], row[4])
                    if row is not None else None
                )
                if existing is not None:
                    connection.commit()
                    if existing != decision:
                        raise FinancialFactConflictConflictError("conflict_id 与既有冲突证据不一致")
                    return
                connection.execute(
                    "INSERT INTO v7_financial_fact_conflicts VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                    (conflict_id, decision.status, decision.conflict_type, json.dumps(decision.fact_ids), decision.relative_difference, decision.preferred_fact_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def get(self, conflict_id: str) -> FinancialFactConflictDecision | None:
        self.store.initialize()
        with self.store.connect() as connection:
            row = connection.execute("SELECT status, conflict_type, fact_ids_json, relative_difference, preferred_fact_id FROM v7_financial_fact_conflicts WHERE conflict_id = ?", (conflict_id,)).fetchone()
        if row is None:
            return None
        return FinancialFactConflictDecision(row[0], row[1], tuple(json.loads(row[2])), row[3], row[4])

    def list_by_fact_ids(self, fact_ids: tuple[str, ...]) -> tuple[tuple[str, FinancialFactConflictDecision], ...]:
        """返回涉及给定 fact_ids 的冲突裁决，按 conflict_id 稳定排序。"""
        if not fact_ids:
            return ()
        self.store.initialize()
        wanted = set(fact_ids)
        with self.store.connect() as connection:
            rows = connection.execute(
                "SELECT conflict_id, status, conflict_type, fact_ids_json, relative_difference, preferred_fact_id FROM v7_financial_fact_conflicts ORDER BY conflict_id"
            ).fetchall()
        matched = []
        for row in rows:
            decision_fact_ids = tuple(json.loads(row[3]))
            if wanted.isdisjoint(decision_fact_ids):
                continue
            matched.append((row[0], FinancialFactConflictDecision(row[1], row[2], decision_fact_ids, row[4], row[5])))
        return tuple(matched)
