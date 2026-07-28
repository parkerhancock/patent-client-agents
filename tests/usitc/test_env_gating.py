"""Tests for env-gated USITC EDIS MCP tool registration.

Verifies that ``patent_client_agents.mcp.tools.usitc`` registers the six
EDIS tools (and the EDIS download fetcher) only when ``USITC_EDIS_TOKEN``
is set, while the three unauthenticated / self-gating tools
(``search_hts_tariffs``, ``run_dataweb_report``, ``list_ids_investigations``)
register unconditionally.

The gate is deliberately broader than the technical auth requirement:
only ``EdisClient.download_attachment`` calls ``require_auth()``, so EDIS
search and metadata would work unauthenticated. The whole EDIS group is
gated anyway so the public demo at ``mcp.patentclient.com`` advertises no
ITC surface rather than search tools whose results cannot be fetched.

Test strategy mirrors ``tests/jpo/test_env_gating.py``: each test
``importlib.reload``s the usitc module under a controlled env after
rebinding ``usitc_mcp`` to a fresh ``FastMCP``, so every decorator runs
against an empty surface and the assertions describe what *this reload*
registered.
"""

from __future__ import annotations

import importlib

import pytest
from fastmcp import FastMCP

from mcp_data_core.mcp import downloads

EDIS_GATED_TOOLS = {
    "search_usitc_investigations",
    "get_usitc_investigation",
    "search_usitc_documents",
    "list_usitc_attachments",
    "download_usitc_investigation_documents",
    "download_usitc_attachment",
}

ALWAYS_REGISTERED_TOOLS = {
    "search_hts_tariffs",
    "run_dataweb_report",
    "list_ids_investigations",
}


def _reload_usitc_with_fresh_mcp() -> object:
    """Reload the USITC tool module under a fresh FastMCP."""
    import patent_client_agents.mcp.tools.usitc as usitc_module

    usitc_module.usitc_mcp = FastMCP("USITC")
    return importlib.reload(usitc_module)


@pytest.fixture
def fresh_state():
    """Snapshot + restore the download source registry around each test.

    Each test mutates the global ``_SOURCES`` dict via reload; restore the
    pre-test state on teardown so other tests in the suite (which rely on
    the conftest-set placeholder token having registered the EDIS fetcher)
    keep working.
    """
    saved_sources = dict(downloads._SOURCES)
    yield
    downloads._SOURCES.clear()
    downloads._SOURCES.update(saved_sources)
    # The usitc module is module-cached; reload once more under the
    # conftest's env so subsequent tests see the registered tools.
    _reload_usitc_with_fresh_mcp()


class TestUsitcEnvGating:
    @pytest.mark.asyncio
    async def test_no_edis_tools_registered_when_env_unset(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """With USITC_EDIS_TOKEN unset, zero EDIS tools register."""
        monkeypatch.delenv("USITC_EDIS_TOKEN", raising=False)

        usitc_module = _reload_usitc_with_fresh_mcp()

        tools = await usitc_module.usitc_mcp.list_tools()  # type: ignore[attr-defined]
        names = {t.name for t in tools}
        assert names & EDIS_GATED_TOOLS == set()

    @pytest.mark.asyncio
    async def test_empty_token_treated_as_unset(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """An empty-string token must not flip registration on.

        Cloud Run renders an unset Secret Manager binding as an empty
        string rather than omitting the var, so this is the shape the
        public demo actually produces if the secret is unmounted but the
        env key survives in a stale revision.
        """
        monkeypatch.setenv("USITC_EDIS_TOKEN", "")

        usitc_module = _reload_usitc_with_fresh_mcp()

        tools = await usitc_module.usitc_mcp.list_tools()  # type: ignore[attr-defined]
        names = {t.name for t in tools}
        assert names & EDIS_GATED_TOOLS == set()

    @pytest.mark.asyncio
    async def test_non_edis_tools_register_regardless(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """HTS, DataWeb, and IDS tools are not gated on the EDIS token."""
        monkeypatch.delenv("USITC_EDIS_TOKEN", raising=False)

        usitc_module = _reload_usitc_with_fresh_mcp()

        tools = await usitc_module.usitc_mcp.list_tools()  # type: ignore[attr-defined]
        names = {t.name for t in tools}
        assert ALWAYS_REGISTERED_TOOLS <= names

    @pytest.mark.asyncio
    async def test_all_edis_tools_registered_when_env_set(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """With the token set, every EDIS tool is registered."""
        monkeypatch.setenv("USITC_EDIS_TOKEN", "test_edis_token")

        usitc_module = _reload_usitc_with_fresh_mcp()

        tools = await usitc_module.usitc_mcp.list_tools()  # type: ignore[attr-defined]
        names = {t.name for t in tools}
        assert EDIS_GATED_TOOLS <= names
        assert ALWAYS_REGISTERED_TOOLS <= names

    def test_edis_download_source_skipped_when_env_unset(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """EDIS download fetcher is NOT registered when the token is unset."""
        monkeypatch.delenv("USITC_EDIS_TOKEN", raising=False)

        downloads._SOURCES.clear()
        _reload_usitc_with_fresh_mcp()

        assert "usitc/documents" not in downloads._SOURCES

    def test_edis_download_source_registered_when_env_set(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """EDIS download fetcher IS registered when the token is set."""
        monkeypatch.setenv("USITC_EDIS_TOKEN", "test_edis_token")

        downloads._SOURCES.clear()
        _reload_usitc_with_fresh_mcp()

        assert "usitc/documents" in downloads._SOURCES
        assert downloads._SOURCES["usitc/documents"].mime_type == "application/pdf"

    def test_gated_functions_remain_importable(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """Gating suppresses MCP registration, not the Python functions.

        Library and skill callers (and the patent-client-facade re-exports)
        import these directly, so they must survive an unset token.
        """
        monkeypatch.delenv("USITC_EDIS_TOKEN", raising=False)

        usitc_module = _reload_usitc_with_fresh_mcp()

        for name in EDIS_GATED_TOOLS:
            assert callable(getattr(usitc_module, name))
