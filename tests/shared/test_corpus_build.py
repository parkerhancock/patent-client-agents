"""Tests for the shared corpus build scaffolding and the builds that use it."""

from __future__ import annotations

import asyncio
import importlib
import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from patent_client_agents.shared.corpus import (
    atomic_output,
    fetch_text,
    load_jsonl_seed,
    run_build_cli,
)

# --- atomic_output -----------------------------------------------------------


def test_atomic_output_replaces_target_on_success(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "corpus.db"
    with atomic_output(out) as tmp:
        assert tmp == out.with_name("corpus.db.tmp")
        tmp.write_bytes(b"new")
        assert not out.exists()
    assert out.read_bytes() == b"new"
    assert not tmp.exists()


def test_atomic_output_keeps_previous_file_when_body_raises(tmp_path: Path) -> None:
    out = tmp_path / "corpus.db"
    out.write_bytes(b"previous")
    with pytest.raises(RuntimeError), atomic_output(out) as tmp:
        tmp.write_bytes(b"half")
        raise RuntimeError("crash midway")
    assert out.read_bytes() == b"previous"
    assert not tmp.exists()


def test_atomic_output_keeps_previous_file_on_keyboard_interrupt(tmp_path: Path) -> None:
    out = tmp_path / "corpus.db"
    out.write_bytes(b"previous")
    with pytest.raises(KeyboardInterrupt), atomic_output(out) as tmp:
        tmp.write_bytes(b"half")
        raise KeyboardInterrupt
    assert out.read_bytes() == b"previous"
    assert list(tmp_path.iterdir()) == [out]


def test_atomic_output_clears_stale_temp_file(tmp_path: Path) -> None:
    out = tmp_path / "corpus.db"
    stale = tmp_path / "corpus.db.tmp"
    stale.write_bytes(b"stale")
    with atomic_output(out) as tmp:
        assert not tmp.exists()
        tmp.write_bytes(b"fresh")
    assert out.read_bytes() == b"fresh"


# --- the builds keep the previous corpus when they fail midway ---------------

# Each entry writes a corpus to ``out`` through the package's real write path.
# The fetch-based packages are driven through their ``write_corpus``; the
# seeded ones build from their bundled seed.
_WRITERS: dict[str, Callable[[Any, Path], object]] = {
    "mpep": lambda m, out: m.write_corpus([], out),
    "tmep": lambda m, out: m.write_corpus([], out),
    "legifrance_ip": lambda m, out: m.write_corpus([], out),
    "upc_statutes": lambda m, out: m.write_corpus([], out, snapshot_date="2026-01-02"),
    "ipos_statutes": lambda m, out: m.write_corpus([], out, snapshot_date="2026-01-02"),
    "ipos_manuals": lambda m, out: m.write_corpus([], out, snapshot_date="2026-01-02"),
    "ilpo_statutes": lambda m, out: m.write_corpus(
        [], out, snapshot_date="2026-01-02", source_version="v1"
    ),
    "dpma_statutes": lambda m, out: m.build_corpus(out),
    "ipo_in_mppp": lambda m, out: m.build_corpus(out),
    "ipo_in_statutes": lambda m, out: m.build_corpus(out),
    "tw_trade_secrets": lambda m, out: m.build_corpus(out),
}


@pytest.mark.parametrize("package", sorted(_WRITERS))
def test_build_that_fails_midway_keeps_previous_corpus(
    package: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    build_mod = importlib.import_module(f"patent_client_agents.{package}.corpus.build")
    out = tmp_path / "corpus.db"
    out.write_bytes(b"previous corpus")
    # Invalid DDL fails after the build has started writing its output.
    monkeypatch.setattr(build_mod, "DDL", "NOT VALID SQL")

    with pytest.raises(sqlite3.Error):
        _WRITERS[package](build_mod, out)

    assert out.read_bytes() == b"previous corpus"
    assert list(tmp_path.iterdir()) == [out]


@pytest.mark.parametrize("package", sorted(_WRITERS))
def test_build_replaces_previous_corpus(package: str, tmp_path: Path) -> None:
    build_mod = importlib.import_module(f"patent_client_agents.{package}.corpus.build")
    out = tmp_path / "corpus.db"
    out.write_bytes(b"previous corpus")

    _WRITERS[package](build_mod, out)

    conn = sqlite3.connect(out)
    try:
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    finally:
        conn.close()
    assert meta["schema_version"]
    assert list(tmp_path.iterdir()) == [out]


# --- load_jsonl_seed -----------------------------------------------------------


def test_load_jsonl_seed_skips_blank_and_comment_lines(tmp_path: Path) -> None:
    seed = tmp_path / "seed.jsonl"
    seed.write_text(
        "# header\n\n" + json.dumps({"section": "1", "text": "a", "title": None}) + "\n",
        encoding="utf-8",
    )
    assert load_jsonl_seed(seed, ("section", "text")) == [
        {"section": "1", "text": "a", "title": None}
    ]


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("{not json", "invalid JSON"),
        ("[1, 2]", "expected object, got list"),
        (json.dumps({"section": "1"}), "missing required key 'text'"),
        (json.dumps({"section": "1", "text": ""}), "missing required key 'text'"),
    ],
)
def test_load_jsonl_seed_rejects_bad_rows(tmp_path: Path, line: str, message: str) -> None:
    seed = tmp_path / "seed.jsonl"
    seed.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=f"seed.jsonl:1: {message}"):
        load_jsonl_seed(seed, ("section", "text"))


# --- fetch_text ----------------------------------------------------------------


def test_fetch_text_follows_redirects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(301, headers={"Location": "/new"})
        return httpx.Response(200, text="body")

    async def run() -> str:
        async with httpx.AsyncClient(
            base_url="https://example.test", transport=httpx.MockTransport(handler)
        ) as client:
            return await fetch_text(client, "/old")

    assert asyncio.run(run()) == "body"


# --- run_build_cli -------------------------------------------------------------


def _done(count: int, _elapsed: float) -> str:
    return f"Wrote {count} sections"


def test_run_build_cli_runs_sync_build(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_build_cli(lambda: 3, verbose=False, done=_done) == 0
    assert capsys.readouterr().out == "Wrote 3 sections\n"


def test_run_build_cli_runs_async_build_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    async def build() -> int:
        return 5

    assert run_build_cli(build, verbose=True, done=_done, to_stderr=True) == 0
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "Wrote 5 sections\n")


def test_run_build_cli_maps_interrupt_to_130(capsys: pytest.CaptureFixture[str]) -> None:
    def build() -> int:
        raise KeyboardInterrupt

    assert run_build_cli(build, verbose=False, done=_done) == 130
    assert capsys.readouterr().err == "Interrupted\n"


def test_run_build_cli_reports_failure_as_1(capsys: pytest.CaptureFixture[str]) -> None:
    def build() -> int:
        raise ValueError("bad seed")

    assert run_build_cli(build, verbose=False, done=_done) == 1
    assert capsys.readouterr().err == "Build failed: bad seed\n"


def test_run_build_cli_can_let_errors_propagate() -> None:
    def build() -> int:
        raise ValueError("bad seed")

    with pytest.raises(ValueError, match="bad seed"):
        run_build_cli(build, verbose=False, done=_done, catch_errors=False)
