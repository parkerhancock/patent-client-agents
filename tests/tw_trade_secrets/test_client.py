"""Tests for the corpus-backed TwTradeSecretsClient."""

from __future__ import annotations

import pytest

from patent_client_agents.tw_trade_secrets import TwTradeSecretsClient
from patent_client_agents.tw_trade_secrets.client import parse_citation
from patent_client_agents.tw_trade_secrets.corpus import CorpusUnavailable


@pytest.fixture(autouse=True)
def _set_corpus(tw_trade_secrets_corpus_path, monkeypatch):
    monkeypatch.setenv("TW_TRADE_SECRETS_CORPUS_PATH", str(tw_trade_secrets_corpus_path))


class TestParseCitation:
    def test_art_dot_with_statute(self) -> None:
        assert parse_citation("Art. 2 Trade Secrets Act") == "2"

    def test_article_word_form(self) -> None:
        assert parse_citation("Article 13") == "13"

    def test_section_word_with_statute(self) -> None:
        assert parse_citation("Section 13 Trade Secrets Act") == "13"

    def test_sec_abbreviated_with_sub_number(self) -> None:
        assert parse_citation("Sec. 13-1") == "13-1"

    def test_s_abbreviated(self) -> None:
        assert parse_citation("S. 13") == "13"

    def test_of_the_form(self) -> None:
        assert parse_citation("Art. 11 of the Trade Secrets Act") == "11"

    def test_bare_number(self) -> None:
        assert parse_citation("13") == "13"

    def test_bare_sub_number(self) -> None:
        assert parse_citation("13-1") == "13-1"

    def test_unparseable_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not parse citation"):
            parse_citation("totally not a citation")


class TestGetSection:
    async def test_by_citation_with_statute(self) -> None:
        async with TwTradeSecretsClient() as c:
            sec = await c.get_section_by_citation("Art. 2 Trade Secrets Act")
        assert sec.section == "2"
        assert sec.title == "Definition of Trade Secret"

    async def test_by_sub_numbered_citation(self) -> None:
        async with TwTradeSecretsClient() as c:
            sec = await c.get_section_by_citation("Art. 13-1")
        assert sec.section == "13-1"
        assert "imprisonment" in sec.text.lower()

    async def test_by_bare_number(self) -> None:
        async with TwTradeSecretsClient() as c:
            sec = await c.get_section("13")
        assert sec.section == "13"
        assert "damages" in sec.text.lower()

    async def test_by_citation_form_via_get_section(self) -> None:
        # get_section also accepts citation forms (delegates to parse_citation)
        async with TwTradeSecretsClient() as c:
            sec = await c.get_section("Art. 13-1")
        assert sec.section == "13-1"

    async def test_unknown_section_raises(self) -> None:
        async with TwTradeSecretsClient() as c:
            with pytest.raises(ValueError, match="not found"):
                await c.get_section("999")


class TestSearch:
    async def test_finds_phrase_adj(self) -> None:
        async with TwTradeSecretsClient() as c:
            r = await c.search("trade secret", syntax="adj")
        assert r.hits

    async def test_and_syntax(self) -> None:
        async with TwTradeSecretsClient() as c:
            r = await c.search("damages royalty", syntax="and")
        assert r.hits
        assert any(h.section == "13" for h in r.hits)

    async def test_or_syntax(self) -> None:
        async with TwTradeSecretsClient() as c:
            r = await c.search("imprisonment royalty", syntax="or")
        assert r.hits

    async def test_exact_syntax(self) -> None:
        async with TwTradeSecretsClient() as c:
            r = await c.search("reasonable measures", syntax="exact")
        assert r.hits
        assert any(h.section == "2" for h in r.hits)

    async def test_query_with_hyphen_quoted(self) -> None:
        # Tokens containing punctuation are wrapped as quoted phrases so
        # FTS5 doesn't treat them as operators.
        async with TwTradeSecretsClient() as c:
            r = await c.search("NT$1,000,000")
        # The quoted phrase matches only the Art. 13-1 fine amount.
        assert [h.section for h in r.hits] == ["13-1"]

    async def test_outline_sort(self) -> None:
        async with TwTradeSecretsClient() as c:
            r = await c.search("trade", sort="outline", syntax="or")
        # Documented string sort over section labels, not numeric outline.
        assert [h.section for h in r.hits] == ["1", "10", "11", "13", "13-1", "2", "3"]

    async def test_empty_query_returns_empty(self) -> None:
        async with TwTradeSecretsClient() as c:
            r = await c.search("   ")
        assert r.hits == []
        assert r.has_more is False

    async def test_pagination(self) -> None:
        async with TwTradeSecretsClient() as c:
            r1 = await c.search("the", per_page=2, page=1, syntax="or")
            r2 = await c.search("the", per_page=2, page=2, syntax="or")
        if r1.hits and r2.hits:
            first = {h.section for h in r1.hits}
            second = {h.section for h in r2.hits}
            assert first & second == set()


class TestMeta:
    async def test_meta(self) -> None:
        async with TwTradeSecretsClient() as c:
            meta = await c.meta()
        assert meta.schema_version >= 1
        assert meta.snapshot_date is not None
        assert meta.section_count > 0


class TestCorpusUnavailable:
    async def test_raises_when_path_missing(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("TW_TRADE_SECRETS_CORPUS_PATH", str(tmp_path / "missing.db"))
        async with TwTradeSecretsClient() as c:
            with pytest.raises(CorpusUnavailable):
                await c.get_section("2")
