# -*- coding: utf-8 -*-
"""根据源文件与既有制品证据生成保守的处理决策。"""

import json
import os
from pathlib import Path
from typing import Any, Iterable


def build_reuse_decisions(
    source_documents: Iterable[dict[str, Any]],
    asset_documents: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """为每份源 PDF 生成唯一且可审计的处理决策。

    现有 Markdown 缺少解析器、配置和输出哈希证据时不得直接标记为 REUSE；
    可保留文本结构并补充证据/制品的场景统一标记为 ENRICH。
    """
    assets_by_filename = {
        item.get("filename"): item
        for item in asset_documents
        if isinstance(item.get("filename"), str)
    }
    decisions: list[dict[str, Any]] = []

    for source in sorted(source_documents, key=lambda item: str(item.get("filename", ""))):
        filename = str(source.get("filename", ""))
        asset = assets_by_filename.get(filename, {})
        readability = source.get("readability_status")
        markdown_status = asset.get("markdown_status", "missing")

        if readability != "readable":
            decision = "FULL_REEXTRACT"
            reasons = ["source_unreadable"]
            error_status = "source_unreadable"
        elif markdown_status != "matched":
            decision = "FULL_REEXTRACT"
            reasons = ["missing_markdown"]
            error_status = "missing_markdown"
        else:
            decision = "ENRICH"
            reasons = ["missing_parser_provenance"]
            missing_local_assets = asset.get("missing_local_assets", [])
            missing_local_image_count = asset.get("missing_local_image_count", 0)
            if missing_local_assets or missing_local_image_count:
                reasons.append("missing_local_assets")
                error_status = "missing_local_assets"
            elif asset.get("asset_status") == "incomplete":
                reasons.append("incomplete_asset_inventory")
                error_status = "incomplete_asset_inventory"
            else:
                error_status = None

        decisions.append({
            "filename": filename,
            "source_sha256": source.get("sha256"),
            "physical_page_count": source.get("physical_page_count"),
            "decision": decision,
            "reasons": reasons,
            "error_status": error_status,
        })

    return {"schema_version": 1, "documents": decisions}


def write_reuse_decisions(decisions: dict[str, Any], output_path: Path) -> None:
    """原子写入仅供迁移审计的处理决策报告。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(output_path.name + ".writing")
    temporary_path.write_text(
        json.dumps(decisions, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_path, output_path)
