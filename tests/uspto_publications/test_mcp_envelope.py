"""Envelope-shape tests for the migrated USPTO Publications (PPUBS) MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.4 (list-accepting
fetches; no batch tools), and §5.5 (lean default + full opt-in).

Mocks ``PublicSearchClient`` at the boundary — we're testing envelope
shape, not the PPUBS upstream.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from mcp_data_core.envelope import ListEnvelope, Provenance
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.mcp.tools.publications import (
    get_patent_publication,
    search_patent_publications,
)

# ──────────────────────────────────────────────────────────────────────
# Fakes — minimal Pydantic models that mimic PublicSearchClient returns
# ──────────────────────────────────────────────────────────────────────


class _FakeBiblio(BaseModel):
    publication_number: str
    patent_title: str = "Test Publication"
    type: str = "US-PGPUB"
    publication_date: str = "2023-01-15"
    app_filing_date: str = "2021-06-01"
    applicant_names: list[str] = []
    assignee_names: list[str] = []
    main_classification_code: str = "G06F"


class _FakeBiblioPage(BaseModel):
    num_found: int
    per_page: int = 25
    page: int = 0
    num_families: int | None = None
    num_documents: int | None = None
    docs: list[_FakeBiblio] = []


class _FakeDocument(BaseModel):
    guid: str
    publication_number: str
    patent_title: str = "Test Publication"
    type: str = "US-PGPUB"
    publication_date: str = "2023-01-15"
    applicants: list[dict] = []


def _make_biblio(pub_no: str, *, title: str = "Test", applicant: str = "Acme Corp") -> _FakeBiblio:
    return _FakeBiblio(
        publication_number=pub_no,
        patent_title=title,
        applicant_names=[applicant],
        assignee_names=[applicant],
    )


def _make_document(pub_no: str, *, title: str = "Test") -> _FakeDocument:
    return _FakeDocument(
        guid=f"guid-{pub_no}",
        publication_number=pub_no,
        patent_title=title,
        applicants=[{"name": "Acme Corp", "country": "US"}],
    )


# ──────────────────────────────────────────────────────────────────────
# search_patent_publications — §5.9, §5.5
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_returns_lean_list_envelope_by_default():
    page = _FakeBiblioPage(
        num_found=2,
        num_families=42,
        num_documents=97,
        docs=[_make_biblio("US20230012345A1", title="First"), _make_biblio("US20230099999A1")],
    )
    with patch("patent_client_agents.mcp.tools.publications.PublicSearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search_biblio = AsyncMock(return_value=page)

        result = await search_patent_publications(query="machine learning", limit=2)

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "USPTO Patent Public Search (PPUBS)"
    assert "ppubs.uspto.gov" in result.provenance.source_url
    assert "searchWithBeFamily" in result.provenance.source_url
    assert len(result.items) == 2
    assert result.more_available is True  # 42 families, 2 shown
    assert "machine learning" in result.summary
    assert "2 documents in 2 of 42 families" in result.summary
    assert "97 documents in all" in result.summary
    # Lean projection per §5.5 — fixed scalar field set, not the raw biblio.
    assert set(result.items[0].keys()) == {
        "publication_number",
        "patent_title",
        "type",
        "publication_date",
        "app_filing_date",
        "applicant",
        "assignee",
        "main_classification_code",
    }
    assert result.items[0]["publication_number"] == "US20230012345A1"
    assert result.items[0]["applicant"] == "Acme Corp"


@pytest.mark.asyncio
async def test_search_full_true_returns_upstream_shape():
    page = _FakeBiblioPage(num_found=1, num_families=1, docs=[_make_biblio("US20230012345A1")])
    with patch("patent_client_agents.mcp.tools.publications.PublicSearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search_biblio = AsyncMock(return_value=page)

        result = await search_patent_publications(query="*", full=True)

    # Full payloads keep the upstream key names (snake_case lists, etc.).
    assert "applicant_names" in result.items[0]
    assert "main_classification_code" in result.items[0]
    assert result.items[0]["applicant_names"] == ["Acme Corp"]


@pytest.mark.asyncio
async def test_search_more_available_false_when_exhausted():
    page = _FakeBiblioPage(
        num_found=2,
        num_families=2,
        docs=[_make_biblio("US20230012345A1"), _make_biblio("US20230099999A1")],
    )
    with patch("patent_client_agents.mcp.tools.publications.PublicSearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search_biblio = AsyncMock(return_value=page)
        result = await search_patent_publications(query="*", limit=25)
    assert result.more_available is False
    assert result.next_cursor is None


@pytest.mark.asyncio
async def test_search_default_uses_reliable_ppubs_page_size():
    page = _FakeBiblioPage(num_found=0, num_families=0, per_page=20, docs=[])
    with patch("patent_client_agents.mcp.tools.publications.PublicSearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search_biblio = AsyncMock(return_value=page)

        await search_patent_publications(query="neural.CLM.")

    mock_client.search_biblio.assert_awaited_once_with(query="neural.CLM.", start=0, limit=20)


@pytest.mark.asyncio
async def test_search_continues_by_family_offset():
    """Pages advance by families, and a family can carry several documents (#91)."""
    from mcp_data_core.envelope import decode_cursor

    first_page = _FakeBiblioPage(
        num_found=2,
        num_families=3,
        num_documents=5,
        docs=[_make_biblio(f"US2023000000{i}A1") for i in range(4)],
    )
    last_page = _FakeBiblioPage(
        num_found=1, num_families=3, num_documents=5, docs=[_make_biblio("US20230000009A1")]
    )
    with patch("patent_client_agents.mcp.tools.publications.PublicSearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search_biblio = AsyncMock(side_effect=[first_page, last_page])
        first = await search_patent_publications(query="q", limit=2)
        last = await search_patent_publications(query="q", next_cursor=first.next_cursor)

    assert len(first.items) == 4
    assert first.more_available is True
    assert decode_cursor(first.next_cursor) == {"offset": 2, "limit": 2}
    assert "4 documents in 2 of 3 families at family offset 0" in first.summary
    assert last.more_available is False
    assert last.next_cursor is None
    mock_client.search_biblio.assert_awaited_with(query="q", start=2, limit=2)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "num_found,num_families,offset",
    [(2, None, 0), (5, 3, 0), (0, 3, 1)],
)
async def test_search_rejects_unknown_or_inconsistent_family_counts(
    num_found, num_families, offset
):
    from mcp_data_core.exceptions import ParseError

    page = _FakeBiblioPage(num_found=num_found, num_families=num_families, docs=[])
    with patch("patent_client_agents.mcp.tools.publications.PublicSearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search_biblio = AsyncMock(return_value=page)
        with pytest.raises(ParseError):
            await search_patent_publications(query="q", offset=offset)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [{"offset": -1}, {"limit": 0}, {"offset": True}, {"next_cursor": "garbage"}],
)
async def test_search_invalid_pagination_fails_before_request(kwargs):
    from mcp_data_core.exceptions import ValidationError

    with patch("patent_client_agents.mcp.tools.publications.PublicSearchClient") as mock_cls:
        with pytest.raises(ValidationError):
            await search_patent_publications(query="q", **kwargs)
    mock_cls.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
# get_patent_publication — §5.4 list-accepting
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_single_string_returns_list_envelope():
    doc = _make_document("US20230012345A1", title="Blockchain authentication")
    with patch("patent_client_agents.mcp.tools.publications.PublicSearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.resolve_document_by_publication_number = AsyncMock(return_value=doc)

        result = await get_patent_publication(publication_number="US20230012345A1")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "USPTO Patent Public Search (PPUBS)"
    assert len(result.items) == 1
    assert "US20230012345A1" in result.summary
    assert "Blockchain authentication" in result.summary
    assert "US20230012345A1" in result.provenance.source_url


@pytest.mark.asyncio
async def test_get_patent_publication_accepts_patent_number_alias():
    doc = _make_document("US10123456B2", title="Issued patent")
    with patch("patent_client_agents.mcp.tools.publications.PublicSearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.resolve_document_by_publication_number = AsyncMock(return_value=doc)

        result = await get_patent_publication(patent_number="US10123456B2")

    mock_client.resolve_document_by_publication_number.assert_awaited_once_with("US10123456B2")
    assert result.items[0]["publication_number"] == "US10123456B2"


@pytest.mark.asyncio
async def test_get_list_returns_list_envelope_and_preserves_order():
    """Numbers in request order should match results in response order (§5.4)."""
    pubs = ["US20230012345A1", "US20230099999A1", "US10123456B2"]
    docs = [_make_document(p) for p in pubs]
    with patch("patent_client_agents.mcp.tools.publications.PublicSearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.resolve_document_by_publication_number = AsyncMock(side_effect=docs)

        result = await get_patent_publication(publication_number=pubs)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 3
    returned = [item["publication_number"] for item in result.items]
    assert returned == pubs
    assert "3 US patent publications" in result.summary
    # Multi-fetch points provenance at the collection URL, not a single record.
    assert result.provenance.source_url.endswith("/api/patents/highlight")


@pytest.mark.asyncio
async def test_get_list_fans_out_to_one_call_per_input():
    pubs = ["US20230012345A1", "US20230099999A1", "US10123456B2"]
    docs = [_make_document(p) for p in pubs]
    with patch("patent_client_agents.mcp.tools.publications.PublicSearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        resolver = AsyncMock(side_effect=docs)
        mock_client.resolve_document_by_publication_number = resolver

        await get_patent_publication(publication_number=pubs)

    # One upstream call per input identifier — proves the fan-out ran.
    assert resolver.await_count == 3
    called_with = [call.args[0] for call in resolver.await_args_list]
    assert called_with == pubs


@pytest.mark.asyncio
async def test_get_fan_out_runs_concurrently():
    """Concurrent fan-out should batch the calls under the semaphore (5).

    The mock awaits a short event before completing; if the fan-out
    were sequential, the 3 calls would each wait their full delay in
    series. Concurrent execution lets them resolve together.
    """
    pubs = ["US1", "US2", "US3"]
    barrier = asyncio.Event()
    seen_concurrent = 0

    async def _slow_resolver(pub_no: str) -> _FakeDocument:
        nonlocal seen_concurrent
        seen_concurrent += 1
        # Wait until we observe all three in-flight before releasing.
        if seen_concurrent >= 3:
            barrier.set()
        await barrier.wait()
        return _make_document(pub_no)

    with patch("patent_client_agents.mcp.tools.publications.PublicSearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.resolve_document_by_publication_number = AsyncMock(side_effect=_slow_resolver)

        result = await asyncio.wait_for(
            get_patent_publication(publication_number=pubs), timeout=2.0
        )

    assert len(result.items) == 3
    assert seen_concurrent == 3


@pytest.mark.asyncio
async def test_get_empty_list_raises():
    with pytest.raises(ValidationError, match="at least one publication number"):
        await get_patent_publication(publication_number=[])


@pytest.mark.asyncio
async def test_get_summary_contains_identifying_text():
    doc = _make_document("US10123456B2", title="Quantum cryptography")
    with patch("patent_client_agents.mcp.tools.publications.PublicSearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.resolve_document_by_publication_number = AsyncMock(return_value=doc)

        result = await get_patent_publication(publication_number="US10123456B2")

    assert "US10123456B2" in result.summary
    assert "Quantum cryptography" in result.summary
    assert "Acme Corp" in result.summary
