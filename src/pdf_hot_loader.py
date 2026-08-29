"""增量 PDF 热加载 worker。

该模块只负责消费热上传清单并推进状态，解析与索引仍复用调用方传入的既有实现。
"""

from dataclasses import dataclass
import logging
import math
import threading
import tempfile
from pathlib import Path
from typing import Any, Callable

from . import knowledge_service

logger = logging.getLogger("pdf_hot_loader")


def merge_company_chunk_data(
    existing: dict[str, Any],
    incoming: dict[str, Any],
    replaced_source_file: str,
) -> dict[str, Any]:
    """合并公司已有分块，替换同一源文件的旧版本，避免增量发布丢失历史资料。"""
    old_chunks = existing.get("child_chunks", [])
    replaced_parent_keys = {
        chunk.get("parent_key")
        for chunk in old_chunks
        if chunk.get("source_file") == replaced_source_file
    }
    child_chunks = [
        chunk for chunk in old_chunks
        if chunk.get("source_file") != replaced_source_file
    ]
    parent_texts = {
        key: value
        for key, value in existing.get("parent_texts", {}).items()
        if key not in replaced_parent_keys
    }
    child_chunks.extend(incoming.get("child_chunks", []))
    parent_texts.update(incoming.get("parent_texts", {}))
    return {"child_chunks": child_chunks, "parent_texts": parent_texts}


@dataclass(frozen=True)
class HotLoadRunResult:
    """单次 worker 扫描结果。"""

    discovered: int
    processed: int
    failed: int


