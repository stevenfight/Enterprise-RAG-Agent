"""端到端测试：前端代理 + 后端完整链路"""
import requests

base = "http://localhost:5173"
passed = 0
failed = 0

def check(name, ok, detail=""):
    global passed, failed
    if ok:
        print(f"  [PASS] {name}: {detail}")
        passed += 1
    else:
        print(f"  [FAIL] {name}: {detail}")
        failed += 1

print("=== 前后端 E2E 集成测试 ===\n")

# 1. 前端页面可访问
r = requests.get(f"{base}/")
check("前端首页", r.status_code == 200 and "DOCTYPE" in r.text,
      f"HTTP {r.status_code}, size={len(r.text)}")

# 2. Vite 代理 → 后端健康检查
r = requests.get(f"{base}/api/health")
try:
    data = r.json()
    ok = data.get("agent_loaded") is True
    check("代理 /api/health", ok,
          f"status={data.get('status')}, agent={data.get('agent_loaded')}")
except:
    check("代理 /api/health", False, f"HTTP {r.status_code}, 非JSON响应")

# 3. 代理 → Agent 查询 (完整 ReAct)
r = requests.post(f"{base}/api/agent/query", json={
    "query": "中国移动2024年营收多少亿元",
    "session_id": "e2e-verify-001",
    "max_steps": 2
})
try:
    data = r.json()
    has_answer = len(data.get("answer", "")) > 10
    has_steps = isinstance(data.get("reasoning_chain"), list)
    check("代理 /api/agent/query", has_answer and has_steps,
          f"answer={data.get('answer','')[:50]}..., steps={len(data.get('reasoning_chain',[]))}")
except Exception as e:
    check("代理 /api/agent/query", False, str(e))

# 4. 前端资源可加载
r = requests.get(f"{base}/src/main.tsx")
check("前端源码可访问", r.status_code == 200,
      f"HTTP {r.status_code}")

print(f"\n结果: {passed} PASS / {failed} FAIL (共 {passed+failed} 项)")
exit(0 if failed == 0 else 1)
