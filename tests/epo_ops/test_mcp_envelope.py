"""Envelope-shape tests for the migrated EPO OPS MCP tools.

Verifies the §5.9 contract for ``search_epo``, ``get_epo_biblio``,
``get_epo_fulltext``, ``get_epo_family``, ``get_epo_legal_events``,
``get_epo_cql_help``, and ``convert_epo_number``. Also exercises
§5.4 (list-accepting gets), §5.5 (lean default + ``full=True``),
§5.6 (cross-refs in docstrings), and §5.13 (CQL help elevator test).

Mocks ``client_from_env`` at the boundary — we're testing envelope
shape, not the upstream EPO OPS HTTP layer.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from law_tools_core.envelope import (
    ListEnvelope,
    Provenance,
    ResponseEnvelope,
    decode_cursor,
)
from patent_client_agents.epo_ops.models import (
    BiblioRecord,
    BiblioResponse,
    Claim,
    DocumentId,
    FamilyMember,
    FamilyResponse,
    FamilySearchEntry,
    FamilySearchResponse,
    FullTextResponse,
    LegalEvent,
    LegalEventsResponse,
    NumberConversionResponse,
    SearchResponse,
    SearchResult,
)
from patent_client_agents.mcp.tools.international import (
    convert_epo_number,
    get_epo_biblio,
    get_epo_cql_help,
    get_epo_family,
    get_epo_fulltext,
    get_epo_legal_events,
    search_epo,
)


def _patch_client_from_env(mock_client) -> object:
    """Patch ``client_from_env`` so its async-context-manager yields ``mock_client``."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)
    return patch("patent_client_agents.mcp.tools.international.client_from_env", return_value=cm)


# ──────────────────────────────────────────────────────────────────────
# Docstring discipline (§5.6 cross-refs, §5.13 elevator test)
# ──────────────────────────────────────────────────────────────────────


def test_search_epo_docstring_names_all_get_epo_siblings():
    """§5.6 — ``search_epo`` first-sentence sells the tool; lists the full ``get_epo_*`` family."""
    doc = search_epo.__doc__ or ""
    first = doc.strip().split("\n", 1)[0]
    # §5.13 elevator test — passes a non-IP reader.
    assert "worldwide patents" in first.lower()
    assert "EPO Open Patent Services" in first
    # §5.6 — names every sibling that the audit called out as missing.
    for sibling in (
        "get_epo_biblio",
        "get_epo_fulltext",
        "get_epo_family",
        "get_epo_legal_events",
        "get_epo_cql_help",
        "convert_epo_number",
    ):
        assert sibling in doc, f"search_epo docstring missing sibling {sibling}"
    assert "Related tools:" in doc


def test_get_epo_cql_help_docstring_passes_elevator_test():
    """§5.13 — CQL acronym is expanded; first sentence is readable cold."""
    doc = get_epo_cql_help.__doc__ or ""
    first = doc.strip().split("\n", 1)[0]
    assert "search syntax" in first.lower()
    # CQL must be expanded — the original first sentence was opaque outside the EPO audience.
    assert "Common Query Language" in first
    assert "search_epo" in doc
    assert "Related tools:" in doc


@pytest.mark.parametrize(
    "tool",
    [get_epo_biblio, get_epo_fulltext, get_epo_family, get_epo_legal_events],
)
def test_each_get_epo_tool_docstring_lists_siblings(tool):
    """§5.6 — every ``get_epo_*`` docstring names ``search_epo`` and the other gets."""
    doc = tool.__doc__ or ""
    assert "Related tools:" in doc
    assert "search_epo" in doc, f"{tool.__name__} missing search_epo cross-ref"
    # Must reference at least one peer ``get_epo_*`` sibling.
    other_gets = [
        n
        for n in (
            "get_epo_biblio",
            "get_epo_fulltext",
            "get_epo_family",
            "get_epo_legal_events",
        )
        if n != tool.__name__
    ]
    assert any(s in doc for s in other_gets), f"{tool.__name__} missing peer get_epo_* refs"


# ──────────────────────────────────────────────────────────────────────
# search_epo — Shape A (ListEnvelope, lean default, cursor)
# ──────────────────────────────────────────────────────────────────────


def _make_search_response(total: int, ids: list[str]) -> SearchResponse:
    return SearchResponse(
        query="test",
        range_begin=1,
        range_end=len(ids),
        total_results=total,
        results=[
            SearchResult(
                docdb_number=f"EP.{i}.A1",
                country="EP",
                doc_number=i,
                kind="A1",
                publication_date="20240101",
                application_number=f"EP2020{i.zfill(6)}",
                family_id=f"fam-{i}",
            )
            for i in ids
        ],
    )


