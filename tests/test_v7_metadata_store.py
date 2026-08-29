"""V7MetadataStore 迁移与写入边界的确定性测试。"""

import sqlite3
from pathlib import Path

import pytest


def test_migrations_are_idempotent_and_preserve_existing_metadata(tmp_path: Path):
    from src.v7_metadata_store import V7MetadataStore

    database_path = tmp_path / "v7_metadata.sqlite3"
    store = V7MetadataStore(database_path)
    store.initialize()
    store.set_metadata("baseline", "kept")

    store.initialize()

    assert store.schema_version() == store.supported_schema_version
    assert store.get_metadata("baseline") == "kept"
    with store.connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] > 0


def test_failed_migration_rolls_back_and_keeps_startup_backup(tmp_path: Path):
    from src.v7_metadata_store import V7MetadataStore

    database_path = tmp_path / "v7_metadata.sqlite3"
    database_path.write_bytes(b"")
    store = V7MetadataStore(
        database_path,
        migrations=[
            (1, ("CREATE TABLE should_not_survive (id INTEGER)", "INVALID SQL")),
        ],
    )

    with pytest.raises(sqlite3.DatabaseError):
        store.initialize()

    assert store.last_backup_path is not None
    assert store.last_backup_path.exists()
    with sqlite3.connect(store.last_backup_path) as backup_connection:
        assert backup_connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone() is None
    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='should_not_survive'"
        ).fetchone() is None


def test_newer_schema_refuses_writes_without_downgrade(tmp_path: Path):
    from src.v7_metadata_store import SchemaVersionError, V7MetadataStore

    database_path = tmp_path / "v7_metadata.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO schema_migrations(version) VALUES (99)")

    store = V7MetadataStore(database_path)

    with pytest.raises(SchemaVersionError, match="99"):
        store.initialize()

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT version FROM schema_migrations").fetchone()[0] == 99
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"


def test_store_connection_context_closes_database_file_on_windows(tmp_path: Path):
    from src.v7_metadata_store import V7MetadataStore

    database_path = tmp_path / "v7_metadata.sqlite3"
    store = V7MetadataStore(database_path)
    store.initialize()

    with store.connect() as connection:
        connection.execute("SELECT 1").fetchone()

    database_path.unlink()
    assert not database_path.exists()


def test_store_migrates_v3_database_to_page_file_integrity_schema(tmp_path: Path):
    from src.v7_metadata_store import V7MetadataStore

    database_path = tmp_path / "v7_metadata.sqlite3"
    V7MetadataStore(
        database_path,
        migrations=V7MetadataStore.DEFAULT_MIGRATIONS[:3],
    ).initialize()

    store = V7MetadataStore(database_path)
    store.initialize()

    with store.connect() as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(v7_page_artifacts)").fetchall()
        }
        issue_table = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'v7_manifest_validation_issues'
            """
        ).fetchone()
    assert {"image_path", "thumbnail_path"}.issubset(columns)
    assert issue_table is not None
    assert store.schema_version() == store.supported_schema_version
