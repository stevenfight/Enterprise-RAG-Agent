# -*- coding: utf-8 -*-
"""E-T33：研究任务的最小真实执行闭环。"""

from decimal import Decimal
from pathlib import Path

from src.durable_execution import DurableExecutionStore
from src.research_delivery import ResearchPlan
from src.research_plan_repository import ResearchPlanRepository
from src.research_report_repository import ResearchReportRepository
from src.research_task_adapter import ResearchTaskAdapter
from src.v7_metadata_store import V7MetadataStore


def _running_task(tmp_path: Path, task_id: str) -> tuple[ResearchTaskAdapter, ResearchPlanRepository, ResearchReportRepository]:
    metadata_store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    adapter = ResearchTaskAdapter(DurableExecutionStore(metadata_store))
    created = adapter.create_task(task_id, ("plan", "retrieve", "review", "report"))
    adapter.start_task(task_id, created.revision, f"start:{task_id}", actor="approver")
    plans = ResearchPlanRepository(metadata_store)
    plans.append(
        ResearchPlan.create(
            plan_id=f"research-plan:{task_id}:1",
            task_id=task_id,
            objective="核对营业收入变化",
            scope=("营业收入",),
            step_ids=("plan", "retrieve", "review", "report"),
            estimated_cost=Decimal("1.00"),
        )
    )
    return adapter, plans, ResearchReportRepository(metadata_store)


def test_executor_commits_plan_steps_creates_source_backed_report_and_completes(tmp_path: Path) -> None:
    from src.research_task_execution import ResearchTaskExecutor

    adapter, plans, reports = _running_task(tmp_path, "execution-success")
    executor = ResearchTaskExecutor(
        adapter,
        plans,
        reports,
        query=lambda _: {
            "answer": "营业收入同比增长，详见年报披露。",
            "sources": [{"source_file": "annual-report.pdf", "pages": [12]}],
        },
    )

    snapshot = executor.execute("execution-success", actor="worker")

    assert snapshot.status == "completed"
    assert snapshot.revision == 2
    report = reports.latest_for_task("execution-success")
    assert report is not None
    assert report.review_status.value == "pending_review"
    assert report.claims[0].support_kind.value == "source"
    assert report.claims[0].source_ids
    events = adapter.execution_store.events(adapter.run_id_for("execution-success"))
    assert [event.event_type for event in events].count("step_completed") == 4


def test_executor_fails_without_source_evidence_and_does_not_create_report(tmp_path: Path) -> None:
    from src.research_task_execution import ResearchTaskExecutor

    adapter, plans, reports = _running_task(tmp_path, "execution-no-source")
    executor = ResearchTaskExecutor(
        adapter,
        plans,
        reports,
        query=lambda _: {"answer": "没有可引用来源", "sources": []},
    )

    snapshot = executor.execute("execution-no-source", actor="worker")

    assert snapshot.status == "failed"
    assert snapshot.revision == 2
    assert reports.latest_for_task("execution-no-source") is None


def test_executor_keeps_task_running_when_another_worker_holds_step_lease(tmp_path: Path) -> None:
    from src.research_task_execution import ResearchTaskExecutor

    adapter, plans, reports = _running_task(tmp_path, "execution-lease-held")
    adapter.claim_step("execution-lease-held", "plan", "other-worker")
    executor = ResearchTaskExecutor(
        adapter,
        plans,
        reports,
        query=lambda _: {"answer": "不应执行检索", "sources": []},
    )

    snapshot = executor.execute("execution-lease-held", actor="worker")

    assert snapshot.status == "running"
    assert reports.latest_for_task("execution-lease-held") is None
    assert all(item.decision_type != "failure" for item in adapter.route_decisions("execution-lease-held"))


def test_final_report_write_failure_rolls_back_final_step_and_completion(tmp_path: Path, monkeypatch) -> None:
    from src.research_task_execution import ResearchTaskExecutor

    adapter, plans, reports = _running_task(tmp_path, "execution-final-atomic")

    def fail_report_write(*_args, **_kwargs) -> None:
        raise RuntimeError("模拟报告持久化失败")

    monkeypatch.setattr(reports, "append_in_transaction", fail_report_write, raising=False)
    executor = ResearchTaskExecutor(
        adapter,
        plans,
        reports,
        query=lambda _: {
            "answer": "营业收入同比增长，详见年报披露。",
            "sources": [{"source_file": "annual-report.pdf", "pages": [12]}],
        },
    )

    snapshot = executor.execute("execution-final-atomic", actor="worker")

    assert snapshot.status == "failed"
    assert reports.latest_for_task("execution-final-atomic") is None
    assert {item.step_id for item in adapter.execution_store.checkpoints(adapter.run_id_for("execution-final-atomic"))} == {"plan", "retrieve", "review"}
