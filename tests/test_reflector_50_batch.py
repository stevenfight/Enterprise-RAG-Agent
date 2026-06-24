# -*- coding: utf-8 -*-
"""反射器 50 组批量测试

从 test_reflector_data_50.json 加载测试数据，逐条运行并输出汇总报告。
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# 加载测试数据
DATA_FILE = os.path.join(os.path.dirname(__file__), "test_reflector_data_50.json")
with open(DATA_FILE, "r", encoding="utf-8") as f:
    test_data = json.load(f)

# 导入模块
from reflector import AnswerReflector

# ============================================================
# 分类汇总
# ============================================================
categories = {
    "hallucination_detection": {"name": "幻觉检测", "total": 0, "passed": 0, "failed": 0},
    "no_hallucination": {"name": "无幻觉", "total": 0, "passed": 0, "failed": 0},
    "source_completeness_high": {"name": "来源完整性 >= 0.9", "total": 0, "passed": 0, "failed": 0},
    "source_completeness_partial": {"name": "来源完整性 < 1.0", "total": 0, "passed": 0, "failed": 0},
    "auto_correct_enabled": {"name": "auto_correct 自动替换", "total": 0, "passed": 0, "failed": 0},
    "auto_correct_disabled": {"name": "auto_correct=False 仅警告", "total": 0, "passed": 0, "failed": 0},
}

failed_details = []

print("=" * 70)
print("反射器 50 组批量测试")
print(f"数据来源: {DATA_FILE}")
print(f"阈值: {test_data['hallucination_threshold']}")
print("=" * 70)

for case in test_data["test_cases"]:
    cat = case["category"]
    categories[cat]["total"] += 1
    exp = case["expected"]
    passed = True
    fail_reason = ""

    # 根据 category 选择构造函数参数
    if cat == "auto_correct_disabled":
        r = AnswerReflector(auto_correct=False)
    else:
        r = AnswerReflector(auto_correct=True)

    result = r.verify(
        answer=case["answer"],
        sources=case["sources"],
    )

    # --- 断言检查 ---

    # 1. has_hallucination
    if "has_hallucination" in exp:
        if result.has_hallucination != exp["has_hallucination"]:
            passed = False
            fail_reason = (f"has_hallucination: 期望 {exp['has_hallucination']}, "
                           f"实际 {result.has_hallucination}")

    # 2. hallucination_count
    if passed and "hallucination_count" in exp:
        if result.hallucination_count != exp["hallucination_count"]:
            passed = False
            fail_reason = (f"hallucination_count: 期望 {exp['hallucination_count']}, "
                           f"实际 {result.hallucination_count}")

    # 3. source_completeness 范围
    if passed and "source_completeness" in exp and "completeness_min" in exp:
        if result.source_completeness < exp["completeness_min"]:
            passed = False
            fail_reason = (f"source_completeness: {result.source_completeness:.4f} "
                           f"< 期望最小值 {exp['completeness_min']}")

    if passed and "source_completeness" in exp and "completeness_max" in exp:
        if result.source_completeness > exp["completeness_max"]:
            passed = False
            fail_reason = (f"source_completeness: {result.source_completeness:.4f} "
                           f"> 期望最大值 {exp['completeness_max']}")

    # 4. auto_correct 修正结果
    if passed and "auto_correct" in exp:
        if exp["auto_correct"] and "corrected_contains" in exp:
            if result.corrected_answer is None:
                passed = False
                fail_reason = "auto_correct=True 但 corrected_answer 为 None"
            elif exp["corrected_contains"] not in result.corrected_answer:
                passed = False
                fail_reason = (f"修正后答案不包含 '{exp['corrected_contains']}', "
                               f"实际: {result.corrected_answer[:80]}")

        if not exp["auto_correct"] and exp.get("corrected_answer_empty"):
            if result.corrected_answer and result.corrected_answer != "":
                passed = False
                fail_reason = (f"auto_correct=False 但产生了非空 corrected_answer: "
                               f"'{result.corrected_answer[:80]}'")

    # 记录结果
    if passed:
        categories[cat]["passed"] += 1
    else:
        categories[cat]["failed"] += 1
        failed_details.append({
            "id": case["id"],
            "category": cat,
            "description": case["description"],
            "reason": fail_reason,
        })

# ============================================================
# 输出汇总
# ============================================================
print("\n" + "=" * 70)
print("分类汇总")
print("=" * 70)

for key, cat in categories.items():
    status = "PASS" if cat["failed"] == 0 else "FAIL"
    pct = (cat["passed"] / max(cat["total"], 1)) * 100
    print(f"  [{status}] {cat['name']}: {cat['passed']}/{cat['total']} ({pct:.0f}%)")

total_passed = sum(c["passed"] for c in categories.values())
total_failed = sum(c["failed"] for c in categories.values())
total = total_passed + total_failed

print("\n" + "=" * 70)
print(f"总计: {total_passed} PASS, {total_failed} FAIL, {total} 项")
print("=" * 70)

if failed_details:
    print("\n失败详情:")
    for fd in failed_details:
        print(f"  [{fd['id']}] ({fd['category']}) {fd['description']}")
        print(f"         原因: {fd['reason']}")

# 退出码: 非零表示有失败
sys.exit(0 if total_failed == 0 else 1)
