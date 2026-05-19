"""Unit tests for ``law_tools_core.corpus_db``.

We build a tiny outline-shaped corpus in a temp SQLite file so the tests
exercise the same SQL the production corpora use (FTS5 ``MATCH``,
``snippet()`` projection, ``meta`` table reads). The tests don't depend
on any of the per-connector built corpora.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import ClassVar

import pytest

from law_tools_core.corpus_db import (
    CorpusDBBase,
    CorpusUnavailable,
    OutlineCorpusDB,
    OutlineCorpusHit,
    OutlineCorpusSection,
)

# ----------------------------------------------------------------------
# Fixtures: build a minimal outline corpus on disk.
# ----------------------------------------------------------------------


def _build_outline_corpus(path: Path) -> None:
    """Create a tiny outline-shaped corpus the tests can open read-only."""
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE sections (
                href TEXT PRIMARY KEY,
                section_number TEXT,
                title TEXT,
                breadcrumb TEXT,
                chapter TEXT,
                html TEXT,
                text TEXT
            );
            CREATE VIRTUAL TABLE sections_fts USING fts5(
                section_number, title, text,
                content='sections',
                content_rowid='rowid'
            );
            """
        )
        conn.executemany(
            "INSERT INTO meta(key, value) VALUES (?, ?)",
            [
                ("corpus_version", "test-1.0"),
                ("synced_at", "2026-05-19T00:00:00Z"),
            ],
        )
        rows = [
            (
                "section-2106.html",
                "2106",
                "Patent Subject Matter Eligibility",
                "Chapter 2100 > Section 2106",
                "Chapter 2100",
                "<p>Subject matter eligibility analysis under 35 USC 101.</p>",
                "Subject matter eligibility analysis under 35 USC 101.",
            ),
            (
                "section-2106.04.html",
                "2106.04",
                "Eligibility Step 2A",
                "Chapter 2100 > Section 2106 > 2106.04",
                "Chapter 2100",
                "<p>Eligibility Step 2A: directed to a judicial exception.</p>",
                "Eligibility Step 2A: directed to a judicial exception.",
            ),
            (
                "section-700.html",
                "700",
                "Examination of Applications",
                "Chapter 700",
                "Chapter 700",
                "<p>General examination procedure.</p>",
                "General examination procedure.",
            ),
        ]
        conn.executemany(
            "INSERT INTO sections(href, section_number, title, breadcrumb, chapter, html, text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        # Repopulate FTS5 from content table.
        conn.execute("INSERT INTO sections_fts(sections_fts) VALUES('rebuild')")
        conn.commit()
    finally:
        conn.close()


class _TestCorpus(OutlineCorpusDB):
    LABEL: ClassVar[str] = "Test Outline Corpus"
    ENV_VAR: ClassVar[str] = "LAW_TOOLS_CORE_TEST_CORPUS_PATH"
    DEFAULT_FILENAME: ClassVar[str] = "law_tools_core_test.db"
    BUILD_COMMAND: ClassVar[str] = "patent-client-agents-build-test-corpus"


@pytest.fixture
def corpus_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    _build_outline_corpus(path)
    return path


# ----------------------------------------------------------------------
# Path resolution + error messages
# ----------------------------------------------------------------------


def test_default_path_uses_class_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """default_path() composes ~/.cache/patent_client_agents/<DEFAULT_FILENAME>."""
    monkeypatch.delenv(_TestCorpus.ENV_VAR, raising=False)
    assert _TestCorpus.default_path().name == "law_tools_core_test.db"
    assert _TestCorpus.default_path().parent.name == "patent_client_agents"


def test_env_var_overrides_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """When ENV_VAR is set, _resolve_path() honors it."""
    override = tmp_path / "override.db"
    monkeypatch.setenv(_TestCorpus.ENV_VAR, str(override))
    assert _TestCorpus._resolve_path(None) == override


def test_explicit_path_beats_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """An explicit path argument outranks the env var."""
    monkeypatch.setenv(_TestCorpus.ENV_VAR, str(tmp_path / "from_env.db"))
    explicit = tmp_path / "explicit.db"
    assert _TestCorpus._resolve_path(explicit) == explicit


def test_missing_corpus_raises_corpus_unavailable(tmp_path: Path) -> None:
    """When the file doesn't exist, open() raises with the install hint."""
    missing = tmp_path / "does-not-exist.db"
    with pytest.raises(CorpusUnavailable) as excinfo:
        _TestCorpus.open(missing)
    msg = str(excinfo.value)
    assert "Test Outline Corpus corpus not found" in msg
    assert _TestCorpus.BUILD_COMMAND in msg
    assert _TestCorpus.ENV_VAR in msg


def test_corpus_unavailable_is_runtime_error() -> None:
    """Catch hierarchy: CorpusUnavailable must remain a RuntimeError subclass."""
    assert issubclass(CorpusUnavailable, RuntimeError)


# ----------------------------------------------------------------------
# Lifecycle + meta
# ----------------------------------------------------------------------


def test_open_returns_subclass_instance(corpus_path: Path) -> None:
    """open() classmethod returns ``cls(...)``, not the base type."""
    with _TestCorpus.open(corpus_path) as corpus:
        assert isinstance(corpus, _TestCorpus)
        assert corpus.path == corpus_path


def test_context_manager_closes(corpus_path: Path) -> None:
    """Exiting the context manager closes the underlying connection."""
    corpus = _TestCorpus.open(corpus_path)
    with corpus:
        pass
    with pytest.raises(sqlite3.ProgrammingError):
        corpus._conn.execute("SELECT 1")


def test_meta_returns_dict(corpus_path: Path) -> None:
    """meta() reads every row out of the corpus's ``meta`` table."""
    with _TestCorpus.open(corpus_path) as corpus:
        meta = corpus.meta()
    assert meta["corpus_version"] == "test-1.0"
    assert meta["synced_at"] == "2026-05-19T00:00:00Z"


def test_meta_get_returns_default_when_absent(corpus_path: Path) -> None:
    """meta_get() returns the supplied default when the key is missing."""
    with _TestCorpus.open(corpus_path) as corpus:
        assert corpus.meta_get("no-such-key", "fallback") == "fallback"
        assert corpus.meta_get("corpus_version") == "test-1.0"


# ----------------------------------------------------------------------
# Outline get_section + search
# ----------------------------------------------------------------------


def test_get_section_by_section_number(corpus_path: Path) -> None:
    with _TestCorpus.open(corpus_path) as corpus:
        section = corpus.get_section(section_number="2106")
    assert isinstance(section, OutlineCorpusSection)
    assert section.title == "Patent Subject Matter Eligibility"
    assert section.chapter == "Chapter 2100"


def test_get_section_by_href(corpus_path: Path) -> None:
    with _TestCorpus.open(corpus_path) as corpus:
        section = corpus.get_section(href="section-700.html")
    assert section is not None
    assert section.section_number == "700"


def test_get_section_missing_returns_none(corpus_path: Path) -> None:
    with _TestCorpus.open(corpus_path) as corpus:
        assert corpus.get_section(section_number="9999") is None


def test_get_section_requires_one_lookup_key(corpus_path: Path) -> None:
    with _TestCorpus.open(corpus_path) as corpus:
        with pytest.raises(ValueError):
            corpus.get_section()


def test_search_returns_outline_hits(corpus_path: Path) -> None:
    with _TestCorpus.open(corpus_path) as corpus:
        hits = corpus.search("eligibility", limit=10)
    assert all(isinstance(h, OutlineCorpusHit) for h in hits)
    assert {h.section_number for h in hits} == {"2106", "2106.04"}


def test_search_snippet_marks_hits(corpus_path: Path) -> None:
    with _TestCorpus.open(corpus_path) as corpus:
        hits = corpus.search("eligibility", limit=10)
    # Every hit's snippet should include the FTS5 `<mark>` highlight.
    assert all("<mark>" in h.snippet for h in hits)


def test_search_outline_sort_orders_by_section_number(corpus_path: Path) -> None:
    """sort='outline' orders by section_number ascending (lexicographic)."""
    with _TestCorpus.open(corpus_path) as corpus:
        hits = corpus.search("examination OR eligibility", sort="outline", limit=10)
    section_numbers = [h.section_number for h in hits]
    assert section_numbers == sorted(section_numbers)


def test_count_for_returns_match_count(corpus_path: Path) -> None:
    with _TestCorpus.open(corpus_path) as corpus:
        assert corpus.count_for("eligibility") == 2
        assert corpus.count_for("zzznosuchterm") == 0


# ----------------------------------------------------------------------
# Custom-shape subclass — confirms CorpusDBBase is usable without
# the outline defaults.
# ----------------------------------------------------------------------


class _StatuteCorpus(CorpusDBBase):
    LABEL: ClassVar[str] = "Test Statute"
    ENV_VAR: ClassVar[str] = "LAW_TOOLS_CORE_TEST_STATUTE_PATH"
    DEFAULT_FILENAME: ClassVar[str] = "test_statute.db"
    BUILD_COMMAND: ClassVar[str] = "patent-client-agents-build-test-statute"


def test_statute_shape_subclass_inherits_lifecycle(corpus_path: Path) -> None:
    """A bare CorpusDBBase subclass still gets open/close/meta from the base."""
    with _StatuteCorpus.open(corpus_path) as corpus:
        assert isinstance(corpus, _StatuteCorpus)
        assert corpus.meta()["corpus_version"] == "test-1.0"
    # No get_section/search on the bare subclass — that's intentional.
    assert not hasattr(_StatuteCorpus, "get_section")
    assert not hasattr(_StatuteCorpus, "search")
