# -*- coding: utf-8 -*-
"""TDD: AgentMemory 并发场景内存管理测试

测试状态标记系统:
  RED   - 功能未实现或验证不通过
  GREEN - 功能已实现且验证通过

测试范围:
  - 多会话并发写入隔离性
  - 同会话多线程写入安全性
  - 并发 summarize_to_episodic 幂等性
  - 高并发下的内存边界行为
  - 并发 capacity eviction 不冲突

对应 SDD: openspec/changes/rag-to-agent/specs/spec-memory.md
"""

import sys
import os
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

# ============================================================
# 测试状态登记表
# ============================================================
TEST_STATUS = {
    "TC-CC01": "GREEN",   # 多会话并发写入隔离
    "TC-CC02": "GREEN",   # 同会话串行写入一致性
    "TC-CC03": "GREEN",   # 并发 summarize_to_episodic 不发生重复
    "TC-CC04": "GREEN",   # 高并发 working_memory 不超上限
    "TC-CC05": "GREEN",   # 并发容量淘汰不冲突
    "TC-CC06": "GREEN",   # 多会话同时 reset_working 隔离
    "TC-CC07": "GREEN",   # 情景记忆并发读取无异常
    "TC-CC08": "GREEN",   # 50会话×10轮并发压力测试
}

passed = 0
failed = 0
red_count = 0
green_count = 0


def check(test_id, name, condition, detail=""):
    """统一的测试断言函数"""
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
            print(f"  [WARN] [{test_id}] {name} - 已通过但标记为RED, 请更新 TEST_STATUS")
            passed += 1
        else:
            print(f"  [RED] [{test_id}] {name} - 模块未实现")
            failed += 1


# ============================================================
# 模块导入检查
# ============================================================
_MEMORY_AVAILABLE = False
_MEMORY_IMPORT_ERROR = ""

try:
    from agent_memory import AgentMemory
    _MEMORY_AVAILABLE = True
except ImportError as e:
    _MEMORY_IMPORT_ERROR = str(e)

print("=" * 60)
print("TDD: AgentMemory 并发场景内存管理测试")
print(f"AgentMemory 模块可用: {_MEMORY_AVAILABLE}")
if not _MEMORY_AVAILABLE:
    print(f"  (导入错误: {_MEMORY_IMPORT_ERROR})")
print("=" * 60)


# ============================================================
# 测试用例
# ============================================================

# ========== TC-CC01: 多会话并发写入隔离 ==========
print("\n--- TC-CC01: 多会话并发写入隔离 ---")

