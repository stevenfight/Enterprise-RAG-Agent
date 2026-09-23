# -*- coding: utf-8 -*-
"""V7 候选 generation 的 staging 验证与 PublicationSet 发布准备编排。"""

from pathlib import Path
from typing import Callable, Iterable

from .publication_set import PublicationSetRepository, PublicationSnapshot
from .v7_generation_migration import V7GenerationMigrator


class V7GenerationPublicationCoordinator:
    """验证候选制品并登记待发布集合，绝不在该步骤切换 active publication。"""

    def __init__(
        self,
        migrator: V7GenerationMigrator,
        publication_repository: PublicationSetRepository,
    ) -> None:
        self.migrator = migrator
        self.publication_repository = publication_repository

    def validate_and_prepare_publication(
        self,
        publication_id: str,
        generation_id: str,
        artifact_root: Path,
        *,
        sample_retriever: Callable[[], list[str]],
        page_artifact_ids: Iterable[str] = (),
        fact_ids: Iterable[str] = (),
    ) -> PublicationSnapshot:
        """固定构建基线，验证 staging 制品并登记 CAS 所需的 prepared publication。"""
        active = self.publication_repository.get_active_publication()
        expected_active_publication_id = active.publication_id if active else None
        expected_corpus_revision = active.corpus_revision if active else None
        self.migrator.validate_candidate(
            generation_id,
            Path(artifact_root),
            sample_retriever=sample_retriever,
        )
        candidate = self.migrator.get_candidate(generation_id)
        snapshot = self.publication_repository.create_publication(
            publication_id,
            generation_id,
            candidate["document_version_ids"],
            page_artifact_ids,
            fact_ids,
        )
        self.publication_repository.prepare_publication_build(
            publication_id,
            expected_active_publication_id,
            expected_corpus_revision,
        )
        return snapshot

    def activate_prepared_publication(self, publication_id: str) -> PublicationSnapshot:
        """受控显式 CAS 激活入口：基线不匹配时得到 superseded，绝不读取 legacy JSON active 指针。"""
        return self.publication_repository.activate_publication(publication_id)
