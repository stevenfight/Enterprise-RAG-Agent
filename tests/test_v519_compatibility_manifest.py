"""v5.19 兼容基线清单必须持续可定位且不可被静默篡改。"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / "evals" / "fixtures" / "v5.19-compatibility-manifest.json"
GIT_BASELINE_AVAILABLE = (REPOSITORY_ROOT / ".git").exists() and shutil.which("git") is not None


def _git(*args: str) -> str:
    """在仓库根目录执行只读 Git 查询。"""
    result = subprocess.run(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        encoding="utf-8",
        text=True,
    )
    return result.stdout.strip()


@pytest.mark.skipif(
    not GIT_BASELINE_AVAILABLE,
    reason="v5.19 Git 指纹核验需要包含 .git 的工作树和 git 可执行文件",
)
def test_v519_manifest_freezes_tracked_configuration_fingerprints() -> None:
    """配置夹具只记录 Git 指纹，避免将可能含敏感值的配置内容复制进测试数据。"""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 1
    assert manifest["baseline_ref"] == "v5.19"
    assert manifest["baseline_commit"] == _git("rev-parse", "v5.19^{commit}")

    for item in manifest["tracked_configuration_files"]:
        actual = _git("ls-tree", "v5.19", "--", item["path"])
        assert actual.split()[2] == item["git_blob"]


def test_v519_manifest_does_not_claim_untracked_data_or_openapi_is_frozen() -> None:
    """没有可审计来源的数据或 API 快照必须保持待办，不能以占位内容冒充真实基线。"""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["untracked_data_fixtures"]
    assert all(item["status"] == "not_captured" for item in manifest["untracked_data_fixtures"])
    assert manifest["openapi_fixture_status"] == "fingerprint_captured"


def test_v519_manifest_records_isolated_openapi_and_key_json_fingerprints() -> None:
    """无密钥临时导出的接口指纹必须可审计，但不保存可能包含运行目录的响应正文。"""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    openapi = manifest["isolated_openapi_fingerprint"]
    assert openapi["path_count"] == 17
    assert openapi["sha256"] == "83267a172d0328fa17e479e9b35631212f2c73b567ecf84d2354510493f658e1"
    assert openapi["paths"] == [
        "/api/admin/filter-reload",
        "/api/admin/filter-status",
        "/api/agent/plan",
        "/api/agent/query",
        "/api/agent/stream",
        "/api/charts/list",
        "/api/companies",
        "/api/comparisons/verified",
        "/api/health",
        "/api/knowledge/documents",
        "/api/knowledge/documents/{filename}",
        "/api/knowledge/upload",
        "/api/langbot/chat",
        "/api/query",
        "/api/retrieve",
        "/api/system/status",
        "/v1/chat/completions",
    ]
    assert manifest["key_json_fingerprints"] == {
        "/api/health": {
            "status_code": 200,
            "top_level_keys": ["agent_loaded", "filter_config_loaded", "filter_enabled", "rag_generator_loaded", "status", "vector_db_dir"],
            "body_sha256": "9a9a5c15477d6f4e2f6a353c31cf6d76738a0d288ad1d965f1808ab2729f38f1",
        },
        "/api/system/status": {
            "status_code": 401,
            "top_level_keys": ["detail"],
            "body_sha256": "818364ec80c3905abf446ec6a1037e0ef116d39b7e316fda567e5eab4dd9538e",
        },
        "/api/companies": {
            "status_code": 401,
            "top_level_keys": ["detail"],
            "body_sha256": "818364ec80c3905abf446ec6a1037e0ef116d39b7e316fda567e5eab4dd9538e",
        },
    }


def test_v519_manifest_records_candidate_openapi_as_additive() -> None:
    """候选 OpenAPI 可以新增端点，但不得移除 v5.19 已冻结路径。"""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    probe = manifest["candidate_openapi_compatibility"]
    assert probe["source_commit"] == "9e4f135"
    assert probe["path_count"] == 39
    assert probe["missing_v519_paths"] == []
    assert probe["added_path_count"] == 22


def test_v519_manifest_records_field_level_openapi_compatibility() -> None:
    """旧操作签名必须不变，既有响应模型只允许新增非必填字段。"""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    compatibility = manifest["field_level_openapi_compatibility"]
    assert compatibility["v5_operation_signature_sha256"] == "fa28c35a2e29fe57f78ce8a6ade3b99c2dae77ed8c75456a6f16ff4a752c7466"
    assert compatibility["candidate_old_operation_signature_sha256"] == compatibility["v5_operation_signature_sha256"]
    assert compatibility["missing_v5_components"] == []
    assert compatibility["changed_components"] == {
        "KnowledgeUploadResponse": {
            "preserved_properties": ["filename", "size", "size_mb", "success"],
            "added_optional_properties": ["document_version_id", "idempotent", "index_status", "logical_document_id", "physical_page_count", "processing_status", "sha256"],
            "required_fields_unchanged": True,
        },
        "SourceInfo": {
            "preserved_properties": ["company_name", "excerpt", "index", "pages", "scores", "source_file"],
            "added_optional_properties": ["document_pages", "visual_locator", "visual_preview_status"],
            "required_fields_unchanged": True,
        },
    }


def test_v519_manifest_records_no_key_response_compatibility() -> None:
    """除单独记录的 SSE 安全例外外，无 Key 基线必须保持可审计。"""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    compatibility = manifest["no_key_response_compatibility"]
    assert compatibility["source_snapshot_commit"] == "588855b"
    assert compatibility["scope_excludes_historical_stream_auth_debt"] is True
    assert compatibility["probe_count"] == 14
    assert compatibility["missing_v519_probes"] == []
    assert compatibility["changed_v519_probes"] == []
    assert compatibility["authentication_rejection"] == {
        "count": 12,
        "status_code": 401,
        "top_level_keys": ["detail"],
        "body_sha256": "818364ec80c3905abf446ec6a1037e0ef116d39b7e316fda567e5eab4dd9538e",
    }
    assert compatibility["validation_before_auth"] == {
        "count": 1,
        "status_code": 422,
        "top_level_keys": ["detail"],
        "body_sha256": "a6fbb2d832df15dd175890812c1f96f186422d38332b79c1421c8ef4977df57e",
    }
    assert compatibility["health"] == {
        "status_code": 200,
        "top_level_keys": ["agent_loaded", "filter_config_loaded", "filter_enabled", "rag_generator_loaded", "status", "vector_db_dir"],
        "redacted_body_sha256": "5c80712364a40d67bde3a6ac1293d62bfd6b66c3c05b3401efd3b2cde199b527",
        "redacted_fields": ["vector_db_dir"],
    }


def test_v519_manifest_records_stream_auth_remediation_as_security_exception() -> None:
    """v5.19 流式鉴权旁路必须保留历史证据，并明确候选已安全修复。"""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    debt = manifest["historical_stream_auth_debt"]
    assert debt["status"] == "remediated_security_exception"
    assert debt["v519_behavior"]["no_key_with_query"] == {
        "status_code": 503,
        "top_level_keys": ["detail"],
        "body_sha256": "8ea356623b408e7a5ca0843ec88548beee6be96653e79d53cdc4d9ee85599531",
    }
    assert debt["v519_behavior"]["invalid_key_with_query"] == debt["v519_behavior"]["no_key_with_query"]
    assert debt["candidate_remediation"] == {
        "verification_test": "tests/test_agent_stream_auth.py",
        "no_key_status_code": 401,
        "invalid_key_status_code": 401,
        "valid_bearer_reaches_downstream": True,
        "valid_research_session_reaches_downstream": True,
    }
    assert debt["compatibility_exception_reason"] == "修复 API Key 中间件对白名单 SSE 路径的鉴权旁路。"
