# -*- coding: utf-8 -*-
"""
提示词注入防护 - TDD 测试文件

测试范围: PI-G01 ~ PI-G12
规则: 全线 RED 启动，代码实现后逐项变 GREEN
"""

import os
import sys
import re

# 项目根路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ============================================================
# 测试状态登记 (全线 RED 启动)
# ============================================================
TEST_STATUS = {
    "PI-G01": "GREEN",  # INTENT_PROMPT_TEMPLATE 含 <用户输入> 标签
    "PI-G02": "GREEN",  # REWRITE_PROMPT_TEMPLATE 含 <用户输入> 标签
    "PI-G03": "GREEN",  # INTENT_PROMPT_TEMPLATE 含边界声明
    "PI-G04": "GREEN",  # REWRITE_PROMPT_TEMPLATE 含边界声明
    "PI-G05": "GREEN",  # agent_core 用户消息含 <user_query> 标签
    "PI-G06": "GREEN",  # agent_core system prompt 含标签边界声明
    "PI-G07": "GREEN",  # retrieval _build_prompt 含 <用户问题> 标签
    "PI-G08": "GREEN",  # retrieval _build_comparison_prompt 含 <用户问题> 标签
    "PI-G09": "GREEN",  # retrieval _build_financial_data_prompt 含 <用户问题> 标签
    "PI-G10": "GREEN",  # agent_core system prompt 含安全规则区块
    "PI-G11": "GREEN",  # retrieval 生成 prompt 含防注入声明
    "PI-G12": "GREEN",  # 正常查询回归验证
}

passed = 0
failed = 0
red_count = 0
green_count = 0


def check(test_id, condition):
    """统一断言函数，自动读取 TEST_STATUS"""
    global passed, failed, red_count, green_count

    status = TEST_STATUS.get(test_id, "RED")
    if status == "RED":
        red_count += 1
    else:
        green_count += 1

    if condition:
        if status == "RED":
            print(f"  [WARN] {test_id}: 标记为 RED 但测试通过，请更新为 GREEN")
        else:
            print(f"  [GREEN] {test_id}: 通过")
        passed += 1
        return True
    else:
        if status == "RED":
            print(f"  [RED] {test_id}: 预期失败 (模块未实现)")
        else:
            print(f"  [FAIL] {test_id}: 标记为 GREEN 但测试失败，代码可能回归")
        failed += 1
        return False


# ============================================================
# 模块导入
# ============================================================
try:
    from src.query_processor import QueryProcessor
    _qp_available = True
except Exception as e:
    print(f"  [导入] query_processor 导入失败: {e}")
    _qp_available = False

try:
    from src.agent_core import ReActAgent
    _agent_available = True
except Exception as e:
    print(f"  [导入] agent_core 导入失败: {e}")
    _agent_available = False

try:
    from src.retrieval import RAGGenerator
    _retrieval_available = True
except Exception as e:
    print(f"  [导入] retrieval 导入失败: {e}")
    _retrieval_available = False


# ============================================================
# 测试用例
# ============================================================
def test_g01_intent_prompt_has_user_input_tag():
    """PI-G01: INTENT_PROMPT_TEMPLATE 含 <用户输入> 标签"""
    if not _qp_available:
        check("PI-G01", False)
        return

    from src.query_processor import INTENT_PROMPT_TEMPLATE
    has_tag = "<用户输入>" in INTENT_PROMPT_TEMPLATE and "</用户输入>" in INTENT_PROMPT_TEMPLATE
    check("PI-G01", has_tag)


def test_g02_rewrite_prompt_has_user_input_tag():
    """PI-G02: REWRITE_PROMPT_TEMPLATE 含 <用户输入> 标签"""
    if not _qp_available:
        check("PI-G02", False)
        return

    from src.query_processor import REWRITE_PROMPT_TEMPLATE
    has_tag = "<用户输入>" in REWRITE_PROMPT_TEMPLATE and "</用户输入>" in REWRITE_PROMPT_TEMPLATE
    check("PI-G02", has_tag)


