"""Envelope-shape tests for ``get_epo_unitary_patent_status``.

Verifies CONNECTOR_STANDARDS.md §5.7 (jurisdiction prefix on the tool
name), §5.8 (no "package" jargon), §5.9 (envelope + provenance), and
§5.13 (elevator-test first sentence) for the renamed Unitary Patent
register tool.

Mocks ``client_from_env`` at the boundary so the upstream EPO Register
HTTP path is not exercised here.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from law_tools_core.envelope import Provenance, ResponseEnvelope
from patent_client_agents.epo_ops.models import (
    UnitaryPatentPackage,
    UnitaryPatentStatus,
)
from patent_client_agents.mcp.tools import international as international_module
from patent_client_agents.mcp.tools.international import (
    _summarize_unitary_patent,
    get_epo_unitary_patent_status,
)


def _patch_client_from_env(mock_client) -> object:
    """Patch ``client_from_env`` so its async-context-manager yields mock_client."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)
    return patch("patent_client_agents.mcp.tools.international.client_from_env", return_value=cm)


# ──────────────────────────────────────────────────────────────────────
# Rename: old name gone, new name importable (§5.7, §5.8, §5.13)
# ──────────────────────────────────────────────────────────────────────


def test_old_name_is_removed_from_module():
    """The pre-rename symbol must not be reachable from the module."""
    assert not hasattr(international_module, "get_unitary_patent_package")


def test_new_name_is_callable_and_async():
    """The renamed tool is a coroutine function under the new identifier."""
    import asyncio

    assert callable(get_epo_unitary_patent_status)
    assert asyncio.iscoroutinefunction(get_epo_unitary_patent_status)


def test_docstring_passes_elevator_test_and_lists_siblings():
    """Per §5.13 + §5.6: first sentence drops jargon; docstring names siblings."""
    doc = get_epo_unitary_patent_status.__doc__ or ""
    first = doc.strip().split("\n", 1)[0]
    # §5.13 — first sentence sells what the tool does in plain English.
    assert first.startswith(
        "Get the Unitary Patent (UP) Register record for a European patent application"
    )
    # §5.8 — "package" jargon removed.
    assert "package" not in first.lower()
    # §5.6 — sibling EPO tools named.
    assert "Related tools:" in doc
    for sibling in ("get_epo_biblio", "get_epo_legal_events", "search_epo"):
        assert sibling in doc, f"docstring missing sibling {sibling}"


# ──────────────────────────────────────────────────────────────────────
# Envelope shape + provenance (§5.9)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_returns_response_envelope_with_provenance_when_up_registered():
    upstream = UnitaryPatentPackage(
        epo_number="EP4108782.B1",
        statuses=[
            UnitaryPatentStatus(
                status_code="9",
                text="Unitary effect registered",
                change_date="20230607",
            ),
            UnitaryPatentStatus(
                status_code="6",
                text="Request for unitary effect filed",
                change_date="20230606",
            ),
        ],
    )
    mock_client = MagicMock()
    mock_client.get_unitary_patent_package = AsyncMock(return_value=upstream)

    with _patch_client_from_env(mock_client):
        result = await get_epo_unitary_patent_status(epo_number="EP4108782.B1")

    assert isinstance(result, ResponseEnvelope)
    assert isinstance(result.provenance, Provenance)
    # §5.9 — source name + URL identify the EPO Register UPP endpoint.
    assert result.provenance.source_name == "EPO Register (Unitary Patent)"
    assert (
        "/rest-services/register/publication/epodoc/EP4108782.B1/upp"
        in result.provenance.source_url
    )
    assert result.provenance.source_url.startswith("https://ops.epo.org/3.2")
    # Summary leads with the EP number and the latest status text.
    assert "EP4108782.B1" in result.summary
    assert "Unitary effect registered" in result.summary
    assert "20230607" in result.summary
    # Full payload flows through `details`.
    assert result.details["epo_number"] == "EP4108782.B1"
    assert len(result.details["statuses"]) == 2


@pytest.mark.asyncio
async def test_returns_empty_details_when_not_elected_for_unitary_effect():
    """Upstream ``None`` means no `<reg:unitary-patent>` block — render as empty."""
    mock_client = MagicMock()
    mock_client.get_unitary_patent_package = AsyncMock(return_value=None)

    with _patch_client_from_env(mock_client):
        result = await get_epo_unitary_patent_status(epo_number="EP3666797.B1")

    assert isinstance(result, ResponseEnvelope)
    # No record but envelope is still present + well-formed.
    assert result.details == {}
    assert "EP3666797.B1" in result.summary
    assert "no unitary-effect record" in result.summary
    assert (
        "/rest-services/register/publication/epodoc/EP3666797.B1/upp"
        in result.provenance.source_url
    )


@pytest.mark.asyncio
async def test_pending_status_flagged_when_only_request_filed():
    """`is_registered` heuristic — request filed without registration → 'pending'."""
    upstream = UnitaryPatentPackage(
        epo_number="EP9999999.B1",
        statuses=[
            UnitaryPatentStatus(
                status_code="6",
                text="Request for unitary effect filed",
                change_date="20250301",
            ),
        ],
    )
    mock_client = MagicMock()
    mock_client.get_unitary_patent_package = AsyncMock(return_value=upstream)

    with _patch_client_from_env(mock_client):
        result = await get_epo_unitary_patent_status(epo_number="EP9999999.B1")

    assert "pending" in result.summary
    assert "registered" not in result.summary or result.summary.count("registered") <= 1


def test_summarize_unitary_patent_handles_empty_record_dict():
    """The summarizer must not crash on an empty/partial record dict."""
    summary = _summarize_unitary_patent({"epo_number": "EP0000000.A1"})
    assert "EP0000000.A1" in summary
    assert "no unitary-effect record" in summary
