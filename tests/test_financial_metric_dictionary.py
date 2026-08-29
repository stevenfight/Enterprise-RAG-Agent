"""B1.2 金融指标词典与别名映射测试。"""

import pytest


def test_metric_dictionary_resolves_only_approved_operating_revenue_aliases():
    from src.financial_metric_dictionary import FinancialMetricDictionary

    dictionary = FinancialMetricDictionary.default()

    assert dictionary.resolve("营业收入") == "operating_revenue"
    assert dictionary.resolve(" 营收 ") == "operating_revenue"
    assert dictionary.resolve("operating_revenue") == "operating_revenue"


@pytest.mark.parametrize("label", ["主营业务收入", "服务收入", "收入"])
def test_metric_dictionary_does_not_merge_ambiguous_revenue_like_labels(label):
    from src.financial_metric_dictionary import FinancialMetricDictionary, UnknownFinancialMetricError

    with pytest.raises(UnknownFinancialMetricError):
        FinancialMetricDictionary.default().resolve(label)


def test_metric_dictionary_rejects_alias_assigned_to_multiple_metrics():
    from src.financial_metric_dictionary import FinancialMetricDefinition, FinancialMetricDictionary

    with pytest.raises(ValueError, match="别名"):
        FinancialMetricDictionary(
            [
                FinancialMetricDefinition("metric_a", ("共同别名",)),
                FinancialMetricDefinition("metric_b", ("共同别名",)),
            ]
        )