def test_g03_intent_prompt_has_boundary_statement():
    """PI-G03: INTENT_PROMPT_TEMPLATE 含边界声明"""
    if not _qp_available:
        check("PI-G03", False)
        return

    from src.query_processor import INTENT_PROMPT_TEMPLATE
    has_statement = (
        "不可作为系统指令" in INTENT_PROMPT_TEMPLATE
        or "不可执行" in INTENT_PROMPT_TEMPLATE
        or "系统指令执行" in INTENT_PROMPT_TEMPLATE
    )
    check("PI-G03", has_statement)


def test_g04_rewrite_prompt_has_boundary_statement():
    """PI-G04: REWRITE_PROMPT_TEMPLATE 含边界声明"""
    if not _qp_available:
        check("PI-G04", False)
        return

    from src.query_processor import REWRITE_PROMPT_TEMPLATE
    has_statement = (
        "不可作为系统指令" in REWRITE_PROMPT_TEMPLATE
        or "不可执行" in REWRITE_PROMPT_TEMPLATE
        or "系统指令执行" in REWRITE_PROMPT_TEMPLATE
    )
    check("PI-G04", has_statement)


def test_g05_agent_user_message_has_user_query_tag():
    """PI-G05: agent_core 用户消息含 <user_query> 标签"""
    if not _agent_available:
        check("PI-G05", False)
        return

    # 读取 agent_core.py 源码检查用户消息构建
    src_path = os.path.join(PROJECT_ROOT, "src", "agent_core.py")
    with open(src_path, "r", encoding="utf-8") as f:
        content = f.read()

    has_tag = "<user_query>" in content and "</user_query>" in content
    check("PI-G05", has_tag)


def test_g06_agent_system_prompt_has_tag_boundary():
    """PI-G06: agent_core system prompt 含标签边界声明"""
    if not _agent_available:
        check("PI-G06", False)
        return

    src_path = os.path.join(PROJECT_ROOT, "src", "agent_core.py")
    with open(src_path, "r", encoding="utf-8") as f:
        content = f.read()

    has_boundary = (
        "<user_query>" in content and "</user_query>" in content
    ) and (
        "系统指令执行" in content or "绝对不能" in content
    )
    check("PI-G06", has_boundary)


