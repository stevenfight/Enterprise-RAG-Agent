# -*- coding: utf-8 -*-
"""旧 generation 回收前置条件的资格评估与审计记录；只记录资格，不做任何物理删除。"""

import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .publication_set import PublicationSetRepository
from .v7_metadata_store import V7MetadataStore


class GenerationRetirementError(RuntimeError):
    """回收资格评估的前置条件不满足。"""


def _is_file_in_use(path: Path) -> bool:
    """探测单个文件是否被任意进程持有句柄。

    Windows 使用独占打开（CreateFileW 共享模式为 0）：任何已存在的句柄
    （包括 Python 默认的共享打开）都会触发共享冲突，返回 True；
    打开失败（如文件消失、拒绝访问）一律保守地视为在用。
    POSIX 分支保留原重命名探测：被独占持有的文件无法重命名。
    """
    if os.name != "nt":
        try:
            os.rename(path, path)
        except OSError:
            return True
        return False
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateFileW.restype = ctypes.c_void_p
    handle = kernel32.CreateFileW(
        str(path),
        0x80000000,  # GENERIC_READ
        0,  # 独占共享：任何已存在句柄都会导致共享冲突
        None,
        3,  # OPEN_EXISTING
        0x80,  # FILE_ATTRIBUTE_NORMAL
        None,
    )
    if handle not in (None, ctypes.c_void_p(-1).value):
        kernel32.CloseHandle(handle)
        return False
    return True


