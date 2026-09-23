# -*- coding: utf-8 -*-
"""索引完成后才提升 V7 文档版本的上层编排测试。"""

from src.v7_document_repository import V7DocumentRepository
from src.v7_metadata_store import V7MetadataStore


def _repository(tmp_path):
    return V7DocumentRepository(V7MetadataStore(tmp_path / "metadata.sqlite3"), tmp_path / "blobs")


def _register(repository, content):
    return repository.register_document_version(
        logical_document_key="annual-report", display_name="年度报告",
        original_filename="年度报告.pdf", file_content=content, physical_page_count=1,
    )


def test_index_promotion_keeps_old_active_when_index_is_incomplete(tmp_path):
    from src.v7_document_index_promotion_coordinator import V7DocumentIndexPromotionCoordinator

    repository = _repository(tmp_path)
    old = _register(repository, b"%PDF-1.7\nold")
    repository.promote_document_version_to_active(old.document_version_id)
    incoming = _register(repository, b"%PDF-1.7\nnew")

    result = V7DocumentIndexPromotionCoordinator(repository).complete_index_and_promote(
        incoming.document_version_id,
        lambda _document_version_id: {"success": False, "generation_id": None},
    )

    assert result.promoted is False
    assert repository.get_active_document_version(old.logical_document_id) == old.document_version_id


def test_index_promotion_promotes_only_after_successful_generation_result(tmp_path):
    from src.v7_document_index_promotion_coordinator import V7DocumentIndexPromotionCoordinator

    repository = _repository(tmp_path)
    old = _register(repository, b"%PDF-1.7\nold")
    repository.promote_document_version_to_active(old.document_version_id)
    incoming = _register(repository, b"%PDF-1.7\nnew")

    result = V7DocumentIndexPromotionCoordinator(repository).complete_index_and_promote(
        incoming.document_version_id,
        lambda document_version_id: {"success": True, "generation_id": f"generation-{document_version_id}"},
    )

    assert result.promoted is True
    assert result.generation_id
    assert repository.get_active_document_version(old.logical_document_id) == incoming.document_version_id
