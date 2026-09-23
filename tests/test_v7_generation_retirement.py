# -*- coding: utf-8 -*-
"""M1.8.d 旧 generation 回收前置条件资格记录测试（只记录资格，不物理删除）。"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest


def _seed_active_documents(store) -> None:
    store.initialize()
    with store.connect() as connection:
        for suffix in ("1", "2"):
            sha256 = hashlib.sha256(f"pdf-{suffix}".encode()).hexdigest()
            connection.execute("INSERT INTO v7_blobs(sha256, size_bytes) VALUES (?, 1)", (sha256,))
            connection.execute(
                "INSERT INTO v7_logical_documents VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (f"logical-{suffix}", f"report-{suffix}", f"报告{suffix}"),
            )
            connection.execute(
                """INSERT INTO v7_document_versions(
                    document_version_id, logical_document_id, blob_sha256,
                    original_filename, physical_page_count, index_status
                ) VALUES (?, ?, ?, ?, 1, 'active')""",
                (f"version-{suffix}", f"logical-{suffix}", sha256, f"报告{suffix}.pdf"),
            )
        connection.commit()


def _chunk(version_id: str) -> dict:
    return {
        "chunk_id": f"chunk-{version_id}",
        "document_version_id": version_id,
        "text_sha256": hashlib.sha256(version_id.encode()).hexdigest(),
        "parser_version": "mineru-v4",
        "splitter_version": "split-v2",
        "preprocess_version": "prep-v1",
        "embedding_model": "text-embedding-v3",
        "embedding_version": "2026-08",
        "vector_dimension": 1024,
        "schema_version": 1,
    }


def _write_staging_artifacts(artifact_root: Path) -> None:
    artifact_root.mkdir(parents=True, exist_ok=True)
    (artifact_root / "index.faiss").write_bytes(b"index")
    (artifact_root / "bm25_index.pkl").write_bytes(b"bm25")
    (artifact_root / "metadata.json").write_text("[]", encoding="utf-8")
    (artifact_root / "parent_texts.json").write_text("{}", encoding="utf-8")


def _validated_generation(store, migrator, generation_id: str, artifact_root: Path) -> None:
    migrator.build_candidate(generation_id, [_chunk("version-1"), _chunk("version-2")])
    migrator.validate_candidate(
        generation_id,
        artifact_root,
        sample_retriever=lambda: ["chunk-version-1", "chunk-version-2"],
    )


def _activate_publication(store, publication_id: str, generation_id: str, expected_active_id, expected_revision) -> None:
    from src.publication_set import PublicationSetRepository

    repository = PublicationSetRepository(store)
    repository.create_publication(
        publication_id,
        generation_id,
        ("version-1", "version-2"),
    )
    repository.prepare_publication_build(publication_id, expected_active_id, expected_revision)
    repository.activate_publication(publication_id)


def _epoch(year: int, month: int, day: int) -> float:
    return datetime(year, month, day, tzinfo=timezone.utc).timestamp()


def _audit_records(store, generation_id: str) -> list[dict]:
    import json

    with store.connect() as connection:
        rows = connection.execute(
            """SELECT audit_type, payload_json FROM v7_generation_migration_audit
            WHERE generation_id = ? AND audit_type = 'retirement_eligibility'
            ORDER BY audit_id""",
            (generation_id,),
        ).fetchall()
    return [(row[0], json.loads(row[1])) for row in rows]


def test_eligible_generation_recorded_without_deletion(tmp_path):
    """满足全部前置条件时记录 eligible 资格，但绝不删除候选、发布集合或制品文件。"""
    from src.publication_set import PublicationSetRepository
    from src.v7_generation_migration import V7GenerationMigrator
    from src.v7_generation_retirement import V7GenerationRetirementEvaluator
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_active_documents(store)
    migrator = V7GenerationMigrator(store)
    old_artifacts = tmp_path / "artifacts-old"
    new_artifacts = tmp_path / "artifacts-new"
    _write_staging_artifacts(old_artifacts)
    _write_staging_artifacts(new_artifacts)
    _validated_generation(store, migrator, "generation-old", old_artifacts)
    _activate_publication(store, "publication-old", "generation-old", None, None)
    _validated_generation(store, migrator, "generation-new", new_artifacts)
    old_active = PublicationSetRepository(store).get_active_publication()
    _activate_publication(store, "publication-new", "generation-new", old_active.publication_id, old_active.corpus_revision)
    with store.connect() as connection:
        connection.execute(
            "UPDATE v7_generation_candidates SET created_at = '2026-01-01 00:00:00' WHERE generation_id = 'generation-old'"
        )
        connection.commit()

    record = V7GenerationRetirementEvaluator(store, PublicationSetRepository(store)).evaluate_retirement_eligibility(
        "generation-old",
        retention_seconds=30 * 86400,
        artifact_root=old_artifacts,
        now=_epoch(2026, 3, 1),
    )

    assert record["eligible"] is True
    assert all(record["conditions"].values())
    # 历史发布集合仍引用旧代际（可作为回滚目标），仅作为明细记录，不阻塞回收资格
    assert record["details"]["referencing_publications"] == ("publication-old",)
    # 只记录资格：候选行、发布集合、制品文件全部保持原样
    assert old_artifacts.joinpath("index.faiss").is_file()
    with store.connect() as connection:
        assert connection.execute(
            "SELECT 1 FROM v7_generation_candidates WHERE generation_id = 'generation-old'"
        ).fetchone() is not None
        assert connection.execute(
            "SELECT 1 FROM v7_publication_sets WHERE publication_id = 'publication-old'"
        ).fetchone() is not None
    records = _audit_records(store, "generation-old")
    assert records and records[-1][1]["eligible"] is True


def test_ineligible_conditions_recorded(tmp_path):
    """被 active publication 引用、保留期未过、有在途请求引用且未提供制品目录时，逐项记录不满足条件。"""
    from src.publication_set import PublicationSetRepository
    from src.v7_generation_migration import V7GenerationMigrator
    from src.v7_generation_retirement import V7GenerationRetirementEvaluator
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_active_documents(store)
    migrator = V7GenerationMigrator(store)
    artifacts = tmp_path / "artifacts-old"
    _write_staging_artifacts(artifacts)
    _validated_generation(store, migrator, "generation-old", artifacts)
    _activate_publication(store, "publication-old", "generation-old", None, None)
    with store.connect() as connection:
        connection.execute(
            "UPDATE v7_generation_candidates SET created_at = '2026-01-01 00:00:00' WHERE generation_id = 'generation-old'"
        )
        connection.commit()

    record = V7GenerationRetirementEvaluator(store, PublicationSetRepository(store)).evaluate_retirement_eligibility(
        "generation-old",
        retention_seconds=30 * 86400,
        active_request_generations=("generation-old",),
        now=_epoch(2026, 1, 2),
    )

    assert record["eligible"] is False
    conditions = record["conditions"]
    assert conditions["no_active_publication_reference"] is False
    assert conditions["no_active_request_reference"] is False
    assert conditions["retention_elapsed"] is False
    assert conditions["artifacts_unlocked"] is False
    assert record["details"]["referencing_publications"] == ("publication-old",)
    records = _audit_records(store, "generation-old")
    assert records and records[-1][1]["eligible"] is False


def test_locked_artifact_probe_blocks_eligibility_until_released(tmp_path):
    """Windows 文件被打开期间资格为 False，释放后重新评估恢复 True。"""
    from src.publication_set import PublicationSetRepository
    from src.v7_generation_migration import V7GenerationMigrator
    from src.v7_generation_retirement import V7GenerationRetirementEvaluator
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_active_documents(store)
    migrator = V7GenerationMigrator(store)
    artifacts = tmp_path / "artifacts-old"
    _write_staging_artifacts(artifacts)
    _validated_generation(store, migrator, "generation-old", artifacts)
    # 回拨创建时间，确保保留期条件满足，测试焦点集中在文件锁定探测上
    with store.connect() as connection:
        connection.execute(
            "UPDATE v7_generation_candidates SET created_at = '2026-01-01 00:00:00' WHERE generation_id = 'generation-old'"
        )
        connection.commit()
    evaluator = V7GenerationRetirementEvaluator(store, PublicationSetRepository(store))

    unlocked_record = evaluator.evaluate_retirement_eligibility(
        "generation-old",
        retention_seconds=0,
        artifact_root=artifacts,
        now=_epoch(2026, 3, 1),
    )
    assert unlocked_record["conditions"]["artifacts_unlocked"] is True

    handle = open(artifacts / "index.faiss", "rb")
    try:
        locked_record = evaluator.evaluate_retirement_eligibility(
            "generation-old",
            retention_seconds=0,
            artifact_root=artifacts,
            now=_epoch(2026, 3, 1),
        )
        assert locked_record["conditions"]["artifacts_unlocked"] is False
        assert locked_record["eligible"] is False
        assert locked_record["details"]["artifact_probe_failures"] == ("index.faiss",)
    finally:
        handle.close()

    released_record = evaluator.evaluate_retirement_eligibility(
        "generation-old",
        retention_seconds=0,
        artifact_root=artifacts,
        now=_epoch(2026, 3, 1),
    )
    assert released_record["eligible"] is True
