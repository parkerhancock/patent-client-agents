"""Envelope-shape tests for the migrated Google Patents MCP tools.

Verifies the §5.1 / §5.5 / §5.7 / §5.9 contract for ``search_patents_global``
and ``get_patent``. Row 4 in MIGRATION_PLAYBOOK.md.

Mocks ``GooglePatentsClient`` at the boundary — we test envelope shape,
not the upstream scraping.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from law_tools_core.envelope import ListEnvelope, Provenance
from patent_client_agents.mcp.tools import patents as patents_module
from patent_client_agents.mcp.tools.patents import get_patent, search_patents_global

# ──────────────────────────────────────────────────────────────────────
# Fakes — minimal shapes that mimic GooglePatentsClient return types
# ──────────────────────────────────────────────────────────────────────


def _make_search_row(pub_no: str, title: str = "Sample") -> SimpleNamespace:
    """Mimic a GooglePatentsSearchResult — only model_dump() is exercised."""
    payload = {
        "result_type": "patent",
        "id": f"patent/{pub_no}/en",
        "rank": 0,
        "title": title,
        "snippet": "Snippet text",
        "publication_number": pub_no,
        "language": "en",
        "priority_date": "2018-05-01",
        "filing_date": "2019-05-01",
        "grant_date": "2022-06-15",
        "publication_date": "2022-06-15",
        "inventor": "Doe, John",
        "assignee": "ACME Corp",
        "pdf_url": "https://example/abc.pdf",
        "thumbnail_url": "https://example/abc.png",
        "detail_url": "https://example/detail",
        "family_country_status": [],
    }
    return SimpleNamespace(model_dump=lambda payload=payload: payload)


def _make_search_response(rows: list, *, total: int) -> SimpleNamespace:
    return SimpleNamespace(results=rows, total_results=total)


def _make_patent_data(pat_no: str, *, title: str = "Patent title") -> SimpleNamespace:
    """Mimic PatentData — model_dump() returns the full record fields used by the tool."""
    payload = {
        "patent_number": pat_no,
        "application_number": "16/123,456",
        "title": title,
        "abstract": "A patent abstract.",
        "status": "Active",
        "current_assignee": "ACME Corp",
        "original_assignee": "ACME Corp",
        "inventors": ["Doe, John", "Smith, Jane"],
        "filing_date": "2019-05-01",
        "grant_date": "2022-06-15",
        "publication_date": "2022-06-15",
        "priority_date": "2018-05-01",
        "claims": [{"number": 1, "text": "A method..."}, {"number": 2, "text": "..."}],
        "description": "Long description text...",
        "pdf_url": "https://example/abc.pdf",
        "kind_code": "B2",
        "expiration_date": "",
        "expiration_estimated": False,
        "structured_limitations": {},
        "cpc_classifications": [],
        "landscapes": [],
        "cited_patents": [],
        "citing_patents": [],
        "cited_patents_family": [],
        "citing_patents_family": [],
        "family_members": [],
        "country_filings": [],
        "similar_patents": [],
        "priority_applications": [],
        "child_applications": [],
        "apps_claiming_priority": [],
        "legal_events": [],
        "non_patent_literature": [],
        "detailed_non_patent_literature": [],
        "prior_art_keywords": [],
        "concepts": [],
        "definitions": [],
        "chemical_data": [],
        "external_links": [],
    }
    return SimpleNamespace(model_dump=lambda payload=payload: payload)


# ──────────────────────────────────────────────────────────────────────
# search_patents_global
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_patents_global_returns_lean_list_envelope_by_default():
    rows = [_make_search_row("US10123456B2", title="First"), _make_search_row("EP3456789A1")]
    fake_response = _make_search_response(rows, total=42)

    with patch.object(patents_module, "GooglePatentsClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.search_patents = AsyncMock(return_value=fake_response)
        result = await search_patents_global(query="neural network")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "Google Patents (worldwide aggregator)"
    assert "/xhr/query" in result.provenance.source_url
    assert result.provenance.source_url.startswith("https://patents.google.com")
    # Lean projection: ~9 scalar fields; no family_country_status, no rank, no id.
    assert len(result.items) == 2
    keys = set(result.items[0].keys())
    assert keys == {
        "publication_number",
        "title",
        "assignee",
        "inventor",
        "filing_date",
        "publication_date",
        "grant_date",
        "country",
        "language",
    }
    assert result.items[0]["country"] == "US"
    assert result.items[1]["country"] == "EP"
    # 2 of 42 → more available.
    assert result.more_available is True
    assert "Google Patents" in result.summary
    assert "2 of 42" in result.summary


@pytest.mark.asyncio
async def test_search_patents_global_full_opt_in_returns_upstream_row_shape():
    rows = [_make_search_row("US10123456B2")]
    fake_response = _make_search_response(rows, total=1)
    with patch.object(patents_module, "GooglePatentsClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.search_patents = AsyncMock(return_value=fake_response)
        result = await search_patents_global(query="*", full=True)

    assert len(result.items) == 1
    # Full payload carries the upstream-shaped fields the lean stub strips.
    assert "rank" in result.items[0]
    assert "family_country_status" in result.items[0]
    assert "thumbnail_url" in result.items[0]
    assert result.more_available is False  # 1 of 1, exhausted


@pytest.mark.asyncio
async def test_search_patents_global_provenance_source_name():
    rows = [_make_search_row("US10123456B2")]
    fake_response = _make_search_response(rows, total=1)
    with patch.object(patents_module, "GooglePatentsClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.search_patents = AsyncMock(return_value=fake_response)
        result = await search_patents_global(query="*")
    assert result.provenance.source_name == "Google Patents (worldwide aggregator)"


# ──────────────────────────────────────────────────────────────────────
# get_patent — §5.4 list-accepting, §5.1 view='full' / view='details'
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_patent_single_string_returns_list_envelope():
    fake_patent = _make_patent_data("US10123456B2", title="A clever invention")

    with patch.object(patents_module, "GooglePatentsClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.get_patent_data = AsyncMock(return_value=fake_patent)
        result = await get_patent(patent_number="US10123456B2")

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    assert result.provenance.source_name == "Google Patents (worldwide aggregator)"
    assert "/patent/US10123456B2" in result.provenance.source_url
    assert "US10123456B2" in result.summary
    assert "A clever invention" in result.summary


@pytest.mark.asyncio
async def test_get_patent_list_preserves_order():
    """Numbers in the request order should match numbers in the response order."""
    numbers = ["US10123456B2", "EP3456789A1", "WO2020123456A1"]
    payloads = [_make_patent_data(n) for n in numbers]

    with patch.object(patents_module, "GooglePatentsClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.get_patent_data = AsyncMock(side_effect=payloads)
        result = await get_patent(patent_number=numbers)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 3
    returned = [item["patent_number"] for item in result.items]
    assert returned == numbers
    # Multi-fetch points provenance at the collection URL.
    assert result.provenance.source_url.endswith("/patent")


@pytest.mark.asyncio
async def test_get_patent_view_full_default_returns_full_shape():
    fake_patent = _make_patent_data("US10123456B2")
    with patch.object(patents_module, "GooglePatentsClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.get_patent_data = AsyncMock(return_value=fake_patent)
        result = await get_patent(patent_number="US10123456B2")

    item = result.items[0]
    # Full payload retains description, claims array, and family arrays.
    assert "description" in item
    assert "cited_patents" in item
    assert "claims" in item
    assert isinstance(item["claims"], list)


@pytest.mark.asyncio
async def test_get_patent_view_details_returns_metadata_subset_shape():
    fake_patent = _make_patent_data("US10123456B2", title="Detail check")
    with patch.object(patents_module, "GooglePatentsClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.get_patent_data = AsyncMock(return_value=fake_patent)
        result = await get_patent(patent_number="US10123456B2", view="details")

    item = result.items[0]
    # The details subset carries the triage fields and the claim_count count, but
    # not the bulky description/claims-array/citations.
    assert item["patent_number"] == "US10123456B2"
    assert item["title"] == "Detail check"
    assert item["claim_count"] == 2
    assert item["inventors"] == ["Doe, John", "Smith, Jane"]
    assert "description" not in item
    assert "cited_patents" not in item
    # The claims array itself isn't returned in 'details'.
    assert "claims" not in item


@pytest.mark.asyncio
async def test_get_patent_invalid_view_raises():
    from law_tools_core.exceptions import ValidationError

    with pytest.raises(ValidationError, match="view must be"):
        await get_patent(patent_number="US10123456B2", view="bogus")


# ──────────────────────────────────────────────────────────────────────
# Old names — §5.7 rename + §5.1 collapse enforced via ImportError
# ──────────────────────────────────────────────────────────────────────


def test_old_name_search_google_patents_is_gone():
    """§5.7 rename: source-named tool replaced by jurisdiction-neutral name."""
    with pytest.raises(ImportError):
        from patent_client_agents.mcp.tools.patents import (  # noqa: F401
            search_google_patents,
        )


def test_old_tool_get_patent_details_is_gone():
    """§5.1 collapse: metadata-subset tool folded into get_patent(view='details')."""
    with pytest.raises(ImportError):
        from patent_client_agents.mcp.tools.patents import (  # noqa: F401
            get_patent_details,
        )


# ──────────────────────────────────────────────────────────────────────
# §5.4 no-batch-tool invariant
# ──────────────────────────────────────────────────────────────────────


def test_no_batch_get_patent_tool():
    """§5.4 forbids `batch_*` tools — list-acceptance lives on the canonical name."""
    import patent_client_agents.mcp.tools.patents as patents_mod

    assert not hasattr(patents_mod, "batch_get_patent")
    assert not hasattr(patents_mod, "batch_search_patents_global")
