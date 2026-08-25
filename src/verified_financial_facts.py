"""人工核验的财务比较事实注册表。"""


class VerifiedFinancialFactRegistry:
    """仅返回具备逐项官方年报来源的比较事实。"""

    _FACTS = (
        {
            "fact_id": "operating-revenue-2024-中国移动",
            "metric_key": "operating_revenue", "fiscal_year": 2024,
            "company_name": "中国移动", "value": 10408, "unit": "亿元",
            "source_file": "移动2024年度报告.pdf", "pages": [3],
            "excerpt": "2024 年，营业收入达到人民币 10,408 亿元。",
        },
        {
            "fact_id": "operating-revenue-2024-中国联通",
            "metric_key": "operating_revenue", "fiscal_year": 2024,
            "company_name": "中国联通", "value": 3896, "unit": "亿元",
            "source_file": "联通2024年度报告.pdf", "pages": [9],
            "excerpt": "2024年，中国联通营业收入稳健增长，达到人民币3,896亿元、同比提升4.6%。",
        },
        {
            "fact_id": "operating-revenue-2024-中国电信",
            "metric_key": "operating_revenue", "fiscal_year": 2024,
            "company_name": "中国电信", "value": 5236, "unit": "亿元",
            "source_file": "电信2024年度报告.pdf", "pages": [10, 11],
            "excerpt": "2024 年，公司营业收入为人民币 5,236 亿元，同比增长 3.1%。",
        },
    )

    def get_comparison(self, metric_key, fiscal_year, companies):
        """按完整公司集合返回同口径比较，缺少任一事实则明确不可用。"""
        requested_companies = list(dict.fromkeys(companies))
        items = [
            fact for fact in self._FACTS
            if fact["metric_key"] == metric_key
            and fact["fiscal_year"] == fiscal_year
            and fact["company_name"] in requested_companies
        ]
        if len(items) != len(requested_companies):
            return {"available": False, "items": []}

        items.sort(key=lambda fact: requested_companies.index(fact["company_name"]))
        return {"available": True, "metric_key": metric_key, "fiscal_year": fiscal_year, "unit": items[0]["unit"], "fact_ids": [item["fact_id"] for item in items], "items": items}

    def get_comparison_for_query(self, query):
        """仅为已登记的精确比较问题返回回答级事实。"""
        normalized_query = str(query).replace(" ", "")
        has_revenue = "营业收入" in normalized_query or "营收" in normalized_query
        has_all_companies = "三大运营商" in normalized_query or all(
            company in normalized_query
            for company in ("中国移动", "中国联通", "中国电信")
        )
        if "2024" not in normalized_query or not has_revenue or not has_all_companies:
            return {"available": False, "items": []}
        return self.get_comparison(
            metric_key="operating_revenue",
            fiscal_year=2024,
            companies=["中国移动", "中国联通", "中国电信"],
        )
