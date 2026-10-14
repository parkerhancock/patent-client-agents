"""Description HTML → Markdown, checked against real Google Patents pages.

Each fixture pairs a patent's description HTML (as Google Patents served it)
with the Markdown markitdown 0.1.5 produced for it, captured before the
converter moved to markdownify directly. US9468645B2 covers tables, images
and links; the others cover headings, lists, bold/italic and paragraph numbers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from patent_client_agents.google_patents.client import _html_to_markdown

FIXTURES = Path(__file__).parent / "fixtures" / "description_markdown"
PATENTS = sorted(p.stem for p in FIXTURES.glob("*.html"))


@pytest.mark.parametrize("patent", PATENTS)
def test_description_markdown_matches_golden(patent: str) -> None:
    html = (FIXTURES / f"{patent}.html").read_text()
    expected = (FIXTURES / f"{patent}.md").read_text()
    assert _html_to_markdown(html) == expected


def test_fixtures_present() -> None:
    assert PATENTS == ["EP3000000B1", "US10123456B2", "US11000000B2", "US9468645B2"]


def test_empty_description_is_none() -> None:
    assert _html_to_markdown("") is None
    assert _html_to_markdown(None) is None
