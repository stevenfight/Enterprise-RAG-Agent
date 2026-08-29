"""增量 PDF 处理 worker 的状态推进测试。"""

from pathlib import Path
import threading

import pytest

import src.knowledge_service as knowledge_service
from src.knowledge_service import upload_pdf, get_documents
from src.pdf_hot_loader import HotLoadRunResult, PdfHotLoadScheduler, PdfHotLoadWorker


@pytest.fixture
def isolated_pdf_store(tmp_path: Path, monkeypatch):
    pdf_dir = tmp_path / "pdf_reports"
    monkeypatch.setattr(knowledge_service, "_PDF_DIR", pdf_dir)
    monkeypatch.setattr(knowledge_service, "_VECTOR_DB_DIR", tmp_path / "vector_dbs")
    monkeypatch.setattr(knowledge_service, "_MANIFEST_PATH", tmp_path / "manifest.json")
    return pdf_dir


def test_worker_processes_pending_document_and_marks_generation(isolated_pdf_store):
    uploaded = upload_pdf(b"%PDF-1.7\nworker", "worker报告.pdf")
    parsed = []
    indexed = []

    def parse_document(path, document):
        parsed.append((path, document["sha256"]))
        return {"chunks": ["content"]}

    def build_index(document, parsed_document):
        indexed.append((document["filename"], parsed_document["chunks"]))
        return "generation-1"

    result = PdfHotLoadWorker(parse_document, build_index).run_once()
    assert result.processed == 1
    assert result.failed == 0
    assert parsed[0][0] == isolated_pdf_store / "worker报告.pdf"
    assert indexed == [("worker报告.pdf", ["content"])]
    assert get_documents()[0]["index_status"] == "indexed"
    assert get_documents()[0]["index_generation"] == "generation-1"
    assert uploaded["sha256"] == parsed[0][1]


def test_worker_discovers_pdf_dropped_directly_into_directory(isolated_pdf_store):
    isolated_pdf_store.mkdir(parents=True, exist_ok=True)
    (isolated_pdf_store / "目录worker.pdf").write_bytes(b"%PDF-1.7\ndropped")
    result = PdfHotLoadWorker(
        lambda _path, _document: {"content": "ok"},
        lambda _document, _parsed: "generation-drop",
    ).run_once()
    assert result.processed == 1
    assert get_documents()[0]["index_status"] == "indexed"


def test_worker_failure_preserves_retryable_state(isolated_pdf_store):
    uploaded = upload_pdf(b"%PDF-1.7\nworker-fail", "失败worker.pdf")

    def parse_document(_path, _document):
        raise ValueError("解析失败")

    def build_index(_document, _parsed_document):
        pytest.fail("解析失败后不应构建索引")

    result = PdfHotLoadWorker(parse_document, build_index).run_once()
    assert result.processed == 0
    assert result.failed == 1
    doc = get_documents()[0]
    assert doc["index_status"] == "index_failed"
    assert doc["index_error"] == "解析失败"
    assert doc["sha256"] == uploaded["sha256"]


def test_worker_stops_automatic_retries_after_max_attempts(isolated_pdf_store):
    upload_pdf(b"%PDF-1.7\nretry-limit", "重试上限.pdf")
    calls = []

    def parse_document(_path, _document):
        calls.append(True)
        raise ValueError("稳定解析失败")

    worker = PdfHotLoadWorker(parse_document, lambda _document, _parsed: "unused", max_attempts=2)
    assert worker.run_once().failed == 1
    assert worker.run_once().failed == 1
    assert worker.run_once().failed == 0
    assert len(calls) == 2
    assert get_documents()[0]["index_status"] == "index_failed"
    assert get_documents()[0]["index_attempts"] == 2


def test_scheduler_start_and_stop_are_explicit_and_idempotent():
    calls = []

    class FakeWorker:
        def run_once(self):
            calls.append(True)
            return HotLoadRunResult(0, 0, 0)

    scheduler = PdfHotLoadScheduler(FakeWorker(), interval_seconds=0.01)
    scheduler.start()
    scheduler.start()
    scheduler.stop(timeout=1)
    scheduler.stop(timeout=1)
    assert calls
    assert scheduler.is_running is False


def test_scheduler_rejects_non_positive_interval():
    with pytest.raises(ValueError, match="interval_seconds"):
        PdfHotLoadScheduler(object(), interval_seconds=0)


