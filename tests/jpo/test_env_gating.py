"""Tests for env-gated JPO MCP tool registration.

Verifies that ``patent_client_agents.mcp.tools.international`` registers
the 12 JPO tools (and the JPO download fetcher) only when both
``JPO_API_USERNAME`` and ``JPO_API_PASSWORD`` are set.

Test strategy: each test ``importlib.reload``s the international module
under a controlled env, then inspects a fresh ``FastMCP`` instance to
see what got registered. We rebind ``international_mcp`` on the module
to a fresh server before reload so the 12 ``@conditional_tool`` decorators
each run against an empty surface — that way the assertions are about
what *this reload* would have registered, not anything that came before.
"""

from __future__ import annotations

import importlib

import pytest
from fastmcp import FastMCP

from law_tools_core.mcp import downloads


def _reload_international_with_fresh_mcp() -> object:
    """Reload the international tool module under a fresh FastMCP.

    Replaces ``international_mcp`` with a brand-new instance, then reloads
    the module so every ``@conditional_tool`` decorator runs against the
    fresh surface. Returns the reloaded module.
    """
    import patent_client_agents.mcp.tools.international as inter

    inter.international_mcp = FastMCP("International")
    return importlib.reload(inter)


@pytest.fixture
def fresh_state(monkeypatch: pytest.MonkeyPatch):
    """Snapshot + restore the download source registry around each test.

    Each test mutates the global ``_SOURCES`` dict via reload; we restore
    the pre-test state on teardown so other tests in the suite (which
    rely on ``register_source_if_configured`` having registered the JPO
    fetcher under the conftest-set placeholder env) keep working.
    """
    saved_sources = dict(downloads._SOURCES)
    yield
    downloads._SOURCES.clear()
    downloads._SOURCES.update(saved_sources)
    # Restore the conftest-managed registration state too. The
    # international module is module-cached; reload once more under the
    # conftest's set env so subsequent tests see the registered tools.
    _reload_international_with_fresh_mcp()


class TestJpoEnvGating:
    @pytest.mark.asyncio
    async def test_no_jpo_tools_registered_when_env_unset(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """With JPO env vars unset, zero get_jpo_* tools register."""
        monkeypatch.delenv("JPO_API_USERNAME", raising=False)
        monkeypatch.delenv("JPO_API_PASSWORD", raising=False)

        inter = _reload_international_with_fresh_mcp()

        tools = await inter.international_mcp.list_tools()  # type: ignore[attr-defined]
        jpo_names = [t.name for t in tools if t.name.startswith("get_jpo_")]
        assert jpo_names == []

        # Sanity: the EPO/CPC tools (which are NOT env-gated) should
        # still be registered — that proves the reload actually ran the
        # decorators and we didn't just import a no-op module.
        all_names = {t.name for t in tools}
        assert "search_epo" in all_names

    @pytest.mark.asyncio
    async def test_only_username_set_skips_registration(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """Partial env (only username) is treated as absent."""
        monkeypatch.setenv("JPO_API_USERNAME", "alice")
        monkeypatch.delenv("JPO_API_PASSWORD", raising=False)

        inter = _reload_international_with_fresh_mcp()

        tools = await inter.international_mcp.list_tools()  # type: ignore[attr-defined]
        jpo_names = [t.name for t in tools if t.name.startswith("get_jpo_")]
        assert jpo_names == []

    @pytest.mark.asyncio
    async def test_only_password_set_skips_registration(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """Partial env (only password) is treated as absent."""
        monkeypatch.delenv("JPO_API_USERNAME", raising=False)
        monkeypatch.setenv("JPO_API_PASSWORD", "secret")

        inter = _reload_international_with_fresh_mcp()

        tools = await inter.international_mcp.list_tools()  # type: ignore[attr-defined]
        jpo_names = [t.name for t in tools if t.name.startswith("get_jpo_")]
        assert jpo_names == []

    @pytest.mark.asyncio
    async def test_all_jpo_tools_registered_when_env_set(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """With both vars set, every JPO tool is registered."""
        monkeypatch.setenv("JPO_API_USERNAME", "alice")
        monkeypatch.setenv("JPO_API_PASSWORD", "secret")

        inter = _reload_international_with_fresh_mcp()

        tools = await inter.international_mcp.list_tools()  # type: ignore[attr-defined]
        jpo_names = {t.name for t in tools if t.name.startswith("get_jpo_")}
        expected = {
            "get_jpo_progress",
            "get_jpo_progress_simple",
            "get_jpo_priority_info",
            "get_jpo_registration_info",
            "get_jpo_number_reference",
            "get_jpo_jplatpat_url",
            "get_jpo_applicant",
            "get_jpo_documents",
            "get_jpo_patent_divisional_info",
            "get_jpo_patent_cited_documents",
            "get_jpo_pct_national_phase_number",
        }
        assert jpo_names == expected

    def test_jpo_download_source_skipped_when_env_unset(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """JPO download fetcher is NOT registered when env is unset."""
        monkeypatch.delenv("JPO_API_USERNAME", raising=False)
        monkeypatch.delenv("JPO_API_PASSWORD", raising=False)

        # Clear the registry so we observe only what THIS reload registers.
        downloads._SOURCES.clear()

        _reload_international_with_fresh_mcp()

        assert "jpo/documents" not in downloads._SOURCES
        # EPO source IS registered unconditionally — sanity check that
        # the reload ran and didn't just no-op.
        assert "epo/patents" in downloads._SOURCES

    def test_jpo_download_source_partial_env_skipped(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """JPO download fetcher is NOT registered when only one var is set."""
        monkeypatch.setenv("JPO_API_USERNAME", "alice")
        monkeypatch.delenv("JPO_API_PASSWORD", raising=False)

        downloads._SOURCES.clear()
        _reload_international_with_fresh_mcp()

        assert "jpo/documents" not in downloads._SOURCES

    def test_jpo_download_source_registered_when_env_set(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """JPO download fetcher IS registered when both vars are set."""
        monkeypatch.setenv("JPO_API_USERNAME", "alice")
        monkeypatch.setenv("JPO_API_PASSWORD", "secret")

        downloads._SOURCES.clear()
        _reload_international_with_fresh_mcp()

        assert "jpo/documents" in downloads._SOURCES
        assert downloads._SOURCES["jpo/documents"].mime_type == "application/zip"
