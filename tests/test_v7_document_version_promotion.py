# -*- coding: utf-8 -*-
"""M1.11 文档版本区分测试。

- 同 logical_document_key 不同内容哈希：登记为新的不可变 document version；
- 新版本登记（完整索引前）绝不替换该逻辑文档的 active 版本；
- 只有显式激活（索引完成后调用）才原子替换 active，旧 active 降级为 superseded。
"""

from pathlib import Path


def _repository(tmp_path: Path):
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "v7_metadata.sqlite3")
    return V7DocumentRepository(store, tmp_path / "blobs")


def _register(repository, key: str, content: bytes, filename: str):
    return repository.register_document_version(
        logical_document_key=key,
        display_name="年度报告",
        original_filename=filename,
        file_content=content,
        physical_page_count=2,
    )


def _index_status(repository, document_version_id: str) -> str:
    with repository.store.connect() as connection:
        row = connection.execute(
            "SELECT index_status FROM v7_document_versions WHERE document_version_id = ?",
            (document_version_id,),
        ).fetchone()
    return row[0]


def test_same_key_different_hash_creates_new_version_and_keeps_active(tmp_path: Path):
    """同名逻辑文档上传不同内容：创建新版本且登记动作不替换 active 版本。"""
    repository = _repository(tmp_path)

    v1 = _register(repository, "annual-report", b"%PDF-1.7\nv1-content", "年度报告.pdf")
    repository.promote_document_version_to_active(v1.document_version_id)
    assert repository.get_active_document_version(v1.logical_document_id) == v1.document_version_id

    # 同名不同内容：新版本登记成功
    v2 = _register(repository, "annual-report", b"%PDF-1.7\nv2-content", "年度报告.pdf")
    assert v2.created is True
    assert v2.document_version_id != v1.document_version_id
    assert v2.logical_document_id == v1.logical_document_id
    assert repository.count_document_versions() == 2
    # 新版本处于 pending_index（完整索引前）
    assert _index_status(repository, v2.document_version_id) == "pending_index"
    # 完整索引前：active 版本不被替换
    assert repository.get_active_document_version(v1.logical_document_id) == v1.document_version_id

    # 索引完成后显式激活：active 原子切换到 v2，v1 降级
    repository.promote_document_version_to_active(v2.document_version_id)
    assert repository.get_active_document_version(v1.logical_document_id) == v2.document_version_id
    assert _index_status(repository, v1.document_version_id) == "superseded"
    assert _index_status(repository, v2.document_version_id) == "active"


def test_logical_document_without_promoted_version_has_no_active(tmp_path: Path):
    """从未显式激活的逻辑文档不返回任何 active 版本（新登记版本默认不接管）。"""
    repository = _repository(tmp_path)

    registration = _register(repository, "fresh-report", b"%PDF-1.7\ncontent", "新报告.pdf")

    assert repository.get_active_document_version(registration.logical_document_id) is None
    assert _index_status(repository, registration.document_version_id) == "pending_index"


def test_promote_unknown_or_foreign_version_is_rejected(tmp_path: Path):
    """激活不存在的版本必须报错，不得静默修改任何状态。"""
    import pytest

    repository = _repository(tmp_path)

    with pytest.raises(ValueError, match="document_version_id"):
        repository.promote_document_version_to_active("nonexistent-version-id")
