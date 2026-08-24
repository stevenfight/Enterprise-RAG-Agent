"""后端 API 冒烟测试 — 验证导入修改后所有关键端点正常"""
import json
from pathlib import Path

import requests

base = "http://localhost:8000"
config_path = Path(__file__).resolve().parents[1] / "config" / "agent_config.json"
with config_path.open("r", encoding="utf-8") as f:
    api_key = json.load(f).get("api", {}).get("key", "no-key-needed")
headers = {"Authorization": f"Bearer {api_key}"}
passed = 0
failed = 0

def check(name, status_code, condition, detail=""):
    global passed, failed
    if 200 <= status_code < 500 and condition:
        print(f"  [PASS] {name}: HTTP {status_code} {detail}")
        passed += 1
    else:
        print(f"  [FAIL] {name}: HTTP {status_code} {detail}")
        failed += 1

print("=== 后端 API 冒烟测试 ===\n")

# 1. 健康检查
r = requests.get(f"{base}/api/health")
data = r.json()
check("GET /api/health", r.status_code,
      data.get("status") == "ok" and data.get("agent_loaded") == True,
      f"agent_loaded={data.get('agent_loaded')}, rag={data.get('rag_generator_loaded')}")

# 2. 图表列表
r = requests.get(f"{base}/api/charts/list", headers=headers)
data = r.json()
check("GET /api/charts/list", r.status_code,
      isinstance(data.get("charts"), list) and data.get("total") == len(data["charts"]),
      f"返回 {data.get('total', 0)} 项")

# 3. Agent 规划
r = requests.get(
    f"{base}/api/agent/plan",
    headers=headers,
    params={"query": "对比三大运营商营收"},
)
data = r.json()
check("GET /api/agent/plan", r.status_code,
      isinstance(data.get("nodes"), list)
      and isinstance(data.get("edges"), list)
      and isinstance(data.get("execution_order"), list),
      f"keys={list(data.keys())[:3]}")

# 4. Agent 查询 (轻量)
r = requests.post(f"{base}/api/agent/query", headers=headers, json={
    "query": "中国移动2024年营收多少",
    "conversation_id": "smoke-test-001",
    "max_steps": 2
})
data = r.json()
check("POST /api/agent/query", r.status_code,
      "answer" in data and isinstance(data.get("reasoning_chain"), list),
      f"answer_len={len(data.get('answer',''))} steps={len(data.get('reasoning_chain',[]))}")

print(f"\n结果: {passed} PASS / {failed} FAIL (共 {passed+failed} 项)")
exit(0 if failed == 0 else 1)