class V7GenerationRetirementEvaluator:
    """逐项评估旧 generation 的回收资格并把结论持久化为迁移审计。

    前置条件（全部满足才记为 eligible）：
    1. 无 active publication 引用；
    2. 无活动请求引用（由调用方申报在途请求固定的 generation）；
    3. 已过保留期；
    4. 制品文件未被打开锁定（Windows 上以独占打开探测，任意进程持有句柄即视为锁定）。

    本评估器只写入 retirement_eligibility 审计记录，绝不删除候选、发布集合或制品文件。
    """

    _REQUIRED_ARTIFACTS = ("index.faiss", "bm25_index.pkl", "metadata.json", "parent_texts.json")

    def __init__(self, store: V7MetadataStore, publication_repository: PublicationSetRepository) -> None:
        self.store = store
        self.publication_repository = publication_repository

    def evaluate_retirement_eligibility(
        self,
        generation_id: str,
        *,
        retention_seconds: int,
        active_request_generations: Iterable[str] = (),
        artifact_root: Path | None = None,
        now: float | None = None,
    ) -> dict[str, Any]:
        """评估并持久化资格记录；返回值同时包含条件明细与引用信息。"""
        if retention_seconds < 0:
            raise ValueError("retention_seconds 不能为负")
        current_epoch = time.time() if now is None else float(now)
        in_flight_generations = set(active_request_generations)
        active = self.publication_repository.get_active_publication()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT created_at FROM v7_generation_candidates WHERE generation_id = ?",
                    (generation_id,),
                ).fetchone()
                if row is None:
                    raise GenerationRetirementError("generation 不存在")
                referencing_publications = tuple(
                    item[0] for item in connection.execute(
                        """SELECT publication_id FROM v7_publication_sets
                        WHERE generation_id = ? ORDER BY publication_id""",
                        (generation_id,),
                    ).fetchall()
                )
                probe_failures, unlocked = self._probe_artifacts(artifact_root)
                conditions = {
                    "no_active_publication_reference": active is None or active.generation_id != generation_id,
                    "no_active_request_reference": generation_id not in in_flight_generations,
                    "retention_elapsed": current_epoch >= self._parse_created_at(row[0]) + retention_seconds,
                    "artifacts_unlocked": unlocked,
                }
                record = {
                    "generation_id": generation_id,
                    "eligible": all(conditions.values()),
                    "conditions": conditions,
                    "details": {
                        "referencing_publications": referencing_publications,
                        "artifact_probe_failures": probe_failures,
                        "artifact_root": str(artifact_root) if artifact_root is not None else None,
                        "retention_seconds": retention_seconds,
                    },
                    "evaluated_at_epoch": current_epoch,
                }
                connection.execute(
                    """INSERT INTO v7_generation_migration_audit(generation_id, audit_type, payload_json)
                    VALUES (?, 'retirement_eligibility', ?)""",
                    (generation_id, json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return record

    @staticmethod
    def _parse_created_at(value: str) -> float:
        """SQLite CURRENT_TIMESTAMP 为 UTC 时间，按 UTC 解析为 epoch 秒。"""
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except (TypeError, ValueError) as error:
            raise GenerationRetirementError("generation created_at 无法解析") from error
        return parsed.timestamp()

    @classmethod
    def _probe_artifacts(cls, artifact_root: Path | None) -> tuple[tuple[str, ...], bool]:
        """探测制品文件是否被打开锁定；未提供制品目录时视为条件不满足。"""
        if artifact_root is None:
            return ("artifact_root_not_provided",), False
        failures = []
        for name in cls._REQUIRED_ARTIFACTS:
            path = Path(artifact_root) / name
            if not path.is_file():
                failures.append(name)
                continue
            if _is_file_in_use(path):
                failures.append(name)
        return tuple(failures), not failures


class V7GenerationRetirementExecutor:
    """M1.10 回收实际执行编排：仅回收资格评估为 eligible 的旧 generation 制品。

    - 合格：物理删除制品目录、候选状态置 retired（保留候选行与发布集合行以维持审计链）、
      登记 retirement_executed 审计；
    - 不合格（active 引用/在途请求/保留期未过/制品锁定任一不满足）：绝不删除或修改任何内容，
      登记 retirement_skipped 审计并附未满足条件明细；
    - 回收绝不触碰 active publication 与 active 代际（active 引用条件在评估阶段已强制拦截）。
    """

    def __init__(self, store: V7MetadataStore, publication_repository: PublicationSetRepository) -> None:
        self.store = store
        self.publication_repository = publication_repository
        self.evaluator = V7GenerationRetirementEvaluator(store, publication_repository)

    def retire_generation(
        self,
        generation_id: str,
        *,
        retention_seconds: int,
        active_request_generations: Iterable[str] = (),
        artifact_root: Path | None = None,
        now: float | None = None,
    ) -> dict[str, Any]:
        """评估资格并按结论执行回收；返回 executed 结果与资格明细。"""
        record = self.evaluator.evaluate_retirement_eligibility(
            generation_id,
            retention_seconds=retention_seconds,
            active_request_generations=active_request_generations,
            artifact_root=artifact_root,
            now=now,
        )
        if not record["eligible"]:
            # 不合格：只记 skipped 审计，任何文件与状态都不动
            unsatisfied = {key: value for key, value in record["conditions"].items() if not value}
            self._write_audit(generation_id, "retirement_skipped", {
                "generation_id": generation_id,
                "unsatisfied_conditions": unsatisfied,
                "details": record["details"],
                "evaluated_at_epoch": record["evaluated_at_epoch"],
            })
            return {
                "generation_id": generation_id,
                "executed": False,
                "audit_type": "retirement_skipped",
                "eligibility": record,
            }

        # 合格：先列出待删制品（按必需制品顺序），再物理删除制品目录
        artifact_root_path = Path(artifact_root) if artifact_root is not None else None
        removed: tuple[str, ...] = ()
        if artifact_root_path is not None:
            removed = tuple(
                name for name in V7GenerationRetirementEvaluator._REQUIRED_ARTIFACTS
                if (artifact_root_path / name).exists()
            )
            shutil.rmtree(artifact_root_path)

        # 候选状态置 retired 并登记执行审计（同一事务，保留候选行与发布集合行）
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "UPDATE v7_generation_candidates SET status = 'retired' WHERE generation_id = ?",
                    (generation_id,),
                )
                self._write_audit_within(generation_id, "retirement_executed", {
                    "generation_id": generation_id,
                    "removed_artifacts": removed,
                    "artifact_root": str(artifact_root) if artifact_root is not None else None,
                    "eligibility": record,
                    "executed_at_epoch": record["evaluated_at_epoch"],
                }, connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return {
            "generation_id": generation_id,
            "executed": True,
            "audit_type": "retirement_executed",
            "eligibility": record,
            "removed_artifacts": removed,
        }

    def _write_audit(self, generation_id: str, audit_type: str, payload: dict[str, Any]) -> None:
        """独立事务写入回收审计记录。"""
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._write_audit_within(generation_id, audit_type, payload, connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _write_audit_within(
        generation_id: str, audit_type: str, payload: dict[str, Any], connection
    ) -> None:
        """在既有事务内写入回收审计记录（由调用方负责提交/回滚）。"""
        connection.execute(
            """INSERT INTO v7_generation_migration_audit(generation_id, audit_type, payload_json)
            VALUES (?, ?, ?)""",
            (generation_id, audit_type, json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))),
        )
