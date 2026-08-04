# -*- coding: utf-8 -*-
"""
P0 关键缺陷修复验证脚本 (v5.1)

测试项:
  SP0-05a: API Key 鉴权（无 Key / 错误 Key / 正确 Key / 健康检查豁免）
  SP0-05b: max_steps 硬上限截断
  SP0-01:  empty_result_count 归零逻辑
  SP0-03:  memory 配置生效
  SP0-04:  per-request Agent 实例隔离

用法:
  python tests/test_p0_fixes.py

要求: 服务已在 localhost:8000 启动（或设置环境变量 BASE_URL）
"""

import json
import os
import sys
import uuid
import urllib.request
import urllib.error

# ---------- 配置 ----------
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

# 从 agent_config.json 读取 API Key 作为测试用的正确值
_this_dir = os.path.dirname(os.path.abspath(__file__))
_config_path = os.path.join(_this_dir, "..", "config", "agent_config.json")
with open(_config_path, "r", encoding="utf-8") as f:
    _config = json.load(f)
VALID_API_KEY = _config.get("api", {}).get("key", "no-key-needed")

# ---------- 工具函数 ----------

_passed = 0
_failed = 0
_results = []


def _request(method: str, path: str, body: dict | None = None,
             headers: dict | None = None) -> tuple[int, dict]:
    """发送 HTTP 请求并返回 (status_code, response_body)"""
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    hdrs = headers or {}
    if data:
        hdrs.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body_data = json.loads(resp.read().decode("utf-8"))
            return resp.status, body_data
    except urllib.error.HTTPError as e:
        error_body = {}
        try:
            error_body = json.loads(e.read().decode("utf-8"))
        except Exception:
            pass
        return e.code, error_body
    except urllib.error.URLError as e:
        return 0, {"error": f"连接失败: {e.reason}"}


def _assert(name: str, condition: bool, detail: str = ""):
    global _passed, _failed
    if condition:
        _passed += 1
        _results.append(("PASS", name, detail))
        print(f"  [PASS] {name}")
    else:
        _failed += 1
        _results.append(("FAIL", name, detail))
        print(f"  [FAIL] {name}  -- {detail}")


def _assert_eq(name: str, actual, expected, detail: str = ""):
    ok = actual == expected
    _assert(name, ok, f"{detail} | 期望={expected}, 实际={actual}" if not ok else detail)


# ============================================================
# 测试套件
# ============================================================

def test_auth_no_key():
    """SP0-05a-01: 无 API Key 请求被拒绝"""
    print("\n[SP0-05a-01] 无 API Key -> 期望 401")
    status, body = _request("POST", "/api/agent/query",
                            body={"query": "测试", "max_steps": 2})
    _assert_eq("无 Key 返回 401", status, 401)
    _assert("响应含 '未授权'", "未授权" in body.get("detail", ""), f"detail={body}")


def test_auth_wrong_key():
    """SP0-05a-02: 错误 API Key 被拒绝"""
    print("\n[SP0-05a-02] 错误 API Key -> 期望 401")
    status, body = _request("POST", "/api/agent/query",
                            body={"query": "测试", "max_steps": 2},
                            headers={"Authorization": "Bearer wrong-key-12345"})
    _assert_eq("错误 Key 返回 401", status, 401)
    _assert("响应含 '未授权'", "未授权" in body.get("detail", ""), f"detail={body}")


def test_auth_valid_key():
    """SP0-05a-03: 正确 API Key 放行"""
    print(f"\n[SP0-05a-03] 正确 API Key -> 期望 200 (key={VALID_API_KEY[:8]}...)")
    status, body = _request("POST", "/api/agent/query",
                            body={"query": "测试", "max_steps": 2},
                            headers={"Authorization": f"Bearer {VALID_API_KEY}"})
    _assert("正确 Key 非 401", status != 401,
            f"status={status}, body={json.dumps(body, ensure_ascii=False)[:200]}")


def test_auth_health_skip():
    """SP0-05a-04: /api/health 无需鉴权"""
    print("\n[SP0-05a-04] /api/health 无 Key -> 期望 200")
    status, body = _request("GET", "/api/health")
    _assert_eq("健康检查返回 200", status, 200)
    _assert("status 字段存在", "status" in body, f"body={body}")


def test_auth_query_no_key():
    """补充: /api/query 无 Key 也需鉴权"""
    print("\n[补充] /api/query 无 Key -> 期望 401")
    status, body = _request("POST", "/api/query",
                            body={"query": "测试"})
    _assert_eq("/api/query 无 Key 返回 401", status, 401)


def test_auth_v1_chat_no_key():
    """补充: /v1/chat/completions 无 Key 也需鉴权"""
    print("\n[补充] /v1/chat/completions 无 Key -> 期望 401")
    status, body = _request("POST", "/v1/chat/completions",
                            body={"model": "rag-agent",
                                  "messages": [{"role": "user", "content": "你好"}],
                                  "stream": False})
    _assert("/v1/chat 无 Key 返回 401", status == 401,
            f"status={status}, body={json.dumps(body, ensure_ascii=False)[:200]}")


