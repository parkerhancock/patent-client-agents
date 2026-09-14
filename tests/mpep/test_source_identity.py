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
    assert "version=test-retained-release" in section.source_url
    assert section.corpus_metadata["edition"] == "fixture-edition"
    assert section.corpus_metadata["build_id"]
    assert section.corpus_metadata["interim_updates_coverage"] == "not_included"
    assert get_corpus_status()["corpus_version"] == "test-retained-release"
