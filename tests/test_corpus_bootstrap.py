from __future__ import annotations

import hashlib
import json
from pathlib import Path

from patent_client_agents.corpus_bootstrap import check_corpora_health, main


def _write_manifest(tmp_path: Path, corpora: dict[str, bytes]) -> Path:
    manifest = {
        "schema_version": 1,
        "updated_at": "2026-08-01T00:00:00Z",
        "corpora": {
            name: {
                "uri": str(tmp_path / "source" / f"{name}.db"),
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
                "local_filename": f"{name}.db",
                "snapshot": "2026-08-01",
                "built_at": "2026-08-01T00:00:00Z",
                "section_count": 1,
                "source_version": "test",
            }
            for name, content in corpora.items()
        },
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_check_corpora_health_reports_ready_missing_and_mismatch(tmp_path: Path):
    manifest = _write_manifest(
        tmp_path, {"ready": b"ready", "missing": b"missing", "stale": b"new"}
    )
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "ready.db").write_bytes(b"ready")
    (cache / "stale.db").write_bytes(b"old")

    report = check_corpora_health(str(manifest), cache)

    assert report.healthy is False
    assert {item.name: item.status for item in report.corpora} == {
        "ready": "ready",
        "missing": "missing",
        "stale": "sha_mismatch",
    }
    assert report.corpora[0].actual_size_bytes == 5


def test_check_corpora_health_only_limits_report(tmp_path: Path):
    manifest = _write_manifest(tmp_path, {"one": b"one", "two": b"two"})
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "two.db").write_bytes(b"two")

    report = check_corpora_health(str(manifest), cache, only=["two"])

    assert report.healthy is True
    assert [item.name for item in report.corpora] == ["two"]


def test_check_cli_prints_json_and_returns_nonzero_for_unhealthy(tmp_path: Path, capsys):
    manifest = _write_manifest(tmp_path, {"missing": b"content"})

    result = main([str(manifest), "--cache-dir", str(tmp_path / "cache"), "--check", "--json"])

    output = json.loads(capsys.readouterr().out)
    assert result == 1
    assert output["healthy"] is False
    assert output["corpora"][0]["status"] == "missing"