class PdfHotLoadWorker:
    """把 pending_index 文档交给解析器和索引构建器处理。"""

    def __init__(
        self,
        parser: Callable[[Path, dict[str, Any]], Any],
        index_builder: Callable[[dict[str, Any], Any], str],
        max_attempts: int = 3,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts 必须是正整数")
        self.parser = parser
        self.index_builder = index_builder
        self.max_attempts = max_attempts

    def run_once(self, limit: int | None = None) -> HotLoadRunResult:
        knowledge_service.sync_pdf_directory()
        pending = knowledge_service.get_pending_documents()
        if limit is not None:
            if limit < 1:
                raise ValueError("limit 必须是正整数")
            pending = pending[:limit]

        processed = 0
        failed = 0
        for document in pending:
            filename = document["filename"]
            pdf_path = knowledge_service._PDF_DIR / filename
            attempts = int(document.get("index_attempts", 0))
            if attempts >= self.max_attempts:
                continue
            try:
                if Path(filename).name != filename or not pdf_path.is_file():
                    raise FileNotFoundError(f"PDF 文件不存在: {filename}")
                parsed = self.parser(pdf_path, document)
                generation = self.index_builder(document, parsed)
                if not isinstance(generation, str) or not generation.strip():
                    raise ValueError("索引构建器未返回有效 generation")
                if knowledge_service.mark_pdf_indexed(
                    filename, document["sha256"], generation, attempts + 1
                ):
                    processed += 1
                else:
                    failed += 1
            except Exception as exc:
                knowledge_service.mark_pdf_index_failed(
                    filename, document["sha256"], str(exc), attempts + 1
                )
                failed += 1
        return HotLoadRunResult(len(pending), processed, failed)


class PdfHotLoadScheduler:
    """显式启动和停止的目录热加载调度器。"""

    def __init__(self, worker: PdfHotLoadWorker, interval_seconds: float = 5.0) -> None:
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
                name="pdf-hot-load-scheduler",
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
            try:
                self.worker.run_once()
            except Exception:
                logger.exception("PDF 热加载调度循环异常")
            self._stop_event.wait(self.interval_seconds)


class PdfDirectorySyncWorker:
    """只负责目录登记的轻量 worker，不触发 MinerU 或 Embedding 调用。"""

    def run_once(self) -> dict[str, list[str]]:
        return knowledge_service.sync_pdf_directory()


class MineruHotLoadPipeline:
    """将单份 PDF 接入现有 MinerU、切分和索引构建链。"""

    NORMAL_PAGE_LIMIT = 200
    LARGE_PDF_BATCH_SIZE = 150

    def __init__(
        self,
        vector_db_dir: str | Path,
        mineru_client=None,
        mineru_api_key: str | None = None,
        embedding_api_key: str | None = None,
        parse_timeout_seconds: float = 600.0,
    ) -> None:
        if not math.isfinite(parse_timeout_seconds) or parse_timeout_seconds <= 0:
            raise ValueError("parse_timeout_seconds 必须是正数")
        self.vector_db_dir = Path(vector_db_dir)
        self._mineru_client = mineru_client
        self.mineru_api_key = mineru_api_key
        self.embedding_api_key = embedding_api_key
        self.parse_timeout_seconds = float(parse_timeout_seconds)

    def _get_mineru_client(self):
        if self._mineru_client is None:
            from mineru import MinerU
            from .utils import get_api_key
            self.mineru_api_key = self.mineru_api_key or get_api_key("MINERU_API_KEY")
            self._mineru_client = MinerU(token=self.mineru_api_key)
        return self._mineru_client

    def parse(self, pdf_path: Path, document: dict[str, Any]) -> dict[str, Any]:
        """只在消费任务时调用 MinerU，并保留任务启动时的源哈希。"""
        if knowledge_service._sha256_file(pdf_path) != document["sha256"]:
            raise RuntimeError("源 PDF 已发生变化，取消解析")
        page_count = self._get_pdf_page_count(pdf_path)
        client = self._get_mineru_client()
        kwargs = {
            "model": "vlm",
            "table": True,
            "formula": True,
            "language": "ch",
            "timeout": int(self.parse_timeout_seconds),
        }
        if page_count <= self.NORMAL_PAGE_LIMIT:
            logger.info("MinerU 普通文件异步解析：%s，共 %d 个物理页", pdf_path.name, page_count)
            results = list(client.extract_batch([str(pdf_path)], **kwargs))
            if len(results) != 1:
                raise RuntimeError("MinerU 未返回唯一的普通文件解析结果")
            result = results[0]
            if getattr(result, "state", None) != "done" or not getattr(result, "markdown", None):
                raise RuntimeError(f"MinerU 解析失败: {getattr(result, 'error', '内容为空')}")
            markdown = result.markdown
            batch_count = 1
        else:
            batch_count = (page_count + self.LARGE_PDF_BATCH_SIZE - 1) // self.LARGE_PDF_BATCH_SIZE
            markdown_parts = []
            logger.info(
                "MinerU 大文件物理分页解析：%s，共 %d 页，每批 %d 页，共 %d 批",
                pdf_path.name, page_count, self.LARGE_PDF_BATCH_SIZE, batch_count,
            )
            for batch_index in range(batch_count):
                start = batch_index * self.LARGE_PDF_BATCH_SIZE + 1
                end = min((batch_index + 1) * self.LARGE_PDF_BATCH_SIZE, page_count)
                logger.info("MinerU 解析物理页 %d-%d（%d/%d）", start, end, batch_index + 1, batch_count)
                result = client.extract(str(pdf_path), pages=f"{start}-{end}", **kwargs)
                if getattr(result, "state", None) != "done" or not getattr(result, "markdown", None):
                    raise RuntimeError(
                        f"MinerU 物理页 {start}-{end} 解析失败: "
                        f"{getattr(result, 'error', '内容为空')}"
                    )
                markdown_parts.append(
                    f"<!-- pdf-physical-page-range: {start}-{end} -->\n{result.markdown}"
                )
            markdown = "\n\n---\n\n".join(markdown_parts)
        return {
            "markdown": markdown,
            "source_pdf": str(pdf_path),
            "sha256": document["sha256"],
            "physical_page_count": page_count,
            "physical_page_batch_count": batch_count,
        }

    @staticmethod
    def _get_pdf_page_count(pdf_path: Path) -> int:
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
        except Exception as exc:
            raise RuntimeError(f"无法读取 PDF 物理页数: {exc}") from exc
        try:
            page_count = len(doc)
        finally:
            doc.close()
        if page_count < 1:
            raise RuntimeError("PDF 不包含有效物理页")
        return page_count

    def build_index(self, document: dict[str, Any], parsed: dict[str, Any]) -> str:
        """复用 text_splitter 与 ingestion，输出到 generation staging。"""
        from .ingestion import build_company_index_to_publication, collect_chunks_by_company
        from .pdf_mineru import _extract_company_name, compute_sha1
        from .text_splitter import split_markdown_reports
        import csv

        pdf_path = Path(parsed["source_pdf"])
        if knowledge_service._sha256_file(pdf_path) != document["sha256"]:
            raise RuntimeError("源 PDF 已发生变化，取消索引")
        with tempfile.TemporaryDirectory(prefix="pdf-hot-load-") as workspace:
            workspace_path = Path(workspace)
            md_dir = workspace_path / "markdown"
            chunked_dir = workspace_path / "chunked"
            md_dir.mkdir()
            md_path = md_dir / f"{pdf_path.stem}.md"
            md_path.write_text(parsed["markdown"], encoding="utf-8")
            subset_csv = workspace_path / "subset.csv"
            company_name = _extract_company_name(pdf_path.stem, md_dir=md_dir)
            with subset_csv.open("w", newline="", encoding="utf-8") as file_handle:
                writer = csv.writer(file_handle)
                writer.writerow(["sha1", "company_name", "file_name"])
                writer.writerow([compute_sha1(pdf_path), company_name, pdf_path.name])
            split_markdown_reports(md_dir, chunked_dir, subset_csv, pdf_dir=pdf_path.parent)
            company_data = collect_chunks_by_company(chunked_dir)
            if company_name not in company_data:
                raise RuntimeError("切分结果未生成可识别公司数据")
            existing_chunked_dir = pdf_path.parent.parent / "databases" / "chunked_reports"
            existing_company_data = collect_chunks_by_company(existing_chunked_dir).get(
                company_name,
                {"child_chunks": [], "parent_texts": {}},
            )
            data = merge_company_chunk_data(
                existing_company_data,
                company_data[company_name],
                pdf_path.name,
            )
            result = build_company_index_to_publication(
                company_name,
                data["child_chunks"],
                data["parent_texts"],
                self.vector_db_dir,
                self._get_embedding_api_key(),
                source_pdf_path=pdf_path,
                expected_sha256=document["sha256"],
            )
            return result.generation_id

    def _get_embedding_api_key(self) -> str:
        if self.embedding_api_key is None:
            from .utils import get_api_key
            self.embedding_api_key = get_api_key("DASHSCOPE_API_KEY")
        return self.embedding_api_key

    def create_worker(self, max_attempts: int = 3) -> PdfHotLoadWorker:
        return PdfHotLoadWorker(self.parse, self.build_index, max_attempts=max_attempts)

    def close(self) -> None:
        if self._mineru_client is not None and hasattr(self._mineru_client, "close"):
            self._mineru_client.close()
