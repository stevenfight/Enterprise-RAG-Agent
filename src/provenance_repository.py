# -*- coding: utf-8 -*-
"""M0.6 的最小关系型溯源仓储，不引入图数据库。"""

from .v7_metadata_store import V7MetadataStore


class ProvenanceRepository:
    """保存发布对象间可受外键约束的关系，并传播来源版本失效状态。"""

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store

    def link_fact_to_document_version(self, fact_id: str, document_version_id: str) -> None:
        self._link("v7_fact_document_versions", "fact_id", fact_id, "document_version_id", document_version_id)

    def link_artifact_to_fact(self, page_artifact_id: str, fact_id: str) -> None:
        self._link("v7_artifact_fact_links", "page_artifact_id", page_artifact_id, "fact_id", fact_id)

    def link_calculation_input(self, calculation_id: str, fact_id: str) -> None:
        self._link("v7_calculation_input_facts", "calculation_id", calculation_id, "fact_id", fact_id)

    def link_claim_fact(self, claim_id: str, fact_id: str) -> None:
        self._link("v7_claim_fact_links", "claim_id", claim_id, "fact_id", fact_id)

    def link_claim_calculation(self, claim_id: str, calculation_id: str) -> None:
        self._link("v7_claim_calculation_links", "claim_id", claim_id, "calculation_id", calculation_id)

    def create_report(self, report_id: str, report_title: str) -> None:
        if not isinstance(report_id, str) or not report_id.strip():
            raise ValueError("report_id 不能为空")
        if not isinstance(report_title, str) or not report_title.strip():
            raise ValueError("report_title 不能为空")
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    "SELECT report_title FROM v7_reports WHERE report_id = ?", (report_id,)
                ).fetchone()
                if existing is None:
                    connection.execute(
                        "INSERT INTO v7_reports(report_id, report_title) VALUES (?, ?)",
                        (report_id, report_title),
                    )
                elif existing[0] != report_title:
                    raise ValueError("report_id 与既有报告标题不一致")
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def link_report_claim(self, report_id: str, claim_id: str) -> None:
        self._link("v7_report_claim_links", "report_id", report_id, "claim_id", claim_id)

    def invalidate_document_version(self, document_version_id: str, reason: str) -> dict[str, list[str]]:
        """使直接或间接依赖该版本的计算、声明、报告进入 stale 状态。"""
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason 不能为空")
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute(
                    "SELECT 1 FROM v7_document_versions WHERE document_version_id = ?", (document_version_id,)
                ).fetchone() is None:
                    raise ValueError("document_version_id 不存在")
                fact_ids = self._ids(connection, "SELECT fact_id FROM v7_fact_document_versions WHERE document_version_id = ?", (document_version_id,))
                calculation_ids = self._related_ids(connection, "v7_calculation_input_facts", "calculation_id", "fact_id", fact_ids)
                claim_ids = sorted(set(
                    self._related_ids(connection, "v7_claim_fact_links", "claim_id", "fact_id", fact_ids)
                    + self._related_ids(connection, "v7_claim_calculation_links", "claim_id", "calculation_id", calculation_ids)
                ))
                report_ids = self._related_ids(connection, "v7_report_claim_links", "report_id", "claim_id", claim_ids)
                connection.execute(
                    "INSERT OR IGNORE INTO v7_document_version_invalidations(document_version_id, reason) VALUES (?, ?)",
                    (document_version_id, reason),
                )
                for calculation_id in calculation_ids:
                    connection.execute(
                        "INSERT INTO v7_calculation_provenance_status(calculation_id, provenance_status, invalidated_at) VALUES (?, 'stale', CURRENT_TIMESTAMP) ON CONFLICT(calculation_id) DO UPDATE SET provenance_status = 'stale', invalidated_at = CURRENT_TIMESTAMP",
                        (calculation_id,),
                    )
                for claim_id in claim_ids:
                    connection.execute(
                        "INSERT INTO v7_claim_provenance_status(claim_id, provenance_status, invalidated_at) VALUES (?, 'stale', CURRENT_TIMESTAMP) ON CONFLICT(claim_id) DO UPDATE SET provenance_status = 'stale', invalidated_at = CURRENT_TIMESTAMP",
                        (claim_id,),
                    )
                for report_id in report_ids:
                    connection.execute("UPDATE v7_reports SET report_status = 'stale' WHERE report_id = ?", (report_id,))
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return {"fact_ids": fact_ids, "calculation_ids": calculation_ids, "claim_ids": claim_ids, "report_ids": report_ids}

    def get_statuses(self, calculation_id: str, claim_id: str, report_id: str) -> dict[str, str]:
        """读取失效传播结果，缺省状态均为 current。"""
        self.store.initialize()
        with self.store.connect() as connection:
            calculation = connection.execute("SELECT provenance_status FROM v7_calculation_provenance_status WHERE calculation_id = ?", (calculation_id,)).fetchone()
            claim = connection.execute("SELECT provenance_status FROM v7_claim_provenance_status WHERE claim_id = ?", (claim_id,)).fetchone()
            report = connection.execute("SELECT report_status FROM v7_reports WHERE report_id = ?", (report_id,)).fetchone()
        return {"calculation_status": calculation[0] if calculation else "current", "claim_status": claim[0] if claim else "current", "report_status": report[0] if report else "current"}

    def _link(self, table: str, left_column: str, left_value: str, right_column: str, right_value: str) -> None:
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    f"INSERT OR IGNORE INTO {table}({left_column}, {right_column}) VALUES (?, ?)",
                    (left_value, right_value),
                )
                connection.commit()
            except Exception as error:
                connection.rollback()
                if "FOREIGN KEY constraint failed" in str(error):
                    raise ValueError("关联对象不存在，拒绝写入悬空关系") from error
                raise

    @staticmethod
    def _ids(connection, statement: str, values: tuple[str, ...]) -> list[str]:
        return sorted(row[0] for row in connection.execute(statement, values).fetchall())

    @staticmethod
    def _related_ids(connection, table: str, result_column: str, input_column: str, values: list[str]) -> list[str]:
        if not values:
            return []
        placeholders = ", ".join("?" for _ in values)
        rows = connection.execute(
            f"SELECT {result_column} FROM {table} WHERE {input_column} IN ({placeholders})",
            values,
        ).fetchall()
        return sorted({row[0] for row in rows})
