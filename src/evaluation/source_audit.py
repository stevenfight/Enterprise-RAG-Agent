"""评测样本来源文件的只读可定位性审计。"""

from pathlib import Path
from collections.abc import Iterable

from .models import EvaluationCase


def audit_source_files(
    cases: Iterable[EvaluationCase],
    source_roots: Iterable[str | Path],
) -> dict[str, object]:
    """检查样本声明的来源文件是否存在于显式根目录中。"""
    source_files = sorted(
        {
            source.source_file
            for case in cases
            for source in case.expected_sources
        }
    )
    roots = tuple(Path(root) for root in source_roots)
    missing = []
    for source_file in source_files:
        path = Path(source_file)
        exists = path.is_file() if path.is_absolute() else any(
            (root / path).is_file() for root in roots
        )
        if not exists:
            missing.append(source_file)
    return {
        "checked_source_count": len(source_files),
        "missing_source_files": missing,
        "ready": not missing,
    }
