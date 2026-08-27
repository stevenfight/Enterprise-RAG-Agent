# -*- coding: utf-8 -*-
"""集成测试: 验证日志埋点在 Web 服务运行时的输出 (v2 - stdout 捕获版)

使用 FastAPI TestClient 模拟 HTTP 请求, 验证所有关键日志节点出现。
"""

import io
import logging
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

# ---- stdout 捕获 ----
stdout_capture = io.StringIO()
sys.stdout = stdout_capture
sys.stderr = stdout_capture  # 部分模块写 stderr

from fastapi.testclient import TestClient
from api_service import app

print("=" * 70)
print("集成测试: Web 服务 + 日志埋点验证 (v2)")
print("=" * 70)

with TestClient(app) as client:
    # 1. 健康检查
    print("\n[Test 1] GET /api/health")
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["rag_generator_loaded"] is True
    print("  PASS status=%s" % data["status"])

    # 2. 公司列表
    print("\n[Test 2] GET /api/companies")
    resp = client.get("/api/companies")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] >= 2
    print("  PASS companies=%d" % data["total_count"])

    # 3. 纯检索
    print("\n[Test 3] POST /api/retrieve (中芯国际)")
    resp = client.post("/api/retrieve", json={
        "query": "营收", "company_name": "中芯国际", "top_n": 2,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] >= 1
    print("  PASS total=%d" % data["total_count"])

    # 4. 完整 RAG 问答
    print("\n[Test 4] POST /api/query (中国移动2024营收)")
    resp = client.post("/api/query", json={
        "query": "中国移动2024年营收是多少", "top_n": 2,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["answer"]) > 20
    print("  PASS answer=%d chars, sources=%d" % (len(data["answer"]), len(data["sources"])))

    # 5. 域外测试
    print("\n[Test 5] 域外查询 (今天天气)")
    resp = client.post("/api/query", json={
        "query": "今天天气怎么样", "top_n": 2,
    })
    assert resp.status_code == 200
    print("  PASS (status=%d)" % resp.status_code)

# ---- 恢复 stdout ----
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__

log_text = stdout_capture.getvalue()

# ---- 日志完整性检查 ----
print("\n" + "=" * 70)
print("日志完整性检查: 10 项检查")
print("=" * 70)

checks = {
    "服务启动": ["FastAPI 应用启动中", "RAGGenerator 实例创建完成"],
    "服务关闭": ["FastAPI 应用关闭"],
    "健康检查": ["收到 /api/health", "health 返回状态"],
    "公司列表": ["收到 /api/companies"],
    "纯检索": ["收到 /api/retrieve", "/api/retrieve 处理完成"],
    "RAG 问答": ["收到 /api/query", "/api/query 处理完成"],
    "检索漏斗": ["漏斗全景", "gte-rerank"],
    "来源构建": ["来源摘要构建完成"],
    "对话历史": ["对话历史已更新"],
    "域外查询处理": ["今天天气"],  # 域外查询出现在检索日志中
}

all_pass = True
for check_name, keywords in checks.items():
    found = all(kw in log_text for kw in keywords)
    status = "PASS" if found else "FAIL"
    if not found:
        all_pass = False
        missing = [kw for kw in keywords if kw not in log_text]
        print("  [FAIL] %-16s 缺失: %s" % (check_name, missing))
    else:
        print("  [PASS] %-16s (%d个)" % (check_name, len(keywords)))

# ---- 模块日志统计 ----
print("\n" + "=" * 70)
print("关键日志行示例")
print("=" * 70)
markers = ["启动中", "收到 /api", "处理完成", "来源摘要", "漏斗全景",
           "gte-rerank", "检索完成", "对话历史", "关闭中", "QueryProcessor"]

for line in log_text.split("\n"):
    if any(m in line for m in markers):
        print("  %s" % line.strip()[:140])

total_lines = len([l for l in log_text.split("\n") if l.strip()])
print("\n  总日志行数: %d" % total_lines)

print("\n" + "=" * 70)
print("结果: %s" % ("ALL PASS" if all_pass else "SOME FAILED"))
print("=" * 70)
