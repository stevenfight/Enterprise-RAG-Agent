# -*- coding: utf-8 -*-
"""旧 VerifiedFinancialFactRegistry 到 V7 FinancialFact 的兼容适配。"""

from decimal import Decimal

from .financial_fact import FinancialFact
from .financial_fact_normalizer import normalize_amount_to_yuan
from .financial_fact_repository import FinancialFactRepository, FinancialFactSaveResult


class FinancialFactRegistryAdapter:
    """只迁移旧注册表已登记的事实，并保持比较响应契约。"""

    def __init__(
        self,
        *,
        legacy_registry,
        repository: FinancialFactRepository,
        calculation_repository=None,
        conflict_repository=None,
    ) -> None:
        self.legacy_registry = legacy_registry
        self.repository = repository
        # 注入公式与冲突仓储后，比较响应才追加声明级证据可选载荷。
        self.calculation_repository = calculation_repository
        self.conflict_repository = conflict_repository

    def import_registered_revenue_facts(self) -> tuple[FinancialFactSaveResult, ...]:
        """将旧注册表的已核验营业收入写入 V7，不发现或猜测新事实。"""
        results: list[FinancialFactSaveResult] = []
        for item in self.legacy_registry._FACTS:
            if item["metric_key"] != "operating_revenue":
                continue
            normalized = normalize_amount_to_yuan(item["value"], item["unit"])
            fact = FinancialFact.create(
                fact_id=item["fact_id"],
                metric_key=item["metric_key"],
                company_name=item["company_name"],
                raw_value=item["value"],
                raw_unit=item["unit"],
                normalized_value=normalized.normalized_value,
                normalized_unit=normalized.normalized_unit,
                currency="CNY",
                period=f"FY{item['fiscal_year']}",
                scope="consolidated",
                source_file=item["source_file"],
                physical_pages=tuple(item["pages"]),
                excerpt=item["excerpt"],
            )
            results.append(self.repository.save(fact))
        return tuple(results)

    def get_comparison(self, metric_key, fiscal_year, companies):
        """仅为 legacy 已登记集合从 V7 事实重建兼容响应。"""
        legacy_comparison = self.legacy_registry.get_comparison(
            metric_key,
            fiscal_year,
            companies,
        )
        if not legacy_comparison.get("available"):
            return {"available": False, "items": []}
        items = []
        facts = []
        for legacy_item in legacy_comparison["items"]:
            fact = self.repository.get(legacy_item["fact_id"])
            if fact is None:
                return {"available": False, "items": []}
            facts.append(fact)
            items.append(
                {
                    "fact_id": fact.fact_id,
                    "metric_key": fact.metric_key,
                    "fiscal_year": int(fact.period.removeprefix("FY")),
                    "company_name": fact.company_name,
                    "value": self._legacy_value(fact.raw_value),
                    "unit": fact.raw_unit,
                    "source_file": fact.source_file,
                    "pages": list(fact.physical_pages),
                    "excerpt": fact.excerpt,
                }
            )
        response = {
            "available": True,
            "metric_key": metric_key,
            "fiscal_year": fiscal_year,
            "unit": items[0]["unit"],
            "fact_ids": [item["fact_id"] for item in items],
            "items": items,
        }
        if self.calculation_repository is None or self.conflict_repository is None:
            return response
        return self._with_claim_evidence(response, facts)

    def _with_claim_evidence(self, response, facts):
        """在兼容响应上追加声明级证据明细可选载荷，不改写任何旧字段。"""
        enriched_items = [
            {
                **item,
                "raw_value": str(fact.raw_value),
                "raw_unit": fact.raw_unit,
                "normalized_value": str(fact.normalized_value),
                "normalized_unit": fact.normalized_unit,
            }
            for item, fact in zip(response["items"], facts)
        ]
        fact_ids = tuple(response["fact_ids"])
        calculations = [
            {
                "calculation_id": calculation_id,
                "operation": result.operation,
                "formula_version": result.formula_version,
                "input_fact_ids": list(result.input_fact_ids),
                "details": result.details,
            }
            for calculation_id, result in self.calculation_repository.list_by_fact_ids(fact_ids)
        ]
        conflicts = [
            {
                "conflict_id": conflict_id,
                "status": decision.status,
                "conflict_type": decision.conflict_type,
                "fact_ids": list(decision.fact_ids),
                "relative_difference": decision.relative_difference,
                "preferred_fact_id": decision.preferred_fact_id,
            }
            for conflict_id, decision in self.conflict_repository.list_by_fact_ids(fact_ids)
        ]
        return {
            **response,
            "items": enriched_items,
            "calculations": calculations,
            "conflicts": conflicts,
        }

    def get_comparison_for_query(self, query):
        """沿用 legacy 的受限问题识别，但从 V7 事实重建结果。"""
        legacy_comparison = self.legacy_registry.get_comparison_for_query(query)
        if not legacy_comparison.get("available"):
            return {"available": False, "items": []}
        return self.get_comparison(
            legacy_comparison["metric_key"],
            legacy_comparison["fiscal_year"],
            [item["company_name"] for item in legacy_comparison["items"]],
        )

    def build_comparison_answer(self, comparison):
        """复用 legacy 的纯展示格式化逻辑，不重新读取 legacy 事实。"""
        return self.legacy_registry.build_comparison_answer(comparison)

    def project_chart_artifact(self, artifact):
        """以 V7 投影结果覆盖已登记比较图表，保持旧图表响应字段。"""
        title = str(artifact.get("title", ""))
        labels = artifact.get("labels") or []
        comparison = self.get_comparison_for_query(f"{title}{''.join(map(str, labels))}")
        if not comparison.get("available"):
            return artifact

        items = comparison["items"]
        projected = dict(artifact)
        if artifact.get("chart_type") == "table":
            projected["columns"] = ["运营商", "2024年营业收入（亿元）", "年报页码"]
            projected["rows"] = [
                [
                    item["company_name"],
                    f"{item['value']:,}",
                    "、".join(f"P{page}" for page in item["pages"]),
                ]
                for item in items
            ]
            return projected

        projected["labels"] = [item["company_name"] for item in items]
        projected["values"] = [item["value"] for item in items]
        projected["data"] = {
            item["company_name"]: item["value"]
            for item in items
        }
        projected["ylabel"] = "营业收入（亿元）"
        return projected

    @staticmethod
    def _legacy_value(value: Decimal) -> int | float:
        """保持旧比较响应的整数金额格式。"""
        if value == value.to_integral_value():
            return int(value)
        return float(value)
