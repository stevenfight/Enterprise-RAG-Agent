# -*- coding: utf-8 -*-
"""全量测试一键运行脚本

自动运行项目中所有测试文件，汇总结果。

用法:
    python tests/run_all.py              # 运行全部
    python tests/run_all.py --skip-llm   # 跳过需要 LLM API 的测试
"""

import subprocess
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TESTS_DIR = Path(__file__).parent


# ============================================================
# 测试文件清单 (按类别分组)
# ============================================================
TEST_SUITES = [
    # 管道回归测试 (需要 LLM API)
    {
        "name": "管道回归 (tdd_all_optimizations)",
        "file": "tdd_all_optimizations.py",
        "category": "pipeline",
        "requires_llm": True,
    },

    # Agent TDD 测试 (不需要 LLM API)
    {
        "name": "Agent TDD - 工具系统",
        "file": "test_agent_tools.py",
        "category": "agent-tdd",
        "requires_llm": False,
    },
    {
        "name": "Agent TDD - 核心框架",
        "file": "test_agent_core.py",
        "category": "agent-tdd",
        "requires_llm": False,
    },
    {
        "name": "Agent TDD - 记忆系统",
        "file": "test_agent_memory.py",
        "category": "agent-tdd",
        "requires_llm": False,
    },
    {
        "name": "Agent TDD - 反思器",
        "file": "test_reflector.py",
        "category": "agent-tdd",
        "requires_llm": False,
    },

    # 内存安全 & 并发测试 (不需要 LLM API)
    {
        "name": "内存泄漏修复",
        "file": "test_memory_leak_fixes.py",
        "category": "memory-safety",
        "requires_llm": False,
    },
    {
        "name": "会话隔离验证",
        "file": "test_memory_isolation_demo.py",
        "category": "memory-safety",
        "requires_llm": False,
    },
    {
        "name": "多轮追问记忆",
        "file": "test_agent_memory_multiturn.py",
        "category": "memory-safety",
        "requires_llm": False,
    },
    {
        "name": "中断恢复",
        "file": "test_agent_memory_interrupt.py",
        "category": "memory-safety",
        "requires_llm": False,
    },
    {
        "name": "并发安全",
        "file": "test_agent_memory_concurrent.py",
        "category": "memory-safety",
        "requires_llm": False,
    },
    {
        "name": "Checklist边界",
        "file": "test_boundary_checklist.py",
        "category": "memory-safety",
        "requires_llm": False,
    },

    # 集成测试 (需要 LLM API)
    {
        "name": "端到端集成",
        "file": "test_e2e_agent.py",
        "category": "integration",
        "requires_llm": False,
    },
]


def run_test(filepath):
    """运行单个测试文件，返回 (passed, failed, output_lines)"""
    cmd = [sys.executable, str(filepath)]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        # 解析输出的最后几行找汇总（合并 stdout + stderr，兼容 unittest 汇总输出到 stderr 的情况）
        output = result.stdout + "\n" + result.stderr
        lines = output.strip().split("\n")
        passed = 0
        failed = 0

        for line in lines:
            if "PASS," in line and "FAIL" in line:
                # 格式: "测试汇总: 10 PASS, 2 FAIL, 共 12 项"
                import re
                m = re.search(r'(\d+)\s*PASS.*?(\d+)\s*FAIL', line)
                if m:
                    passed = int(m.group(1))
                    failed = int(m.group(2))
                break
        else:
            # 回退：兼容标准 unittest 输出格式
            import re
            total = 0
            for line in lines:
                m = re.search(r'Ran\s+(\d+)\s+tests?', line)
                if m:
                    total = int(m.group(1))
                    break
            if total > 0:
                # 检查是否全部通过
                ok = any("OK" in line for line in lines[-3:])
                if ok:
                    passed = total
                    failed = 0
                else:
                    # 尝试解析失败数
                    for line in lines:
                        m = re.search(r'failures=(\d+)', line)
                        if m:
                            failed = int(m.group(1))
                            passed = total - failed
                            break
                        m = re.search(r'errors=(\d+)', line)
                        if m:
                            errors = int(m.group(1))
                            failed = max(failed, errors)
                            passed = total - failed
                            break
                    if passed == 0 and failed == 0:
                        failed = total

        return passed, failed, lines
    except subprocess.TimeoutExpired:
        return 0, 0, ["[TIMEOUT] 测试超时 (>120s)"]
    except Exception as e:
        return 0, 0, [f"[ERROR] {e}"]


def main():
    skip_llm = "--skip-llm" in sys.argv

    print("=" * 70)
    print("全量测试一键运行")
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"测试目录:   {TESTS_DIR}")
    if skip_llm:
        print("模式:       跳过 LLM 测试")
    print("=" * 70)

    total_passed = 0
    total_failed = 0
    suite_results = []

    for suite in TEST_SUITES:
        if skip_llm and suite["requires_llm"]:
            suite_results.append({
                "name": suite["name"],
                "passed": 0,
                "failed": 0,
                "skipped": True,
            })
            print(f"\n{'─' * 50}")
            print(f"[跳过] {suite['name']} (需要 LLM API)")
            continue

        filepath = TESTS_DIR / suite["file"]
        if not filepath.exists():
            print(f"\n{'─' * 50}")
            print(f"[缺失] {suite['name']} - 文件不存在: {filepath}")
            continue

        print(f"\n{'─' * 50}")
        print(f"[运行] {suite['name']}")

        p, f, lines = run_test(filepath)
        total_passed += p
        total_failed += f
        suite_results.append({
            "name": suite["name"],
            "passed": p,
            "failed": f,
            "skipped": False,
        })

        # 显示最后几行
        for line in lines[-5:]:
            if line.strip():
                print(f"  {line.strip()}")

    # ============================================================
    # 汇总表
    # ============================================================
    print("\n" + "=" * 70)
    print("全量测试汇总")
    print("=" * 70)

    for r in suite_results:
        if r["skipped"]:
            status = "[跳过]"
        elif r["failed"] == 0:
            status = "[PASS]"
        else:
            status = f"[{r['failed']} FAIL]"
        print(f"  {status:12s} {r['name']}")

    total = total_passed + total_failed
    pass_rate = (total_passed / max(total, 1)) * 100
    print(f"\n  合计: {total_passed} PASS, {total_failed} FAIL, 共 {total} 项")
    print(f"  通过率: {pass_rate:.1f}%")
    print("=" * 70)

    return 1 if total_failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
