"""Regression tests for the nightly fee snapshot publication policy."""

from argparse import Namespace
from pathlib import Path

import pytest

from scripts import build_fees_snapshot


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