@pytest.mark.asyncio
async def test_search_epo_returns_list_envelope_with_lean_stubs():
    upstream = _make_search_response(total=42, ids=["1234567", "2345678"])
    mock_client = MagicMock()
    mock_client.search_published = AsyncMock(return_value=upstream)

    with _patch_client_from_env(mock_client):
        result = await search_epo(cql_query="ta=CRISPR", range_begin=1, range_end=2)

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == (
        "European Patent Office Open Patent Services (EPO OPS)"
    )
    assert "/published-data/search" in result.provenance.source_url
    assert "EPO OPS" in result.summary
    assert "2 of 42 hits" in result.summary

    # Lean stubs — flattened publication_number, no nested DocumentId fields.
    assert len(result.items) == 2
    first = result.items[0]
    assert set(first.keys()) == {
        "publication_number",
        "application_number",
        "publication_date",
        "country",
        "kind",
        "family_id",
    }
    assert first["publication_number"] == "EP1234567A1"
    assert first["application_number"] is not None
    assert first["family_id"] == "fam-1234567"
    assert first["publication_date"] == "20240101"

    # more_available + cursor: 42 total, 2 shown starting at range_begin=1.
    assert result.more_available is True
    assert result.next_cursor is not None
    payload = decode_cursor(result.next_cursor)
    assert payload == {"range_begin": 3, "range_end": 4}


@pytest.mark.asyncio
async def test_search_epo_full_returns_upstream_rows():
    upstream = _make_search_response(total=2, ids=["1", "2"])
    mock_client = MagicMock()
    mock_client.search_published = AsyncMock(return_value=upstream)

    with _patch_client_from_env(mock_client):
        result = await search_epo(cql_query="*", full=True)

    # full=True keeps the upstream SearchResult shape (has docdb_number).
    assert "docdb_number" in result.items[0]
    assert result.more_available is False
    assert result.next_cursor is None


@pytest.mark.asyncio
async def test_search_epo_family_grouping_uses_families_path():
    upstream = FamilySearchResponse(
        query="ta=widget",
        total_results=5,
        range_begin=1,
        range_end=1,
        families=[
            FamilySearchEntry(
                family_id="fam-1",
                members=[
                    SearchResult(
                        country="EP",
                        doc_number="1234567",
                        kind="A1",
                        family_id="fam-1",
                    )
                ],
            )
        ],
    )
    mock_client = MagicMock()
    mock_client.search_families = AsyncMock(return_value=upstream)

    with _patch_client_from_env(mock_client):
        result = await search_epo(cql_query="ta=widget", group_by="family", range_end=1)

    assert "/family/search" in result.provenance.source_url
    assert result.items[0]["family_id"] == "fam-1"
    assert result.items[0]["member_count"] == 1
    assert "family" in result.summary
    # 5 total, 1 shown → cursor advances by 1.
    assert result.more_available is True


@pytest.mark.asyncio
async def test_search_epo_decodes_inbound_cursor():
    upstream = _make_search_response(total=20, ids=["a", "b"])
    mock_client = MagicMock()
    mock_client.search_published = AsyncMock(return_value=upstream)

    from law_tools_core.envelope import encode_cursor

    cursor = encode_cursor({"range_begin": 11, "range_end": 12})
    with _patch_client_from_env(mock_client):
        await search_epo(cql_query="*", next_cursor=cursor)

    # Upstream should have been called with the decoded range, not the defaults.
    mock_client.search_published.assert_awaited_once_with(query="*", range_begin=11, range_end=12)


# ──────────────────────────────────────────────────────────────────────
# get_epo_biblio — Shape C (list-accepting, §5.4)
# ──────────────────────────────────────────────────────────────────────


def _make_biblio(number: str, *, title: str = "Test", applicant: str = "Acme") -> BiblioResponse:
    return BiblioResponse(
        documents=[
            BiblioRecord(
                docdb_number=number,
                application_number=f"EP2020{number[-6:].zfill(6)}",
                title=title,
                applicants=[applicant],
                inventors=["Jane Doe"],
            )
        ]
    )


@pytest.mark.asyncio
async def test_get_epo_biblio_single_string_returns_list_envelope():
    upstream = _make_biblio("EP1234567A1", title="Widget Apparatus")
    mock_client = MagicMock()
    mock_client.fetch_biblio = AsyncMock(return_value=upstream)

    with _patch_client_from_env(mock_client):
        result = await get_epo_biblio(patent_number="EP1234567A1")

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    assert result.provenance.source_name.startswith("European Patent Office")
    assert "/published-data/publication/docdb/EP1234567A1/biblio" in result.provenance.source_url
    assert "EP1234567A1" in result.summary
    assert "Widget Apparatus" in result.summary


