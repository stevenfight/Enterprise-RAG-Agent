"""评测数据集与来源清单绑定的 RED/GREEN 测试。"""

import hashlib
import json
import sys
from pathlib import Path

from src.evaluation.cli import main as evaluation_cli_main
from src.evaluation.source_binding import audit_source_binding


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_binding(
    path: Path,
    dataset: Path,
    inventory: Path,
    *,
    dataset_path: str | None = None,
    dataset_sha256: str | None = None,
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "dataset_path": dataset_path or str(dataset),
                "dataset_sha256": dataset_sha256 or _sha256(dataset),
                "source_inventory_path": str(inventory),
                "source_inventory_sha256": _sha256(inventory),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_source_binding_accepts_matching_paths_and_hashes(tmp_path: Path):
    dataset = tmp_path / "dataset.jsonl"
    inventory = tmp_path / "inventory.json"
    manifest = tmp_path / "binding.json"
    dataset.write_text('{"id":"case-001"}\n', encoding="utf-8")
    inventory.write_text('{"schema_version":1,"documents":[]}', encoding="utf-8")
    _write_binding(manifest, dataset, inventory)

    report = audit_source_binding(dataset, inventory, manifest)

    assert report["ready"] is True
    assert report["path_mismatches"] == []
    assert report["hash_mismatches"] == []


def test_source_binding_rejects_missing_manifest(tmp_path: Path):
    dataset = tmp_path / "dataset.jsonl"
    inventory = tmp_path / "inventory.json"
    dataset.write_text("dataset", encoding="utf-8")
    inventory.write_text("{}", encoding="utf-8")

    report = audit_source_binding(dataset, inventory, tmp_path / "missing.json")

    assert report["ready"] is False
    assert report["manifest_error"]


def test_source_binding_reports_dataset_hash_drift(tmp_path: Path):
    dataset = tmp_path / "dataset.jsonl"
    inventory = tmp_path / "inventory.json"
    manifest = tmp_path / "binding.json"
    dataset.write_text("dataset", encoding="utf-8")
    inventory.write_text("{}", encoding="utf-8")
    _write_binding(manifest, dataset, inventory)
    dataset.write_text("dataset-drift", encoding="utf-8")

    report = audit_source_binding(dataset, inventory, manifest)

    assert report["ready"] is False
    assert report["hash_mismatches"] == ["dataset"]


def test_source_binding_reports_path_drift(tmp_path: Path):
    dataset = tmp_path / "dataset.jsonl"
    inventory = tmp_path / "inventory.json"
    manifest = tmp_path / "binding.json"
    dataset.write_text("dataset", encoding="utf-8")
    inventory.write_text("{}", encoding="utf-8")
    _write_binding(manifest, dataset, inventory, dataset_path="other.jsonl")

    report = audit_source_binding(dataset, inventory, manifest)

    assert report["ready"] is False
    assert report["path_mismatches"] == ["dataset"]


def test_cli_requires_source_inventory_for_binding_manifest(tmp_path: Path, monkeypatch):
    fixtures = tmp_path / "fixtures.json"
    fixtures.write_text(
        Path("evals/fixtures/offline-core.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    inventory = tmp_path / "inventory.json"
    inventory.write_text('{"schema_version":1,"documents":[]}', encoding="utf-8")
    manifest = tmp_path / "binding.json"
    dataset = Path("evals/datasets/core.jsonl").resolve()
    _write_binding(manifest, dataset, inventory)
    output_dir = tmp_path / "report"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluation",
            "--dataset",
            str(dataset),
            "--fixtures",
            str(fixtures),
            "--output-dir",
            str(output_dir),
            "--source-binding-manifest",
            str(manifest),
        ],
    )

    assert evaluation_cli_main() == 1
    report = json.loads(
        (output_dir / "evaluation-report.json").read_text(encoding="utf-8")
    )
    assert report["metadata"]["source_binding"]["ready"] is False
    assert "--source-inventory" in report["metadata"]["source_binding"]["manifest_error"]
