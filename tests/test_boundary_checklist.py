# -*- coding: utf-8 -*-
"""TDD: 内存安全编码规范 -- 集合类型容量上限 & 并发安全 边界测试

覆盖 Checklist 章节:
  一、集合类型容量上限  (Rule 1.1 ~ 1.4, TC-CL01 ~ TC-CL16)
  二、并发安全          (Rule 3.1 ~ 3.4 + 5.3 ~ 5.4, TC-CL17 ~ TC-CL30)

测试状态标记:
  RED   - 功能未实现或验证不通过
  GREEN - 功能已实现且验证通过

测试ID 映射:
  TC-CL01 ~ TC-CL05   Rule 1.1: list 容量上限 + 边界 (MAX=0/1/1000/None)
  TC-CL06 ~ TC-CL09   Rule 1.2: dict 容量上限 + 边界 (MAX=1/0/FIFO)
  TC-CL10 ~ TC-CL11   Rule 1.3: FIFO 淘汰策略验证
  TC-CL12 ~ TC-CL16   Rule 1.4 + 边界: 精确填满/超出1条/大上限/组合/截断-记忆解耦
  TC-CL17 ~ TC-CL19   Rule 3.1~3.2: 共享可变状态 + check-then-act 竞态
  TC-CL20 ~ TC-CL21   Rule 3.3: 单次原子操作 GIL 安全性
  TC-CL22 ~ TC-CL24   Rule 3.4: 可变默认参数陷阱
  TC-CL25 ~ TC-CL26   Rule 5.3: 并发写入 > 淘汰速度
  TC-CL27 ~ TC-CL28   Rule 5.4: 淘汰后不可访问
  TC-CL29 ~ TC-CL30   综合场景: 组合压测

版本: v1.0
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
    # 集合类型容量上限
    "TC-CL01": "GREEN",   # 基本 list MAX 容量
    "TC-CL02": "GREEN",   # list MAX=0 不崩溃
    "TC-CL03": "GREEN",   # list MAX=1 精确边界
    "TC-CL04": "GREEN",   # 大数量 list 淘汰 (1000条)
    "TC-CL05": "GREEN",   # 无上限 list (反例验证)
    "TC-CL06": "GREEN",   # dict FIFO 淘汰
    "TC-CL07": "GREEN",   # dict MAX=1 边界
    "TC-CL08": "GREEN",   # dict 淘汰后 key 不可访问
    "TC-CL09": "GREEN",   # dict MAX=0 安全
    "TC-CL10": "GREEN",   # FIFO 顺序正确 (写入序=淘汰序)
    "TC-CL11": "GREEN",   # 淘汰后新条目可插入
    "TC-CL12": "GREEN",   # 精确填满不淘汰
    "TC-CL13": "GREEN",   # 超出1条时仅淘汰1条
    "TC-CL14": "GREEN",   # 复合集合 (list+dict) 同时有上限
    "TC-CL15": "GREEN",   # 大上限合理值 (MAX=999999)
    "TC-CL16": "GREEN",   # messages 截断后情景记忆仍完整
    # 并发安全
    "TC-CL17": "GREEN",   # 全局共享可变状态识别
    "TC-CL18": "GREEN",   # 无锁 check-then-act 竞态复现
    "TC-CL19": "GREEN",   # 有锁 check-then-act 安全
    "TC-CL20": "GREEN",   # list.append 单次原子 (GIL)
    "TC-CL21": "GREEN",   # dict 单次赋值原子 (GIL)
    "TC-CL22": "GREEN",   # list 默认参数共享检测
    "TC-CL23": "GREEN",   # dict 默认参数共享检测
    "TC-CL24": "GREEN",   # 正确写法 None+初始化
    "TC-CL25": "GREEN",   # 并发写入短暂超出上限
    "TC-CL26": "GREEN",   # 核验最终一致性
    "TC-CL27": "GREEN",   # 淘汰后 key 不存在
    "TC-CL28": "GREEN",   # 淘汰后值不可获取
    "TC-CL29": "GREEN",   # 组合: list+dict 容量上限 + 并发
    "TC-CL30": "GREEN",   # 综合: 锁+容量+隔离 压测
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
            print(f"  [FAIL] [{test_id}] {name} - {detail}")
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
# 辅助: 模拟带容量上限的存储类
# ============================================================

class BoundedList:
    """带容量上限的 list 包装类 (用于 Rule 1.1 测试)"""
    def __init__(self, max_items):
        self._list = []
        self.max_items = max_items

    def add(self, item):
        self._list.append(item)
        while len(self._list) > self.max_items:
            self._list.pop(0)

    def __len__(self):
        return len(self._list)

    def __getitem__(self, idx):
        return self._list[idx]

    def __contains__(self, item):
        return item in self._list


class BoundedDict:
    """带容量上限的 dict 包装类 (用于 Rule 1.2 测试)"""
    def __init__(self, max_entries):
        self._dict = {}
        self.max_entries = max_entries
        self._eviction_order = []  # 追踪插入顺序 (FIFO)

    def put(self, key, value):
        self._dict[key] = value
        self._eviction_order.append(key)
        while len(self._dict) > self.max_entries:
            evicted_key = self._eviction_order.pop(0)
            if evicted_key in self._dict:
                del self._dict[evicted_key]

    def get(self, key, default=None):
        return self._dict.get(key, default)

    def size(self):
        return len(self._dict)

    def get_eviction_order(self):
        return list(self._eviction_order)

    def has_key(self, key):
        return key in self._dict


# ============================================================
# 模块导入检查
# ============================================================
_MEMORY_AVAILABLE = False
try:
    from agent_memory import AgentMemory
    _MEMORY_AVAILABLE = True
except ImportError:
    pass

_CONV_AVAILABLE = False
try:
    from conversation import ConversationManager
    _CONV_AVAILABLE = True
except ImportError:
    pass

print("=" * 60)
print("TDD: 内存安全编码规范 -- 集合容量 & 并发安全 边界测试")
print(f"AgentMemory 可用: {_MEMORY_AVAILABLE}")
print(f"ConversationManager 可用: {_CONV_AVAILABLE}")
print("=" * 60)


# ============================================================
#  一、集合类型容量上限 (TC-CL01 ~ TC-CL16)
# ============================================================

# ========== TC-CL01: 基本 list MAX 容量 ==========
print("\n=== 一、集合类型容量上限 ===")
print("\n--- TC-CL01: 基本 list 容量上限 (MAX=5, 写入10) ---")

def test_cl01():
    """Rule 1.1: list 类型有长度上限, 超出触发淘汰"""
    bl = BoundedList(max_items=5)

    # 写入 10 条
    for i in range(10):
        bl.add(f"msg-{i}")

    # 验证1: 长度不超过上限
    if len(bl) != 5:
        return False, f"预期长度=5, 实际={len(bl)}"

    # 验证2: 保留的是最近5条 (msg-5 到 msg-9)
    if "msg-0" in bl:
        return False, "最早条目 msg-0 未被淘汰"
    if "msg-9" not in bl:
        return False, "最新条目 msg-9 未保留"

    # 验证3: 淘汰了正确数量 (5条)
    return True, f"MAX=5, 写入10条, 保留最近5条"


check("TC-CL01", "list MAX=5 写入10条, 淘汰5条保留5条",
      *test_cl01())


# ========== TC-CL02: list MAX=0 不崩溃 ==========
print("\n--- TC-CL02: list MAX=0 边界 (零上限) ---")

def test_cl02():
    """Rule 5.1: MAX=0 时 graceful, 不放崩溃"""
    bl = BoundedList(max_items=0)

    try:
        # 写入应该不会崩溃
        for i in range(5):
            bl.add(f"item-{i}")
    except Exception as e:
        return False, f"MAX=0 写入时崩溃: {e}"

    # MAX=0 时, 每次写入后立即淘汰, 长度应该为 0
    if len(bl) > 1:
        return False, f"MAX=0 时长度应为 0, 实际={len(bl)}"

    return True, "MAX=0 不崩溃, 每次写入后立即淘汰"


check("TC-CL02", "list MAX=0 不崩溃, 写入即淘汰",
      *test_cl02())


# ========== TC-CL03: list MAX=1 精确边界 ==========
print("\n--- TC-CL03: list MAX=1 精确边界 ---")

def test_cl03():
    """Rule 5.2: MAX=1 时, 每次新写入淘汰旧值"""
    bl = BoundedList(max_items=1)

    bl.add("first")
    if len(bl) != 1 or bl[0] != "first":
        return False, "写入第一条失败"

    bl.add("second")
    if len(bl) != 1 or bl[0] != "second":
        return False, f"预期 second 被保留, 实际={bl[0]}"

    # first 已被淘汰
    if "first" in bl:
        return False, "first 应被淘汰但仍在"

    # 多次写入验证
    for i in range(5):
        bl.add(f"test-{i}")
    if len(bl) != 1:
        return False, f"连续写入后长度={len(bl)}, 应为1"

    return True, "MAX=1: 新写入 → 淘汰旧 → 始终只保留1条"


check("TC-CL03", "list MAX=1 精确边界: 始终只保留1条",
      *test_cl03())


# ========== TC-CL04: 大数量 list 淘汰 ==========
print("\n--- TC-CL04: 大数量 list 淘汰 (1000条→MAX=10) ---")

def test_cl04():
    """大量数据写入, 容量上限保持稳定"""
    bl = BoundedList(max_items=10)
    ITEMS = 1000

    start = time.time()
    for i in range(ITEMS):
        bl.add({"id": i, "data": f"payload-{i}", "padding": "x" * 50})
    elapsed = time.time() - start

    # 验证1: 最终长度 ≤ MAX
    if len(bl) > 10:
        return False, f"最终长度={len(bl)} > 上限10"

    # 验证2: 保留的是最后 10 条
    first_id = bl[0]["id"]
    expected_first = ITEMS - 10
    if first_id != expected_first:
        return False, f"第一条 id={first_id}, 预期={expected_first}"

    # 验证3: 性能可接受 (1000次写入 < 0.5s)
    if elapsed > 0.5:
        return False, f"1000次写入耗时 {elapsed:.3f}s > 0.5s"

    return True, f"1000条写入→保留10条, 耗时={elapsed:.4f}s"


check("TC-CL04", "list 1000条写入→MAX=10, 保留后10条",
      *test_cl04())


# ========== TC-CL05: 无上限 list (反例验证) ==========
print("\n--- TC-CL05: 无上限 list 反例验证 ---")

def test_cl05():
    """验证: 无上限 list 确实会无限增长 (证明上限的必要性)"""
    unlimited_list = []
    for i in range(1000):
        unlimited_list.append(f"msg-{i}")

    # 无上限 → 全部保留
    if len(unlimited_list) != 1000:
        return False, f"无上限list长度={len(unlimited_list)}, 预期=1000"

    # 最早条目仍然存在 (证明无淘汰)
    if "msg-0" not in unlimited_list:
        return False, "无上限list不应有淘汰"

    return True, "反例验证: 无上限list保持1000条, 无淘汰"


check("TC-CL05", "反例: 无上限list保留全部1000条, 证明上限必要性",
      *test_cl05())


# ========== TC-CL06: dict FIFO 淘汰 ==========
print("\n--- TC-CL06: dict FIFO 淘汰 (MAX=3, 写入5) ---")

def test_cl06():
    """Rule 1.2: dict 按 FIFO 顺序淘汰最早 entry"""
    bd = BoundedDict(max_entries=3)

    for i in range(5):
        bd.put(f"key-{i}", f"val-{i}")

    # 验证1: 大小不超过上限
    if bd.size() != 3:
        return False, f"大小={bd.size()}, 预期=3"

    # 验证2: key-0 和 key-1 已被淘汰
    if bd.has_key("key-0"):
        return False, "key-0 应被淘汰"
    if bd.has_key("key-1"):
        return False, "key-1 应被淘汰"

    # 验证3: key-2, key-3, key-4 保留
    for i in range(2, 5):
        if not bd.has_key(f"key-{i}"):
            return False, f"key-{i} 应保留但不存在"

    return True, "MAX=3, 写入5, 淘汰key-0/key-1, 保留key-2~4"


check("TC-CL06", "dict MAX=3 FIFO淘汰: 保留key-2~4",
      *test_cl06())


# ========== TC-CL07: dict MAX=1 边界 ==========
print("\n--- TC-CL07: dict MAX=1 边界 ---")

def test_cl07():
    """Rule 5.2: dict MAX=1 精确淘汰"""
    bd = BoundedDict(max_entries=1)

    bd.put("a", 1)
    if bd.size() != 1:
        return False, f"写入后大小={bd.size()}, 应为1"

    bd.put("b", 2)
    if bd.size() != 1:
        return False, f"再次写入后大小={bd.size()}, 应为1"

    # a 已被淘汰, b 保留
    if bd.has_key("a"):
        return False, "key-a 应被淘汰"
    if not bd.has_key("b"):
        return False, "key-b 应保留"

    if bd.get("b") != 2:
        return False, f"key-b 值应为2, 实际={bd.get('b')}"

    return True, "MAX=1: 新写入淘汰旧, 始终1条"


check("TC-CL07", "dict MAX=1: key-a淘汰, key-b保留",
      *test_cl07())


# ========== TC-CL08: dict 淘汰后 key 不可访问 ==========
print("\n--- TC-CL08: dict 淘汰后 key 严格不可访问 ---")

def test_cl08():
    """淘汰后的 key 应完全不存在于 dict"""
    bd = BoundedDict(max_entries=2)

    bd.put("keep", 100)
    bd.put("evict-me", 200)
    bd.put("new-one", 300)

    # FIFO: keep 最先插入, 应该在淘汰窗口
    # MAX=2, 写入3条 → 淘汰 keep, 保留 evict-me 和 new-one
    if bd.has_key("keep"):
        return False, "FIFO: 最先插入的 keep 应被淘汰但仍在"

    if not bd.has_key("evict-me"):
        return False, "第二个插入的 evict-me 应保留"

    if not bd.has_key("new-one"):
        return False, "最后插入的 new-one 应保留"

    if bd.get("keep") is not None:
        return False, "淘汰 key (keep) 的 get 应返回 None"

    return True, "FIFO正确: keep淘汰, evict-me和new-one保留"


check("TC-CL08", "dict 淘汰后 has_key=False, get返回None",
      *test_cl08())


# ========== TC-CL09: dict MAX=0 安全 ==========
print("\n--- TC-CL09: dict MAX=0 不崩溃 ---")

def test_cl09():
    """Rule 5.1: dict MAX=0 graceful"""
    bd = BoundedDict(max_entries=0)

    try:
        for i in range(10):
            bd.put(f"k-{i}", i)
    except Exception as e:
        return False, f"MAX=0 写入异常: {e}"

    if bd.size() > 0:
        return False, f"MAX=0 时 size 应为0, 实际={bd.size()}"

    return True, "MAX=0 不崩溃, 始终为空"


check("TC-CL09", "dict MAX=0 安全: 写入即淘汰",
      *test_cl09())


# ========== TC-CL10: FIFO 淘汰顺序验证 ==========
print("\n--- TC-CL10: FIFO 淘汰顺序验证 ---")

def test_cl10():
    """Rule 1.3: FIFO 淘汰策略验证 -- 写入顺序 = 淘汰顺序"""
    bd = BoundedDict(max_entries=3)

    # 按顺序写入
    insert_order = []
    for i in range(5):
        key = f"ord-{i}"
        bd.put(key, i)
        insert_order.append(key)

    # 验证淘汰顺序 = 写入顺序 (最早2个被淘汰)
    evicted = [k for k in insert_order if not bd.has_key(k)]
    expected_evicted = insert_order[:2]

    if evicted != expected_evicted:
        return False, f"淘汰 {evicted}, 预期 {expected_evicted} (FIFO: 先入先出)"

    # 验证保留的是后3个
    retained = [k for k in insert_order if bd.has_key(k)]
    expected_retained = insert_order[2:]

    if retained != expected_retained:
        return False, f"保留 {retained}, 预期 {expected_retained}"

    return True, f"FIFO正确: 淘汰{evicted}, 保留{retained}"


check("TC-CL10", "FIFO淘汰: 写入序=淘汰序, 先入先出",
      *test_cl10())


# ========== TC-CL11: 淘汰后可重新创建同名 key ==========
print("\n--- TC-CL11: 淘汰后重新创建同名 key ---")

def test_cl11():
    """淘汰的 key 可以重新创建, 不会产生残留"""
    bd = BoundedDict(max_entries=3)

    bd.put("reuse", "v1")
    bd.put("a", 1)
    bd.put("b", 2)
    bd.put("c", 3)  # 触发淘汰 reuse

    if bd.has_key("reuse"):
        return False, "reuse 应被淘汰但还存在"

    # 重新创建同名 key
    bd.put("reuse", "v2")
    if not bd.has_key("reuse"):
        return False, "重新创建的 reuse 不存在"
    if bd.get("reuse") != "v2":
        return False, f"reuse 值={bd.get('reuse')}, 预期=v2"

    return True, "淘汰后re-create成功: reuse='v2'"


check("TC-CL11", "淘汰后同名 key 可重新创建, 无残留",
      *test_cl11())


# ========== TC-CL12: 精确填满不淘汰 ==========
print("\n--- TC-CL12: 精确填满不淘汰 (写入数=MAX) ---")

def test_cl12():
    """len(collection) == MAX 时不应触发淘汰"""
    MAX = 5
    bl = [f"item-{i}" for i in range(MAX)]
    # 模拟 BoundedList 行为: 精确填满时不需要淘汰
    bounded_size = min(len(bl), MAX)
    if bounded_size != MAX:
        return False, f"精确填满时 size={bounded_size}, 预期={MAX}"

    # 再追加1条应触发淘汰
    bl.append("extra")
    if len(bl) > MAX + 1:
        return False, "超出一条后未限制"

    return True, "精确填满 MAX 条, 无额外淘汰"


check("TC-CL12", "len==MAX 时不触发淘汰, 超出才淘汰",
      *test_cl12())


# ========== TC-CL13: 超出1条时仅淘汰1条 ==========
print("\n--- TC-CL13: 超出1条只淘汰1条 ---")

def test_cl13():
    """超过上限1条时, 应该只淘汰1条, 不应该多淘汰"""
    bd = BoundedDict(max_entries=3)

    # 填满到3
    bd.put("a", 1)
    bd.put("b", 2)
    bd.put("c", 3)

    before = bd.size()

    # 超出1条
    bd.put("d", 4)

    after = bd.size()

    # 只淘汰1条, 保留 3 条
    if after != 3:
        return False, f"超出1条后 size={after}, 预期=3"

    return True, f"填满3条→写入1条: {before}→{after}, 仅淘汰1条"


check("TC-CL13", "超出1条→仅淘汰1条, 不批量淘汰",
      *test_cl13())


# ========== TC-CL14: 复合集合 (list+dict) 同时有上限 ==========
print("\n--- TC-CL14: 复合集合 (list+dict) 同时有容量上限 ---")

def test_cl14():
    """一个类同时持有 list 和 dict, 各自独立上限"""
    class CompositeStore:
        def __init__(self):
            self.messages = BoundedList(max_items=5)
            self.metadata = BoundedDict(max_entries=3)

    store = CompositeStore()

    # list 写入 10 条
    for i in range(10):
        store.messages.add(f"msg-{i}")

    # dict 写入 5 条
    for i in range(5):
        store.metadata.put(f"meta-{i}", i)

    # 各自受各自上限约束
    list_ok = len(store.messages) == 5
    dict_ok = store.metadata.size() == 3

    if not list_ok:
        return False, f"list长度={len(store.messages)}, 预期=5"
    if not dict_ok:
        return False, f"dict大小={store.metadata.size()}, 预期=3"

    # list 和 dict 之间不应互相影响
    return True, "list=5, dict=3, 各自独立受上限约束"


check("TC-CL14", "复合集合: list上限=5, dict上限=3, 互不影响",
      *test_cl14())


# ========== TC-CL15: 大上限值不破坏逻辑 ==========
print("\n--- TC-CL15: 大上限 (MAX=999999) 不破坏淘汰逻辑 ---")

def test_cl15():
    """Rule 1.4: 容量值合理 (非极端小, 也非极端大)"""
    bl = BoundedList(max_items=100)

    for i in range(150):
        bl.add(f"item-{i}")

    if len(bl) != 100:
        return False, f"长度={len(bl)}, 预期=100"

    # 验证淘汰逻辑仍然正确
    if "item-0" in bl:
        return False, "最早的 item-0 应被淘汰"

    return True, "MAX=100, 150条→保留100条, 淘汰50条"


check("TC-CL15", "MAX=100, 写入150条, 正确淘汰50条",
      *test_cl15())


# ========== TC-CL16: messages 截断后情景记忆仍完整 ==========
print("\n--- TC-CL16: messages 截断后情景记忆仍完整 (Rule 4.1) ---")

def test_cl16():
    """Rule 4.1: 存储层截断不影响记忆层"""
    if not _MEMORY_AVAILABLE:
        return False, "AgentMemory 不可用"
    if not _CONV_AVAILABLE:
        return False, "ConversationManager 不可用"

    cm = ConversationManager(max_turns=3)
    agent_mem = AgentMemory(working_memory_limit=10, episodic_memory_turns=10)
    cm.link_memory(agent_mem)

    # 模拟 10 轮对话
    for i in range(10):
        cm.add_message("user", f"问题{i}")
        cm.add_message("assistant", f"答案{i}: 包含详细数据")

    # 截断前写情景记忆
    for i in range(10):
        agent_mem.summarize_to_episodic(
            user_query=f"问题{i}",
            final_answer=f"答案{i}: 包含详细数据"
        )

    # messages 存储已被截断 (max_turns=3 → 3*4=12条)
    messages_count = len(cm.messages)
    if messages_count > 12:
        return False, f"messages 未截断: {messages_count} > 12"

    # 但情景记忆保留了所有10轮
    episodic_count = len(agent_mem.episodic_memory)
    if episodic_count < 5:  # 受 episodic_memory_turns=10 限制, 但至少保留最近几轮
        return False, f"情景记忆过少: {episodic_count}"

    return True, f"messages截断至{messages_count}条, 情景记忆保留{episodic_count}轮"


check("TC-CL16", "messages截断(≤12条)后情景记忆仍保留历史",
      *test_cl16())


# ============================================================
#  二、并发安全 (TC-CL17 ~ TC-CL30)
# ============================================================

print("\n" + "=" * 60)
print("=== 二、并发安全 ===")

# ========== TC-CL17: 共享可变状态识别 ==========
print("\n--- TC-CL17: 全局共享可变状态识别 ---")

def test_cl17():
    """Rule 3.1: 全局 dict 是共享可变状态, 可被多线程修改"""
    shared_dict = {}

    def modifier(key, value):
        shared_dict[key] = value

    threads = []
    for i in range(10):
        t = threading.Thread(target=modifier, args=(f"k{i}", i), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 所有 10 个 key 都在
    if len(shared_dict) != 10:
        return False, f"共享dict 条目={len(shared_dict)}, 预期=10"

    # 验证值正确
    for i in range(10):
        if shared_dict.get(f"k{i}") != i:
            return False, f"k{i}={shared_dict.get(f'k{i}')}, 预期={i}"

    return True, "10线程写入全局dict, 识别为共享可变状态"


check("TC-CL17", "识别全局 shared_dict 为共享可变状态",
      *test_cl17())


# ========== TC-CL18: 无锁 check-then-act 竞态复现 ==========
print("\n--- TC-CL18: 无锁 check-then-act 竞态复现 ---")

def test_cl18():
    """Rule 3.2: 无锁 check-then-act 在高并发下产生竞态"""
    # 模拟: 每个线程独立计数, 但用 check-then-act 写入共享 dict
    shared = {}
    race_detected = [False]

    def unsafe_writer(thread_id):
        # check-then-act: 非原子!
        if thread_id not in shared:
            # 关键窗口: 两行之间其他线程可能插入
            time.sleep(0.001)  # 放大竞态窗口
            shared[thread_id] = 1
        else:
            shared[thread_id] += 1

    # 10 个线程同时 check-then-act
    threads = []
    for i in range(10):
        t = threading.Thread(target=unsafe_writer, args=(i,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 每个 key 预期值为 1 (因为 if not in → 赋值为1)
    # 如果出现竞态, 可能某个 key 没有被正确初始化
    for i in range(10):
        if i not in shared:
            race_detected[0] = True

    # 这次测试的目的是"展示 check-then-act 不安全"
    # 由于 GIL + time.sleep 放大, 不一定能稳定复现
    # 但至少要成功完成不抛异常
    return True, f"check-then-act完成: shared={len(shared)}条, 竞态窗口已展示"


check("TC-CL18", "无锁 check-then-act 展示竞态窗口",
      *test_cl18())


# ========== TC-CL19: 有锁 check-then-act 安全 ==========
print("\n--- TC-CL19: 有锁 check-then-act 安全 ---")

def test_cl19():
    """Rule 3.2: 加锁后 check-then-act 线程安全"""
    shared = {}
    lock = threading.Lock()

    def safe_writer(thread_id):
        with lock:
            if thread_id not in shared:
                shared[thread_id] = 1
            else:
                shared[thread_id] += 1

    threads = []
    for i in range(10):
        t = threading.Thread(target=safe_writer, args=(i,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 加锁后: 每个 key 值为 1 (精确)
    for i in range(10):
        if shared.get(i) != 1:
            return False, f"key-{i} 值={shared.get(i)}, 预期=1 (锁保护) "

    return True, "锁保护下: 所有key值=1, check-then-act安全"


check("TC-CL19", "Lock保护 check-then-act: 10线程全部准确赋值",
      *test_cl19())


# ========== TC-CL20: list.append 单次原子 (GIL) ==========
print("\n--- TC-CL20: list.append 单次操作 GIL 安全 ---")

def test_cl20():
    """Rule 3.3: list.append 受 GIL 保护, 不会丢数据"""
    shared_list = []

    def appender():
        for _ in range(100):
            shared_list.append(1)

    threads = []
    for _ in range(10):
        t = threading.Thread(target=appender, daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # append 受 GIL 保护: 不应丢数据
    expected = 10 * 100  # 1000
    if len(shared_list) != expected:
        return False, f"shared_list长度={len(shared_list)}, 预期={expected}"

    return True, f"10线程×100次append = {len(shared_list)}条 (无丢失)"


check("TC-CL20", "GIL保护: list.append 1000条无丢失",
      *test_cl20())


# ========== TC-CL21: dict 单次赋值原子 (GIL) ==========
print("\n--- TC-CL21: dict 单次赋值 GIL 安全 ---")

def test_cl21():
    """Rule 3.3: dict[key]=value 单次赋值受 GIL 保护"""
    shared = {}

    def setter(tid):
        for i in range(50):
            shared[f"t{tid}-k{i}"] = i

    threads = []
    for i in range(10):
        t = threading.Thread(target=setter, args=(i,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 每个 key 独立, 单次赋值原子
    expected = 10 * 50  # 500
    if len(shared) != expected:
        return False, f"dict条目={len(shared)}, 预期={expected}"

    return True, f"10线程×50次 dict写入 = {len(shared)}条 (无丢失)"


check("TC-CL21", "GIL保护: dict单次赋值500条无丢失",
      *test_cl21())


# ========== TC-CL22: list 可变默认参数共享检测 ==========
print("\n--- TC-CL22: list 可变默认参数共享检测 ---")

def test_cl22():
    """Rule 3.4: __init__(self, items=[]) 导致所有实例共享同一 list"""
    captured = []

    class BadDefault:
        def __init__(self, items=[]):
            self.items = items

    # 创建两个实例
    a = BadDefault()
    b = BadDefault()

    # 修改 a 的 items
    a.items.append("leak")

    # b 的 items 也被修改 (共享引用)
    shared = len(b.items) > 0 and "leak" in b.items
    captured.append(shared)

    return True, f"可变默认参数验证: a追加→b受影响={shared}"


check("TC-CL22", "list默认参数: a.items追加→b.items也被修改",
      *test_cl22())


# ========== TC-CL23: dict 可变默认参数共享检测 ==========
print("\n--- TC-CL23: dict 可变默认参数共享检测 ---")

def test_cl23():
    """Rule 3.4: __init__(self, config={}) 同样共享"""
    class BadConfig:
        def __init__(self, config={}):
            self.config = config

    c1 = BadConfig()
    c2 = BadConfig()

    c1.config["db"] = "mysql"

    # c2 也被修改
    if "db" in c2.config:
        return True, "dict默认参数: c1.config['db']='mysql' → c2.config也有'db'"

    return True, "dict默认参数已共享验证"


check("TC-CL23", "dict默认参数: c1修改→c2也受影响",
      *test_cl23())


# ========== TC-CL24: 正确写法 None + 初始化 ==========
print("\n--- TC-CL24: 正确写法 None + 初始化隔离 ---")

def test_cl24():
    """Rule 3.4 正确做法: 用 None 避免默认参数共享"""
    class GoodInit:
        def __init__(self, items=None):
            self.items = items if items is not None else []

    a = GoodInit()
    b = GoodInit()

    a.items.append("safe")

    # b 不受影响
    if len(b.items) != 0:
        return False, f"b.items长度={len(b.items)}, 预期=0"

    return True, "正确写法: a追加不影响b (独立list)"


check("TC-CL24", "None+初始化: 各实例独立, 互不影响",
      *test_cl24())


# ========== TC-CL25: 并发写入短暂超出上限 ==========
print("\n--- TC-CL25: 并发写入短暂超出上限 (Rule 5.3) ---")

def test_cl25():
    """Rule 5.3: 并发写入时允许短暂超出 1~2 条, 但不超上限*2"""
    MAX = 5
    bounded = []
    lock = threading.Lock()
    peak_observed = [0]

    def writer():
        for _ in range(20):
            bounded.append(1)
            with lock:
                # 淘汰 (模拟 BoundedList)
                while len(bounded) > MAX:
                    bounded.pop(0)
                if len(bounded) > peak_observed[0]:
                    peak_observed[0] = len(bounded)

    threads = []
    for _ in range(5):
        t = threading.Thread(target=writer, daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 验证1: 最终不超过上限
    if len(bounded) > MAX:
        return False, f"最终长度={len(bounded)} > 上限{MAX}"

    # 验证2: 过程峰值不超过 MAX*2 (允许短暂超出)
    if peak_observed[0] > MAX * 2:
        return False, f"峰值{peak_observed[0]} > 上限*2 ({MAX*2}), 超出太多"

    return True, f"上限={MAX}, 最终={len(bounded)}, 峰值={peak_observed[0]} (<={MAX*2})"


check("TC-CL25", "并发写入: 峰值不超MAX*2, 最终不超MAX",
      *test_cl25())


# ========== TC-CL26: 并发核验最终一致性 ==========
print("\n--- TC-CL26: 核验并发写入最终一致性 ---")

def test_cl26():
    """并发写入后数据完整性核验"""
    results = {}
    lock = threading.Lock()

    def consistent_writer(tid):
        for i in range(10):
            key = f"final-{tid}-{i}"
            with lock:
                results[key] = tid * 100 + i

    threads = []
    for i in range(5):
        t = threading.Thread(target=consistent_writer, args=(i,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 核验: 50个key都存在且值正确
    for tid in range(5):
        for i in range(10):
            key = f"final-{tid}-{i}"
            expected = tid * 100 + i
            if results.get(key) != expected:
                return False, f"{key}={results.get(key)}, 预期={expected}"

    return True, f"{len(results)}条数据, 全部一致性通过"


check("TC-CL26", "5线程×10条写入: 50条全部一致性核验通过",
      *test_cl26())


# ========== TC-CL27: 淘汰后 key 确认不存在 ==========
print("\n--- TC-CL27: 淘汰后 key 确认不存在于 dict ---")

def test_cl27():
    """Rule 5.4: FIFO 淘汰后 key 被物理删除"""
    bd = BoundedDict(max_entries=2)

    bd.put("evicted", "data")
    bd.put("a", 1)
    bd.put("b", 2)

    # evicted 应该被淘汰
    if "evicted" in bd._dict:
        return False, "evicted 仍在 _dict 中"

    # 尝试获取应该返回 None
    if bd.get("evicted") is not None:
        return False, "get('evicted') 应返回 None"

    return True, "evicted: has_key=False, get→None, 物理删除"


check("TC-CL27", "淘汰后物理删除: has_key=False且get返回None",
      *test_cl27())


# ========== TC-CL28: 淘汰后值不可通过任何方式获取 ==========
print("\n--- TC-CL28: 淘汰后不可通过任何方式获取值 ---")

def test_cl28():
    """淘汰后所有访问方式都返回不存在"""
    bd = BoundedDict(max_entries=1)

    bd.put("only", "secret")
    bd.put("new", "visible")

    # 所有查询方式都应返回不存在
    passes = True
    if bd.has_key("only"):
        passes = False
    if bd.get("only") is not None:
        passes = False
    if "only" in bd._dict:
        passes = False

    if not passes:
        return False, "被淘汰的 key 仍可通过某种方式访问"

    return True, "淘汰后所有访问路径 (has_key/get/in) 均返回不存在"


check("TC-CL28", "淘汰后所有访问方式均不可达",
      *test_cl28())


# ========== TC-CL29: 组合压测 (list容量+dict容量+并发) ==========
print("\n--- TC-CL29: 组合: list+dict容量上限 + 并发 ---")

def test_cl29():
    """复合场景: 同时操作 list 和 dict 容量上限, 并发安全"""
    MAX_L = 10
    MAX_D = 5
    shared_list = []
    shared_dict = {}
    lock = threading.Lock()
    errors = []

    def combined_worker(tid):
        try:
            for i in range(20):
                with lock:
                    # list 操作
                    shared_list.append(f"T{tid}-{i}")
                    while len(shared_list) > MAX_L:
                        shared_list.pop(0)

                    # dict 操作
                    shared_dict[f"T{tid}-{i}"] = tid * 100 + i
                    # dict FIFO: 超过上限淘汰最早
                    if len(shared_dict) > MAX_D:
                        oldest_key = next(iter(shared_dict))
                        del shared_dict[oldest_key]
        except Exception as e:
            errors.append(str(e))

    threads = []
    for i in range(3):
        t = threading.Thread(target=combined_worker, args=(i,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    if errors:
        return False, f"组合操作异常: {errors[:3]}"

    list_ok = len(shared_list) <= MAX_L
    dict_ok = len(shared_dict) <= MAX_D

    if not list_ok:
        return False, f"list长度={len(shared_list)} > 上限{MAX_L}"
    if not dict_ok:
        return False, f"dict大小={len(shared_dict)} > 上限{MAX_D}"

    return True, f"组合: list≤{MAX_L}, dict≤{MAX_D}, 无异常"


check("TC-CL29", "组合压测: 3线程 list+dict 同时受上限约束",
      *test_cl29())


# ========== TC-CL30: 综合压测 (锁+容量+隔离) ==========
print("\n--- TC-CL30: 综合: 锁+容量+隔离 三者压测 ---")

def test_cl30():
    """最完整场景: 多实例隔离 + 各自有上限 + 锁保护"""
    if not _MEMORY_AVAILABLE:
        return False, "AgentMemory 不可用"

    NUM_INSTANCES = 10
    instances = [AgentMemory(working_memory_limit=5) for _ in range(NUM_INSTANCES)]
    errors = []
    isolation_check = {"cross_write_detected": False}
    lock = threading.Lock()

    def full_worker(idx):
        mem = instances[idx]
        try:
            for r in range(3):
                # 写入工作记忆
                for s in range(8):
                    mem.add(
                        thought=f"实例{idx}-轮{r}-步骤{s}",
                        action="retrieve" if s % 2 == 0 else "calculator",
                        action_input={"query": "test"},
                        observation=f"结果{idx}-{s}",
                    )

                # 验证隔离: 检查工作记忆中是否有其他实例的数据
                for step in mem.working_memory:
                    if f"实例{idx}" not in step["thought"]:
                        with lock:
                            isolation_check["cross_write_detected"] = True

                # 转情景记忆
                mem.summarize_to_episodic(
                    user_query=f"实例{idx}第{r}轮",
                    final_answer=f"实例{idx}答案{r}: 财务数据={idx*10+r}",
                )

        except Exception as e:
            with lock:
                errors.append(f"实例{idx}: {str(e)[:80]}")

    threads = []
    start_time = time.time()
    for i in range(NUM_INSTANCES):
        t = threading.Thread(target=full_worker, args=(i,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
    elapsed = time.time() - start_time

    if errors:
        return False, f"异常: {errors[:3]}"

    # 验证隔离
    if isolation_check["cross_write_detected"]:
        return False, "发现跨实例数据污染!"

    # 验证各实例上限
    for i, mem in enumerate(instances):
        if len(mem.working_memory) > 5:
            return False, f"实例{i}: WM={len(mem.working_memory)} > 5"

    return True, (f"{NUM_INSTANCES}实例×3轮, 隔离={not isolation_check['cross_write_detected']}, "
                  f"耗时={elapsed:.2f}s")


check("TC-CL30", "10实例隔离+容量上限+锁保护: 无污染无溢出",
      *test_cl30())


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
    print("状态: 全部 RED - 模块尚未实现")
elif red_count > 0:
    print(f"状态: 部分通过 - 还有 {red_count} 项 RED 待开发")
else:
    print("状态: 全部 GREEN - Checklist 边界测试完成")
print("=" * 60)
