"""The facade's USITC surface is gated on an EDIS direct or file token.

EDIS tools are env-gated upstream in
``patent_client_agents.mcp.tools.usitc`` so the public demo at
mcp.patentclient.com advertises no ITC surface. That gate alone is NOT
enough here: ``conditional_tool`` suppresses registration on ``usitc_mcp``
but deliberately leaves the underlying functions importable, and this
facade re-exports them by direct import. So the facade mirrors the gate,
and these tests pin both halves of it.

Two exposure paths are covered:

1. Verbatim re-exports (``search_usitc_investigations`` et al.) — must
   not register as facade tools when the token is absent.
2. Cross-source dispatcher enums (``get_litigation.forum``,
   ``download_document.source``) — must not offer usitc values that
   would route agents into a dead branch.

Note ``test_verbatim_reexposes_are_importable`` in
test_litigation_facade.py asserts the *module attributes* stay callable
regardless; that is the complementary half of the contract and passes in
both configurations by design.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

EDIS_REEXPORTED_TOOLS = {
    "search_usitc_investigations",
    "search_usitc_documents",
    "list_usitc_attachments",
}


def _reload_facade_modules():
    """Reload both facade modules so their import-time env reads re-run.

    Returns ``(litigation_module, documents_module)``. Each module rebinds
    its own ``FastMCP`` at import, so a reload yields a fresh surface built
    entirely under the current env.
    """
    from patent_client_agents.facade import documents as documents_module
    from patent_client_agents.facade import litigation as litigation_module

    return (
        importlib.reload(litigation_module),
        importlib.reload(documents_module),
    )


@pytest.fixture
def restore_modules():
    """Reload both modules under the ambient env after each test.

    The modules are process-cached and other test modules import their
    tool functions, so leaving a reloaded-under-fake-env copy in
    ``sys.modules`` would leak across the suite.
    """
    yield
    _reload_facade_modules()


async def _tool_names(mcp) -> set[str]:
    return {t.name for t in await mcp.list_tools()}


async def _param_enum(mcp, tool_name: str, param: str) -> list[str]:
    tools = {t.name: t for t in await mcp.list_tools()}
    return tools[tool_name].parameters["properties"][param]["enum"]


class TestUsitcFacadeGating:
    async def test_reexports_absent_when_token_unset(
        self, monkeypatch: pytest.MonkeyPatch, restore_modules: None
    ) -> None:
        monkeypatch.delenv("USITC_EDIS_TOKEN", raising=False)

        litigation_module, _ = _reload_facade_modules()

        names = await _tool_names(litigation_module.litigation_facade_mcp)
        assert names & EDIS_REEXPORTED_TOOLS == set()
        # Sanity: the non-USITC re-exports must still be there, otherwise
        # this assertion would pass against an empty surface.
        assert {"search_upc_decisions", "list_ptab_children"} <= names

    async def test_reexports_present_when_token_set(
        self, monkeypatch: pytest.MonkeyPatch, restore_modules: None
    ) -> None:
        monkeypatch.setenv("USITC_EDIS_TOKEN", "test_edis_token")

        litigation_module, _ = _reload_facade_modules()

        names = await _tool_names(litigation_module.litigation_facade_mcp)
        assert EDIS_REEXPORTED_TOOLS <= names

    async def test_forum_enum_drops_usitc_when_token_unset(
        self, monkeypatch: pytest.MonkeyPatch, restore_modules: None
    ) -> None:
        monkeypatch.delenv("USITC_EDIS_TOKEN", raising=False)

        litigation_module, _ = _reload_facade_modules()

        enum = await _param_enum(litigation_module.litigation_facade_mcp, "get_litigation", "forum")
        assert "usitc" not in enum
        assert {"ptab", "upc"} <= set(enum)

    async def test_forum_enum_keeps_usitc_when_token_set(
        self, monkeypatch: pytest.MonkeyPatch, restore_modules: None
    ) -> None:
        monkeypatch.setenv("USITC_EDIS_TOKEN", "test_edis_token")

        litigation_module, _ = _reload_facade_modules()

        enum = await _param_enum(litigation_module.litigation_facade_mcp, "get_litigation", "forum")
        assert "usitc" in enum

    async def test_download_source_enum_drops_usitc_when_token_unset(
        self, monkeypatch: pytest.MonkeyPatch, restore_modules: None
    ) -> None:
        monkeypatch.delenv("USITC_EDIS_TOKEN", raising=False)

        _, documents_module = _reload_facade_modules()

        enum = await _param_enum(
            documents_module.documents_facade_mcp, "download_document", "source"
        )
        assert not [v for v in enum if v.startswith("usitc")]
        assert {"patent_pdf", "cafc", "ipa_bulk"} <= set(enum)

    async def test_download_source_enum_keeps_usitc_when_token_set(
        self, monkeypatch: pytest.MonkeyPatch, restore_modules: None
    ) -> None:
        monkeypatch.setenv("USITC_EDIS_TOKEN", "test_edis_token")

        _, documents_module = _reload_facade_modules()

        enum = await _param_enum(
            documents_module.documents_facade_mcp, "download_document", "source"
        )
        assert {"usitc_attachment", "usitc_investigation"} <= set(enum)

    async def test_empty_token_treated_as_unset(
        self, monkeypatch: pytest.MonkeyPatch, restore_modules: None
    ) -> None:
        """Cloud Run renders an unmounted secret binding as an empty string."""
        monkeypatch.setenv("USITC_EDIS_TOKEN", "")

        litigation_module, documents_module = _reload_facade_modules()

        names = await _tool_names(litigation_module.litigation_facade_mcp)
        assert names & EDIS_REEXPORTED_TOOLS == set()

        forum = await _param_enum(
            litigation_module.litigation_facade_mcp, "get_litigation", "forum"
        )
        assert "usitc" not in forum

        source = await _param_enum(
            documents_module.documents_facade_mcp, "download_document", "source"
        )
        assert not [v for v in source if v.startswith("usitc")]

    async def test_token_file_enables_usitc_surface(
        self,
        monkeypatch: pytest.MonkeyPatch,
        restore_modules: None,
        tmp_path: Path,
    ) -> None:
        token_file = tmp_path / "edis-token"
        token_file.write_text("test_edis_token")
        monkeypatch.delenv("USITC_EDIS_TOKEN", raising=False)
        monkeypatch.setenv("USITC_EDIS_TOKEN_FILE", str(token_file))

        litigation_module, documents_module = _reload_facade_modules()

        names = await _tool_names(litigation_module.litigation_facade_mcp)
        assert EDIS_REEXPORTED_TOOLS <= names
        forum = await _param_enum(
            litigation_module.litigation_facade_mcp, "get_litigation", "forum"
        )
        assert "usitc" in forum
        source = await _param_enum(
            documents_module.documents_facade_mcp, "download_document", "source"
        )
        assert {"usitc_attachment", "usitc_investigation"} <= set(source)
