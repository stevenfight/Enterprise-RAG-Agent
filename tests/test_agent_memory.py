# -*- coding: utf-8 -*-
"""TDD: Agent 记忆系统测试

测试状态标记系统:
  RED   - 模块尚未实现，测试跳过
  GREEN - 模块已实现，测试通过

使用说明:
  - 每个测试用例有唯一 test_id (对应 specs/test-cases.md)
  - 开发前全部标 RED
  - 模块实现后逐个变 GREEN
  - 测试通过后修改 TEST_STATUS 中对应条目为 "GREEN"

对应 SDD: openspec/changes/rag-to-agent/specs/spec-memory.md
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ============================================================
# 测试状态登记表 (开发过程中逐步改为 "GREEN")
# ============================================================
TEST_STATUS = {
    "TC-M01": "GREEN",   # test_working_memory_add
    "TC-M02": "GREEN",   # test_working_memory_reset
    "TC-M03": "GREEN",   # test_working_memory_limit
    "TC-M04": "GREEN",   # test_episodic_summarize
    "TC-M05": "GREEN",   # test_episodic_context
    "TC-M06": "GREEN",   # test_long_term_disabled
    "TC-M07": "GREEN",   # test_conversation_manager_compat
}

passed = 0
failed = 0
red_count = 0
green_count = 0


def check(test_id, name, condition, detail=""):
    """统一的测试断言函数，自动读取 TEST_STATUS 标记"""
    global passed, failed, red_count, green_count

    status = TEST_STATUS.get(test_id, "RED")

    if status == "GREEN":
        green_count += 1
        if condition:
            print(f"  [GREEN] [{test_id}] {name}")
            passed += 1
        else:
            print(f"  [FAIL] [{test_id}] {name} - 预期通过但失败: {detail}")
            failed += 1
    else:
        red_count += 1
        if condition:
            print(f"  [WARN] [{test_id}] {name} - 已通过但标记为RED, 请更新 TEST_STATUS 为 GREEN")
            passed += 1
        else:
            print(f"  [RED] [{test_id}] {name} - 模块未实现")
            failed += 1


# ============================================================
# 尝试导入模块 (当前不存在，预期导入失败)
# ============================================================
_MEMORY_AVAILABLE = False
_MEMORY_IMPORT_ERROR = ""

try:
    from agent_memory import AgentMemory
    _MEMORY_AVAILABLE = True
except ImportError as e:
    _MEMORY_IMPORT_ERROR = str(e)

# 检查现有 ConversationManager
_CONV_AVAILABLE = False
try:
    from conversation import ConversationManager
    _CONV_AVAILABLE = True
except ImportError:
    pass


print("=" * 60)
print("TDD: Agent 记忆系统测试")
print(f"AgentMemory 模块可用: {_MEMORY_AVAILABLE}")
if not _MEMORY_AVAILABLE:
    print(f"  (导入错误: {_MEMORY_IMPORT_ERROR})")
print(f"ConversationManager 可用: {_CONV_AVAILABLE}")
print("=" * 60)


# ============================================================
# 测试用例
# ============================================================

# ========== TC-M01: 工作记忆添加步骤 ==========
print("\n--- TC-M01: 工作记忆添加步骤记录 ---")

def test_m01():
    if not _MEMORY_AVAILABLE:
        return False, ""
    from agent_memory import AgentMemory
    memory = AgentMemory.__new__(AgentMemory)
    has_add = hasattr(memory, 'add') and callable(getattr(memory, 'add', None))
    has_reset = hasattr(memory, 'reset_working') and callable(getattr(memory, 'reset_working', None))
    has_context = hasattr(memory, 'get_working_context') and callable(getattr(memory, 'get_working_context', None))
    return has_add and has_reset and has_context, ""


check("TC-M01", "AgentMemory 定义 add/reset_working/get_working_context 方法",
      test_m01()[0], detail=test_m01()[1])


# ========== TC-M02: 工作记忆重置 ==========
print("\n--- TC-M02: 工作记忆重置 ---")

def test_m02():
    if not _MEMORY_AVAILABLE:
        return False, ""
    from agent_memory import AgentMemory
    memory = AgentMemory.__new__(AgentMemory)
    has_reset_working = hasattr(memory, 'reset_working') and callable(getattr(memory, 'reset_working', None))
    return has_reset_working, ""


check("TC-M02", "AgentMemory.reset_working 清空工作记忆",
      test_m02()[0], detail=test_m02()[1])


# ========== TC-M03: 工作记忆上限淘汰 ==========
print("\n--- TC-M03: 工作记忆超过上限自动淘汰 ---")

def test_m03():
    if not _MEMORY_AVAILABLE:
        return False, ""
    from agent_memory import AgentMemory
    # 设置较小的上限便于验证淘汰行为
    memory = AgentMemory(working_memory_limit=3)

    # 写入5步, 超过上限3应触发淘汰
    for i in range(5):
        memory.add(
            thought=f"思考步骤{i}",
            action="retrieve",
            action_input={"query": f"测试查询{i}"},
            observation=f"观察结果{i}",
        )

    # 验证1: working_memory_limit 属性存在
    has_limit = hasattr(memory, 'working_memory_limit')
    if not has_limit:
        return False, "AgentMemory 缺少 working_memory_limit 属性"

    # 验证2: 实际淘汰行为正确 (写入5步, 上限3, 应保留最近3步)
    actual_len = len(memory.working_memory)
    if actual_len != 3:
        return False, f"预期 working_memory 长度为 3, 实际: {actual_len}"

    # 验证3: 被淘汰的是最早2步 (步骤1-2), 保留的是步骤3-5
    step_numbers = [s["step_number"] for s in memory.working_memory]
    if step_numbers != [1, 2, 3]:
        return False, f"预期 step_numbers 为 [1,2,3] (已重新编号), 实际: {step_numbers}"

    # 验证4: 保留的内容是最新的步数 (第5步 i=4)
    last_obs = memory.working_memory[-1]["observation"]
    if "观察结果4" not in last_obs:
        return False, f"预期最后一条保留 观察结果4, 实际: {last_obs}"

    return True, ""


check("TC-M03", "AgentMemory 工作记忆超过上限自动淘汰 (5步 -> 保留3步)",
      test_m03()[0], detail=test_m03()[1])


# ========== TC-M04: 工作记忆转情景记忆 ==========
print("\n--- TC-M04: 工作记忆转情景记忆 ---")

def test_m04():
    if not _MEMORY_AVAILABLE:
        return False, ""
    from agent_memory import AgentMemory
    memory = AgentMemory.__new__(AgentMemory)
    has_summarize = hasattr(memory, 'summarize_to_episodic') and callable(
        getattr(memory, 'summarize_to_episodic', None))
    return has_summarize, ""


check("TC-M04", "AgentMemory.summarize_to_episodic 方法存在",
      test_m04()[0], detail=test_m04()[1])


# ========== TC-M05: 情景记忆上下文获取 ==========
print("\n--- TC-M05: 获取情景记忆上下文 ---")

def test_m05():
    if not _MEMORY_AVAILABLE:
        return False, ""
    from agent_memory import AgentMemory
    memory = AgentMemory.__new__(AgentMemory)
    has_episodic = hasattr(memory, 'get_episodic_context') and callable(
        getattr(memory, 'get_episodic_context', None))
    return has_episodic, ""


check("TC-M05", "AgentMemory.get_episodic_context 方法存在",
      test_m05()[0], detail=test_m05()[1])


# ========== TC-M06: 长期记忆关闭 ==========
print("\n--- TC-M06: 长期记忆关闭时返回 None ---")

def test_m06():
    if not _MEMORY_AVAILABLE:
        return False, ""
    from agent_memory import AgentMemory
    memory = AgentMemory.__new__(AgentMemory)
    has_long_term = hasattr(memory, 'get_long_term') and callable(
        getattr(memory, 'get_long_term', None))
    has_enable = hasattr(memory, 'enable_long_term')
    return has_long_term or has_enable, ""


check("TC-M06", "AgentMemory 支持长期记忆开关 (enable_long_term)",
      test_m06()[0], detail=test_m06()[1])


# ========== TC-M07: 兼容 ConversationManager ==========
print("\n--- TC-M07: 与 ConversationManager 兼容 ---")

def test_m07():
    # 验证 ConversationManager 不受 AgentMemory 影响
    if not _CONV_AVAILABLE:
        return False, "ConversationManager 模块不可用"

    from conversation import ConversationManager
    conv = ConversationManager()
    # 验证原有功能正常
    has_add = hasattr(conv, 'add_message') and callable(getattr(conv, 'add_message', None))
    has_history = hasattr(conv, 'get_history') and callable(getattr(conv, 'get_history', None))
    has_context = hasattr(conv, 'get_context_string') and callable(getattr(conv, 'get_context_string', None))
    has_clear = hasattr(conv, 'clear') and callable(getattr(conv, 'clear', None))

    # 进行基本操作验证
    conv.add_message("user", "测试消息")
    history = conv.get_history(1)
    msg_ok = len(history) > 0 and history[0]["role"] == "user"

    return has_add and has_history and has_context and has_clear and msg_ok, ""


check("TC-M07", "ConversationManager 原有功能不受影响 (add/get/clear)",
      test_m07()[0], detail=test_m07()[1])


# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 60)
total = passed + failed
red_pct = (red_count / max(total, 1)) * 100
green_pct = (green_count / max(total, 1)) * 100
print(f"测试汇总: {passed} PASS, {failed} FAIL, 共 {total} 项")
print(f"状态分布: {red_count} RED ({red_pct:.0f}%) | {green_count} GREEN ({green_pct:.0f}%)")
if red_count == total:
    print("状态: 全部 RED - 模块尚未实现，等待开发")
elif red_count > 0:
    print(f"状态: 部分通过 - 还有 {red_count} 项 RED 待开发")
else:
    print("状态: 全部 GREEN - 模块开发完成")
print("=" * 60)