def test_scheduler_reports_inflight_worker_during_bounded_stop():
    started = threading.Event()
    release = threading.Event()

    class BlockingWorker:
        def run_once(self):
            started.set()
            release.wait(1)
            return HotLoadRunResult(0, 0, 0)

    scheduler = PdfHotLoadScheduler(BlockingWorker(), interval_seconds=1)
    scheduler.start()
    assert started.wait(1)
    assert scheduler.stop(timeout=0.01) is False
    assert scheduler.is_running is True
    release.set()
    assert scheduler.stop(timeout=1) is True
    assert scheduler.is_running is False


def test_mineru_adapter_is_lazy_and_validates_result(monkeypatch, tmp_path: Path):
    from src.pdf_hot_loader import MineruHotLoadPipeline

    class FakeResult:
        state = "done"
        markdown = "# 财务数据"

    class FakeClient:
        def __init__(self):
            self.calls = []

        def extract(self, path, **kwargs):
            self.calls.append((path, kwargs))
            return FakeResult()

        def extract_batch(self, paths, **kwargs):
            self.calls.append((paths, kwargs))
            yield FakeResult()

    client = FakeClient()
    pipeline = MineruHotLoadPipeline(tmp_path / "vector_dbs", mineru_client=client)
    assert client.calls == []
    pdf_path = tmp_path / "报告.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\ncontent")
    document = {"filename": pdf_path.name, "sha256": knowledge_service._sha256_file(pdf_path)}
    monkeypatch.setattr(pipeline, "_get_pdf_page_count", lambda _path: 5)
    parsed = pipeline.parse(pdf_path, document)
    assert parsed["markdown"] == "# 财务数据"
    assert parsed["sha256"] == document["sha256"]
    assert client.calls[0][1]["model"] == "vlm"


def test_mineru_adapter_rejects_changed_source_before_index(monkeypatch, tmp_path: Path):
    from src.pdf_hot_loader import MineruHotLoadPipeline

    pipeline = MineruHotLoadPipeline(tmp_path / "vector_dbs")
    pdf_path = tmp_path / "报告.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\nold")
    document = {"filename": pdf_path.name, "sha256": knowledge_service._sha256_file(pdf_path)}
    pdf_path.write_bytes(b"%PDF-1.7\nnew")
    with pytest.raises(RuntimeError, match="源 PDF 已发生变化"):
        pipeline.build_index(document, {"markdown": "# data", "source_pdf": str(pdf_path), "sha256": document["sha256"]})


def test_mineru_adapter_keeps_mineru_and_embedding_credentials_separate(tmp_path: Path):
    pipeline = __import__("src.pdf_hot_loader", fromlist=["MineruHotLoadPipeline"]).MineruHotLoadPipeline(
        tmp_path / "vector_dbs", mineru_api_key="mineru-key", embedding_api_key="embedding-key"
    )
    assert pipeline.mineru_api_key == "mineru-key"
    assert pipeline._get_embedding_api_key() == "embedding-key"


def test_mineru_adapter_uses_configured_parse_timeout(monkeypatch, tmp_path: Path):
    from src.pdf_hot_loader import MineruHotLoadPipeline

    class FakeResult:
        state = "done"
        markdown = "# 财务数据"

    class FakeClient:
        def __init__(self):
            self.calls = []

        def extract(self, path, **kwargs):
            self.calls.append((path, kwargs))
            return FakeResult()

        def extract_batch(self, paths, **kwargs):
            self.calls.append((paths, kwargs))
            yield FakeResult()

    client = FakeClient()
    pipeline = MineruHotLoadPipeline(
        tmp_path / "vector_dbs",
        mineru_client=client,
        parse_timeout_seconds=23,
    )
    pdf_path = tmp_path / "超时配置.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\\ncontent")
    document = {"filename": pdf_path.name, "sha256": knowledge_service._sha256_file(pdf_path)}

    monkeypatch.setattr(pipeline, "_get_pdf_page_count", lambda _path: 5)
    pipeline.parse(pdf_path, document)

    assert client.calls[0][1]["timeout"] == 23


