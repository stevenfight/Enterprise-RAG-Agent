"""MinerU 解析旁路状态记录的确定性测试。

M1.4：为 MinerU _extract_single/_process_large_pdf 增加旁路状态记录，
保留原解析结果和逻辑；失败页批次必须使文档保持 incomplete（M-T03）。
"""

from pathlib import Path

import fitz


def _three_page_pdf(path: Path) -> None:
    """生成 3 页物理页的临时 PDF。"""
    document = fitz.open()
    for _ in range(3):
        page = document.new_page()
        page.draw_rect(fitz.Rect(0, 0, 100, 100), color=(1, 0, 0), fill=(1, 0, 0))
    document.save(path)
    document.close()


def _manifest_with_pages(tmp_path: Path, page_count: int):
    """播种文档版本与 manifest，返回 (store, manifest)。"""
    from src.document_asset_manifest_repository import DocumentAssetManifestRepository
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    document = V7DocumentRepository(store, tmp_path / "blobs").register_document_version(
        logical_document_key="mineru-report",
        display_name="MinerU 报告",
        original_filename="report.pdf",
        file_content=b"%PDF-1.7\nmineru-source",
        physical_page_count=page_count,
    )
    manifest = DocumentAssetManifestRepository(store).create_or_get(
        document_version_id=document.document_version_id,
        source_sha256=document.blob_sha256,
        physical_page_count=page_count,
        asset_status="incomplete",
    )
    return store, manifest


class _StubResult:
    """MinerU 解析结果替身。"""

    def __init__(self, state="done", markdown="内容", error=None):
        self.state = state
        self.markdown = markdown
        self.error = error


class _StubClient:
    """按调用顺序返回预设结果的 MinerU 客户端替身。"""

    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def extract(self, pdf_path, **kwargs):
        self.calls.append(kwargs.get("pages"))
        outcome = self._results.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_successful_batches_are_recorded_by_bypass(tmp_path: Path):
    from src.pdf_mineru import MinerUParseBatchBypass, _process_large_pdf
    from src.parse_batch_repository import ParseBatchRepository

    pdf_path = tmp_path / "report.pdf"
    _three_page_pdf(pdf_path)
    store, manifest = _manifest_with_pages(tmp_path, 3)
    repository = ParseBatchRepository(store)
    bypass = MinerUParseBatchBypass(repository, manifest.manifest_id)
    client = _StubClient([
        _StubResult(markdown="第一批内容"),
        _StubResult(markdown="第二批内容"),
    ])

    markdown_dir = tmp_path / "markdown"
    ok = _process_large_pdf(client, pdf_path, markdown_dir, chunk_size=2, parse_batch_bypass=bypass)

    assert ok is True
    assert client.calls == ["1-2", "3-3"]
    output = markdown_dir / "report.md"
    assert output.exists()
    assert "第一批内容" in output.read_text(encoding="utf-8")
    assert "第二批内容" in output.read_text(encoding="utf-8")
    coverage = repository.summarize(manifest.manifest_id)
    assert coverage.complete is True
    assert coverage.missing_physical_pages == ()
    assert coverage.failed_physical_pages == ()
    assert coverage.unresolved_physical_pages == ()


def test_failed_batch_keeps_document_incomplete(tmp_path: Path):
    from src.pdf_mineru import MinerUParseBatchBypass, _process_large_pdf
    from src.parse_batch_repository import ParseBatchRepository

    pdf_path = tmp_path / "report.pdf"
    _three_page_pdf(pdf_path)
    store, manifest = _manifest_with_pages(tmp_path, 3)
    repository = ParseBatchRepository(store)
    bypass = MinerUParseBatchBypass(repository, manifest.manifest_id)
    client = _StubClient([
        _StubResult(markdown="第一批内容"),
        _StubResult(state="failed", markdown=None, error="remote_timeout"),
    ])

    markdown_dir = tmp_path / "markdown"
    ok = _process_large_pdf(client, pdf_path, markdown_dir, chunk_size=2, parse_batch_bypass=bypass)

    # 原解析逻辑不变：失败批次跳过，成功批次仍合并写出
    assert ok is True
    output = markdown_dir / "report.md"
    assert output.exists()
    assert "第一批内容" in output.read_text(encoding="utf-8")
    # M-T03：失败页批次使文档保持 incomplete
    coverage = repository.summarize(manifest.manifest_id)
    assert coverage.complete is False
    assert coverage.failed_physical_pages == (3,)
    assert manifest.asset_status == "incomplete"


def test_bypass_recording_failure_does_not_break_parsing(tmp_path: Path):
    from src.pdf_mineru import MinerUParseBatchBypass, _process_large_pdf

    pdf_path = tmp_path / "report.pdf"
    _three_page_pdf(pdf_path)
    store, manifest = _manifest_with_pages(tmp_path, 3)

    class _BrokenRepository:
        """record 必然失败的仓储替身，用于验证旁路记录失败不影响解析。"""

        def record(self, **kwargs):
            raise RuntimeError("旁路存储不可用")

    bypass = MinerUParseBatchBypass(_BrokenRepository(), manifest.manifest_id)
    client = _StubClient([
        _StubResult(markdown="第一批内容"),
        _StubResult(markdown="第二批内容"),
    ])

    markdown_dir = tmp_path / "markdown"
    ok = _process_large_pdf(client, pdf_path, markdown_dir, chunk_size=2, parse_batch_bypass=bypass)

    assert ok is True
    output = markdown_dir / "report.md"
    assert output.exists()
    assert "第一批内容" in output.read_text(encoding="utf-8")
    assert "第二批内容" in output.read_text(encoding="utf-8")


def test_extract_single_exception_path_records_failed_batch(tmp_path: Path):
    from src.pdf_mineru import MinerUParseBatchBypass, _extract_single
    from src.parse_batch_repository import ParseBatchRepository

    pdf_path = tmp_path / "report.pdf"
    _three_page_pdf(pdf_path)
    store, manifest = _manifest_with_pages(tmp_path, 3)
    repository = ParseBatchRepository(store)
    bypass = MinerUParseBatchBypass(repository, manifest.manifest_id)
    client = _StubClient([RuntimeError("网络中断")])

    markdown_dir = tmp_path / "markdown"
    markdown_dir.mkdir()
    markdown = _extract_single(
        client, pdf_path, markdown_dir, page_range="1-3", parse_batch_bypass=bypass
    )

    assert markdown is None
    coverage = repository.summarize(manifest.manifest_id)
    assert coverage.complete is False
    assert coverage.failed_physical_pages == (1, 2, 3)
