# -*- coding: utf-8 -*-
"""扫描视觉数值候选的外键绑定、审核与事实关联仓储。"""

import json
from dataclasses import dataclass
from typing import Mapping

from .scan_page_vision import ScanPageVisionResult
from .v7_metadata_store import V7MetadataStore
from .visual_fact_normalizer import normalize_visual_numeric_payload


@dataclass(frozen=True)
class VisualFactCandidate:
    """已持久化的扫描视觉数值候选。"""

    candidate_id: str
    manifest_id: str
    page_artifact_id: str
    extracted_text: str
    numeric_payload: Mapping[str, object]
    confidence: float
    review_status: str
    fact_id: str | None = None


class VisualFactCandidateRepository:
    """候选先持久化审核，再由准入服务写入事实。"""

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store

    def register_scan_candidate(self, *, candidate_id: str, manifest_id: str, page_artifact_id: str, scan_result: ScanPageVisionResult, numeric_payload: Mapping[str, object]) -> VisualFactCandidate:
        """登记扫描候选；只接受同一 manifest/page 的 candidate 响应。"""
        if scan_result.status != "candidate" or scan_result.confidence is None:
            raise ValueError("扫描结果不是可审核候选")
        if scan_result.manifest_id != manifest_id or scan_result.page_artifact_id != page_artifact_id:
            raise ValueError("扫描结果与候选身份不一致")
        if not isinstance(numeric_payload, Mapping) or not numeric_payload:
            raise ValueError("numeric_payload 不能为空")
        self.store.initialize()
        normalized = normalize_visual_numeric_payload(numeric_payload)
        persisted_payload = {
            **dict(numeric_payload),
            "normalized_value": str(normalized.normalized_value),
            "normalized_unit": normalized.normalized_unit,
            "conversion_trace": normalized.conversion_trace,
        }
        payload_json = json.dumps(persisted_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute("SELECT manifest_id FROM v7_page_artifacts WHERE page_artifact_id = ?", (page_artifact_id,)).fetchone()
                if row is None or row[0] != manifest_id:
                    raise ValueError("页制品不存在或不属于 manifest")
                connection.execute("INSERT INTO v7_visual_fact_candidates(candidate_id, manifest_id, page_artifact_id, extracted_text, numeric_payload_json, confidence, review_status) VALUES (?, ?, ?, ?, ?, ?, 'pending_review')", (candidate_id, manifest_id, page_artifact_id, scan_result.extracted_text, payload_json, float(scan_result.confidence)))
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self.get(candidate_id)

    def review(self, candidate_id: str, review_status: str) -> VisualFactCandidate:
        """人工审核只能将待审核候选转为 verified 或 rejected。"""
        if review_status not in {"verified", "rejected"}:
            raise ValueError("审核结果无效")
        self.store.initialize()
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT review_status FROM v7_visual_fact_candidates WHERE candidate_id = ?", (candidate_id,)).fetchone()
            if row is None:
                connection.rollback()
                raise ValueError("视觉事实候选不存在")
            if row[0] != "pending_review":
                connection.rollback()
                raise ValueError("视觉事实候选不允许重复审核")
            connection.execute("UPDATE v7_visual_fact_candidates SET review_status = ?, reviewed_at = CURRENT_TIMESTAMP WHERE candidate_id = ?", (review_status, candidate_id))
            connection.commit()
        return self.get(candidate_id)

    def link_fact(self, candidate_id: str, fact_id: str) -> VisualFactCandidate:
        """仅将已审核候选关联到已经由准入服务保存的事实。"""
        self.store.initialize()
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT review_status, fact_id FROM v7_visual_fact_candidates WHERE candidate_id = ?", (candidate_id,)).fetchone()
            if row is None or row[0] != "verified" or row[1] is not None:
                connection.rollback()
                raise ValueError("视觉事实候选尚未审核或已关联事实")
            connection.execute("UPDATE v7_visual_fact_candidates SET fact_id = ? WHERE candidate_id = ?", (fact_id, candidate_id))
            connection.commit()
        return self.get(candidate_id)

    def get(self, candidate_id: str) -> VisualFactCandidate | None:
        self.store.initialize()
        with self.store.connect() as connection:
            row = connection.execute("SELECT candidate_id, manifest_id, page_artifact_id, extracted_text, numeric_payload_json, confidence, review_status, fact_id FROM v7_visual_fact_candidates WHERE candidate_id = ?", (candidate_id,)).fetchone()
        if row is None:
            return None
        return VisualFactCandidate(row[0], row[1], row[2], row[3], json.loads(row[4]), float(row[5]), row[6], row[7])
