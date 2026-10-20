"""Offline tests for the strict, explicit MPEP maintenance build."""

from __future__ import annotations

import asyncio
import importlib.util
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "pca_ts_mpep_build", Path(__file__).with_name("build-mpep-corpus.py")
)
assert spec and spec.loader
builder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)


def roots():
    return [
        builder.Root(f"chapter{n}.html", f"{n:04} - Chapter", str(n)) for n in range(100, 3000, 100)
    ]


def test_official_toc_requires_pinned_identity_and_all_chapters():
    nodes = "".join(
        f'<li title="{r.title}"><a href="#/current/{r.href}"></a></li>' for r in roots()
    )
    toc = f"<div>{builder.RELEASE} Version{nodes}</div>"
    assert builder.parse_roots(toc) == roots()
    with pytest.raises(ValueError, match="pinned release"):
        builder.parse_roots(toc.replace(builder.RELEASE, "older"))
    with pytest.raises(ValueError, match="29 numbered"):
        builder.parse_roots(toc.replace(nodes[: nodes.index("</li>") + 5], ""))
    with pytest.raises(ValueError, match="Malformed"):
        builder.parse_roots(toc.replace("chapter100.html", "../escape.html"))


def test_acquisition_rejects_wrong_empty_or_incomplete_responses():
    async def acquire(**overrides):
        async def fetch(root):
            return SimpleNamespace(
                source_version=builder.RELEASE, chapter=root.chapter, sections=[1], **overrides
            )

        return await builder.acquire_pages(roots(), fetch, max_requests=29)

    assert len(asyncio.run(acquire())) == 29

    async def wrong(root):
        return SimpleNamespace(source_version="current", chapter=root.chapter, sections=[1])

    with pytest.raises(ValueError, match="release identity"):
        asyncio.run(builder.acquire_pages(roots(), wrong, max_requests=29))

    async def empty(root):
        return SimpleNamespace(source_version=builder.RELEASE, chapter=root.chapter, sections=[])

    with pytest.raises(ValueError, match="no indexable"):
        asyncio.run(builder.acquire_pages(roots(), empty, max_requests=29))

    async def mismatch(root):
        return SimpleNamespace(source_version=builder.RELEASE, chapter="9999", sections=[1])

    with pytest.raises(ValueError, match="Chapter response"):
        asyncio.run(builder.acquire_pages(roots(), mismatch, max_requests=29))
    with pytest.raises(ValueError, match="budget"):
        asyncio.run(builder.acquire_pages(roots(), wrong, max_requests=28))


def test_fetch_failure_is_not_silently_skipped():
    async def fail(_root):
        raise RuntimeError("offline synthetic fetch failure")

    with pytest.raises(RuntimeError, match="synthetic fetch failure"):
        asyncio.run(builder.acquire_pages(roots(), fail, max_requests=29))


def test_standalone_copy_preserves_rows_and_finalizes_delete_mode(tmp_path):
    source = tmp_path / "source.db"
    conn = sqlite3.connect(source)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT)")
    conn.execute("INSERT INTO meta VALUES('source_version',?)", (builder.RELEASE,))
    conn.commit()
    conn.close()
    source_bytes = source.read_bytes()
    target = tmp_path / "target.db"
    builder.standalone_copy(source, target)
    assert source.read_bytes() == source_bytes
    assert target.read_bytes()[18:20] == b"\x01\x01"
    check = sqlite3.connect(target.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        assert check.execute("SELECT value FROM meta").fetchone()[0] == builder.RELEASE
        assert check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        check.close()


def test_existing_output_is_preserved_before_import_or_fetch(tmp_path):
    output = tmp_path / "existing.db"
    output.write_bytes(b"preserve existing artifact")
    with pytest.raises(ValueError, match="never overwritten"):
        asyncio.run(builder.build(SimpleNamespace(output=output)))
    assert output.read_bytes() == b"preserve existing artifact"


def test_offline_rebuild_preserves_old_source_age_separately_from_build_time():
    receipts = [
        {"retrieved_at": "2024-11-01T09:00:00-05:00"},
        {"retrieved_at": "2024-11-01T14:15:00Z"},
    ]
    original = builder.source_time_metadata(
        receipts, built_at=datetime(2024, 11, 1, 15, tzinfo=UTC)
    )
    rebuilt = builder.source_time_metadata(
        receipts, built_at=datetime(2026, 10, 20, 18, tzinfo=UTC)
    )
    assert original["synced_at"] == rebuilt["synced_at"] == "2024-11-01T14:15:00+00:00"
    assert original["snapshot_date"] == rebuilt["snapshot_date"] == "2024-11-01"
    assert original["release_checked_at"] == rebuilt["release_checked_at"] == "2024-11-01"
    assert rebuilt["source_first_retrieved_at"] == "2024-11-01T14:00:00+00:00"
    assert rebuilt["source_last_retrieved_at"] == rebuilt["synced_at"]
    assert original["artifact_built_at"] != rebuilt["artifact_built_at"]


@pytest.mark.parametrize(
    "receipts",
    [
        [],
        [{}],
        [{"retrieved_at": None}],
        [{"retrieved_at": "not a date"}],
        [{"retrieved_at": "2024-11-01"}],
        [{"retrieved_at": "2024-11-01T10:00:00"}],
        [{"retrieved_at": "2026-10-21T00:00:00Z"}],
        [{"retrieved_at": "2024-11-01T00:00:00Z"}, {"retrieved_at": "invalid"}],
    ],
)
def test_invalid_source_receipt_times_are_rejected(receipts):
    with pytest.raises(ValueError):
        builder.source_time_metadata(receipts, built_at=datetime(2026, 10, 20, tzinfo=UTC))
