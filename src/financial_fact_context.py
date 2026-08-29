# -*- coding: utf-8 -*-
"""FinancialFact 的期间、口径、来源和修订版本领域实体。"""

from dataclasses import dataclass
from datetime import date


def _require_identifier(field_name: str, value: str) -> str:
    """只接受非空且不含控制字符的稳定标识。"""
    if not isinstance(value, str) or not value.strip() or any(ord(char) < 32 for char in value):
        raise ValueError(f"{field_name} 必须是非空稳定标识")
    return value


@dataclass(frozen=True)
class FinancialPeriod:
    """财务事实的明确报告期间，不从标签猜测日期范围。"""

    period_id: str
    period_start: date
    period_end: date
    fiscal_year: int
    period_type: str

    @classmethod
    def create(
        cls,
        *,
        period_id: str,
        period_start: date,
        period_end: date,
        fiscal_year: int,
        period_type: str,
    ) -> "FinancialPeriod":
        """创建年度、半年度或季度期间，并验证日期范围。"""
        _require_identifier("period_id", period_id)
        if type(period_start) is not date or type(period_end) is not date:
            raise ValueError("期间起止日期必须是 date")
        if period_start > period_end:
            raise ValueError("期间起止日期无效")
        if type(fiscal_year) is not int or fiscal_year < 1900 or fiscal_year > 9999:
            raise ValueError("fiscal_year 必须是四位年份")
        if period_type not in {"annual", "half_year", "quarter"}:
            raise ValueError("period_type 必须是 annual、half_year 或 quarter")
        if period_type == "annual" and not 360 <= (period_end - period_start).days <= 371:
            raise ValueError("annual 期间必须覆盖合理的完整年度跨度")
        if period_end.year != fiscal_year:
            raise ValueError("期间结束年份必须等于 fiscal_year")
        return cls(period_id, period_start, period_end, fiscal_year, period_type)


@dataclass(frozen=True)
class FinancialScope:
    """财务口径与审计状态，不把集团和母公司混为同一事实。"""

    scope_id: str
    consolidation: str
    accounting_standard: str
    audited: bool

    @classmethod
    def create(
        cls,
        *,
        scope_id: str,
        consolidation: str,
        accounting_standard: str,
        audited: bool,
    ) -> "FinancialScope":
        """创建受限口径枚举，阻止未知口径静默进入比较。"""
        _require_identifier("scope_id", scope_id)
        if consolidation not in {"consolidated", "parent_company", "continuing_operations"}:
            raise ValueError("consolidation 必须是已支持口径")
        _require_identifier("accounting_standard", accounting_standard)
        if type(audited) is not bool:
            raise ValueError("audited 必须是布尔值")
        return cls(scope_id, consolidation, accounting_standard, audited)


@dataclass(frozen=True)
class FinancialFactSource:
    """指向不可变文档版本的来源证据，页码始终是 PDF 物理页。"""

    source_id: str
    logical_document_id: str
    document_version_id: str
    source_file: str
    physical_pages: tuple[int, ...]
    excerpt: str
    source_type: str
    authority_level: str

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        logical_document_id: str,
        document_version_id: str,
        source_file: str,
        physical_pages: tuple[int, ...],
        excerpt: str,
        source_type: str,
        authority_level: str,
    ) -> "FinancialFactSource":
        """创建一手或二手来源，不允许缺失文档版本或页码。"""
        for name, value in {
            "source_id": source_id,
            "logical_document_id": logical_document_id,
            "document_version_id": document_version_id,
            "source_file": source_file,
            "excerpt": excerpt,
        }.items():
            _require_identifier(name, value)
        if (
            not isinstance(physical_pages, tuple)
            or not physical_pages
            or any(type(page) is not int or page <= 0 for page in physical_pages)
            or len(set(physical_pages)) != len(physical_pages)
        ):
            raise ValueError("physical_pages 必须是唯一的正整数元组")
        if source_type not in {"annual_report", "interim_report", "filing", "secondary"}:
            raise ValueError("source_type 必须是已支持来源类型")
        if authority_level not in {"primary", "secondary"}:
            raise ValueError("authority_level 必须是 primary 或 secondary")
        return cls(
            source_id,
            logical_document_id,
            document_version_id,
            source_file,
            physical_pages,
            excerpt,
            source_type,
            authority_level,
        )


@dataclass(frozen=True)
class FinancialFactRevision:
    """不可变事实版本关系，修订只能通过新版本表达。"""

    fact_version_id: str
    fact_id: str
    supersedes_fact_version_id: str | None

    @classmethod
    def create(
        cls,
        *,
        fact_version_id: str,
        fact_id: str,
        supersedes_fact_version_id: str | None = None,
    ) -> "FinancialFactRevision":
        """创建事实版本；禁止新版本引用自身为前序版本。"""
        _require_identifier("fact_version_id", fact_version_id)
        _require_identifier("fact_id", fact_id)
        if supersedes_fact_version_id is not None:
            _require_identifier("supersedes_fact_version_id", supersedes_fact_version_id)
            if supersedes_fact_version_id == fact_version_id:
                raise ValueError("supersedes_fact_version_id 不能指向自身")
        return cls(fact_version_id, fact_id, supersedes_fact_version_id)
