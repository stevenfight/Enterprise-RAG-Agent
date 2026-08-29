"""隔离构建并原子发布增量索引代际。"""

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4


class IndexIntegrityError(RuntimeError):
    """staging 索引文件或元数据不完整。"""


class IndexPublicationResult:
    """索引发布结果。"""

    def __init__(self, generation_id: str, company_name: str, build_info: dict[str, Any]):
        self.generation_id = generation_id
        self.company_name = company_name
        self.build_info = build_info


class IndexPublicationManager:
    """为公司索引提供 staging、校验和 active 指针管理。"""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.staging_dir = self.root_dir / ".staging"
        self.generations_dir = self.root_dir / "generations"
        self.active_dir = self.root_dir / "active"

    def get_active(self, company_name: str) -> dict[str, Any] | None:
        """读取当前 active 指针；不存在或损坏时不猜测版本。"""
        pointer = self.active_dir / f"{company_name}.json"
        if not pointer.exists():
            return None
        try:
            data = json.loads(pointer.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IndexIntegrityError(f"active 指针不可读: {company_name}") from exc
        if data.get("company_name") != company_name or not data.get("generation_id"):
            raise IndexIntegrityError(f"active 指针格式无效: {company_name}")
        return data

    @staticmethod
    def _validate_company_name(company_name: str) -> None:
        if not company_name or Path(company_name).name != company_name:
            raise ValueError("公司名不能包含路径字符")

    @staticmethod
    def _validate_company_index(company_dir: Path) -> None:
        required = ("index.faiss", "bm25_index.pkl", "metadata.json", "parent_texts.json")
        missing = [name for name in required if not (company_dir / name).is_file()]
        if missing:
            raise IndexIntegrityError(f"索引制品缺失: {', '.join(missing)}")
        if any((company_dir / name).stat().st_size == 0 for name in required):
            raise IndexIntegrityError("索引制品存在空文件")
        try:
            metadata = json.loads((company_dir / "metadata.json").read_text(encoding="utf-8"))
            parent_texts = json.loads((company_dir / "parent_texts.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IndexIntegrityError("索引元数据不是合法 JSON") from exc
        if not isinstance(metadata, list) or not isinstance(parent_texts, dict):
            raise IndexIntegrityError("索引元数据类型无效")

    def build_and_publish(
        self,
        company_name: str,
        builder: Callable[[Path], dict[str, Any]],
        pre_publish_validator: Callable[[], None] | None = None,
    ) -> IndexPublicationResult:
        """在隔离代际构建，校验后只更新 active 指针。"""
        self._validate_company_name(company_name)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        generation_id = f"generation-{time.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:12]}"
        staging_generation = self.staging_dir / generation_id
        staging_company = staging_generation / company_name
        try:
            build_info = builder(staging_company)
            if not isinstance(build_info, dict):
                raise IndexIntegrityError("索引构建器未返回对象元数据")
            if pre_publish_validator is not None:
                pre_publish_validator()
            self._validate_company_index(staging_company)
            generation_manifest = {
                "generation_id": generation_id,
                "company_name": company_name,
                "build_info": build_info,
                "created_at": time.strftime('%Y-%m-%d %H:%M:%S'),
            }
            (staging_generation / "generation.json").write_text(
                json.dumps(generation_manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.generations_dir.mkdir(parents=True, exist_ok=True)
            final_generation = self.generations_dir / generation_id
            os.replace(staging_generation, final_generation)
            self._publish_pointer(company_name, generation_id, build_info)
            return IndexPublicationResult(generation_id, company_name, build_info)
        finally:
            if staging_generation.exists():
                shutil.rmtree(staging_generation)

    def publish_existing_company_index(
        self,
        company_name: str,
        legacy_root: str | Path,
    ) -> IndexPublicationResult:
        """将已校验的旧公司索引复制到新 generation，不重新调用模型。"""
        legacy_company_dir = Path(legacy_root) / company_name
        required = ("index.faiss", "bm25_index.pkl", "metadata.json", "parent_texts.json")

        def copy_builder(staging_company: Path) -> dict[str, Any]:
            if not legacy_company_dir.is_dir():
                raise FileNotFoundError(f"旧索引目录不存在: {legacy_company_dir}")
            staging_company.mkdir(parents=True, exist_ok=True)
            for filename in required:
                source = legacy_company_dir / filename
                if not source.is_file():
                    raise IndexIntegrityError(f"旧索引制品缺失: {source}")
                shutil.copy2(source, staging_company / filename)
            return {
                "source": "legacy_index",
                "legacy_company_dir": str(legacy_company_dir),
            }

        return self.build_and_publish(company_name, copy_builder)

    def _publish_pointer(self, company_name: str, generation_id: str, build_info: dict[str, Any]) -> None:
        self.active_dir.mkdir(parents=True, exist_ok=True)
        pointer = self.active_dir / f"{company_name}.json"
        temp_pointer = pointer.with_name(pointer.name + ".uploading")
        payload = {
            "company_name": company_name,
            "generation_id": generation_id,
            "build_info": build_info,
        }
        temp_pointer.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_pointer, pointer)
