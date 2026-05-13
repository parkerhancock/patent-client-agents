"""Shared fixtures for MPEP tests.

The corpus-backed :class:`MpepClient` reads from a SQLite/FTS5 database
materialized by ``patent-client-agents-build-mpep-corpus``. Tests
exercise that real read path against a tiny fixture corpus built from
hand-authored ``ParsedPage`` objects so we can assert on known queries
without depending on the full ~50MB scraped corpus.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from patent_client_agents.mpep.corpus.build import (
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
        href=f"d0e_{safe}.html",
        section_number=section_number,
        title=title,
        chapter=chapter,
        breadcrumb=f"Chapter {chapter} > {section_number}",
        html=f"<div><h1>{section_number} {title}</h1><p>{text}</p></div>",
        text=f"{section_number} {title} {text}",
    )


@pytest.fixture(scope="session")
def mpep_corpus_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build a tiny on-disk corpus once per test session."""
    out = tmp_path_factory.mktemp("mpep-corpus") / "mpep.db"
    sections = [
        _fixture_section(
            "2106",
            "Patent Subject Matter Eligibility",
            "Determining whether a claim is directed to patent-eligible "
            "subject matter under 35 U.S.C. 101 follows a two-step framework.",
            "2100",
        ),
        _fixture_section(
            "2106.04(a)",
            "Abstract Ideas",
            "Abstract ideas are one of the judicial exceptions to patent "
            "eligibility. The Alice/Mayo framework guides analysis.",
            "2100",
        ),
        _fixture_section(
            "2143",
            "Examples of Basic Requirements of a Prima Facie Case of Obviousness",
            "A prima facie case of obviousness requires identifying a "
            "reason to combine the prior art teachings.",
            "2100",
        ),
        _fixture_section(
            "706",
            "Rejection of Claims",
            "Examiners reject claims based on prior art under 102 and 103, "
            "or on grounds of indefiniteness under 112.",
            "700",
        ),
        _fixture_section(
            "706.03(a)",
            "Rejections Under 35 U.S.C. 101",
            "Patent eligibility rejections under 35 U.S.C. 101 follow the framework in MPEP 2106.",
            "700",
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
def mpep_corpus_env(monkeypatch: pytest.MonkeyPatch, mpep_corpus_path: Path) -> Path:
    """Point ``MPEP_CORPUS_PATH`` at the fixture corpus for one test."""
    monkeypatch.setenv("MPEP_CORPUS_PATH", str(mpep_corpus_path))
    return mpep_corpus_path
