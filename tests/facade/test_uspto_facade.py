"""Routing contract for the consolidated USPTO facade dispatchers.

The facade tools hold no business logic — each branch forwards to an
existing per-source function that is already tested for §5.9 envelope
shape (see tests/uspto_odp/test_mcp_envelope.py). These tests pin the
*routing*: that the right ``dataset``/``mode`` enum value reaches the right
underlying function with the right arguments, and that the facade returns
that function's result unchanged. The targets are patched where the facade
imports them (``...mcp.facade.uspto``), so no upstream HTTP is touched.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from mcp_data_core.exceptions import ValidationError
from patent_client_agents.facade.uspto import (
    get_file_history,
    get_uspto,
    search_uspto,
)

_MOD = "patent_client_agents.facade.uspto"


# ──────────────────────────────────────────────────────────────────────
# search_uspto
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_uspto_routes_applications_with_offset():
    with patch(f"{_MOD}.search_applications", new=AsyncMock(return_value="APPS")) as m:
        out = await search_uspto(dataset="applications", query="q", limit=5, offset=2, full=True)
    assert out == "APPS"
    m.assert_awaited_once_with(query="q", limit=5, offset=2, full=True)


@pytest.mark.asyncio
async def test_search_uspto_routes_publications_and_drops_offset():
    # PPUBS paginates by limit only — offset must NOT be forwarded.
    with patch(f"{_MOD}.search_patent_publications", new=AsyncMock(return_value="PUBS")) as m:
        out = await search_uspto(dataset="publications", query="CLM/neural", limit=3, offset=9)
    assert out == "PUBS"
    m.assert_awaited_once_with(query="CLM/neural", limit=3, full=False)


@pytest.mark.asyncio
async def test_search_uspto_publications_defaults_to_reliable_page_size():
    with patch(f"{_MOD}.search_patent_publications", new=AsyncMock(return_value="PUBS")) as m:
        out = await search_uspto(dataset="publications", query="neural.CLM.")
    assert out == "PUBS"
    m.assert_awaited_once_with(query="neural.CLM.", limit=20, full=False)


@pytest.mark.asyncio
async def test_search_uspto_routes_petitions():
    with patch(f"{_MOD}.search_petitions", new=AsyncMock(return_value="PET")) as m:
        out = await search_uspto(dataset="petitions", query="q", limit=7, offset=1)
    assert out == "PET"
    m.assert_awaited_once_with(query="q", limit=7, offset=1, full=False)


# ──────────────────────────────────────────────────────────────────────
# get_uspto — uniform identifier-in, ListEnvelope-out across all five
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("dataset", "target", "expected_call"),
    [
        ("application", "get_application", {"args": ("16123456",), "kwargs": {}}),
        (
            "publication",
            "get_patent_publication",
            {"args": (), "kwargs": {"publication_number": "16123456"}},
        ),
        ("petition", "get_petition", {"args": ("16123456",), "kwargs": {}}),
        ("office_action", "get_office_action", {"args": ("16123456",), "kwargs": {}}),
        ("assignment", "get_patent_assignment", {"args": ("16123456",), "kwargs": {}}),
    ],
)
async def test_get_uspto_routes_each_dataset(dataset, target, expected_call):
    with patch(f"{_MOD}.{target}", new=AsyncMock(return_value="REC")) as m:
        out = await get_uspto(dataset=dataset, identifier="16123456")
    assert out == "REC"
    m.assert_awaited_once_with(*expected_call["args"], **expected_call["kwargs"])


@pytest.mark.asyncio
async def test_get_uspto_passes_list_identifier_through():
    ids = ["16123456", "17654321"]
    with patch(f"{_MOD}.get_application", new=AsyncMock(return_value="RECS")) as m:
        out = await get_uspto(dataset="application", identifier=ids)
    assert out == "RECS"
    m.assert_awaited_once_with(ids)


@pytest.mark.asyncio
@pytest.mark.parametrize("dataset", ["application", "assignment"])
@pytest.mark.parametrize("identifier", ["US10123456", "US10123456B2", "US20230012345A1"])
async def test_get_uspto_rejects_patent_numbers_for_application(dataset, identifier):
    """Patent/publication-shaped ids must fail fast locally, not 404 at USPTO."""
    target = "get_application" if dataset == "application" else "get_patent_assignment"
    with patch(f"{_MOD}.{target}", new=AsyncMock()) as m:
        with pytest.raises(ValidationError, match="numeric USPTO application number"):
            await get_uspto(dataset=dataset, identifier=identifier)
    m.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_uspto_rejects_patent_numbers_in_list_before_any_call():
    """One bad id in a batch fails the whole call before any USPTO round-trip."""
    with patch(f"{_MOD}.get_application", new=AsyncMock()) as m:
        with pytest.raises(ValidationError, match="US10123456"):
            await get_uspto(dataset="application", identifier=["16123456", "US10123456"])
    m.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_uspto_accepts_formatted_application_number():
    """Separators in a real application number stay valid."""
    with patch(f"{_MOD}.get_application", new=AsyncMock(return_value="REC")) as m:
        out = await get_uspto(dataset="application", identifier="16/123,456")
    assert out == "REC"
    m.assert_awaited_once_with("16/123,456")


@pytest.mark.asyncio
async def test_get_uspto_publication_still_accepts_patent_numbers():
    """The publication dataset is the documented path for patent numbers — no guard."""
    with patch(f"{_MOD}.get_patent_publication", new=AsyncMock(return_value="PUB")) as m:
        out = await get_uspto(dataset="publication", identifier="US10123456B2")
    assert out == "PUB"
    m.assert_awaited_once_with(publication_number="US10123456B2")


# ──────────────────────────────────────────────────────────────────────
# get_file_history — mode dispatch
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_file_history_list_is_default():
    with patch(f"{_MOD}.list_file_history", new=AsyncMock(return_value="LIST")) as m:
        out = await get_file_history(application_number="16123456")
    assert out == "LIST"
    m.assert_awaited_once_with("16123456")


@pytest.mark.asyncio
async def test_get_file_history_item_routes_with_format():
    with patch(f"{_MOD}.get_file_history_item", new=AsyncMock(return_value="ITEM")) as m:
        out = await get_file_history(
            application_number="16123456",
            mode="item",
            document_identifier="DOC1",
            format="xml",
        )
    assert out == "ITEM"
    m.assert_awaited_once_with("16123456", "DOC1", format="xml")


@pytest.mark.asyncio
async def test_get_file_history_item_defaults_to_pdf():
    with patch(f"{_MOD}.get_file_history_item", new=AsyncMock(return_value="ITEM")) as m:
        out = await get_file_history(
            application_number="16123456",
            mode="item",
            document_identifier="DOC1",
        )
    assert out == "ITEM"
    m.assert_awaited_once_with("16123456", "DOC1", format="pdf")


@pytest.mark.asyncio
async def test_get_file_history_item_requires_document_identifier():
    from mcp_data_core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await get_file_history(application_number="16123456", mode="item")


@pytest.mark.asyncio
async def test_get_file_history_download_forwards_filters():
    with patch(f"{_MOD}.download_file_history", new=AsyncMock(return_value="DL")) as m:
        out = await get_file_history(
            application_number="16123456",
            mode="download",
            document_codes=["CTNF", "NOA"],
            after="2020-01-01",
        )
    assert out == "DL"
    m.assert_awaited_once_with(
        "16123456",
        item_ids=None,
        document_codes=["CTNF", "NOA"],
        after="2020-01-01",
        before=None,
    )


# ──────────────────────────────────────────────────────────────────────
# End-to-end: facade → real per-source function → §5.9 envelope. Proves the
# envelope contract survives the dispatch (not just that routing is wired).
# ──────────────────────────────────────────────────────────────────────


class _FakeSearchResponse:
    def __init__(self, count, patent_bag):
        self._count = count
        self._bag = patent_bag

    def model_dump(self):
        return {"count": self._count, "patentBag": self._bag}


@pytest.mark.asyncio
async def test_search_uspto_applications_preserves_envelope_end_to_end():
    from mcp_data_core.envelope import ListEnvelope, Provenance

    fake = _FakeSearchResponse(
        count=42,
        patent_bag=[
            {
                "applicationNumberText": "16123456",
                "applicationMetaData": {"inventionTitle": "Test"},
            }
        ],
    )
    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as cls:
        client = cls.return_value.__aenter__.return_value
        client.search_applications = AsyncMock(return_value=fake)
        out = await search_uspto(dataset="applications", query="title:test", limit=1)

    assert isinstance(out, ListEnvelope)
    assert isinstance(out.provenance, Provenance)
    assert out.provenance.source_name == "USPTO Open Data Portal"
    assert "/api/v1/patent/applications/search" in out.provenance.source_url
    assert len(out.items) == 1
    assert out.more_available is True  # 42 total, 1 shown
