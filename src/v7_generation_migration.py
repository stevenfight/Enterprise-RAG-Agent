# -*- coding: utf-8 -*-
"""首轮 v7 候选 generation 的构建、验证与迁移审计。"""

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable

from .v7_metadata_store import V7MetadataStore


class GenerationMigrationError(RuntimeError):
    """候选 generation 的基线、证据或验证条件不满足。"""


class V7GenerationMigrator:
    """只构建可审计候选 generation，不负责 active publication。"""

    _VECTOR_EVIDENCE_FIELDS = (
        "parser_version", "splitter_version", "preprocess_version",
        "embedding_model", "embedding_version", "vector_dimension", "schema_version",
    )
    _REQUIRED_ARTIFACTS = (
        "index.faiss", "bm25_index.pkl", "metadata.json", "parent_texts.json",
    )

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store

    def build_candidate(
        self,
        generation_id: str,
        chunks: Iterable[dict[str, Any]],
        *,
        _excluded_document_version_id: str | None = None,
    ) -> dict[str, Any]:
        """固定 active 文档基线并记录每个 chunk 的复用或重嵌入决策。"""
        if not isinstance(generation_id, str) or not generation_id.strip():
            raise ValueError("generation_id 不能为空")
        self.store.initialize()
        normalized_chunks = [self._normalize_chunk(item) for item in chunks]
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                documents = self._active_documents(connection, _excluded_document_version_id)
                expected_ids = [item["document_version_id"] for item in documents]
                actual_ids = sorted({item["document_version_id"] for item in normalized_chunks})
                if actual_ids != expected_ids:
                    raise GenerationMigrationError("候选 generation 未覆盖全部 active 文档版本")
                corpus_revision = self._corpus_revision(documents)
                actions = {item["chunk_id"]: self._vector_action(item) for item in normalized_chunks}
                payload = {
                    "document_version_ids": expected_ids,
                    "corpus_revision": corpus_revision,
                    "chunk_actions": actions,
                    "chunks": normalized_chunks,
                }
                payload_json = self._canonical_json(payload)
                existing = connection.execute(
                    "SELECT payload_json FROM v7_generation_candidates WHERE generation_id = ?", (generation_id,)
                ).fetchone()
                if existing is not None:
                    if existing[0] != payload_json:
                        raise GenerationMigrationError("generation_id 与既有迁移载荷不一致")
                    connection.commit()
                    return self.get_candidate(generation_id)
                connection.execute(
                    "INSERT INTO v7_generation_candidates(generation_id, corpus_revision, status, payload_json) VALUES (?, ?, 'candidate', ?)",
                    (generation_id, corpus_revision, payload_json),
                )
                for document in documents:
                    connection.execute(
                        "INSERT INTO v7_generation_documents VALUES (?, ?, ?)",
                        (generation_id, document["document_version_id"], document["blob_sha256"]),
                    )
                for chunk in normalized_chunks:
                    connection.execute(
                        "INSERT INTO v7_generation_chunks VALUES (?, ?, ?, ?, ?, ?)",
                        (generation_id, chunk["chunk_id"], chunk["document_version_id"], chunk["text_sha256"], actions[chunk["chunk_id"]], self._canonical_json(chunk)),
                    )
                self._audit(connection, generation_id, "baseline_frozen", {
                    "corpus_revision": corpus_revision,
                    "document_version_ids": expected_ids,
                    "source_sha256s": [item["blob_sha256"] for item in documents],
                })
                if _excluded_document_version_id is not None:
                    self._audit(connection, generation_id, "document_exclusion_planned", {
                        "excluded_document_version_id": _excluded_document_version_id,
                    })
                self._audit(connection, generation_id, "chunk_migration_decision", {"chunk_actions": actions})
                foreign_key_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
                if foreign_key_violations:
                    raise GenerationMigrationError("迁移前溯源外键完整性校验失败")
                self._audit(connection, generation_id, "provenance_foreign_key_check", {"violations": []})
                self._audit(connection, generation_id, "publication_boundary", {
                    "status": "candidate_only",
                    "legacy_active_pointer": "unchanged",
                    "rollback": "not_applicable_before_publication",
                })
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self.get_candidate(generation_id)

    def build_candidate_excluding_document(
        self,
        generation_id: str,
        excluded_document_version_id: str,
        chunks: Iterable[dict[str, Any]],
    ) -> dict[str, Any]:
        """构建排除已索引文档的候选代际，不修改 active 文档或发布集。"""
        if not isinstance(excluded_document_version_id, str) or not excluded_document_version_id.strip():
            raise ValueError("excluded_document_version_id 不能为空")
        self.store.initialize()
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT index_status FROM v7_document_versions WHERE document_version_id = ?",
                (excluded_document_version_id,),
            ).fetchone()
        if row is None:
            raise GenerationMigrationError("待移除文档版本不存在")
        # M3.10.b：deleting 是删除线性化的目标状态，rebuild_required 删除请求
        # 需要排除的正是该版本；除 active/deleting 之外的其余状态仍然拒绝。
        if row[0] not in ("active", "deleting"):
            raise GenerationMigrationError("待移除文档版本不是 active 状态")
        return self.build_candidate(
            generation_id,
            chunks,
            _excluded_document_version_id=excluded_document_version_id,
        )

    def validate_candidate(
        self,
        generation_id: str,
        artifact_root: Path,
        *,
        sample_retriever: Callable[[], list[str]],
        legacy_active_pointer: Path | None = None,
    ) -> dict[str, Any]:
        """验证不可变候选制品；本方法绝不写入 legacy active 指针。"""
        self.store.initialize()
        artifact_root = Path(artifact_root)
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT status, payload_json, artifact_manifest_json FROM v7_generation_candidates WHERE generation_id = ?", (generation_id,)
                ).fetchone()
                if row is None:
                    raise GenerationMigrationError("generation_id 不存在")
                payload = json.loads(row[1])
                manifest = self._artifact_manifest(artifact_root)
                existing_manifest = json.loads(row[2])
                if existing_manifest and existing_manifest != manifest:
                    raise GenerationMigrationError("候选 generation 制品哈希或大小不一致")
                self._validate_metadata_sidecars(artifact_root)
                dimensions = {item["vector_dimension"] for item in payload["chunks"]}
                if len(dimensions) != 1 or next(iter(dimensions)) <= 0:
                    raise GenerationMigrationError("候选 generation 向量维度不一致")
                sample = sample_retriever()
                if not isinstance(sample, list) or not sample:
                    raise GenerationMigrationError("抽样检索未返回候选 chunk")
                chunk_ids = {item["chunk_id"] for item in payload["chunks"]}
                if not set(sample).issubset(chunk_ids):
                    raise GenerationMigrationError("抽样检索返回未知 chunk")
                validation = {
                    "status": "validated",
                    "document_count": len(payload["document_version_ids"]),
                    "chunk_count": len(payload["chunks"]),
                    "vector_dimension": next(iter(dimensions)),
                    "artifact_manifest": manifest,
                    "sample_chunk_ids": sorted(sample),
                    "legacy_active_pointer_unchanged": str(legacy_active_pointer) if legacy_active_pointer else None,
                }
                connection.execute(
                    "UPDATE v7_generation_candidates SET status = 'validated', artifact_manifest_json = ?, validation_json = ? WHERE generation_id = ?",
                    (self._canonical_json(manifest), self._canonical_json(validation), generation_id),
                )
                self._audit(connection, generation_id, "validation_passed", validation)
                connection.commit()
                return validation
            except Exception as error:
                connection.rollback()
                if isinstance(error, GenerationMigrationError):
                    migration_error = error
                else:
                    migration_error = GenerationMigrationError(str(error))
        self._record_validation_failure(generation_id, str(migration_error))
        raise migration_error

    def get_candidate(self, generation_id: str) -> dict[str, Any]:
        """读取候选 generation 与其固定的基线、chunk 决策和验证结果。"""
        self.store.initialize()
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT corpus_revision, status, payload_json, validation_json FROM v7_generation_candidates WHERE generation_id = ?", (generation_id,)
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row[2])
        return {
            "generation_id": generation_id,
            "corpus_revision": row[0],
            "status": row[1],
            "document_version_ids": payload["document_version_ids"],
            "chunk_actions": payload["chunk_actions"],
            "validation": json.loads(row[3]),
        }

    @staticmethod
    def _canonical_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _active_documents(
        connection,
        excluded_document_version_id: str | None = None,
    ) -> list[dict[str, str]]:
        query = "SELECT document_version_id, blob_sha256 FROM v7_document_versions WHERE index_status = 'active'"
        parameters: tuple[str, ...] = ()
        if excluded_document_version_id is not None:
            query += " AND document_version_id != ?"
            parameters = (excluded_document_version_id,)
        rows = connection.execute(f"{query} ORDER BY document_version_id", parameters).fetchall()
        if not rows:
            raise GenerationMigrationError("不存在 active 文档版本，无法建立迁移基线")
        return [{"document_version_id": row[0], "blob_sha256": row[1]} for row in rows]

    @staticmethod
    def _corpus_revision(documents: list[dict[str, str]]) -> str:
        canonical = "\n".join(f"{item['document_version_id']}:{item['blob_sha256']}" for item in documents)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _normalize_chunk(self, chunk: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(chunk, dict):
            raise GenerationMigrationError("chunk 必须为对象")
        required = ("chunk_id", "document_version_id", "text_sha256")
        if any(not isinstance(chunk.get(key), str) or not chunk[key].strip() for key in required):
            raise GenerationMigrationError("chunk 缺少稳定 ID 或文本哈希")
        result = {key: chunk.get(key) for key in required + self._VECTOR_EVIDENCE_FIELDS}
        if not isinstance(result["text_sha256"], str) or len(result["text_sha256"]) != 64:
            raise GenerationMigrationError("chunk 文本哈希无效")
        return result

    def _vector_action(self, chunk: dict[str, Any]) -> str:
        if any(chunk.get(field) in (None, "") for field in self._VECTOR_EVIDENCE_FIELDS):
            return "reembed_required"
        if not isinstance(chunk["vector_dimension"], int) or chunk["vector_dimension"] <= 0:
            return "reembed_required"
        if not isinstance(chunk["schema_version"], int) or chunk["schema_version"] <= 0:
            return "reembed_required"
        return "reuse_eligible"

    def _artifact_manifest(self, artifact_root: Path) -> list[dict[str, Any]]:
        manifest = []
        for name in self._REQUIRED_ARTIFACTS:
            path = artifact_root / name
            if not path.is_file() or path.stat().st_size <= 0:
                raise GenerationMigrationError(f"索引制品缺失或为空: {name}")
            content = path.read_bytes()
            manifest.append({"name": name, "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
        return manifest

    @staticmethod
    def _validate_metadata_sidecars(artifact_root: Path) -> None:
        """校验 FAISS/BM25 使用的两个 JSON 旁车具有预期容器类型。"""
        try:
            metadata = json.loads((artifact_root / "metadata.json").read_text(encoding="utf-8"))
            parent_texts = json.loads((artifact_root / "parent_texts.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise GenerationMigrationError("BM25/FAISS metadata 不是合法 JSON") from error
        if not isinstance(metadata, list) or not isinstance(parent_texts, dict):
            raise GenerationMigrationError("BM25/FAISS metadata 类型无效")

    def _audit(self, connection, generation_id: str, audit_type: str, payload: dict[str, Any]) -> None:
        connection.execute(
            "INSERT INTO v7_generation_migration_audit(generation_id, audit_type, payload_json) VALUES (?, ?, ?)",
            (generation_id, audit_type, self._canonical_json(payload)),
        )

    def _record_validation_failure(self, generation_id: str, reason: str) -> None:
        """验证失败也必须持久化，且不会改变任何 legacy 发布指针。"""
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                exists = connection.execute(
                    "SELECT 1 FROM v7_generation_candidates WHERE generation_id = ?", (generation_id,)
                ).fetchone()
                if exists is not None:
                    connection.execute(
                        "UPDATE v7_generation_candidates SET status = 'validation_failed' WHERE generation_id = ?",
                        (generation_id,),
                    )
                    self._audit(connection, generation_id, "validation_failed", {"reason": reason})
                connection.commit()
            except Exception:
                connection.rollback()
                raise
