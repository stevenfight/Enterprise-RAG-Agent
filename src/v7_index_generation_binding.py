# -*- coding: utf-8 -*-
"""把实际 IndexPublicationManager 已发布代际制品绑定到 V7 candidate 的不可变清单。"""

import json
from pathlib import Path
from typing import Callable

from .index_publication import IndexPublicationManager, IndexPublicationResult
from .v7_generation_migration import V7GenerationMigrator


class IndexGenerationBindingError(RuntimeError):
    """已发布代际制品目录与 V7 candidate 绑定失败。"""


class V7IndexGenerationBinder:
    """以路径无关 hash/size manifest 固化已发布制品。

    绑定只登记不可变制品清单，绝不改写 legacy active 指针，也绝不创建 PublicationSet；
    PublicationSet 必须由发布协调器在制品验证成功后另行准备。
    """

    def __init__(self, index_manager: IndexPublicationManager, migrator: V7GenerationMigrator) -> None:
        self.index_manager = index_manager
        self.migrator = migrator

    def bind_published_generation(
        self,
        publication_result: IndexPublicationResult,
        v7_generation_id: str,
        *,
        sample_retriever: Callable[[], list[str]],
    ) -> dict:
        """将已发布 generation 的公司制品目录注册为 V7 candidate 的不可变制品清单。"""
        artifact_root = (
            self.index_manager.generations_dir
            / publication_result.generation_id
            / publication_result.company_name
        )
        if not artifact_root.is_dir():
            raise IndexGenerationBindingError(f"已发布代际制品目录不存在: {artifact_root}")
        self._validate_generation_manifest(artifact_root, publication_result)
        # validate_candidate 持久化路径无关的 hash/size manifest；失败时候选进入
        # validation_failed 且不会触碰 legacy 指针，也不会有任何 PublicationSet 产生。
        return self.migrator.validate_candidate(
            v7_generation_id,
            artifact_root,
            sample_retriever=sample_retriever,
        )

    @staticmethod
    def _validate_generation_manifest(artifact_root: Path, publication_result: IndexPublicationResult) -> None:
        """确认目录内 generation.json 与发布结果中的代际和公司一致。"""
        manifest_path = artifact_root.parent / "generation.json"
        if not manifest_path.is_file():
            raise IndexGenerationBindingError("generation.json 不存在")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise IndexGenerationBindingError("generation.json 不可读") from error
        if (
            not isinstance(manifest, dict)
            or manifest.get("generation_id") != publication_result.generation_id
            or manifest.get("company_name") != publication_result.company_name
        ):
            raise IndexGenerationBindingError("generation.json 与发布结果不一致")
