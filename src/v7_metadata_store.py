# -*- coding: utf-8 -*-
"""v7 共享元数据 SQLite 基础设施。

该模块只提供版本化数据库的连接与迁移边界，不自动接入 legacy API、PDF、
向量索引或 AgentMemory。
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence


class SchemaVersionError(RuntimeError):
    """数据库 schema 高于当前代码可安全处理的版本。"""


Migration = tuple[int, Sequence[str]]


class V7MetadataStore:
    """为 B/M/C/D 共用的 SQLite 连接和迁移器。"""

    DEFAULT_BUSY_TIMEOUT_MS = 5_000
    DEFAULT_MIGRATIONS: tuple[Migration, ...] = (
        (
            1,
            (
                """
                CREATE TABLE v7_store_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """,
            ),
        ),
        (
            2,
            (
                """
                CREATE TABLE v7_blobs (
                    sha256 TEXT PRIMARY KEY,
                    size_bytes INTEGER NOT NULL CHECK (size_bytes > 0),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE v7_logical_documents (
                    logical_document_id TEXT PRIMARY KEY,
                    logical_document_key TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE v7_document_versions (
                    document_version_id TEXT PRIMARY KEY,
                    logical_document_id TEXT NOT NULL,
                    blob_sha256 TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    physical_page_count INTEGER NOT NULL CHECK (physical_page_count > 0),
                    index_status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(logical_document_id, blob_sha256),
                    FOREIGN KEY(logical_document_id)
                        REFERENCES v7_logical_documents(logical_document_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY(blob_sha256)
                        REFERENCES v7_blobs(sha256)
                        ON DELETE RESTRICT
                )
                """,
            ),
        ),
        (
            3,
            (
                """
                CREATE TABLE v7_document_asset_manifests (
                    manifest_id TEXT PRIMARY KEY,
                    document_version_id TEXT NOT NULL UNIQUE,
                    source_sha256 TEXT NOT NULL,
                    physical_page_count INTEGER NOT NULL CHECK (physical_page_count > 0),
                    asset_status TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(document_version_id)
                        REFERENCES v7_document_versions(document_version_id)
                        ON DELETE RESTRICT
                )
                """,
                """
                CREATE TABLE v7_page_artifacts (
                    page_artifact_id TEXT PRIMARY KEY,
                    manifest_id TEXT NOT NULL,
                    physical_page_number INTEGER NOT NULL CHECK (physical_page_number > 0),
                    artifact_kind TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    artifact_status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(manifest_id)
                        REFERENCES v7_document_asset_manifests(manifest_id)
                        ON DELETE RESTRICT
                )
                """,
                """
                CREATE TABLE v7_visual_regions (
                    visual_region_id TEXT PRIMARY KEY,
                    page_artifact_id TEXT NOT NULL,
                    x0 REAL NOT NULL CHECK (x0 >= 0 AND x0 <= 1),
                    y0 REAL NOT NULL CHECK (y0 >= 0 AND y0 <= 1),
                    x1 REAL NOT NULL CHECK (x1 >= 0 AND x1 <= 1),
                    y1 REAL NOT NULL CHECK (y1 >= 0 AND y1 <= 1),
                    region_status TEXT NOT NULL,
                    FOREIGN KEY(page_artifact_id)
                        REFERENCES v7_page_artifacts(page_artifact_id)
                        ON DELETE RESTRICT
                )
                """,
                """
                CREATE TABLE v7_table_artifacts (
                    table_artifact_id TEXT PRIMARY KEY,
                    manifest_id TEXT NOT NULL,
                    visual_region_id TEXT,
                    source_format TEXT NOT NULL,
                    artifact_status TEXT NOT NULL,
                    FOREIGN KEY(manifest_id)
                        REFERENCES v7_document_asset_manifests(manifest_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY(visual_region_id)
                        REFERENCES v7_visual_regions(visual_region_id)
                        ON DELETE RESTRICT
                )
                """,
                """
                CREATE TABLE v7_chart_artifacts (
                    chart_artifact_id TEXT PRIMARY KEY,
                    manifest_id TEXT NOT NULL,
                    visual_region_id TEXT,
                    artifact_status TEXT NOT NULL,
                    FOREIGN KEY(manifest_id)
                        REFERENCES v7_document_asset_manifests(manifest_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY(visual_region_id)
                        REFERENCES v7_visual_regions(visual_region_id)
                        ON DELETE RESTRICT
                )
                """,
                """
                CREATE TABLE v7_visual_evidence (
                    visual_evidence_id TEXT PRIMARY KEY,
                    manifest_id TEXT NOT NULL,
                    page_artifact_id TEXT,
                    visual_region_id TEXT,
                    table_artifact_id TEXT,
                    chart_artifact_id TEXT,
                    evidence_status TEXT NOT NULL,
                    FOREIGN KEY(manifest_id)
                        REFERENCES v7_document_asset_manifests(manifest_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY(page_artifact_id)
                        REFERENCES v7_page_artifacts(page_artifact_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY(visual_region_id)
                        REFERENCES v7_visual_regions(visual_region_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY(table_artifact_id)
                        REFERENCES v7_table_artifacts(table_artifact_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY(chart_artifact_id)
                        REFERENCES v7_chart_artifacts(chart_artifact_id)
                        ON DELETE RESTRICT
                )
                """,
            ),
        ),
        (
            4,
            (
                """
                ALTER TABLE v7_page_artifacts
                ADD COLUMN image_path TEXT
                """,
                """
                ALTER TABLE v7_page_artifacts
                ADD COLUMN thumbnail_path TEXT
                """,
                """
                CREATE TABLE v7_manifest_validation_issues (
                    manifest_id TEXT NOT NULL,
                    physical_page_number INTEGER NOT NULL
                        CHECK (physical_page_number > 0),
                    issue_code TEXT NOT NULL,
                    detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(manifest_id, physical_page_number, issue_code),
                    FOREIGN KEY(manifest_id)
                        REFERENCES v7_document_asset_manifests(manifest_id)
                        ON DELETE RESTRICT
                )
                """,
            ),
        ),
        (
            5,
            (
                """
                CREATE TABLE v7_parse_batches (
                    manifest_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    physical_page_start INTEGER NOT NULL
                        CHECK (physical_page_start > 0),
                    physical_page_end INTEGER NOT NULL
                        CHECK (physical_page_end >= physical_page_start),
                    parser_name TEXT NOT NULL,
                    parser_version TEXT NOT NULL,
                    batch_status TEXT NOT NULL,
                    error_code TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(manifest_id, batch_id),
                    FOREIGN KEY(manifest_id)
                        REFERENCES v7_document_asset_manifests(manifest_id)
                        ON DELETE RESTRICT
                )
                """,
            ),
        ),
        (
            6,
            (
                """
                CREATE TABLE v7_financial_facts (
                    fact_id TEXT PRIMARY KEY,
                    metric_key TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    raw_value TEXT NOT NULL,
                    raw_unit TEXT NOT NULL,
                    normalized_value TEXT NOT NULL,
                    normalized_unit TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    period TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    source_file TEXT NOT NULL,
                    physical_pages_json TEXT NOT NULL,
                    excerpt TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ),
        ),
        (
            7,
            (
                """CREATE TABLE v7_financial_periods (period_id TEXT PRIMARY KEY, period_start TEXT NOT NULL, period_end TEXT NOT NULL, fiscal_year INTEGER NOT NULL, period_type TEXT NOT NULL)""",
                """CREATE TABLE v7_financial_scopes (scope_id TEXT PRIMARY KEY, consolidation TEXT NOT NULL, accounting_standard TEXT NOT NULL, audited INTEGER NOT NULL CHECK (audited IN (0, 1)))""",
                """CREATE TABLE v7_financial_fact_sources (source_id TEXT PRIMARY KEY, logical_document_id TEXT NOT NULL, document_version_id TEXT NOT NULL, source_file TEXT NOT NULL, physical_pages_json TEXT NOT NULL, excerpt TEXT NOT NULL, source_type TEXT NOT NULL, authority_level TEXT NOT NULL, FOREIGN KEY(logical_document_id) REFERENCES v7_logical_documents(logical_document_id) ON DELETE RESTRICT, FOREIGN KEY(document_version_id) REFERENCES v7_document_versions(document_version_id) ON DELETE RESTRICT)""",
            ),
        ),
        (
            8,
            (
                """CREATE TABLE v7_fact_calculations (calculation_id TEXT PRIMARY KEY, operation TEXT NOT NULL, formula_version TEXT NOT NULL, input_fact_ids_json TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
            ),
        ),
        (
            9,
            (
                """CREATE TABLE v7_financial_fact_conflicts (conflict_id TEXT PRIMARY KEY, status TEXT NOT NULL, conflict_type TEXT NOT NULL, fact_ids_json TEXT NOT NULL, relative_difference TEXT NOT NULL, preferred_fact_id TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
            ),
        ),
        (
            10,
            (
                """CREATE TABLE v7_claims (claim_id TEXT PRIMARY KEY, claim_text TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
                """CREATE TABLE v7_evidence_bundles (bundle_id TEXT PRIMARY KEY, claim_id TEXT NOT NULL, fact_ids_json TEXT NOT NULL, calculation_ids_json TEXT NOT NULL, conflict_ids_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(claim_id) REFERENCES v7_claims(claim_id) ON DELETE RESTRICT)""",
            ),
        ),
        (
            11,
            (
                """CREATE TABLE v7_execution_runs (run_id TEXT PRIMARY KEY, status TEXT NOT NULL, revision INTEGER NOT NULL, cancellation_token TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
                """CREATE TABLE v7_step_attempts (attempt_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, step_id TEXT NOT NULL, attempt_token TEXT NOT NULL UNIQUE, owner_token TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, completed_at TEXT, FOREIGN KEY(run_id) REFERENCES v7_execution_runs(run_id) ON DELETE RESTRICT)""",
                """CREATE TABLE v7_leases (run_id TEXT NOT NULL, step_id TEXT NOT NULL, attempt_id TEXT NOT NULL UNIQUE, owner_token TEXT NOT NULL, expires_at REAL NOT NULL, PRIMARY KEY(run_id, step_id), FOREIGN KEY(run_id) REFERENCES v7_execution_runs(run_id) ON DELETE RESTRICT, FOREIGN KEY(attempt_id) REFERENCES v7_step_attempts(attempt_id) ON DELETE RESTRICT)""",
                """CREATE TABLE v7_execution_checkpoints (checkpoint_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, step_id TEXT NOT NULL, attempt_id TEXT NOT NULL, schema_version INTEGER NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(run_id) REFERENCES v7_execution_runs(run_id) ON DELETE RESTRICT, FOREIGN KEY(attempt_id) REFERENCES v7_step_attempts(attempt_id) ON DELETE RESTRICT)""",
                """CREATE TABLE v7_execution_invocations (idempotency_key TEXT PRIMARY KEY, run_id TEXT NOT NULL, step_id TEXT NOT NULL, attempt_id TEXT NOT NULL, status TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(run_id) REFERENCES v7_execution_runs(run_id) ON DELETE RESTRICT, FOREIGN KEY(attempt_id) REFERENCES v7_step_attempts(attempt_id) ON DELETE RESTRICT)""",
                """CREATE TABLE v7_task_events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, revision INTEGER NOT NULL, event_type TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(run_id) REFERENCES v7_execution_runs(run_id) ON DELETE RESTRICT)""",
                """CREATE TABLE v7_execution_commands (command_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, target_status TEXT NOT NULL, expected_revision INTEGER NOT NULL, result_revision INTEGER NOT NULL, result_status TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(run_id) REFERENCES v7_execution_runs(run_id) ON DELETE RESTRICT)""",
            ),
        ),
        (
            23,
            (
                # C2.7：研究任务路由决策只追加表，记录选定 single/multi 路径、失败分类与显式重试链，禁止覆盖历史
                """
                CREATE TABLE v7_task_route_decisions (
                    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    decision_type TEXT NOT NULL CHECK (decision_type IN ('selected', 'failure', 'retry')),
                    selected_path TEXT CHECK (selected_path IS NULL OR selected_path IN ('single', 'multi')),
                    detail_json TEXT NOT NULL DEFAULT '{}',
                    actor TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """CREATE INDEX idx_v7_route_decisions_task ON v7_task_route_decisions(task_id, decision_id)""",
            ),
        ),
    )

    def __init__(
        self,
        database_path: Path,
        migrations: Sequence[Migration] | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self._migrations = tuple(migrations or self.DEFAULT_MIGRATIONS)
        self.last_backup_path: Path | None = None
        versions = [version for version, _ in self._migrations]
        if versions != sorted(versions) or len(versions) != len(set(versions)):
            raise ValueError("v7 schema migration 版本必须严格递增且唯一")

    @property
    def supported_schema_version(self) -> int:
        """返回当前代码可写入的最高 schema 版本。"""
        return self._migrations[-1][0] if self._migrations else 0

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """创建配置一致且退出时必定关闭的 SQLite 连接。"""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self.database_path,
            timeout=self.DEFAULT_BUSY_TIMEOUT_MS / 1_000,
        )
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {self.DEFAULT_BUSY_TIMEOUT_MS}")
            connection.execute("PRAGMA journal_mode = WAL")
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        """幂等初始化并在真实迁移前创建数据库备份。"""
        existed_before_open = self.database_path.exists()
        if existed_before_open:
            existing_version = self._read_existing_schema_version()
            if (
                existing_version is not None
                and existing_version > self.supported_schema_version
            ):
                raise SchemaVersionError(
                    "v7 数据库 schema 版本 "
                    f"{existing_version} 高于当前代码支持的 "
                    f"{self.supported_schema_version}，拒绝写入"
                )
        with self.connect() as connection:
            has_migration_table = self._has_schema_migrations_table(connection)
            backup_created = False
            if existed_before_open and not has_migration_table:
                self._backup_database(connection)
                backup_created = True
            self._ensure_schema_migrations_table(connection)
            current_version = self._read_schema_version(connection)
            if current_version > self.supported_schema_version:
                raise SchemaVersionError(
                    "v7 数据库 schema 版本 "
                    f"{current_version} 高于当前代码支持的 "
                    f"{self.supported_schema_version}，拒绝写入"
                )

            pending_migrations = [
                migration for migration in self._migrations
                if migration[0] > current_version
            ]
            if not pending_migrations:
                return

            if existed_before_open and not backup_created:
                self._backup_database(connection)
            try:
                connection.execute("BEGIN IMMEDIATE")
                for version, statements in pending_migrations:
                    for statement in statements:
                        connection.execute(statement)
                    connection.execute(
                        "INSERT INTO schema_migrations(version) VALUES (?)",
                        (version,),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def schema_version(self) -> int:
        """读取当前 schema 版本；调用方应先初始化数据库。"""
        with self.connect() as connection:
            return self._read_schema_version(connection)

    def set_metadata(self, key: str, value: str) -> None:
        """写入基础元数据，供后续仓储复用迁移后的事务边界。"""
        self.initialize()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO v7_store_metadata(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
            connection.commit()

    def get_metadata(self, key: str) -> str | None:
        """读取基础元数据；缺失时返回 None。"""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT value FROM v7_store_metadata WHERE key = ?",
                (key,),
            ).fetchone()
        return row[0] if row else None

    @staticmethod
    def _ensure_schema_migrations_table(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()

    @staticmethod
    def _has_schema_migrations_table(connection: sqlite3.Connection) -> bool:
        """仅检查迁移表存在性，避免在备份前写入已有数据库。"""
        row = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'schema_migrations'
            """
        ).fetchone()
        return row is not None

    @staticmethod
    def _read_schema_version(connection: sqlite3.Connection) -> int:
        row = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def _read_existing_schema_version(self) -> int | None:
        """在配置 WAL 前探测已有数据库，防止高版本拒绝路径产生写入。"""
        connection = sqlite3.connect(self.database_path)
        try:
            if not self._has_schema_migrations_table(connection):
                return None
            return self._read_schema_version(connection)
        finally:
            connection.close()

    def _backup_database(self, source_connection: sqlite3.Connection) -> None:
        """在迁移前生成一致性 SQLite 备份，不通过文件复制读取 WAL。"""
        backup_path = self.database_path.with_name(
            self.database_path.name + ".pre_migration.bak"
        )
        backup_connection = sqlite3.connect(backup_path)
        try:
            source_connection.backup(backup_connection)
        finally:
            backup_connection.close()
        self.last_backup_path = backup_path
