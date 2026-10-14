"""Tests for the IPO India MPPP corpus build script."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from patent_client_agents.ipo_in_mppp.corpus.build import (
    build_corpus,
    main,
)


def test_build_writes_db(tmp_path: Path) -> None:
    out = tmp_path / "mppp.db"
    n = build_corpus(out)
    assert n > 0
    conn = sqlite3.connect(out)
    try:
        count = conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
        assert count == n
    finally:
        conn.close()


def test_build_stamps_source_version_by_default(tmp_path: Path) -> None:
    out = tmp_path / "mppp.db"
    build_corpus(out)
    conn = sqlite3.connect(out)
    try:
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    finally:
        conn.close()
    assert meta["source_version"] == "v3.0 (2019)"


def test_build_rejects_bad_json(tmp_path: Path) -> None:
    seed = tmp_path / "bad.jsonl"
    seed.write_text("definitely not json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        build_corpus(tmp_path / "out.db", seed_path=seed)


def test_build_rejects_missing_key(tmp_path: Path) -> None:
    seed = tmp_path / "bad.jsonl"
    seed.write_text(json.dumps({"section_number": "1"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required key 'text'"):
        build_corpus(tmp_path / "out.db", seed_path=seed)


def test_build_rejects_non_object_row(tmp_path: Path) -> None:
    seed = tmp_path / "list.jsonl"
    seed.write_text('["not an object"]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="expected object"):
        build_corpus(tmp_path / "out.db", seed_path=seed)


def test_build_overwrites_existing(tmp_path: Path) -> None:
    out = tmp_path / "mppp.db"
    out.write_bytes(b"sentinel")
    build_corpus(out)
    assert out.exists()
    # Replaced
    conn = sqlite3.connect(out)
    try:
        cnt = conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    finally:
        conn.close()
    assert cnt > 0


def test_build_skips_comments_and_blanks(tmp_path: Path) -> None:
    seed = tmp_path / "seed.jsonl"
    seed.write_text(
        "# comment\n\n"
        + json.dumps(
            {
                "section_number": "01.01",
                "title": "Intro",
                "text": "MPPP introduction text.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    n = build_corpus(tmp_path / "out.db", seed_path=seed)
    assert n == 1


def test_main_cli(tmp_path: Path) -> None:
    out = tmp_path / "out.db"
    rc = main(["--output", str(out)])
    assert rc == 0
    assert out.exists()


def test_main_cli_bad_seed(tmp_path: Path) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text("not json\n", encoding="utf-8")
    rc = main(["--output", str(tmp_path / "out.db"), "--seed", str(bad)])
    assert rc != 0
