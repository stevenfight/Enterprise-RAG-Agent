"""v5.19 兼容基线清单必须持续可定位且不可被静默篡改。"""

import json
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / "evals" / "fixtures" / "v5.19-compatibility-manifest.json"


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
    assert manifest["openapi_fixture_status"] == "not_captured"
