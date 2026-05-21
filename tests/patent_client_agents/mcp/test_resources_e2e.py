"""End-to-end test: resource templates declared by tools/*.py modules are
reachable through the mounted ``ip_mcp`` server's ``resources/read`` and
``resources/templates/list`` surfaces.

This is the wiring test for the dual-transport download story: every
``register_source(...)`` pairs with an ``@<sub>_mcp.resource(...)``
handler so MCP-resource-aware clients (Claude CoWork in particular)
can fetch the same bytes through the MCP session, bypassing the HTTP
``download_url`` / domain-allowlist path.
"""

from __future__ import annotations

import asyncio

import pytest

from mcp_data_core.mcp import downloads
from patent_client_agents.mcp import ip_mcp


@pytest.fixture
def _isolated_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))


@pytest.fixture(autouse=True)
def _preserve_sources():
    """Snapshot/restore the global source registry so per-test fetcher
    overrides don't bleed into other tests."""
    saved = dict(downloads._SOURCES)
    yield
    downloads._SOURCES.clear()
    downloads._SOURCES.update(saved)


def test_resource_templates_are_listed():
    """All connectors' resource templates should be discoverable through
    ip_mcp's resources/templates/list — that's how MCP clients learn the
    URI shapes to deep-link into."""
    templates = asyncio.run(ip_mcp.list_resource_templates())
    template_uris = {t.uri_template for t in templates}

    # URI shape mirrors the source's cache-key path verbatim, so that
    # ``build_resource_uri(resource_path)`` and the @mcp.resource template
    # are guaranteed to agree. This is the dual-transport invariant:
    # cache key === MCP URI === HTTP /downloads path.
    expected = {
        "pca://patents/{publication_number}",
        "pca://publications/{publication_number}",
        "pca://epo/patents/{publication_number}",
        "pca://uspto/applications/{application_number}/documents/{document_identifier}",
        "pca://ptab/documents/{document_identifier}",
    }
    missing = expected - template_uris
    assert not missing, f"missing resource templates: {missing}\ngot: {sorted(template_uris)}"


def test_resource_read_uses_registered_fetcher_and_cache(_isolated_cache):
    """``resources/read`` on ``pca://patents/{publication_number}`` should
    delegate to the same fetcher that the HTTP ``/downloads/patents/...``
    route uses — exercising the dual-transport contract end-to-end."""
    calls = {"n": 0}

    async def fake_patent_fetch(remainder: str) -> tuple[bytes, str]:
        calls["n"] += 1
        return b"%PDF-1.4 stub", f"{remainder}.pdf"

    # Overwrite the registered fetcher with our stub for this test.
    downloads.register_source("patents", fake_patent_fetch, "application/pdf")

    result = asyncio.run(ip_mcp.read_resource("pca://patents/US10000000B2"))
    assert len(result.contents) == 1
    content = result.contents[0]
    assert content.content == b"%PDF-1.4 stub"
    assert content.mime_type == "application/pdf"

    # Second read is a cache hit — fetcher not re-invoked.
    asyncio.run(ip_mcp.read_resource("pca://patents/US10000000B2"))
    assert calls["n"] == 1


def test_resource_read_routes_per_source(_isolated_cache):
    """Each registered source serves its own URI shape independently."""
    fetched: list[str] = []

    async def patent_fetch(remainder: str) -> tuple[bytes, str]:
        fetched.append(f"patent:{remainder}")
        return f"p:{remainder}".encode(), f"{remainder}.pdf"

    async def app_doc_fetch(remainder: str) -> tuple[bytes, str]:
        fetched.append(f"app:{remainder}")
        return f"a:{remainder}".encode(), f"{remainder}.pdf"

    downloads.register_source("patents", patent_fetch, "application/pdf")
    downloads.register_source("uspto/applications", app_doc_fetch, "application/pdf")

    asyncio.run(ip_mcp.read_resource("pca://patents/US10"))
    asyncio.run(ip_mcp.read_resource("pca://uspto/applications/16123456/documents/XYZ"))

    assert "patent:US10" in fetched
    assert "app:16123456/documents/XYZ" in fetched
