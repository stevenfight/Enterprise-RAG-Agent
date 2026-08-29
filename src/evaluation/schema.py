"""评测样本加载和集合级校验。"""

import json
from pathlib import Path
from typing import Iterable

from .models import EvaluationCase, ValidationError


def load_jsonl_cases(path: str | Path) -> list[EvaluationCase]:
    """加载 JSONL，并在集合层拒绝重复 ID 和解析错误。"""
    path = Path(path)
    cases = []
    seen = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValidationError(f"无法读取评测数据集: {path}") from exc
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"第 {line_number} 行不是合法 JSON") from exc
        case = EvaluationCase.from_dict(raw)
        if case.case_id in seen:
            raise ValidationError(f"重复样本 ID: {case.case_id}")
        seen.add(case.case_id)
        cases.append(case)
    if not cases:
        raise ValidationError("评测数据集不能为空")
    return cases


def validate_cases(cases: Iterable[EvaluationCase]) -> list[EvaluationCase]:
    """校验已构造样本集合的唯一 ID。"""
    result = list(cases)
    ids = [case.case_id for case in result]
    if len(ids) != len(set(ids)):
        raise ValidationError("重复样本 ID")
    if not result:
        raise ValidationError("评测数据集不能为空")
    return result
