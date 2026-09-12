# -*- coding: utf-8 -*-
"""隔离测试 Compose 的静态契约。"""

from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_staging_compose_isolated_from_production_resources() -> None:
    """测试栈必须使用独立端口、数据目录、容器名与网络。"""
    compose = yaml.safe_load(
        (PROJECT_ROOT / "docker-compose.staging.yml").read_text(encoding="utf-8")
    )
    backend = compose["services"]["backend"]
    frontend = compose["services"]["frontend"]

    assert backend["container_name"] == "rag-backend-staging"
    assert frontend["container_name"] == "rag-frontend-staging"
    assert backend["ports"] == ["127.0.0.1:18000:8000"]
    assert frontend["ports"] == ["127.0.0.1:18081:80"]
    assert backend["volumes"] == ["./.staging/data:/app/data"]
    assert backend["env_file"] == ["${STAGING_ENV_FILE:-.env.staging}"]
    assert "./data:/app/data" not in backend["volumes"]
    assert all("/app/config" not in volume for volume in backend["volumes"])
    assert compose["networks"]["rag-staging-network"]["name"] == "rag-staging-network"


def test_staging_compose_limits_resources_and_keeps_credentials_local() -> None:
    """共机测试服务不可自动重启，凭据文件必须保持未跟踪。"""
    compose = yaml.safe_load(
        (PROJECT_ROOT / "docker-compose.staging.yml").read_text(encoding="utf-8")
    )
    for service in compose["services"].values():
        assert service["restart"] == "no"
        assert service["cpus"] in {"0.75", "0.25"}
        assert service["mem_limit"] in {"1g", "128m"}

    environment_template = (PROJECT_ROOT / "staging.env.example").read_text(encoding="utf-8")
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "RESEARCH_SESSION_COOKIE_SECURE=false" in environment_template
    active_environment_lines = [
        line.strip()
        for line in environment_template.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert not any(line.startswith("DASHSCOPE_API_KEY=") for line in active_environment_lines)
    assert ".env.staging" in gitignore
