"""Regression tests for the nightly fee snapshot publication policy."""

import re
from argparse import Namespace
from pathlib import Path

import pytest
import yaml

from scripts import build_fees_snapshot

_REPO_ROOT = Path(__file__).parents[1]
_GOOGLE_API_KEY = re.compile(rb"AIza[0-9A-Za-z_-]{35}")
_RECAPTCHA_SITE_KEY = re.compile(rb'"recaptcha_site_key":"([^"]+)"')


def _args() -> Namespace:
    return Namespace(check=False, offices=None)


@pytest.mark.asyncio
async def test_all_scraper_failures_leave_index_untouched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    index = tmp_path / "index.json"
    index.write_text('{"total_schedules": 12}\n')

    async def all_failed(only: set[str] | None) -> tuple[list[dict], list[tuple[str, str]]]:
        return [], [("USPTO", "patent")]

    monkeypatch.setattr(build_fees_snapshot, "SNAPSHOT_DIR", tmp_path)
    monkeypatch.setattr(build_fees_snapshot, "_parse_args", _args)
    monkeypatch.setattr(build_fees_snapshot, "_build_all", all_failed)

    assert await build_fees_snapshot._main() == 2
    assert index.read_text() == '{"total_schedules": 12}\n'


@pytest.mark.asyncio
async def test_empty_build_without_reported_failures_leaves_index_untouched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    index = tmp_path / "index.json"
    index.write_text('{"total_schedules": 12}\n')

    async def empty_build(only: set[str] | None) -> tuple[list[dict], list[tuple[str, str]]]:
        return [], []

    monkeypatch.setattr(build_fees_snapshot, "SNAPSHOT_DIR", tmp_path)
    monkeypatch.setattr(build_fees_snapshot, "_parse_args", _args)
    monkeypatch.setattr(build_fees_snapshot, "_build_all", empty_build)

    assert await build_fees_snapshot._main() == 2
    assert index.read_text() == '{"total_schedules": 12}\n'


@pytest.mark.asyncio
async def test_partial_success_writes_index_and_returns_partial_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def partly_succeeded(
        only: set[str] | None,
    ) -> tuple[list[dict], list[tuple[str, str]]]:
        return [{"office_code": "EPO"}], [("USPTO", "patent")]

    monkeypatch.setattr(build_fees_snapshot, "SNAPSHOT_DIR", tmp_path)
    monkeypatch.setattr(build_fees_snapshot, "_parse_args", _args)
    monkeypatch.setattr(build_fees_snapshot, "_build_all", partly_succeeded)

    assert await build_fees_snapshot._main() == 1
    assert '"total_schedules": 1' in (tmp_path / "index.json").read_text()


def test_turkpatent_fixtures_do_not_contain_live_google_keys() -> None:
    fixtures = (
        "tr_turkpatent_patents_2026-05-19.html",
        "tr_turkpatent_designs_2026-05-19.html",
        "tr_turkpatent_trademarks_2026-05-19.html",
    )

    for filename in fixtures:
        content = (_REPO_ROOT / "tests" / "fees" / "fixtures" / filename).read_bytes()
        assert _GOOGLE_API_KEY.search(content) is None, filename
        assert _RECAPTCHA_SITE_KEY.findall(content) == [b"test-placeholder"], filename


def test_fee_snapshot_workflow_opens_review_pr() -> None:
    workflow_path = _REPO_ROOT / ".github" / "workflows" / "fees-snapshot.yml"
    workflow = yaml.safe_load(workflow_path.read_text())

    assert workflow["permissions"] == {"contents": "write", "pull-requests": "write"}
    assert workflow["concurrency"] == {"group": "fees-snapshot", "cancel-in-progress": False}
    checkout = workflow["jobs"]["rebuild"]["steps"][0]
    assert checkout["with"]["persist-credentials"] is False
    steps = {step["name"]: step for step in workflow["jobs"]["rebuild"]["steps"] if "name" in step}

    commit_step = steps["Commit snapshot branch"]
    assert commit_step["env"]["GH_TOKEN"] == "${{ github.token }}"
    commit_script = commit_step["run"]
    assert 'AUTOMATION_BRANCH="automation/fees-snapshot"' in commit_script
    assert "gh auth setup-git" in commit_script
    assert (
        'git push --force-with-lease origin "HEAD:refs/heads/$AUTOMATION_BRANCH"' in commit_script
    )

    pr_step = steps["Create or update snapshot pull request"]
    assert pr_step["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert "gh pr list" in pr_step["run"]
    assert "gh pr edit" in pr_step["run"]
    assert "gh pr create" in pr_step["run"]
