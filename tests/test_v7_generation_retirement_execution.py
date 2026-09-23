# -*- coding: utf-8 -*-
"""M1.10 旧 generation 回收实际执行编排测试。

只回收资格评估为 eligible 的旧 generation 制品：
- 合格：物理删除制品目录、候选状态置 retired、登记 retirement_executed 审计；
- 不合格（active 引用/保留期未过/在途请求/制品锁定）：绝不删除任何内容，
  登记 retirement_skipped 审计；
- 回收绝不影响 active publication（不会把 active 替换或移除）。
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


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


def _audit_records(store, generation_id: str, audit_type: str | None = None) -> list[dict]:
    with store.connect() as connection:
        if audit_type is None:
            rows = connection.execute(
                """SELECT audit_type, payload_json FROM v7_generation_migration_audit
                WHERE generation_id = ? ORDER BY audit_id""",
                (generation_id,),
            ).fetchall()
        else:
            rows = connection.execute(
                """SELECT audit_type, payload_json FROM v7_generation_migration_audit
                WHERE generation_id = ? AND audit_type = ? ORDER BY audit_id""",
                (generation_id, audit_type),
            ).fetchall()
    return [(row[0], json.loads(row[1])) for row in rows]


def _candidate_status(store, generation_id: str) -> str:
    with store.connect() as connection:
        row = connection.execute(
            "SELECT status FROM v7_generation_candidates WHERE generation_id = ?",
            (generation_id,),
        ).fetchone()
    return row[0]


def _two_generation_scenario(tmp_path):
    """播种 old/new 两个已验证代际：old 先激活后被 new 取代（old 失去 active 引用）。"""
    from src.publication_set import PublicationSetRepository
    from src.v7_generation_migration import V7GenerationMigrator
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
    # 回拨旧代际创建时间，使保留期条件可满足
    with store.connect() as connection:
        connection.execute(
            "UPDATE v7_generation_candidates SET created_at = '2026-01-01 00:00:00' WHERE generation_id = 'generation-old'"
        )
        connection.commit()
    return store, old_artifacts


def test_eligible_generation_artifacts_are_removed_and_status_retired(tmp_path):
    """合格旧代际：制品被物理删除、候选置 retired、登记 retirement_executed 审计，active 不受影响。"""
    from src.publication_set import PublicationSetRepository
    from src.v7_generation_retirement import V7GenerationRetirementExecutor
    from src.v7_metadata_store import V7MetadataStore

    store, old_artifacts = _two_generation_scenario(tmp_path)

    result = V7GenerationRetirementExecutor(store, PublicationSetRepository(store)).retire_generation(
        "generation-old",
        retention_seconds=30 * 86400,
        artifact_root=old_artifacts,
        now=_epoch(2026, 3, 1),
    )

    assert result["executed"] is True
    assert result["generation_id"] == "generation-old"
    # 制品文件全部被物理删除（目录被移除）
    assert not old_artifacts.exists()
    # 候选状态置为 retired（保留行以维持审计链，但不再可复用）
    assert _candidate_status(store, "generation-old") == "retired"
    # 历史发布集合行保留（审计与回滚溯源依据）
    with store.connect() as connection:
        assert connection.execute(
            "SELECT 1 FROM v7_publication_sets WHERE publication_id = 'publication-old'"
        ).fetchone() is not None
    # active publication 始终是 new，回收绝不替换或移除 active
    active = PublicationSetRepository(store).get_active_publication()
    assert active.publication_id == "publication-new"
    assert active.generation_id == "generation-new"
    # 审计：先资格评估（eligible=True），后执行记录
    executed = _audit_records(store, "generation-old", "retirement_executed")
    assert len(executed) == 1
    payload = executed[0][1]
    # payload 从 JSON 读回，列表顺序与必需制品顺序一致
    assert payload["removed_artifacts"] == ["index.faiss", "bm25_index.pkl", "metadata.json", "parent_texts.json"]
    eligibility = _audit_records(store, "generation-old", "retirement_eligibility")
    assert eligibility and eligibility[-1][1]["eligible"] is True


def test_ineligible_generation_is_never_removed(tmp_path):
    """不合格旧代际（本例：仍被 active 引用）：绝不删除制品，登记 retirement_skipped 审计。"""
    from src.publication_set import PublicationSetRepository
    from src.v7_generation_migration import V7GenerationMigrator
    from src.v7_generation_retirement import V7GenerationRetirementExecutor
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

    result = V7GenerationRetirementExecutor(store, PublicationSetRepository(store)).retire_generation(
        "generation-old",
        retention_seconds=30 * 86400,
        artifact_root=artifacts,
        now=_epoch(2026, 1, 2),
    )

    assert result["executed"] is False
    # 制品全部保持原样
    for name in ("index.faiss", "bm25_index.pkl", "metadata.json", "parent_texts.json"):
        assert (artifacts / name).is_file()
    # 候选状态未被修改
    assert _candidate_status(store, "generation-old") == "validated"
    # 审计记录 skipped，且包含未满足条件明细
    skipped = _audit_records(store, "generation-old", "retirement_skipped")
    assert len(skipped) == 1
    assert skipped[0][1]["unsatisfied_conditions"]["no_active_publication_reference"] is False


def test_locked_artifact_blocks_execution_until_released(tmp_path):
    """Windows 制品被打开锁定期间回收被跳过且不删除任何文件，释放后重新执行回收成功。"""
    from src.publication_set import PublicationSetRepository
    from src.v7_generation_retirement import V7GenerationRetirementExecutor
    from src.v7_metadata_store import V7MetadataStore

    store, old_artifacts = _two_generation_scenario(tmp_path)
    executor = V7GenerationRetirementExecutor(store, PublicationSetRepository(store))

    handle = open(old_artifacts / "index.faiss", "rb")
    try:
        locked_result = executor.retire_generation(
            "generation-old",
            retention_seconds=30 * 86400,
            artifact_root=old_artifacts,
            now=_epoch(2026, 3, 1),
        )
        assert locked_result["executed"] is False
        # 锁定期间任何文件都不被删除
        assert (old_artifacts / "index.faiss").is_file()
        assert (old_artifacts / "bm25_index.pkl").is_file()
        assert _candidate_status(store, "generation-old") == "validated"
        skipped = _audit_records(store, "generation-old", "retirement_skipped")
        assert skipped and skipped[-1][1]["unsatisfied_conditions"]["artifacts_unlocked"] is False
    finally:
        handle.close()

    released_result = executor.retire_generation(
        "generation-old",
        retention_seconds=30 * 86400,
        artifact_root=old_artifacts,
        now=_epoch(2026, 3, 1),
    )
    assert released_result["executed"] is True
    assert not old_artifacts.exists()
    assert _candidate_status(store, "generation-old") == "retired"