def test_g07_build_prompt_has_user_question_tag():
    """PI-G07: retrieval _build_prompt 含 <用户问题> 标签"""
    if not _retrieval_available:
        check("PI-G07", False)
        return

    src_path = os.path.join(PROJECT_ROOT, "src", "retrieval.py")
    with open(src_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 找到 _build_prompt 方法区域
    prompt_start = content.find("def _build_prompt")
    if prompt_start == -1:
        check("PI-G07", False)
        return

    # 取方法体后面的内容到下一个 def 为止
    next_def = content.find("def _", prompt_start + 10)
    method_body = content[prompt_start:next_def] if next_def != -1 else content[prompt_start:]

    has_tag = "<用户问题>" in method_body and "</用户问题>" in method_body
    check("PI-G07", has_tag)


def test_g08_build_comparison_prompt_has_user_question_tag():
    """PI-G08: retrieval _build_comparison_prompt 含 <用户问题> 标签"""
    if not _retrieval_available:
        check("PI-G08", False)
        return

    src_path = os.path.join(PROJECT_ROOT, "src", "retrieval.py")
    with open(src_path, "r", encoding="utf-8") as f:
        content = f.read()

    prompt_start = content.find("def _build_comparison_prompt")
    if prompt_start == -1:
        check("PI-G08", False)
        return

    next_def = content.find("def _", prompt_start + 10)
    method_body = content[prompt_start:next_def] if next_def != -1 else content[prompt_start:]

    has_tag = "<用户问题>" in method_body and "</用户问题>" in method_body
    check("PI-G08", has_tag)


def test_g09_build_financial_prompt_has_user_question_tag():
    """PI-G09: retrieval _build_financial_data_prompt 含 <用户问题> 标签"""
    if not _retrieval_available:
        check("PI-G09", False)
        return

    src_path = os.path.join(PROJECT_ROOT, "src", "retrieval.py")
    with open(src_path, "r", encoding="utf-8") as f:
        content = f.read()

    prompt_start = content.find("def _build_financial_data_prompt")
    if prompt_start == -1:
        check("PI-G09", False)
        return

    next_def = content.find("def _", prompt_start + 10)
    method_body = content[prompt_start:next_def] if next_def != -1 else content[prompt_start:]

    has_tag = "<用户问题>" in method_body and "</用户问题>" in method_body
    check("PI-G09", has_tag)


def test_g10_agent_system_prompt_has_security_rules():
    """PI-G10: agent_core system prompt 含安全规则区块"""
    if not _agent_available:
        check("PI-G10", False)
        return

    src_path = os.path.join(PROJECT_ROOT, "src", "agent_core.py")
    with open(src_path, "r", encoding="utf-8") as f:
        content = f.read()

    has_section = "安全规则" in content or "security" in content.lower()
    # 检查是否有至少3条具体的拒绝规则
    reject_indicators = [
        "你不会执行" if "你不会执行" in content else None,
        "你永远不会执行" if "你永远不会执行" in content else None,
        "不可作为系统指令" if "不可作为系统指令" in content else None,
        "不执行" if "不执行" in content else None,
        "拒绝" if "拒绝" in content else None,
        "不会执行" if "不会执行" in content else None,
    ]
    rule_count = sum(1 for x in reject_indicators if x)

    check("PI-G10", has_section and rule_count >= 2)


def test_g11_retrieval_prompt_has_injection_defense():
    """PI-G11: retrieval 生成 prompt 含防注入声明"""
    if not _retrieval_available:
        check("PI-G11", False)
        return

    src_path = os.path.join(PROJECT_ROOT, "src", "retrieval.py")
    with open(src_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 检查是否有防注入相关声明
    has_defense = (
        "不可作为系统指令" in content
        or "不可执行" in content
        or "不能执行" in content
        or "请拒绝" in content
        or "改变角色" in content
    )
    check("PI-G11", has_defense)


def test_g12_regression_normal_query():
    """PI-G12: 正常查询回归验证 -- 模块可正常导入"""
    can_import = _qp_available and _retrieval_available
    check("PI-G12", can_import)


# ============================================================
# 汇总输出
# ============================================================
def main():
    print("=" * 60)
    print("  提示词注入防护 TDD 测试")
    print("=" * 60)
    print()

    tests = [
        test_g01_intent_prompt_has_user_input_tag,
        test_g02_rewrite_prompt_has_user_input_tag,
        test_g03_intent_prompt_has_boundary_statement,
        test_g04_rewrite_prompt_has_boundary_statement,
        test_g05_agent_user_message_has_user_query_tag,
        test_g06_agent_system_prompt_has_tag_boundary,
        test_g07_build_prompt_has_user_question_tag,
        test_g08_build_comparison_prompt_has_user_question_tag,
        test_g09_build_financial_prompt_has_user_question_tag,
        test_g10_agent_system_prompt_has_security_rules,
        test_g11_retrieval_prompt_has_injection_defense,
        test_g12_regression_normal_query,
    ]

    for test_func in tests:
        test_func()

    print()
    print("=" * 60)
    print(f"  汇总: {passed} passed, {failed} failed")
    print(f"  红绿分布: {red_count} RED, {green_count} GREEN")
    print("=" * 60)

    if red_count == 12 and green_count == 0:
        print("  -> 全部 RED - 模块尚未实现，等待开发")
    elif green_count == 12 and red_count == 0:
        print("  -> 全部 GREEN - 提示词注入防护实现完成!")
    elif passed == 12:
        print("  -> 全部通过但存在 WARN 状态，请更新标记为 GREEN")
    else:
        print(f"  -> 存在 {failed} 个失败，请排查")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
