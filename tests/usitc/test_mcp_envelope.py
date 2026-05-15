"""Envelope-shape tests for the migrated USITC MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope + Provenance), §5.5
(lean default + ``full=True`` opt-in), §5.4 (list-accepting fetches),
§5.6 (cross-references in docstrings), and §5.13 (elevator test for
``run_dataweb_report``).

Mocks ``EdisClient`` / ``HtsClient`` / ``DataWebClient`` / ``IdsClient``
at the boundary — we're testing envelope shape, not the upstream APIs.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from law_tools_core.envelope import ListEnvelope, Provenance, ResponseEnvelope
from law_tools_core.exceptions import ValidationError
from patent_client_agents.mcp.tools.usitc import (
    get_usitc_investigation,
    list_usitc_attachments,
    run_dataweb_report,
    search_hts_tariffs,
    search_usitc_investigations,
)
from patent_client_agents.usitc.models import (
    DataWebReport,
    EdisAttachment,
    EdisInvestigation,
    HtsSearchResult,
)

# ──────────────────────────────────────────────────────────────────────
# Helpers — minimal upstream model instances
# ──────────────────────────────────────────────────────────────────────


def _make_investigation(
    number: str,
    *,
    title: str = "Certain Widgets",
    status: str = "Active",
    phase: str = "Violation",
    inv_type: str = "Sec 337",
    docket: str = "3500",
) -> EdisInvestigation:
    return EdisInvestigation(
        investigationNumber=number,
        investigationPhase=phase,
        investigationType=inv_type,
        investigationStatus=status,
        investigationTitle=title,
        docketNumber=docket,
        documentListUri=f"https://edis.usitc.gov/data/document?investigationNumber={number}",
    )


def _make_attachment(att_id: int, *, doc_id: int = 5001, title: str = "Exhibit") -> EdisAttachment:
    return EdisAttachment(
        id=att_id,
        documentId=doc_id,
        title=title,
        fileSize=12345,
        originalFileName=f"{title}.pdf",
        pageCount=10,
        createDate="2024-06-01 00:00:00.0",
        lastModifiedDate="2024-06-01 00:00:00.0",
        downloadUri=f"https://edis.usitc.gov/data/download/{doc_id}/{att_id}",
    )


def _make_hts(number: str, *, description: str = "Widget") -> HtsSearchResult:
    return HtsSearchResult(
        htsno=number,
        description=description,
        heading="8542",
        chapter="85",
    )


# ──────────────────────────────────────────────────────────────────────
# search_usitc_investigations — §5.9, §5.5
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_usitc_investigations_returns_lean_list_envelope_by_default():
    investigations = [
        _make_investigation("337-1234", title="Certain Widgets"),
        _make_investigation("337-1235", title="Certain Gizmos"),
    ]
    with patch("patent_client_agents.mcp.tools.usitc.EdisClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.list_investigations = AsyncMock(return_value=investigations)

        result = await search_usitc_investigations(status="Active")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "U.S. International Trade Commission (USITC)"
    assert result.provenance.source_url.startswith("https://edis.usitc.gov")
    # Live proxy → no corpus metadata.
    assert result.provenance.corpus_synced_at is None
    assert result.provenance.corpus_version is None
    assert len(result.items) == 2
    # Lean projection (§5.5) — exactly these keys.
    expected_keys = {
        "investigation_number",
        "title",
        "investigation_status",
        "investigation_phase",
        "investigation_type",
        "docket_number",
    }
    assert set(result.items[0].keys()) == expected_keys
    assert result.items[0]["investigation_number"] == "337-1234"
    # Summary names the active filter and result count.
    assert "USITC investigations" in result.summary
    assert "status=Active" in result.summary
    assert "2 hits" in result.summary


@pytest.mark.asyncio
async def test_search_usitc_investigations_full_true_returns_upstream_shape():
    investigations = [_make_investigation("337-1234")]
    with patch("patent_client_agents.mcp.tools.usitc.EdisClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.list_investigations = AsyncMock(return_value=investigations)

        result = await search_usitc_investigations(full=True)

    # Full mode carries the upstream-dumped record (incl. document_list_uri).
    item = result.items[0]
    assert "document_list_uri" in item
    assert "investigation_number" in item


# ──────────────────────────────────────────────────────────────────────
# get_usitc_investigation — §5.4 list-accepting
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_usitc_investigation_single_returns_list_envelope():
    record = _make_investigation("337-1234")
    with patch("patent_client_agents.mcp.tools.usitc.EdisClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.list_investigations = AsyncMock(return_value=[record])

        result = await get_usitc_investigation(investigation_number="337-1234")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "U.S. International Trade Commission (USITC)"
    assert "/data/investigation/337-1234" in result.provenance.source_url
    assert len(result.items) == 1
    assert "USITC investigation 337-1234" in result.summary
    assert "Certain Widgets" in result.summary


@pytest.mark.asyncio
async def test_get_usitc_investigation_list_preserves_order():
    numbers = ["337-1234", "337-1235", "337-1236"]
    records = [[_make_investigation(n)] for n in numbers]
    with patch("patent_client_agents.mcp.tools.usitc.EdisClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.list_investigations = AsyncMock(side_effect=records)

        result = await get_usitc_investigation(investigation_number=numbers)

    assert [r["investigation_number"] for r in result.items] == numbers
    assert "Fetched 3 of 3 USITC investigations" in result.summary


@pytest.mark.asyncio
async def test_get_usitc_investigation_partial_not_found_lists_missing():
    with patch("patent_client_agents.mcp.tools.usitc.EdisClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        # First call returns a hit, second call returns an empty list.
        mock_client.list_investigations = AsyncMock(
            side_effect=[[_make_investigation("337-1234")], []]
        )

        result = await get_usitc_investigation(investigation_number=["337-1234", "337-9999"])

    assert len(result.items) == 1
    assert "Not found: 337-9999" in result.summary


@pytest.mark.asyncio
async def test_get_usitc_investigation_empty_list_raises():
    with pytest.raises(ValidationError, match="at least one"):
        await get_usitc_investigation(investigation_number=[])


# ──────────────────────────────────────────────────────────────────────
# list_usitc_attachments — Shape D facet fetch
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_usitc_attachments_returns_list_envelope():
    attachments = [
        _make_attachment(7001, doc_id=5001, title="Exhibit A"),
        _make_attachment(7002, doc_id=5001, title="Exhibit B"),
    ]
    with patch("patent_client_agents.mcp.tools.usitc.EdisClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.list_attachments = AsyncMock(return_value=attachments)

        result = await list_usitc_attachments(document_id=5001)

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "U.S. International Trade Commission (USITC)"
    assert "/data/attachment/5001" in result.provenance.source_url
    assert len(result.items) == 2
    assert result.items[0]["id"] == 7001
    # Auth-gated download_uri stripped from items.
    assert "download_uri" not in result.items[0]
    assert "USITC document 5001" in result.summary
    assert "2 attachments" in result.summary


# ──────────────────────────────────────────────────────────────────────
# search_hts_tariffs — §5.5
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_hts_tariffs_returns_lean_list_envelope_by_default():
    results = [
        _make_hts("8542.31.0001", description="Processors and controllers"),
        _make_hts("8542.32.0001", description="Memories"),
    ]
    with patch("patent_client_agents.mcp.tools.usitc.HtsClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=results)

        result = await search_hts_tariffs(query="semiconductor")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "U.S. International Trade Commission (USITC)"
    assert "hts.usitc.gov" in result.provenance.source_url
    assert len(result.items) == 2
    # Lean projection.
    assert set(result.items[0].keys()) == {
        "hts_number",
        "description",
        "heading",
        "chapter",
    }
    assert "`semiconductor`" in result.summary
    assert "2 hits" in result.summary


# ──────────────────────────────────────────────────────────────────────
# run_dataweb_report — §5.9 single-record + §5.13 elevator test
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_dataweb_report_returns_response_envelope():
    report = DataWebReport(
        dto={
            "rows": [
                {"hts": "8542", "value": 12345.67},
                {"hts": "8541", "value": 9876.54},
            ]
        },
        raw={"any": "thing"},
    )
    with patch("patent_client_agents.mcp.tools.usitc.DataWebClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.run_report = AsyncMock(return_value=report)

        result = await run_dataweb_report(
            trade_type="Import",
            classification="HTS",
            years="2024",
            data_metrics="CONS_CUSTOMS_VALUE",
        )

    assert isinstance(result, ResponseEnvelope)
    assert result.provenance.source_name == "U.S. International Trade Commission (USITC)"
    assert "datawebws.usitc.gov" in result.provenance.source_url
    # Summary identifies it as a USITC DataWeb report — needed because §5.13
    # asks the first line of the response to ground "DataWeb" for non-trade
    # readers.
    assert "USITC DataWeb" in result.summary
    assert "Import" in result.summary
    assert "2024" in result.summary
    assert "2 row(s)" in result.summary
    # ``details`` carries the upstream dump verbatim.
    assert "dto" in result.details
    assert result.details["dto"]["rows"][0]["hts"] == "8542"


@pytest.mark.asyncio
async def test_run_dataweb_report_first_sentence_passes_elevator_test():
    """§5.13: first sentence must ground 'DataWeb' for a non-trade-attorney reader."""
    docstring = run_dataweb_report.__doc__ or ""
    first_line = docstring.strip().splitlines()[0]
    assert "US import/export statistics" in first_line
    assert "USITC DataWeb" in first_line


# ──────────────────────────────────────────────────────────────────────
# §5.6 cross-references — every migrated tool ends with "Related tools:"
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "tool",
    [
        search_usitc_investigations,
        get_usitc_investigation,
        list_usitc_attachments,
        search_hts_tariffs,
        run_dataweb_report,
    ],
)
def test_docstring_ends_with_related_tools(tool):
    docstring = tool.__doc__ or ""
    assert "Related tools:" in docstring, f"{tool.__name__} missing Related tools line"


# ──────────────────────────────────────────────────────────────────────
# §5.4 invariant — no batch tools
# ──────────────────────────────────────────────────────────────────────


def test_no_batch_tool_present():
    """§5.4 forbids batch_* tools."""
    from patent_client_agents.mcp.tools import usitc as usitc_module

    assert not hasattr(usitc_module, "batch_usitc_investigations")
    assert not hasattr(usitc_module, "batch_get_usitc_investigation")
    assert not hasattr(usitc_module, "batch_search_usitc_investigations")
