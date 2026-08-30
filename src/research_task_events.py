"""C2.4 研究任务持久事件流适配。"""

from __future__ import annotations

from dataclasses import dataclass

from src.durable_execution import DurableExecutionStore, EventRecord
from src.research_task_adapter import ResearchTaskAdapter


@dataclass(frozen=True)
class ResearchTaskEventPage:
    """研究任务事件读取结果。"""

    events: tuple[EventRecord, ...]
    oldest_event_id: int | None
    next_event_id: int | None
    resync_required: bool


class ResearchTaskEventStream:
    """把 task_id 映射到 C0 的保留期事件窗口。"""

    def __init__(self, execution_store: DurableExecutionStore) -> None:
        self.execution_store = execution_store

    def read(
        self,
        task_id: str,
        *,
        after_event_id: int | None,
        now: str,
        retention_seconds: int,
    ) -> ResearchTaskEventPage:
        """读取事件；过旧游标返回重同步标记而不静默跳过。"""
        window = self.execution_store.event_window(
            ResearchTaskAdapter.run_id_for(task_id),
            after_event_id,
            now=now,
            retention_seconds=retention_seconds,
        )
        return ResearchTaskEventPage(
            window.events,
            window.oldest_event_id,
            window.next_event_id,
            window.resync_required,
        )
