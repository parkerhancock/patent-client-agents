"""Shared fixtures for TMEP tests.

Same pattern as the MPEP conftest — a session-scoped fixture corpus
built from hand-authored sections, and a per-test ``mpep_corpus_env``
that points ``TMEP_CORPUS_PATH`` at it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from patent_client_agents.tmep.corpus.build import (
    ParsedPage,
    ParsedSection,
    write_corpus,
)


def _fixture_section(
    section_number: str,
    title: str,
    text: str,
    chapter: str,
) -> ParsedSection:
    safe = section_number.replace(".", "_").replace("(", "_").replace(")", "")
    return ParsedSection(
        href=f"TMEP-{chapter}d1e_{safe}.html",
        section_number=section_number,
        title=title,
        chapter=chapter,
        breadcrumb=f"Chapter {chapter} > {section_number}",
        html=f"<div><h1>{section_number} {title}</h1><p>{text}</p></div>",
        text=f"{section_number} {title} {text}",
    )


@pytest.fixture(scope="session")
def tmep_corpus_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("tmep-corpus") / "tmep.db"
    sections = [
        _fixture_section(
            "1207",
            "Refusal on Basis of Likelihood of Confusion, Mistake, or Deception",
            "Examiners refuse registration when a mark so resembles another "
            "as to be likely to cause confusion, mistake, or deception.",
            "1200",
        ),
        _fixture_section(
            "1207.01",
            "Likelihood of Confusion",
            "DuPont sets out the multi-factor test for assessing likelihood "
            "of confusion under Section 2(d) of the Trademark Act.",
            "1200",
        ),
        _fixture_section(
            "1209.03(u)",
            "Punctuation",
            "Marks that consist solely of punctuation are refused under "
            "Sections 1, 2, and 45 as failing to function as a trademark.",
            "1200",
        ),
        _fixture_section(
            "1402",
            "Identification of Goods and Services",
            "Identifications must be definite, accurate, and use ordinary "
            "language to describe the goods or services in trade.",
            "1400",
        ),
        _fixture_section(
            "904",
            "Specimens",
            "A specimen is a real-world example of how the mark is used in "
            "connection with the goods or services identified in the application.",
            "900",
        ),
    ]
    page = ParsedPage(
        fetched_href="seed.html",
        chapter=None,
        sections=sections,
        discovered_hrefs=set(),
    )
    write_corpus([page], out)
    return out


@pytest.fixture
def tmep_corpus_env(monkeypatch: pytest.MonkeyPatch, tmep_corpus_path: Path) -> Path:
    """Point ``TMEP_CORPUS_PATH`` at the fixture corpus for one test."""
    monkeypatch.setenv("TMEP_CORPUS_PATH", str(tmep_corpus_path))
    return tmep_corpus_path
