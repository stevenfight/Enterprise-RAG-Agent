# -*- coding: utf-8 -*-
"""旧 generation 回收的受控批量执行与显式启停调度入口。"""

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .v7_generation_retirement import V7GenerationRetirementExecutor


@dataclass(frozen=True)
class GenerationRetirementBatchRunResult:
    """单轮批量回收的可审计汇总；明细仍由逐 generation 审计记录保存。"""

    scanned_generation_ids: tuple[str, ...]
    executed_generation_ids: tuple[str, ...]
    skipped_generation_ids: tuple[str, ...]


class V7GenerationRetirementBatchWorker:
    """仅对 validated generation 发起受控回收，实际资格仍由执行器逐项确认。"""

    def __init__(
        self,
        executor: V7GenerationRetirementExecutor,
        *,
        retention_seconds: int,
        artifact_root_resolver: Callable[[str], Path | None],
        active_request_generations_supplier: Callable[[], Iterable[str]] = lambda: (),
        batch_size: int = 20,
    ) -> None:
        if retention_seconds < 0:
            raise ValueError("retention_seconds 不能为负")
        if batch_size <= 0:
            raise ValueError("batch_size 必须大于 0")
        self.executor = executor
        self.retention_seconds = retention_seconds
        self.artifact_root_resolver = artifact_root_resolver
        self.active_request_generations_supplier = active_request_generations_supplier
        self.batch_size = batch_size

    def run_once(self, *, now: float | None = None) -> GenerationRetirementBatchRunResult:
        """处理一批 validated generation；active 和在途引用仍由执行器拦截并审计。"""
        generation_ids = self._list_validated_generation_ids()
        active_request_generations = tuple(self.active_request_generations_supplier())
        executed = []
        skipped = []
        for generation_id in generation_ids:
            result = self.executor.retire_generation(
                generation_id,
                retention_seconds=self.retention_seconds,
                active_request_generations=active_request_generations,
                artifact_root=self.artifact_root_resolver(generation_id),
                now=now,
            )
            if result["executed"]:
                executed.append(generation_id)
            else:
                skipped.append(generation_id)
        return GenerationRetirementBatchRunResult(
            scanned_generation_ids=generation_ids,
            executed_generation_ids=tuple(executed),
            skipped_generation_ids=tuple(skipped),
        )

    def _list_validated_generation_ids(self) -> tuple[str, ...]:
        """按创建时间与 generation ID 稳定排序，避免单轮选择漂移。"""
        self.executor.store.initialize()
        with self.executor.store.connect() as connection:
            rows = connection.execute(
                """SELECT generation_id FROM v7_generation_candidates
                WHERE status = 'validated'
                ORDER BY created_at ASC, generation_id ASC
                LIMIT ?""",
                (self.batch_size,),
            ).fetchall()
        return tuple(row[0] for row in rows)


class V7GenerationRetirementScheduler:
    """显式启动、停止旧 generation 回收批处理，避免应用启动即执行物理删除。"""

    def __init__(self, worker: V7GenerationRetirementBatchWorker, interval_seconds: float = 3600.0) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds 必须大于 0")
        self.worker = worker
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        with self._lock:
            if self.is_running:
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="v7-generation-retirement-scheduler",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float | None = None) -> bool:
        with self._lock:
            thread = self._thread
            if thread is None:
                return True
            self._stop_event.set()
        thread.join(timeout)
        if thread.is_alive():
            return False
        with self._lock:
            if self._thread is thread:
                self._thread = None
        return True

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self.worker.run_once()
            self._stop_event.wait(self.interval_seconds)
