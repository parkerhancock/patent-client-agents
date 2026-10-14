"""Tests for the IPO India statutes corpus build script."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from patent_client_agents.ipo_in_statutes.corpus.build import (
    build_corpus,
    main,
)


def test_build_corpus_writes_db(tmp_path: Path) -> None:
    out = tmp_path / "ipo_in_statutes.db"
    n = build_corpus(out)
    assert n > 0
    assert out.exists()
    conn = sqlite3.connect(out)
    try:
        cnt = conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
        assert cnt == n
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        assert meta["schema_version"] == "1"
        assert meta["section_count"] == str(n)
    finally:
        conn.close()


def test_build_corpus_with_source_version(tmp_path: Path) -> None:
    out = tmp_path / "ipo_in_statutes.db"
    build_corpus(out, source_version="Test-Edition-1")
    conn = sqlite3.connect(out)
    try:
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    finally:
        conn.close()
    assert meta["source_version"] == "Test-Edition-1"


def test_build_corpus_overwrites_existing(tmp_path: Path) -> None:
    out = tmp_path / "ipo_in_statutes.db"
    out.write_bytes(b"sentinel")
    build_corpus(out)
    assert out.exists()
    # New contents replace the sentinel
    assert out.read_bytes()[:6] != b"sentin"


def test_build_corpus_rejects_invalid_json(tmp_path: Path) -> None:
    bad_seed = tmp_path / "bad.jsonl"
    bad_seed.write_text("this is not json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        build_corpus(tmp_path / "out.db", seed_path=bad_seed)


def test_build_corpus_rejects_missing_key(tmp_path: Path) -> None:
    bad_seed = tmp_path / "missing.jsonl"
    bad_seed.write_text(
        json.dumps({"statute_name": "Patents Act", "section_number": "1"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing required key 'text'"):
        build_corpus(tmp_path / "out.db", seed_path=bad_seed)


def test_build_corpus_rejects_non_object_row(tmp_path: Path) -> None:
    bad_seed = tmp_path / "list.jsonl"
    bad_seed.write_text("[1, 2, 3]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected object"):
        build_corpus(tmp_path / "out.db", seed_path=bad_seed)


def test_build_corpus_ignores_blank_and_comment_lines(tmp_path: Path) -> None:
    seed = tmp_path / "with_comments.jsonl"
    seed.write_text(
        "# comment line\n"
        "\n"
        + json.dumps(
            {
                "statute_name": "Patents Act",
                "section_number": "1",
                "title": "Short title",
                "text": "This Act may be called the Patents Act, 1970.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    n = build_corpus(tmp_path / "out.db", seed_path=seed)
    assert n == 1


def test_main_cli_smoke(tmp_path: Path) -> None:
    out = tmp_path / "out.db"
    rc = main(["--output", str(out)])
    assert rc == 0
    assert out.exists()


def test_main_cli_bad_seed_returns_nonzero(tmp_path: Path) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text("not json\n", encoding="utf-8")
    rc = main(["--output", str(tmp_path / "out.db"), "--seed", str(bad)])
    assert rc != 0