def test_mineru_adapter_uses_async_batch_for_normal_pdf(monkeypatch, tmp_path: Path):
    from src.pdf_hot_loader import MineruHotLoadPipeline

    class FakeResult:
        state = "done"
        markdown = "# 普通文件"

    class FakeClient:
        def __init__(self):
            self.batch_calls = []
            self.single_calls = []

        def extract_batch(self, paths, **kwargs):
            self.batch_calls.append((paths, kwargs))
            yield FakeResult()

        def extract(self, path, **kwargs):
            self.single_calls.append((path, kwargs))
            return FakeResult()

    client = FakeClient()
    pipeline = MineruHotLoadPipeline(tmp_path / "vector_dbs", mineru_client=client)
    pdf_path = tmp_path / "普通.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\ncontent")
    document = {"filename": pdf_path.name, "sha256": knowledge_service._sha256_file(pdf_path)}
    monkeypatch.setattr(pipeline, "_get_pdf_page_count", lambda _path: 20)

    parsed = pipeline.parse(pdf_path, document)

    assert parsed["physical_page_count"] == 20
    assert parsed["physical_page_batch_count"] == 1
    assert len(client.batch_calls) == 1
    assert client.single_calls == []
    assert client.batch_calls[0][1]["timeout"] == 600


def test_mineru_adapter_splits_large_pdf_by_physical_pages(monkeypatch, tmp_path: Path):
    from src.pdf_hot_loader import MineruHotLoadPipeline

    class FakeResult:
        state = "done"
        markdown = "批次内容"

    class FakeClient:
        def __init__(self):
            self.calls = []

        def extract(self, path, **kwargs):
            self.calls.append((path, kwargs))
            return FakeResult()

    client = FakeClient()
    pipeline = MineruHotLoadPipeline(tmp_path / "vector_dbs", mineru_client=client)
    pdf_path = tmp_path / "大型.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\ncontent")
    document = {"filename": pdf_path.name, "sha256": knowledge_service._sha256_file(pdf_path)}
    monkeypatch.setattr(pipeline, "_get_pdf_page_count", lambda _path: 301)

    parsed = pipeline.parse(pdf_path, document)

    assert parsed["physical_page_count"] == 301
    assert parsed["physical_page_batch_count"] == 3
    assert [call[1]["pages"] for call in client.calls] == ["1-150", "151-300", "301-301"]
    assert "pdf-physical-page-range: 151-300" in parsed["markdown"]


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_mineru_adapter_rejects_invalid_parse_timeout(tmp_path: Path, timeout: float):
    from src.pdf_hot_loader import MineruHotLoadPipeline

    with pytest.raises(ValueError, match="parse_timeout_seconds"):
        MineruHotLoadPipeline(tmp_path / "vector_dbs", parse_timeout_seconds=timeout)


def test_merge_company_chunk_data_keeps_existing_documents_and_replaces_same_source():
    from src.pdf_hot_loader import merge_company_chunk_data

    existing = {
        "child_chunks": [
            {"source_file": "旧报告.pdf", "parent_key": "旧报告::p1", "text": "old"},
            {"source_file": "待替换.pdf", "parent_key": "待替换::p1", "text": "stale"},
        ],
        "parent_texts": {
            "旧报告::p1": "old parent",
            "待替换::p1": "stale parent",
        },
    }
    incoming = {
        "child_chunks": [
            {"source_file": "待替换.pdf", "parent_key": "待替换::p2", "text": "fresh"},
        ],
        "parent_texts": {"待替换::p2": "fresh parent"},
    }

    merged = merge_company_chunk_data(existing, incoming, "待替换.pdf")

    assert [chunk["text"] for chunk in merged["child_chunks"]] == ["old", "fresh"]
    assert merged["parent_texts"] == {
        "旧报告::p1": "old parent",
        "待替换::p2": "fresh parent",
    }


