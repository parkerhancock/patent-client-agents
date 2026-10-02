from __future__ import annotations

import hashlib
import sqlite3

import pytest

from patent_client_agents.mcp.tools.mpep import search_mpep
from patent_client_agents.mpep import MpepClient, get_corpus_status


@pytest.mark.asyncio
async def test_unavailable_version_fails_on_every_read(mpep_corpus_env):
    async with MpepClient() as client:
        for call in (
            client.get_section("2106", version="old"),
            client.search("patent", version="old"),
            client.resolve_section_href("2106", version="old"),
        ):
            with pytest.raises(ValueError, match="unavailable"):
                await call
    with pytest.raises(ValueError, match="unavailable"):
        await search_mpep("patent", version="old")


@pytest.mark.asyncio
async def test_section_hash_and_real_release_metadata(mpep_corpus_env, tmp_path, monkeypatch):
    import shutil

    path = tmp_path / "release.db"
    shutil.copyfile(mpep_corpus_env, path)
    with sqlite3.connect(path) as db:
        db.execute("INSERT OR REPLACE INTO meta VALUES ('source_version', 'test-retained-release')")
        db.execute("INSERT OR REPLACE INTO meta VALUES ('edition', 'fixture-edition')")
    db.close()
    db.close()
    monkeypatch.setenv("MPEP_CORPUS_PATH", str(path))
    async with MpepClient() as client:
        section = await client.get_section("2106", version="test-retained-release")
    assert section.version == "test-retained-release"
    assert section.content_sha256 == hashlib.sha256(section.html.encode()).hexdigest()
    assert section.source_url is not None
    assert "version=test-retained-release" in section.source_url
    assert section.corpus_metadata["edition"] == "fixture-edition"
    assert section.corpus_metadata["build_id"]
    assert section.corpus_metadata["interim_updates_coverage"] == "not_included"
    assert get_corpus_status()["corpus_version"] == "test-retained-release"


def _chapter(version: str | None, *, href: str = "d0e100.html", link: str = "") -> str:
    selector = ""
    if version:
        selector = (
            '<select id="edition-select">'
            '<option class="E9_R-07.2022">Historical release</option>'
            f'<option class="{version}" selected="selected">Selected release</option>'
            "</select>"
        )
    return (
        selector + f'<div id="{href.removesuffix(".html")}">'
        "<h1>2106 Patent Subject Matter Eligibility [R-07.2022]</h1>"
        "<p>Patent eligibility guidance.</p></div>"
        + (f'<a href="{link}">Next chapter</a>' if link else "")
    )


@pytest.mark.parametrize("version", ["E9_R-01.2024", None])
@pytest.mark.asyncio
async def test_builder_selected_release_reaches_retrieval_and_search(
    tmp_path, monkeypatch, version
):
    from patent_client_agents.mcp.tools.mpep import get_mpep_section
    from patent_client_agents.mpep.corpus.build import parse_chapter_html, write_corpus

    source_url = "https://mpep.uspto.gov/RDMS/MPEP/content?version=current&href=d0e100.html"
    page = parse_chapter_html("d0e100.html", _chapter(version), source_url=source_url)
    path = tmp_path / "release.db"
    write_corpus([page], path)
    monkeypatch.setenv("MPEP_CORPUS_PATH", str(path))
    expected = version or "unknown"
    with sqlite3.connect(path) as db:
        metadata = dict(db.execute("SELECT key, value FROM meta"))
    assert metadata["source_version"] == expected
    assert metadata["source_url"] == source_url
    async with MpepClient() as client:
        section = await client.get_section("2106")
    assert section.version == expected
    assert get_corpus_status()["corpus_version"] == expected
    for result in (await search_mpep("patent"), await get_mpep_section("2106")):
        assert result.provenance.corpus_version == expected


@pytest.mark.parametrize("other", ["E9_R-07.2022", None])
def test_mixed_release_identity_preserves_existing_corpus(tmp_path, other):
    from patent_client_agents.mpep.corpus.build import parse_chapter_html, write_corpus

    path = tmp_path / "existing.db"
    path.write_bytes(b"existing artifact")
    pages = [
        parse_chapter_html("one.html", _chapter("E9_R-01.2024")),
        parse_chapter_html("two.html", _chapter(other)),
    ]
    with pytest.raises(ValueError, match="mixed release"):
        write_corpus(pages, path)
    assert path.read_bytes() == b"existing artifact"


def test_explicit_release_mismatch_is_rejected_before_writing(tmp_path):
    from patent_client_agents.mpep.corpus.build import parse_chapter_html, write_corpus

    path = tmp_path / "release.db"
    page = parse_chapter_html("one.html", _chapter("E9_R-01.2024"))
    with pytest.raises(ValueError, match="explicit release metadata"):
        write_corpus([page], path, release_metadata={"source_version": "E9_R-07.2022"})
    assert not path.exists()


def test_ambiguous_selected_release_is_rejected():
    from patent_client_agents.mpep.corpus.build import parse_chapter_html

    document = _chapter("E9_R-01.2024").replace(
        '<option class="E9_R-07.2022">',
        '<option class="E9_R-07.2022" selected="selected">',
    )
    with pytest.raises(ValueError, match="ambiguous selected release"):
        parse_chapter_html("one.html", document)


@pytest.mark.asyncio
@pytest.mark.parametrize("second", ["E9_R-01.2024", "E9_R-07.2022"])
async def test_crawler_pins_selected_release_and_rejects_disagreement(monkeypatch, second):
    from patent_client_agents.mpep.corpus.build import MpepScraper

    versions = []

    async def fetch(self, href):
        versions.append(self._version)
        if href == "d0e100.html":
            return _chapter("E9_R-01.2024", link="#/E9_R-01.2024/d0e200.html")
        return _chapter(second, href="d0e200.html")

    monkeypatch.setattr(MpepScraper, "fetch", fetch)
    async with MpepScraper() as scraper:
        if second == "E9_R-01.2024":
            pages = await scraper.crawl(seed_hrefs=["d0e100.html"])
            assert len(pages) == 2
        else:
            with pytest.raises(ValueError, match="requested version"):
                await scraper.crawl(seed_hrefs=["d0e100.html"])
    assert versions == ["current", "E9_R-01.2024"]
