# -*- coding: utf-8 -*-
"""B2.5 声明级 EvidenceBundle：把声明与事实、计算、冲突关联为不可变可审计对象。"""

import json
from dataclasses import dataclass

from .v7_metadata_store import V7MetadataStore


class EvidenceBundleConflictError(RuntimeError):
    """同一 bundle_id 对应的声明证据关联不一致。"""


@dataclass(frozen=True)
class EvidenceBundle:
    """关联声明与事实、计算、冲突的不可变证据包。"""

    bundle_id: str
    claim_id: str
    claim_text: str
    fact_ids: tuple[str, ...]
    calculation_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]

    @classmethod
    def create(
        cls,
        *,
        bundle_id: str,
        claim_id: str,
        claim_text: str,
        fact_ids: tuple[str, ...] | list[str] = (),
        calculation_ids: tuple[str, ...] | list[str] = (),
        conflict_ids: tuple[str, ...] | list[str] = (),
    ) -> "EvidenceBundle":
        """创建经边界校验的证据包，不从缺失字段推测关联。"""
        for field_name, value in {
            "bundle_id": bundle_id,
            "claim_id": claim_id,
            "claim_text": claim_text,
        }.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} 不能为空")
        normalized_facts = cls._normalize_reference_ids(fact_ids, "fact_ids")
        normalized_calculations = cls._normalize_reference_ids(calculation_ids, "calculation_ids")
        normalized_conflicts = cls._normalize_reference_ids(conflict_ids, "conflict_ids")
        if not (normalized_facts or normalized_calculations or normalized_conflicts):
            raise ValueError("证据包必须至少关联一条事实、计算或冲突")
        return cls(
            bundle_id=bundle_id,
            claim_id=claim_id,
            claim_text=claim_text,
            fact_ids=normalized_facts,
            calculation_ids=normalized_calculations,
            conflict_ids=normalized_conflicts,
        )

    @staticmethod
    def _normalize_reference_ids(value: tuple[str, ...] | list[str], field_name: str) -> tuple[str, ...]:
        """校验引用 ID 列表：元素非空且不重复。"""
        if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
            raise ValueError(f"{field_name} 必须是 ID 元组或列表")
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"{field_name} 中的引用 ID 不能为空")
        if len(set(value)) != len(value):
            raise ValueError(f"{field_name} 中存在重复引用 ID")
        return tuple(value)

    def to_response(self) -> dict:
        """输出 JSON 兼容字典，作为既有来源响应的可选新增字段。"""
        return {
            "bundle_id": self.bundle_id,
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "fact_ids": list(self.fact_ids),
            "calculation_ids": list(self.calculation_ids),
            "conflict_ids": list(self.conflict_ids),
        }


class EvidenceBundleRepository:
    """持久化声明级证据包，拒绝悬空引用与静默改写。"""

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store

    def save(self, bundle: EvidenceBundle) -> None:
        """幂等保存证据包；同一 bundle_id 内容不一致时报冲突。"""
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                claim_row = connection.execute(
                    "SELECT claim_text FROM v7_claims WHERE claim_id = ?",
                    (bundle.claim_id,),
                ).fetchone()
                if claim_row is not None and claim_row[0] != bundle.claim_text:
                    raise EvidenceBundleConflictError("claim_id 与既有声明文本不一致")
                if claim_row is None:
                    connection.execute(
                        "INSERT INTO v7_claims(claim_id, claim_text) VALUES (?, ?)",
                        (bundle.claim_id, bundle.claim_text),
                    )
                self._ensure_references_exist(connection, bundle)
                existing = connection.execute(
                    "SELECT claim_id, fact_ids_json, calculation_ids_json, conflict_ids_json FROM v7_evidence_bundles WHERE bundle_id = ?",
                    (bundle.bundle_id,),
                ).fetchone()
                if existing is not None:
                    connection.commit()
                    existing_bundle = EvidenceBundle(
                        bundle.bundle_id,
                        existing[0],
                        bundle.claim_text,
                        tuple(json.loads(existing[1])),
                        tuple(json.loads(existing[2])),
                        tuple(json.loads(existing[3])),
                    )
                    if existing_bundle != bundle:
                        raise EvidenceBundleConflictError("bundle_id 与既有证据包不一致")
                    return
                connection.execute(
                    "INSERT INTO v7_evidence_bundles(bundle_id, claim_id, fact_ids_json, calculation_ids_json, conflict_ids_json) VALUES (?, ?, ?, ?, ?)",
                    (
                        bundle.bundle_id,
                        bundle.claim_id,
                        json.dumps(list(bundle.fact_ids)),
                        json.dumps(list(bundle.calculation_ids)),
                        json.dumps(list(bundle.conflict_ids)),
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def get(self, bundle_id: str) -> EvidenceBundle | None:
        """按 bundle_id 读取证据包；缺失时返回 None。"""
        self.store.initialize()
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT bundle_id, claim_id, fact_ids_json, calculation_ids_json, conflict_ids_json FROM v7_evidence_bundles WHERE bundle_id = ?",
                (bundle_id,),
            ).fetchone()
            if row is None:
                return None
            claim_row = connection.execute(
                "SELECT claim_text FROM v7_claims WHERE claim_id = ?",
                (row[1],),
            ).fetchone()
        claim_text = claim_row[0] if claim_row is not None else ""
        return EvidenceBundle(
            row[0],
            row[1],
            claim_text,
            tuple(json.loads(row[2])),
            tuple(json.loads(row[3])),
            tuple(json.loads(row[4])),
        )

    @staticmethod
    def _ensure_references_exist(connection, bundle: EvidenceBundle) -> None:
        """校验引用的事实、计算、冲突均已持久化，阻止悬空引用。"""
        for fact_id in bundle.fact_ids:
            row = connection.execute(
                "SELECT 1 FROM v7_financial_facts WHERE fact_id = ?", (fact_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"证据包引用的事实 {fact_id} 不存在，拒绝悬空引用")
        for calculation_id in bundle.calculation_ids:
            row = connection.execute(
                "SELECT 1 FROM v7_fact_calculations WHERE calculation_id = ?", (calculation_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"证据包引用的计算 {calculation_id} 不存在，拒绝悬空引用")
        for conflict_id in bundle.conflict_ids:
            row = connection.execute(
                "SELECT 1 FROM v7_financial_fact_conflicts WHERE conflict_id = ?", (conflict_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"证据包引用的冲突 {conflict_id} 不存在，拒绝悬空引用")