def test_mineru_pipeline_build_preserves_existing_company_chunks(monkeypatch, tmp_path: Path):
    from types import SimpleNamespace

    import src.ingestion as ingestion
    import src.pdf_mineru as pdf_mineru
    import src.text_splitter as text_splitter
    from src.pdf_hot_loader import MineruHotLoadPipeline

    pdf_dir = tmp_path / "pdf_reports"
    pdf_dir.mkdir()
    pdf_path = pdf_dir / "待替换.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\ncontent")
    existing_chunked_dir = tmp_path / "databases" / "chunked_reports"
    existing_chunked_dir.mkdir(parents=True)
    captured = {}

    existing = {
        "测试公司": {
            "child_chunks": [
                {"source_file": "旧报告.pdf", "parent_key": "旧报告::p1", "text": "old"},
            ],
            "parent_texts": {"旧报告::p1": "old parent"},
        },
    }
    incoming = {
        "测试公司": {
            "child_chunks": [
                {"source_file": "待替换.pdf", "parent_key": "待替换::p1", "text": "fresh"},
            ],
            "parent_texts": {"待替换::p1": "fresh parent"},
        },
    }

    monkeypatch.setattr(pdf_mineru, "_extract_company_name", lambda *_args, **_kwargs: "测试公司")
    monkeypatch.setattr(pdf_mineru, "compute_sha1", lambda _path: "sha1")
    monkeypatch.setattr(text_splitter, "split_markdown_reports", lambda *_args, **_kwargs: None)

    def collect_chunks(path):
        return existing if Path(path) == existing_chunked_dir else incoming

    monkeypatch.setattr(ingestion, "collect_chunks_by_company", collect_chunks)

    def build_index(*args, **kwargs):
        captured["child_chunks"] = args[1]
        captured["parent_texts"] = args[2]
        return SimpleNamespace(generation_id="generation-merged")

    monkeypatch.setattr(ingestion, "build_company_index_to_publication", build_index)
    pipeline = MineruHotLoadPipeline(tmp_path / "vector_dbs", embedding_api_key="embedding-key")
    document = {"filename": pdf_path.name, "sha256": knowledge_service._sha256_file(pdf_path)}

    generation = pipeline.build_index(
        document,
        {"markdown": "# data", "source_pdf": str(pdf_path), "sha256": document["sha256"]},
    )

    assert generation == "generation-merged"
    assert [chunk["text"] for chunk in captured["child_chunks"]] == ["old", "fresh"]
    assert captured["parent_texts"] == {
        "旧报告::p1": "old parent",
        "待替换::p1": "fresh parent",
    }


def test_api_hot_load_config_keeps_external_indexing_disabled_by_default(monkeypatch):
    import src.api_service as api_service

    scheduler_calls = []

    class FakeScheduler:
        def __init__(self, worker, interval_seconds):
            scheduler_calls.append((worker, interval_seconds))

        def start(self):
            pass

    monkeypatch.setattr(api_service, "PdfHotLoadScheduler", FakeScheduler)
    monkeypatch.setattr(api_service, "MineruHotLoadPipeline", None, raising=False)
    scheduler = api_service._create_pdf_hot_load_scheduler({
        "pdf_hot_load_enabled": True,
        "pdf_hot_load_indexing_enabled": False,
        "pdf_hot_load_interval_seconds": 15,
    })

    assert scheduler is not None
    assert len(scheduler_calls) == 1
    assert isinstance(scheduler_calls[0][0], api_service.PdfDirectorySyncWorker)


def test_api_hot_load_config_creates_pipeline_only_when_indexing_enabled(monkeypatch):
    import src.api_service as api_service

    scheduler_calls = []
    closed = []

    class FakePipeline:
        def __init__(self, vector_dir, parse_timeout_seconds=600.0):
            self.vector_dir = vector_dir
            self.parse_timeout_seconds = parse_timeout_seconds

        def create_worker(self, max_attempts=3):
            assert max_attempts == 3
            return "pipeline-worker"

        def close(self):
            closed.append(True)

    class FakeScheduler:
        def __init__(self, worker, interval_seconds):
            scheduler_calls.append((worker, interval_seconds))

        def start(self):
            pass

        def stop(self, timeout=None):
            return True

    monkeypatch.setattr(api_service, "MineruHotLoadPipeline", FakePipeline)
    monkeypatch.setattr(api_service, "PdfHotLoadScheduler", FakeScheduler)
    scheduler = api_service._create_pdf_hot_load_scheduler({
        "pdf_hot_load_enabled": True,
        "pdf_hot_load_indexing_enabled": True,
        "pdf_hot_load_interval_seconds": 20,
        "pdf_hot_load_parse_timeout_seconds": 45,
    })

    assert scheduler is not None
    assert scheduler_calls == [("pipeline-worker", 20.0)]
    assert api_service.pdf_hot_load_pipeline.parse_timeout_seconds == 45.0
    assert api_service.pdf_hot_load_pipeline.vector_dir == api_service.vector_db_dir
    api_service._close_pdf_hot_load_resources(scheduler)
    assert closed == [True]