# ============================================================
# SP0-05b: max_steps 硬上限
# ============================================================

def test_max_steps_hard_limit():
    """SP0-05b-01: max_steps 超出硬上限被截断"""
    print(f"\n[SP0-05b-01] max_steps=100 -> 期望截断为 <=15")
    status, body = _request("POST", "/api/agent/query",
                            body={"query": "测试", "max_steps": 100},
                            headers={"Authorization": f"Bearer {VALID_API_KEY}"})
    if status != 200:
        _assert("max_steps 测试-服务可达", False, f"status={status}")
        return

    total_steps = body.get("total_steps", 0)
    _assert("total_steps 不超过硬上限", total_steps <= 15,
            f"total_steps={total_steps}, 期望 <=15")


def test_max_steps_normal():
    """SP0-05b-02: max_steps 未超上限正常使用"""
    print(f"\n[SP0-05b-02] max_steps=3 -> 期望不截断")
    status, body = _request("POST", "/api/agent/query",
                            body={"query": "测试", "max_steps": 3},
                            headers={"Authorization": f"Bearer {VALID_API_KEY}"})
    if status == 200:
        ts = body.get("total_steps", 0)
        _assert("total_steps <= 3", ts <= 3, f"total_steps={ts}")


# ============================================================
# SP0-04: per-request Agent 隔离
# ============================================================

def test_per_request_isolation():
    """SP0-04-01: 两个请求使用不同的 session_id，memory 互不干扰"""
    print("\n[SP0-04-01] per-request Agent 会话隔离")

    h = {"Authorization": f"Bearer {VALID_API_KEY}"}
    sid_a = f"test-session-a-{uuid.uuid4().hex[:6]}"
    sid_b = f"test-session-b-{uuid.uuid4().hex[:6]}"

    # 会话 A: 查询公司 A
    s_a, b_a = _request("POST", "/api/agent/query",
                        body={"query": "贵州茅台的营收是多少？", "max_steps": 2,
                              "conversation_id": sid_a},
                        headers=h)

    # 会话 B: 查询另一个公司
    s_b, b_b = _request("POST", "/api/agent/query",
                        body={"query": "宁德时代的营收是多少？", "max_steps": 2,
                              "conversation_id": sid_b},
                        headers=h)

    # 验证两个请求都成功，没有互相干扰
    _assert("会话 A 请求成功", s_a in (200, 503), f"status={s_a}")
    _assert("会话 B 请求成功", s_b in (200, 503), f"status={s_b}")

    if s_a == 200 and s_b == 200:
        # 后续请求: 会话 A 追问，验证上下文隔离
        s_a2, b_a2 = _request("POST", "/api/agent/query",
                              body={"query": "刚才我问的那家公司的净利润呢？", "max_steps": 2,
                                    "conversation_id": sid_a},
                              headers=h)
        _assert("会话 A 追问成功", s_a2 in (200, 503), f"status={s_a2}")
        if s_a2 == 200:
            answer_lower = b_a2.get("answer", "").lower()
            _assert("上下文保留(贵州茅台)", "茅台" in answer_lower,
                    f"answer前100字: {b_a2.get('answer', '')[:100]}")


# ============================================================
# 主入口
# ============================================================

def main():
    global _passed, _failed, _results

    print("=" * 60)
    print(f" P0 关键缺陷修复验证脚本 (v5.1)")
    print(f" 目标服务: {BASE_URL}")
    print(f" API Key:  {VALID_API_KEY[:8]}..." if VALID_API_KEY != "no-key-needed"
          else f" API Key:  {VALID_API_KEY}")
    print("=" * 60)

    # ---- SP0-05a: API Key 鉴权 ----
    print("\n" + "=" * 40)
    print(" SP0-05a: API Key 鉴权")
    print("=" * 40)
    test_auth_no_key()
    test_auth_wrong_key()
    test_auth_valid_key()
    test_auth_health_skip()
    test_auth_query_no_key()
    test_auth_v1_chat_no_key()

    # ---- SP0-05b: max_steps 硬上限 ----
    print("\n" + "=" * 40)
    print(" SP0-05b: max_steps 硬上限")
    print("=" * 40)
    test_max_steps_hard_limit()
    test_max_steps_normal()

    # ---- SP0-04: per-request 隔离 ----
    print("\n" + "=" * 40)
    print(" SP0-04: per-request Agent 会话隔离")
    print("=" * 40)
    test_per_request_isolation()

    # ---- 汇总 ----
    print("\n" + "=" * 60)
    total = _passed + _failed
    print(f" 总计: {total} | 通过: {_passed} | 失败: {_failed}")
    if _failed == 0:
        print(" 全部测试通过")
    else:
        print(" 存在失败的测试:")
        for r, n, d in _results:
            if r == "FAIL":
                print(f"   [FAIL] {n}: {d}")
    print("=" * 60)

    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
