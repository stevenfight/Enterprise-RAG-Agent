# -*- coding: utf-8 -*-
"""M1.10.a 旧 generation 回收批量调度入口测试。"""

import hashlib
from datetime import datetime, timezone


def _seed_validated_generation(store, generation_id: str) -> None:
    store.initialize()
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO v7_generation_candidates(
                generation_id, corpus_revision, status, payload_json, created_at
            ) VALUES (?, 'revision-1', 'validated', '{}', '2026-01-01 00:00:00')""",
            (generation_id,),
        )
        connection.commit()


def _write_artifacts(artifact_root) -> None:
    artifact_root.mkdir()
    for filename, content in (
        ("index.faiss", b"index"),
        ("bm25_index.pkl", b"bm25"),
        ("metadata.json", b"[]"),
        ("parent_texts.json", b"{}"),
    ):
        (artifact_root / filename).write_bytes(content)


def test_batch_worker_only_processes_validated_generations_and_honors_batch_limit(tmp_path):
    """批处理只处理 validated generation，且单轮不超过 batch_size。"""
    from src.publication_set import PublicationSetRepository
    from src.v7_generation_retirement import V7GenerationRetirementExecutor
    from src.v7_generation_retirement_scheduler import V7GenerationRetirementBatchWorker
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_validated_generation(store, "generation-first")
    _seed_validated_generation(store, "generation-second")
    with store.connect() as connection:
        connection.execute(
            "UPDATE v7_generation_candidates SET status = 'retired' WHERE generation_id = 'generation-second'"
        )
        connection.commit()
    artifacts = tmp_path / "generation-first"
    _write_artifacts(artifacts)
    worker = V7GenerationRetirementBatchWorker(
        V7GenerationRetirementExecutor(store, PublicationSetRepository(store)),
        retention_seconds=0,
        artifact_root_resolver=lambda generation_id: artifacts if generation_id == "generation-first" else None,
        batch_size=1,
    )

    result = worker.run_once(now=datetime(2026, 3, 1, tzinfo=timezone.utc).timestamp())

    assert result.scanned_generation_ids == ("generation-first",)
    assert result.executed_generation_ids == ("generation-first",)
    assert result.skipped_generation_ids == ()
    assert not artifacts.exists()
    with store.connect() as connection:
        statuses = dict(connection.execute("SELECT generation_id, status FROM v7_generation_candidates"))
    assert statuses == {"generation-first": "retired", "generation-second": "retired"}


def test_batch_worker_keeps_in_flight_generation_and_reports_skip(tmp_path):
    """在途 generation 被传递给执行器，必须保持制品和 validated 状态。"""
    from src.publication_set import PublicationSetRepository
    from src.v7_generation_retirement import V7GenerationRetirementExecutor
    from src.v7_generation_retirement_scheduler import V7GenerationRetirementBatchWorker
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_validated_generation(store, "generation-in-flight")
    artifacts = tmp_path / "generation-in-flight"
    _write_artifacts(artifacts)
    worker = V7GenerationRetirementBatchWorker(
        V7GenerationRetirementExecutor(store, PublicationSetRepository(store)),
        retention_seconds=0,
        artifact_root_resolver=lambda _generation_id: artifacts,
        active_request_generations_supplier=lambda: ("generation-in-flight",),
    )

    result = worker.run_once(now=datetime(2026, 3, 1, tzinfo=timezone.utc).timestamp())

    assert result.scanned_generation_ids == ("generation-in-flight",)
    assert result.executed_generation_ids == ()
    assert result.skipped_generation_ids == ("generation-in-flight",)
    assert artifacts.exists()
    with store.connect() as connection:
        assert connection.execute(
            "SELECT status FROM v7_generation_candidates WHERE generation_id = 'generation-in-flight'"
        ).fetchone()[0] == "validated"
