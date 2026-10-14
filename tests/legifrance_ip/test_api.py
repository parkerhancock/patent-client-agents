"""Tests for the Légifrance IP module-level async API."""

from __future__ import annotations

import pytest

from patent_client_agents.legifrance_ip import (
    get_section,
    search,
)


@pytest.fixture(autouse=True)
def _set_corpus(legifrance_ip_corpus_path, monkeypatch):
    monkeypatch.setenv("LEGIFRANCE_IP_CORPUS_PATH", str(legifrance_ip_corpus_path))


async def test_search_oneshot() -> None:
    r = await search("brevetabilité")
    assert r.hits
    assert any(h.section == "L611-10" for h in r.hits)


async def test_search_oneshot_diacritics_fold() -> None:
    # remove_diacritics=2 in the schema → 'brevetabilite' matches 'brevetabilité'
    r = await search("brevetabilite")
    assert r.hits


async def test_search_oneshot_statute_filter() -> None:
    r = await search("secret", statute="Code de commerce")
    for hit in r.hits:
        assert hit.statute == "Code de commerce"


async def test_get_section_oneshot_l_dot_form() -> None:
    sec = await get_section("L. 611-10 CPI")
    assert sec.statute == "CPI"
    assert sec.section == "L611-10"
    assert sec.title is not None


async def test_get_section_oneshot_art_form() -> None:
    sec = await get_section("Art. L. 151-1 Code de commerce")
    assert sec.statute == "Code de commerce"
    assert sec.section == "L151-1"