@pytest.mark.asyncio
async def test_get_epo_biblio_list_preserves_order():
    """§5.4 fan-out must preserve positional order across the input list."""
    responses = {
        "EP1.A1": _make_biblio("EP1.A1", title="First"),
        "EP2.A1": _make_biblio("EP2.A1", title="Second"),
        "EP3.A1": _make_biblio("EP3.A1", title="Third"),
    }
    mock_client = MagicMock()

    async def _fake_fetch(*, number: str):
        return responses[number]

    mock_client.fetch_biblio = AsyncMock(side_effect=_fake_fetch)

    with _patch_client_from_env(mock_client):
        result = await get_epo_biblio(patent_number=["EP1.A1", "EP2.A1", "EP3.A1"])

    titles = [item["documents"][0]["title"] for item in result.items]
    assert titles == ["First", "Second", "Third"]
    assert "/published-data/publication" in result.provenance.source_url
    # Multi-ID provenance points at the collection path, not a specific record.
    assert "biblio" not in result.provenance.source_url


@pytest.mark.asyncio
async def test_get_epo_biblio_empty_input_raises():
    from law_tools_core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await get_epo_biblio(patent_number=[])


# ──────────────────────────────────────────────────────────────────────
# get_epo_fulltext — Shape C
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_epo_fulltext_list_preserves_order():
    responses = {
        "EP1.A1": FullTextResponse(
            docdb_number="EP1.A1", section="claims", claims=[Claim(number=1, text="A widget.")]
        ),
        "EP2.A1": FullTextResponse(
            docdb_number="EP2.A1",
            section="claims",
            claims=[Claim(number=1, text="X."), Claim(number=2, text="Y.")],
        ),
    }
    mock_client = MagicMock()

    async def _fake_fetch(*, number: str):
        return responses[number]

    mock_client.fetch_fulltext = AsyncMock(side_effect=_fake_fetch)

    with _patch_client_from_env(mock_client):
        result = await get_epo_fulltext(patent_number=["EP1.A1", "EP2.A1"])

    assert [item["docdb_number"] for item in result.items] == ["EP1.A1", "EP2.A1"]
    assert "fulltext" in result.summary.lower()


# ──────────────────────────────────────────────────────────────────────
# get_epo_family — Shape C
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_epo_family_single_summarizes_member_count():
    upstream = FamilyResponse(
        publication_number="EP1234567A1",
        num_records=3,
        members=[
            FamilyMember(family_id="fam-1", publication_number=f"EP{i}.A1") for i in (1, 2, 3)
        ],
    )
    mock_client = MagicMock()
    mock_client.fetch_family = AsyncMock(return_value=upstream)

    with _patch_client_from_env(mock_client):
        result = await get_epo_family(patent_number="EP1234567A1")

    assert isinstance(result, ListEnvelope)
    assert "INPADOC family" in result.summary
    assert "3 member" in result.summary
    assert "/family/publication/docdb/EP1234567A1" in result.provenance.source_url


# ──────────────────────────────────────────────────────────────────────
# get_epo_legal_events — Shape C
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_epo_legal_events_summary_counts_events():
    upstream = LegalEventsResponse(
        publication_reference=DocumentId(country="EP", number="1234567", kind="A1"),
        events=[
            LegalEvent(event_code="PG25", event_date="20230101"),
            LegalEvent(event_code="PG26", event_date="20240101"),
        ],
    )
    mock_client = MagicMock()
    mock_client.fetch_legal_events = AsyncMock(return_value=upstream)

    with _patch_client_from_env(mock_client):
        result = await get_epo_legal_events(patent_number="EP1234567A1")

    assert isinstance(result, ListEnvelope)
    assert "2 legal event" in result.summary
    assert "/legal/publication/docdb/EP1234567A1" in result.provenance.source_url


# ──────────────────────────────────────────────────────────────────────
# get_epo_cql_help — Shape B (single static record)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_epo_cql_help_returns_response_envelope():
    result = await get_epo_cql_help()
    assert isinstance(result, ResponseEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name.startswith("European Patent Office")
    assert "fields" in result.details
    assert "operators" in result.details
    assert "examples" in result.details
    # First sentence already validated in docstring tests above; double-check
    # the user-facing summary leads with the practical promise.
    assert "CQL" in result.summary or "syntax" in result.summary.lower()


# ──────────────────────────────────────────────────────────────────────
# convert_epo_number — Shape B (single-record conversion)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_convert_epo_number_returns_response_envelope():
    upstream = NumberConversionResponse(
        input_document=DocumentId(country="EP", number="1234567", kind="A1", format="original"),
        output_document=DocumentId(country="EP", number="1234567", kind="A1", format="docdb"),
    )
    mock_client = MagicMock()
    mock_client.convert_number = AsyncMock(return_value=upstream)

    with _patch_client_from_env(mock_client):
        result = await convert_epo_number(
            number="EP1234567A1", input_format="original", output_format="docdb"
        )

    assert isinstance(result, ResponseEnvelope)
    assert result.provenance.source_name.startswith("European Patent Office")
    assert "/number-service/publication/original/EP1234567A1/docdb" in result.provenance.source_url
    assert "EP1234567A1" in result.summary
    assert result.details["output_document"]["country"] == "EP"
