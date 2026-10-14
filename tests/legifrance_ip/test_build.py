"""Tests for the Légifrance IP corpus build script."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from patent_client_agents.legifrance_ip.corpus.build import (
    CORPUS_VERSION,
    build_corpus,
    load_seed,
    main,
    write_corpus,
)


def test_load_seed_default_path() -> None:
    rows = load_seed()
    assert len(rows) >= 7
    statutes = {r.statute for r in rows}
    assert statutes == {"CPI", "Code de commerce"}


def test_load_seed_skips_blank_lines(tmp_path: Path) -> None:
    seed = tmp_path / "with_blanks.jsonl"
    seed.write_text(
        "\n"
        + json.dumps(
            {
                "statute": "CPI",
                "section": "L611-10",
                "title": "Conditions de brevetabilité",
                "text": "Sont brevetables les inventions nouvelles.",
            }
        )
        + "\n\n",
        encoding="utf-8",
    )
    rows = load_seed(seed)
    assert len(rows) == 1
    assert rows[0].statute == "CPI"


def test_load_seed_rejects_invalid_json(tmp_path: Path) -> None:
    bad_seed = tmp_path / "bad.jsonl"
    bad_seed.write_text("this is not json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        load_seed(bad_seed)


def test_load_seed_rejects_missing_key(tmp_path: Path) -> None:
    bad_seed = tmp_path / "missing.jsonl"
    bad_seed.write_text(
        json.dumps({"statute": "CPI", "section": "L611-10"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing required key"):
        load_seed(bad_seed)


def test_build_corpus_writes_db(tmp_path: Path) -> None:
    out = tmp_path / "legifrance_ip.db"
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
        assert meta["source_version"] == CORPUS_VERSION
        # snapshot_date set to today's ISO date
        assert meta["snapshot_date"]
    finally:
        conn.close()


def test_write_corpus_skips_duplicate_keys(tmp_path: Path) -> None:
    # write_corpus dedupes on (statute, section) so a repeated seed row
    # doesn't fail with a UNIQUE constraint or double-count.
    rows = load_seed()
    out = tmp_path / "dedup.db"
    inserted = write_corpus(list(rows) + list(rows), out)
    assert inserted == len(rows)


def test_build_corpus_overwrites_existing(tmp_path: Path) -> None:
    out = tmp_path / "legifrance_ip.db"
    out.write_bytes(b"sentinel")
    build_corpus(out)
    assert out.exists()
    # New contents replace the sentinel.
    assert out.read_bytes()[:6] != b"sentin"


def test_main_cli_smoke(tmp_path: Path) -> None:
    out = tmp_path / "out.db"
    rc = main(["--output", str(out)])
    assert rc == 0
    assert out.exists()


def test_main_cli_custom_seed(tmp_path: Path) -> None:
    seed = tmp_path / "custom.jsonl"
    seed.write_text(
        json.dumps(
            {
                "statute": "CPI",
                "section": "L611-1",
                "title": "Test",
                "text": "Test body.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "out.db"
    rc = main(["--output", str(out), "--seed", str(seed)])
    assert rc == 0
    assert out.exists()
