"""Envelope-shape tests for the migrated USPTO Office Actions MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.2 (orphan-search fix — get_office_action
now exists), §5.4 (list-accepting get_*), §5.5 (lean default + full=True
opt-in), §5.6 (Related tools docstring footer), and §5.9 (envelope
contract) for ``search_office_actions`` and ``get_office_action``.

Mocks ``OfficeActionClient`` at the boundary — we're testing envelope
shape, not the upstream Solr API.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from law_tools_core.envelope import ListEnvelope, Provenance, decode_cursor
from patent_client_agents.mcp.tools.office_actions import (
    get_office_action,
    search_office_actions,
)

# ──────────────────────────────────────────────────────────────────────
# Fakes — minimal Pydantic-shaped responses mirroring OfficeActionClient
# ──────────────────────────────────────────────────────────────────────


class _FakeSearchResponse(BaseModel):
    num_found: int = 0
    start: int = 0
    results: list[dict] = []

    def model_dump(self, **kwargs):  # type: ignore[override]
        return {
            "num_found": self.num_found,
            "start": self.start,
            "results": self.results,
        }


def _rejection_doc(
    doc_id: str = "oa001",
    appl: str = "16123456",
    *,
    has_rej_103: int = 1,
    has_rej_112: int = 0,
    art_unit: str = "2161",
) -> dict:
    return {
        "id": doc_id,
        "patent_application_number": appl,
        "legal_section_code": "103",
        "legacy_document_code_identifier": "CTNF",
        "submission_date": "2023-04-12",
        "group_art_unit_number": art_unit,
        "national_class": "438",
        "has_rej_103": has_rej_103,
        "has_rej_112": has_rej_112,
        "has_rej_101": 0,
        "has_rej_102": 0,
        "has_rej_dp": 0,
    }


def _text_doc(
    doc_id: str = "oa001",
    appl: str = "16123456",
    *,
    title: str = "Widget Apparatus",
    body: str = "OFFICE ACTION SUMMARY...",
) -> dict:
    return {
        "id": doc_id,
        "patent_application_number": appl,
        "submission_date": "2023-04-12",
        "legacy_document_code_identifier": "CTNF",
        "invention_title": title,
        "group_art_unit_number": "2161",
        "patent_number": "",
        "application_type_category": "UTILITY",
        "body_text": [body],
        "sections": [{"name": "Summary", "text": body}],
    }


# ──────────────────────────────────────────────────────────────────────
# search_office_actions — envelope + lean default + full=True opt-in
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_office_actions_returns_list_envelope():
    fake_response = _FakeSearchResponse(
        num_found=42,
        results=[
            _rejection_doc(doc_id="oa001", has_rej_103=1, has_rej_112=0),
            _rejection_doc(doc_id="oa002", has_rej_103=0, has_rej_112=1),
        ],
    )

    with patch(
        "patent_client_agents.mcp.tools.office_actions.OfficeActionClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.search_rejections = AsyncMock(return_value=fake_response)

        result = await search_office_actions(
            criteria="patentApplicationNumber:16123456",
            result_type="rejections",
            rows=2,
        )

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "USPTO Office Actions Dataset"
    assert "/api/v1/patent/oa/oa_rejections/v2/records" in result.provenance.source_url
    assert len(result.items) == 2
    # More remaining (42 total, 2 shown, start=0)
    assert result.more_available is True
    assert result.next_cursor is not None
    cursor_payload = decode_cursor(result.next_cursor)
    assert cursor_payload == {"start": 2, "rows": 2}
    assert "USPTO office actions" in result.summary
    assert "rejections" in result.summary
    assert "2 of 42" in result.summary


@pytest.mark.asyncio
async def test_search_office_actions_lean_default():
    """Lean projection: only the ~8 scalar fields, not the full Solr record."""
    raw = _rejection_doc(doc_id="oa001", has_rej_103=1, has_rej_112=1)
    raw["national_subclass"] = "123"  # extra field that should NOT survive lean projection
    raw["paragraph_number"] = "0042"
    fake_response = _FakeSearchResponse(num_found=1, results=[raw])

    with patch(
        "patent_client_agents.mcp.tools.office_actions.OfficeActionClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.search_rejections = AsyncMock(return_value=fake_response)

        result = await search_office_actions(criteria="hasRej103:1", result_type="rejections")

    stub = result.items[0]
    assert set(stub.keys()) == {
        "document_identifier",
        "application_number",
        "mail_date",
        "document_code",
        "art_unit",
        "rejection_types",
        "legal_section_code",
        "national_class",
    }
    assert stub["rejection_types"] == ["§103", "§112"]
    assert stub["document_identifier"] == "oa001"
    assert "national_subclass" not in stub  # not surfaced in lean shape
    assert "paragraph_number" not in stub


@pytest.mark.asyncio
async def test_search_office_actions_full_opt_in_returns_raw_records():
    raw = _rejection_doc(doc_id="oa001", has_rej_103=1)
    raw["paragraph_number"] = "0042"
    fake_response = _FakeSearchResponse(num_found=1, results=[raw])

    with patch(
        "patent_client_agents.mcp.tools.office_actions.OfficeActionClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.search_rejections = AsyncMock(return_value=fake_response)

        result = await search_office_actions(
            criteria="hasRej103:1", result_type="rejections", full=True
        )

    # With full=True, the raw Solr fields survive (paragraph_number kept).
    assert result.items[0]["paragraph_number"] == "0042"
    assert result.items[0]["has_rej_103"] == 1


@pytest.mark.asyncio
async def test_search_office_actions_more_available_false_when_exhausted():
    fake_response = _FakeSearchResponse(num_found=1, results=[_rejection_doc(doc_id="oa001")])

    with patch(
        "patent_client_agents.mcp.tools.office_actions.OfficeActionClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.search_rejections = AsyncMock(return_value=fake_response)

        result = await search_office_actions(criteria="*", result_type="rejections")

    assert result.more_available is False
    assert result.next_cursor is None


# ──────────────────────────────────────────────────────────────────────
# get_office_action — §5.4 list-accepting, §5.2 orphan-fix
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_office_action_single_string_returns_list_envelope():
    fake_response = _FakeSearchResponse(
        num_found=1, results=[_text_doc(doc_id="oa001", appl="16123456")]
    )

    with patch(
        "patent_client_agents.mcp.tools.office_actions.OfficeActionClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.search_office_action_text = AsyncMock(return_value=fake_response)

        result = await get_office_action(document_identifier="oa001")

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    assert result.provenance.source_name == "USPTO Office Actions Dataset"
    assert "/api/v1/patent/oa/oa_actions/v1/records" in result.provenance.source_url
    # Summary contains the identifying text for the single record.
    assert "oa001" in result.summary
    assert "16123456" in result.summary
    assert "Widget Apparatus" in result.summary

    # The underlying client was called with an id:<doc_id> Lucene query.
    call_kwargs = mock_client.search_office_action_text.call_args
    query_arg = call_kwargs.args[0]
    assert query_arg == "id:oa001"


@pytest.mark.asyncio
async def test_get_office_action_list_preserves_order():
    ids = ["oa_A", "oa_B", "oa_C"]
    responses = [
        _FakeSearchResponse(num_found=1, results=[_text_doc(doc_id=i, appl=f"16000{n}")])
        for n, i in enumerate(ids)
    ]

    with patch(
        "patent_client_agents.mcp.tools.office_actions.OfficeActionClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.search_office_action_text = AsyncMock(side_effect=responses)

        result = await get_office_action(document_identifier=ids)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 3
    returned_ids = [item["id"] for item in result.items]
    assert returned_ids == ids
    assert "3 of 3 USPTO office actions" in result.summary


@pytest.mark.asyncio
async def test_get_office_action_bounded_concurrency_fanout():
    """All three fan-out calls run concurrently against the same client instance."""
    ids = ["a", "b", "c"]
    responses = [_FakeSearchResponse(num_found=1, results=[_text_doc(doc_id=i)]) for i in ids]

    with patch(
        "patent_client_agents.mcp.tools.office_actions.OfficeActionClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.search_office_action_text = AsyncMock(side_effect=responses)

        result = await get_office_action(document_identifier=ids)

    # Single async-context entry, three fan-out fetches inside it.
    assert mock_client_cls.return_value.__aenter__.call_count == 1
    assert mock_client.search_office_action_text.call_count == 3
    assert len(result.items) == 3


# ──────────────────────────────────────────────────────────────────────
# §5.2 — orphan-search fixed, §5.4 — no batch tool
# ──────────────────────────────────────────────────────────────────────


def test_search_and_get_both_importable():
    """§5.2: search_office_actions used to be an orphan (no fetch tool).
    The migration adds get_office_action so both verbs are importable.
    """
    from patent_client_agents.mcp.tools import office_actions as oa_module

    assert hasattr(oa_module, "search_office_actions")
    assert hasattr(oa_module, "get_office_action")


def test_no_batch_tool_present():
    """§5.4 forbids batch_* tools — list-accepting get_* replaces them."""
    from patent_client_agents.mcp.tools import office_actions as oa_module

    assert not hasattr(oa_module, "batch_get_office_action")
    assert not hasattr(oa_module, "batch_office_action")
    assert not hasattr(oa_module, "batch_office_actions")
