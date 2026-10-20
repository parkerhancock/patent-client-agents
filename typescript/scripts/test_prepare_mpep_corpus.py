from __future__ import annotations

import importlib.util
import shutil
import sqlite3
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("prepare-mpep-corpus.py")
SPEC = importlib.util.spec_from_file_location("prepare_mpep", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
FIXTURE = SCRIPT.parent.parent / "tests/fixtures/mpep/compressed.db"


def test_prepare_preserves_compression_metadata_and_unknown_release(tmp_path):
    source = tmp_path / "legacy.db"
    shutil.copyfile(FIXTURE, source)
    with sqlite3.connect(source) as db:
        db.execute("PRAGMA journal_mode=WAL")
    source_hash = MODULE.digest(source)
    output = tmp_path / "prepared.db"
    result = MODULE.prepare(source, output, source_hash)
    assert result["source_sha256"] == MODULE.digest(source) == source_hash
    assert result["metadata_preserved"] is True
    assert output.read_bytes()[18:20] == b"\x01\x01"
    with sqlite3.connect(source) as original, sqlite3.connect(output) as prepared:
        assert (
            original.execute("SELECT * FROM meta ORDER BY key").fetchall()
            == prepared.execute("SELECT * FROM meta ORDER BY key").fetchall()
        )
        assert (
            original.execute("SELECT * FROM compression_dict").fetchall()
            == prepared.execute("SELECT * FROM compression_dict").fetchall()
        )
        assert original.execute(
            "SELECT html FROM sections WHERE section_number='2106'"
        ).fetchone() == (
            prepared.execute("SELECT html FROM sections WHERE section_number='2106'").fetchone()
        )
    with pytest.raises(ValueError, match="never overwritten"):
        MODULE.prepare(source, output)


def test_prepare_rejects_bad_pin_without_publication(tmp_path):
    output = tmp_path / "prepared.db"
    with pytest.raises(ValueError, match="pin"):
        MODULE.prepare(FIXTURE, output, "0" * 64)
    assert not output.exists()
    assert list(tmp_path.iterdir()) == []