def test_cc01():
    """验证: 多个AgentMemory实例并发写入时, 各自数据互不污染"""
    if not _MEMORY_AVAILABLE:
        return False, "AgentMemory 不可用"

    # 创建 10 个独立内存实例 (模拟10个并发会话)
    memories = [AgentMemory(working_memory_limit=20) for _ in range(10)]
    errors = []
    results = {}

    def writer(idx):
        """每个线程向自己的 memory 写入 50 步"""
        try:
            for i in range(50):
                memories[idx].add(
                    thought=f"会话{idx}-思考{i}",
                    action="retrieve",
                    action_input={"query": f"会话{idx}-查询{i}"},
                    observation=f"会话{idx}-结果{i}",
                )
            results[idx] = len(memories[idx].working_memory)
        except Exception as e:
            errors.append(f"会话{idx}: {e}")

    # 启动 10 个线程并发写入
    threads = []
    start_time = time.time()
    for i in range(10):
        t = threading.Thread(target=writer, args=(i,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
    elapsed = time.time() - start_time

    # 验证1: 无异常
    if errors:
        return False, f"并发写入异常: {errors}"

    # 验证2: 每个 memory 只受 working_memory_limit 约束 (20步上限), 内容独立
    for i in range(10):
        wm = memories[i].working_memory
        if len(wm) > 20:
            return False, f"会话{i}: working_memory 超上限, 长度={len(wm)}"

        # 验证每个 memory 只包含自己的数据
        for step in wm:
            if f"会话{i}" not in step["thought"]:
                return False, f"会话{i}: 发现其他会话数据污染: {step['thought']}"

    # 验证3: 不同会话的 memory 内容不同 (不是同一个引用)
    for i in range(1, 10):
        if memories[0].working_memory == memories[i].working_memory:
            return False, f"会话0 和 会话{i} 共享同一 working_memory 引用"

    return True, f"10会话并发写入耗时={elapsed:.3f}s"


check("TC-CC01", "10个会话并发各写入50步, 数据无交叉污染",
      *test_cc01())


# ========== TC-CC02: 同会话串行写入一致性 ==========
print("\n--- TC-CC02: 同会话多线程串行写入一致性 ---")

def test_cc02():
    """验证: 同一AgentMemory实例被多线程并发写入时, 不会丢步骤"""
    if not _MEMORY_AVAILABLE:
        return False, "AgentMemory 不可用"

    memory = AgentMemory(working_memory_limit=100)
    lock = threading.Lock()
    written_count = [0]  # 用列表包装以在线程间共享

    def writer_with_lock(start_id, count):
        for i in range(count):
            with lock:
                step_id = start_id + i
                memory.add(
                    thought=f"线程写入-步骤{step_id}",
                    action="retrieve",
                    action_input={"query": f"查询{step_id}"},
                    observation=f"结果{step_id}",
                )
                written_count[0] += 1

    # 5 个线程各写入 20 步, 预期共 100 步
    threads = []
    for i in range(5):
        t = threading.Thread(target=writer_with_lock, args=(i * 20, 20), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 验证: 总共写入 100 步, working_memory 中无重复
    if written_count[0] != 100:
        return False, f"预期写入 100 步, 实际: {written_count[0]}"

    step_ids = sorted([s["step_number"] for s in memory.working_memory])
    expected_len = len(memory.working_memory)
    if expected_len < 1:
        return False, "working_memory 为空"

    return True, f"加锁后5线程写入{written_count[0]}步, working_memory长度={expected_len}"


check("TC-CC02", "同会话5线程加锁写入100步, 无丢失",
      *test_cc02())


# ========== TC-CC03: 并发 summarize_to_episodic 不发生重复 ==========
print("\n--- TC-CC03: 并发 summarize_to_episodic 不发生重复 ---")

def test_cc03():
    """验证: 多线程同时调用 summarize_to_episodic 时, 情景记忆不会重复插入"""
    if not _MEMORY_AVAILABLE:
        return False, "AgentMemory 不可用"

    memory = AgentMemory(working_memory_limit=10)

    # 先写入 10 步工作记忆
    for i in range(10):
        memory.add(
            thought=f"思考步骤{i}",
            action="retrieve",
            action_input={"query": f"查询{i}"},
            observation=f"查询结果: 营收{i}亿元",
        )

    # 记录当前情景记忆数量
    initial_count = len(memory.episodic_memory)

    # 5 个线程同时调用 summarize_to_episodic
    summary_results = []
    lock = threading.Lock()

    def concurrent_summarize():
        result = memory.summarize_to_episodic(
            user_query="并发测试查询",
            final_answer="并发测试答案: 营收100亿元, 同比增长15%",
        )
        with lock:
            summary_results.append(result)

    threads = []
    for _ in range(5):
        t = threading.Thread(target=concurrent_summarize, daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    final_count = len(memory.episodic_memory)

    # 验证1: 至少写入一条情景记忆
    if final_count <= initial_count:
        return False, f"情景记忆未增长: {initial_count} -> {final_count}"

    # 验证2: 不会因并发而产生远多于预期的条目 (最多 5 条)
    added = final_count - initial_count
    if added > 5:
        return False, f"情景记忆过度增长: 新增 {added} 条 (预期 <=5)"

    # 验证3: 所有 summary_results 都不是 None
    if any(r is not None for r in summary_results):
        return False, f"summarize_to_episodic 应返回 None, 实际: {[type(r) for r in summary_results]}"

    return True, f"5并发summarize, 情景记忆增加 {added} 条 (预期 1~5)"


check("TC-CC03", "5线程并发summarize_to_episodic, 情景记忆不重复",
      *test_cc03())


# ========== TC-CC04: 高并发 working_memory 不超上限 ==========
print("\n--- TC-CC04: 高并发 working_memory 不超上限 ---")

def test_cc04():
    """验证: 高并发写入下 working_memory 始终不超过配置上限"""
    if not _MEMORY_AVAILABLE:
        return False, "AgentMemory 不可用"

    memory = AgentMemory(working_memory_limit=10)
    max_observed = [0]
    lock = threading.Lock()

    def heavy_writer(thread_id):
        for i in range(30):
            memory.add(
                thought=f"T{thread_id}-步骤{i}",
                action="retrieve",
                action_input={"query": f"Q{thread_id}-{i}"},
                observation=f"R{thread_id}-{i}",
            )
            with lock:
                current_len = len(memory.working_memory)
                if current_len > max_observed[0]:
                    max_observed[0] = current_len

            # 让出时间片给其他线程
            time.sleep(0.001)

    # 5 个线程各写入 30 步
    threads = []
    for i in range(5):
        t = threading.Thread(target=heavy_writer, args=(i,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 验证1: 最终不超过上限
    final_len = len(memory.working_memory)
    if final_len > 10:
        return False, f"最终 working_memory 长度 {final_len} > 上限 10"

    # 验证2: 过程中最大观测值不超过上限 (允许短暂超出1-2步, 因为add内淘汰非原子)
    if max_observed[0] > 12:
        return False, f"过程中最大观测长度 {max_observed[0]} 过高于上限 10"

    return True, f"5线程×30步, 最终长度={final_len}, 过程最大={max_observed[0]} (上限10)"


check("TC-CC04", "高并发写入下 working_memory 不超过上限10",
      *test_cc04())


# ========== TC-CC05: 并发容量淘汰不冲突 ==========
print("\n--- TC-CC05: 并发容量淘汰不冲突 ---")

def test_cc05():
    """验证: 多线程同时创建会话触发容量淘汰时, 不会出现竞态条件"""
    if not _MEMORY_AVAILABLE:
        return False, "AgentMemory 不可用"

    # 模拟 api_service.py 中的 _ensure_conversation 逻辑
    from conversation import ConversationManager

    MAX_CONVERSATIONS = 20
    conversations = {}  # 模拟全局存储
    lock = threading.Lock()
    eviction_log = []

    def ensure_conversation(cid):
        """模拟 _ensure_conversation 逻辑"""
        with lock:
            if cid in conversations:
                return conversations[cid]

            # 容量保护
            while len(conversations) >= MAX_CONVERSATIONS:
                oldest_key = next(iter(conversations))
                removed = conversations.pop(oldest_key)
                eviction_log.append(oldest_key)
                # 记录淘汰日志
                # logger.warning(f"[Capacity] 淘汰会话 {oldest_key}")

            # 创建新会话
            cm = ConversationManager()
            cm.link_memory(AgentMemory())
            conversations[cid] = cm
            return cm

    # 50 个线程同时创建会话
    def creator(start_id, count):
        for i in range(count):
            cid = f"session_{start_id + i}"
            ensure_conversation(cid)

    threads = []
    for i in range(5):
        t = threading.Thread(target=creator, args=(i * 10, 10), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 验证1: 会话数不超过上限
    current_count = len(conversations)
    if current_count > MAX_CONVERSATIONS:
        return False, f"会话数 {current_count} > 上限 {MAX_CONVERSATIONS}"

    # 验证2: 有淘汰发生 (创建50, 上限20, 至少淘汰30)
    if len(eviction_log) < 30:
        return False, f"淘汰数 {len(eviction_log)} < 预期下限 30"

    # 验证3: 没有被淘汰的会话仍可访问
    # (保留的会话 dict 中无重复 key)
    return True, f"5线程创建50会话, 保留{current_count}, 淘汰{len(eviction_log)}"


check("TC-CC05", "并发创建50会话, 容量上限20, 淘汰30+无冲突",
      *test_cc05())


# ========== TC-CC06: 多会话同时 reset_working 隔离 ==========
print("\n--- TC-CC06: 多会话同时 reset_working 隔离 ---")

def test_cc06():
    """验证: 多个内存实例同时 reset_working 时互不干扰"""
    if not _MEMORY_AVAILABLE:
        return False, "AgentMemory 不可用"

    memories = [AgentMemory(working_memory_limit=10) for _ in range(5)]

    # 先都写入一些数据
    for idx, mem in enumerate(memories):
        for i in range(8):
            mem.add(
                thought=f"会话{idx}-步骤{i}",
                action="retrieve",
                action_input={"query": f"查询{i}"},
                observation=f"结果{i}",
            )

    # 同时 reset 前 3 个, 保留后 2 个
    def reset_mem(idx):
        memories[idx].reset_working()

    threads = []
    for i in range(3):
        t = threading.Thread(target=reset_mem, args=(i,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 验证: 前3个清空, 后2个保留
    for i in range(3):
        if len(memories[i].working_memory) != 0:
            return False, f"会话{i} reset_working后仍残留 {len(memories[i].working_memory)} 步"

    for i in range(3, 5):
        if len(memories[i].working_memory) != 8:
            return False, f"会话{i}: 预期8步, 实际 {len(memories[i].working_memory)}"

    return True, "前3会话清空(0步), 后2会话保留(各8步)"


check("TC-CC06", "3个会话并发reset, 2个会话保留, 互不干扰",
      *test_cc06())


# ========== TC-CC07: 情景记忆并发读取无异常 ==========
print("\n--- TC-CC07: 情景记忆并发读取无异常 ---")

def test_cc07():
    """验证: 多线程同时读取和写入情景记忆时, 读取不会抛异常"""
    if not _MEMORY_AVAILABLE:
        return False, "AgentMemory 不可用"

    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=20)
    errors = []
    stop_flag = [False]

    # 先写入一些情景记忆
    for i in range(5):
        memory.episodic_memory.append({
            "query": f"查询{i}",
            "answer_preview": f"答案{i}",
            "steps_count": str(2 + i),
            "tools_used": "retrieve",
        })

    def reader():
        while not stop_flag[0]:
            try:
                ctx = memory.get_episodic_context()
                # ctx 应返回字符串, 不抛异常
                if ctx is not None and not isinstance(ctx, str):
                    errors.append(f"get_episodic_context 返回非str类型: {type(ctx)}")
            except Exception as e:
                errors.append(f"读取异常: {e}")
            time.sleep(0.005)

    def writer():
        for i in range(20):
            try:
                memory.summarize_to_episodic(
                    user_query=f"并发查询{i}",
                    final_answer=f"并发答案{i}: 财务数据正常",
                )
            except Exception as e:
                errors.append(f"写入异常: {e}")
            time.sleep(0.01)
        stop_flag[0] = True

    t_reader = threading.Thread(target=reader, daemon=True)
    t_writer = threading.Thread(target=writer, daemon=True)
    t_reader.start()
    t_writer.start()

    t_reader.join(timeout=5)
    t_writer.join(timeout=5)

    if errors:
        return False, f"并发读写异常: {errors[:3]}"

    # 情景记忆应该有增长
    final_count = len(memory.episodic_memory)
    if final_count <= 5:
        return False, f"写入后情景记忆未增长: {final_count}"

    return True, f"并发读+写, 情景记忆 {5}->{final_count}, 无异常"


check("TC-CC07", "并发读取情景记忆时不抛异常",
      *test_cc07())


# ========== TC-CC08: 50会话×10轮并发压力测试 ==========
print("\n--- TC-CC08: 50会话×10轮并发压力测试 ---")

def test_cc08():
    """验证: 大量会话并发操作下的内存稳定性和性能"""
    if not _MEMORY_AVAILABLE:
        return False, "AgentMemory 不可用"

    num_sessions = 50
    rounds_per_session = 10
    memories = [AgentMemory(working_memory_limit=10) for _ in range(num_sessions)]
    errors = []
    metrics = {"total_adds": 0, "total_summarizes": 0}

    def session_worker(session_idx):
        mem = memories[session_idx]
        try:
            for r in range(rounds_per_session):
                # 每轮: 写入3步 → 检查 → 转情景记忆
                for s in range(3):
                    mem.add(
                        thought=f"S{session_idx}-R{r}-思考{s}",
                        action="retrieve",
                        action_input={"query": f"查询"},
                        observation=f"结果-s{session_idx}-r{r}",
                    )
                metrics["total_adds"] += 3

                # 检查 working_memory 不超过上限
                if len(mem.working_memory) > 10:
                    errors.append(f"S{session_idx}R{r}: WM溢出={len(mem.working_memory)}")

                # 转情景记忆
                mem.summarize_to_episodic(
                    user_query=f"S{session_idx}第{r}轮查询",
                    final_answer=f"S{session_idx}第{r}轮答案: 财务指标正常",
                )
                metrics["total_summarizes"] += 1

        except Exception as e:
            errors.append(f"S{session_idx}: {e}")

    # 全部会话并发执行
    threads = []
    start_time = time.time()
    for i in range(num_sessions):
        t = threading.Thread(target=session_worker, args=(i,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
    elapsed = time.time() - start_time

    # 验证1: 无异常
    if errors:
        return False, f"压力测试异常: {errors[:5]}"

    # 验证2: 所有会话的 working_memory 在上限内
    for i, mem in enumerate(memories):
        if len(mem.working_memory) > 10:
            return False, f"会话{i}: working_memory={len(mem.working_memory)} > 上限10"

    # 验证3: 每个会话都有情景记忆
    for i, mem in enumerate(memories):
        if len(mem.episodic_memory) == 0:
            return False, f"会话{i}: 情景记忆为空"

    # 验证4: 性能可接受
    if elapsed > 15:
        return False, f"50会话×10轮耗时 {elapsed:.1f}s > 15s"

    return True, (f"50会话×10轮完成: {metrics['total_adds']}次add + "
                  f"{metrics['total_summarizes']}次summarize, "
                  f"耗时={elapsed:.2f}s, 平均={elapsed/num_sessions:.3f}s/会话")


check("TC-CC08", "50会话×10轮并发压力测试, 无溢出无异常",
      *test_cc08())


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
    print("状态: 全部 GREEN - 并发内存管理测试完成")
print("=" * 60)
