"""Envelope-shape tests for the migrated CanLII MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.4 (list-accepting
fetches; no batch tools), §5.5 (lean default + full opt-in), §5.6
(cross-references), and §5.8 (browse_* → search_* renames).

Mocks ``CanLIIClient`` at the boundary — we're testing envelope shape,
not the upstream REST API.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel, Field

from law_tools_core.envelope import ListEnvelope, Provenance
from law_tools_core.exceptions import ValidationError
from patent_client_agents.mcp.tools.canlii import (
    get_canlii_case,
    get_canlii_cited_cases,
    get_canlii_cited_legislations,
    get_canlii_citing_cases,
    get_canlii_legislation,
    list_canlii_case_databases,
    list_canlii_legislation_databases,
    search_canlii_cases,
    search_canlii_legislation,
)

# ──────────────────────────────────────────────────────────────────────
# Fakes — minimal Pydantic models that mimic CanLIIClient return types
# ──────────────────────────────────────────────────────────────────────


class _FakeCaseDatabase(BaseModel):
    database_id: str = Field(alias="databaseId")
    jurisdiction: str
    name: str

    model_config = {"populate_by_name": True}


class _FakeCaseDatabaseList(BaseModel):
    case_databases: list[_FakeCaseDatabase] = Field(alias="caseDatabases")

    model_config = {"populate_by_name": True}


class _FakeLegislationDatabase(BaseModel):
    database_id: str = Field(alias="databaseId")
    type: str
    jurisdiction: str
    name: str

    model_config = {"populate_by_name": True}


class _FakeLegislationDatabaseList(BaseModel):
    legislation_databases: list[_FakeLegislationDatabase] = Field(alias="legislationDatabases")

    model_config = {"populate_by_name": True}


class _FakeCaseId(BaseModel):
    en: str | None = None
    fr: str | None = None


class _FakeCaseRef(BaseModel):
    database_id: str
    case_id: _FakeCaseId
    title: str
    citation: str


class _FakeCaseList(BaseModel):
    cases: list[_FakeCaseRef]


class _FakeCaseMetadata(BaseModel):
    database_id: str
    case_id: str
    url: str
    title: str
    citation: str
    language: str = "en"
    decision_date: date | None = None
    keywords: str | None = None


class _FakeCitedCases(BaseModel):
    cited_cases: list[_FakeCaseRef]


class _FakeCitingCases(BaseModel):
    citing_cases: list[_FakeCaseRef]


class _FakeCitedLegislationRef(BaseModel):
    database_id: str
    legislation_id: str
    title: str
    citation: str | None = None
    type: str | None = None


class _FakeCitedLegislations(BaseModel):
    cited_legislations: list[_FakeCitedLegislationRef]


class _FakeLegislationRef(BaseModel):
    database_id: str
    legislation_id: str
    title: str
    citation: str
    type: str = "STATUTE"


class _FakeLegislationList(BaseModel):
    legislations: list[_FakeLegislationRef]


class _FakeLegislationMetadata(BaseModel):
    legislation_id: str
    url: str
    title: str
    citation: str
    type: str = "STATUTE"
    language: str = "en"
    start_date: date | None = None
    end_date: date | None = None
    repealed: str | None = None
    content: list[dict] = Field(default_factory=list)


def _make_case_ref(case_id: str, title: str = "Acme v. Bob", db: str = "fct") -> _FakeCaseRef:
    return _FakeCaseRef(
        database_id=db,
        case_id=_FakeCaseId(en=case_id),
        title=title,
        citation=f"2024 FC {case_id[-3:]} (CanLII)",
    )


def _make_case_metadata(case_id: str, title: str = "Acme v. Bob") -> _FakeCaseMetadata:
    return _FakeCaseMetadata(
        database_id="csc-scc",
        case_id=case_id,
        url=f"http://canlii.ca/t/{case_id}",
        title=title,
        citation=f"2024 SCC {case_id[-3:]} (CanLII)",
        decision_date=date(2024, 3, 7),
        keywords="patent infringement",
    )


def _make_legislation_ref(lid: str, title: str = "Patent Act") -> _FakeLegislationRef:
    return _FakeLegislationRef(
        database_id="cas",
        legislation_id=lid,
        title=title,
        citation=f"R.S.C., 1985, c. {lid[-3:].upper()}",
    )


def _make_legislation_metadata(
    lid: str, title: str = "Patent Act", repealed: str | None = None
) -> _FakeLegislationMetadata:
    return _FakeLegislationMetadata(
        legislation_id=lid,
        url=f"http://canlii.ca/t/{lid}",
        title=title,
        citation=f"R.S.C., 1985, c. {lid[-3:].upper()}",
        repealed=repealed,
        start_date=date(1985, 1, 1),
    )


# ──────────────────────────────────────────────────────────────────────
# §5.8 rename — browse_canlii_* deleted; search_canlii_* exposed
# ──────────────────────────────────────────────────────────────────────


def test_browse_canlii_names_were_renamed_to_search():
    """The §5.8 violations should no longer be importable."""
    from patent_client_agents.mcp.tools import canlii as canlii_module

    assert not hasattr(canlii_module, "browse_canlii_cases")
    assert not hasattr(canlii_module, "browse_canlii_legislation")
    assert hasattr(canlii_module, "search_canlii_cases")
    assert hasattr(canlii_module, "search_canlii_legislation")


def test_no_batch_tool_present():
    """§5.4 forbids batch_* tools — list-accepting get_* replaces them."""
    from patent_client_agents.mcp.tools import canlii as canlii_module

    assert not hasattr(canlii_module, "batch_canlii_case")
    assert not hasattr(canlii_module, "batch_get_canlii_case")


# ──────────────────────────────────────────────────────────────────────
# list_canlii_case_databases / list_canlii_legislation_databases — §5.9
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_case_databases_returns_list_envelope():
    response = _FakeCaseDatabaseList(
        case_databases=[
            _FakeCaseDatabase(databaseId="fct", jurisdiction="ca", name="Federal Court"),
            _FakeCaseDatabase(databaseId="csc-scc", jurisdiction="ca", name="Supreme Court"),
        ]
    )
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.list_case_databases = AsyncMock(return_value=response)

        result = await list_canlii_case_databases()

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "CanLII (Canadian Legal Information Institute)"
    assert "/v1/caseBrowse/en/" in result.provenance.source_url
    assert len(result.items) == 2
    assert "2 courts" in result.summary or "2 " in result.summary


@pytest.mark.asyncio
async def test_list_legislation_databases_returns_list_envelope():
    response = _FakeLegislationDatabaseList(
        legislation_databases=[
            _FakeLegislationDatabase(
                databaseId="cas", type="STATUTE", jurisdiction="ca", name="Federal Statutes"
            ),
        ]
    )
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.list_legislation_databases = AsyncMock(return_value=response)

        result = await list_canlii_legislation_databases()

    assert isinstance(result, ListEnvelope)
    assert "/v1/legislationBrowse/en/" in result.provenance.source_url
    assert len(result.items) == 1


# ──────────────────────────────────────────────────────────────────────
# search_canlii_cases — §5.9, §5.5 lean default
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_canlii_cases_returns_lean_list_envelope_by_default():
    response = _FakeCaseList(
        cases=[
            _make_case_ref("2024fc100", title="Patent Co. v. Crown"),
            _make_case_ref("2024fc101", title="Trademark Co. v. Acme"),
        ]
    )
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.browse_cases = AsyncMock(return_value=response)

        result = await search_canlii_cases(database_id="fct")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "CanLII (Canadian Legal Information Institute)"
    assert "/v1/caseBrowse/en/fct/" in result.provenance.source_url
    assert len(result.items) == 2
    # Lean projection: exactly these keys.
    assert set(result.items[0].keys()) == {"case_id", "citation", "title", "database_id"}
    assert result.items[0]["case_id"] == "2024fc100"
    assert "fct" in result.summary


@pytest.mark.asyncio
async def test_search_canlii_cases_full_true_returns_upstream_shape():
    response = _FakeCaseList(cases=[_make_case_ref("2024fc100")])
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.browse_cases = AsyncMock(return_value=response)

        result = await search_canlii_cases(database_id="fct", full=True)

    # Full mode preserves the upstream nested case_id object.
    assert isinstance(result.items[0]["case_id"], dict)
    assert result.items[0]["case_id"]["en"] == "2024fc100"


@pytest.mark.asyncio
async def test_search_canlii_cases_more_available_when_page_full():
    # When the upstream returns exactly result_count rows, more_available=True.
    response = _FakeCaseList(cases=[_make_case_ref(f"2024fc{i:03d}") for i in range(3)])
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.browse_cases = AsyncMock(return_value=response)

        result = await search_canlii_cases(database_id="fct", result_count=3)

    assert result.more_available is True


# ──────────────────────────────────────────────────────────────────────
# get_canlii_case — §5.4 list-accepting
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_canlii_case_single_returns_list_envelope():
    record = _make_case_metadata("2008scc9", title="Dunsmuir v. New Brunswick")
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_case = AsyncMock(return_value=record)

        result = await get_canlii_case(database_id="csc-scc", case_id="2008scc9")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "CanLII (Canadian Legal Information Institute)"
    assert "/v1/caseBrowse/en/csc-scc/2008scc9/" in result.provenance.source_url
    assert len(result.items) == 1
    assert result.items[0]["case_id"] == "2008scc9"
    assert "2008scc9" in result.summary
    assert "Dunsmuir" in result.summary


@pytest.mark.asyncio
async def test_get_canlii_case_list_preserves_order():
    ids = ["2008scc9", "2020fca100", "2024fc77"]
    records = [_make_case_metadata(cid, title=f"Case {cid}") for cid in ids]
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_case = AsyncMock(side_effect=records)

        result = await get_canlii_case(database_id="csc-scc", case_id=ids)

    assert isinstance(result, ListEnvelope)
    assert [r["case_id"] for r in result.items] == ids
    # Multi-record summary lists the IDs.
    assert "Fetched 3" in result.summary
    for cid in ids:
        assert cid in result.summary
    # Multi-record path is the database root, not a specific case.
    assert result.provenance.source_url.endswith("/v1/caseBrowse/en/csc-scc/")


@pytest.mark.asyncio
async def test_get_canlii_case_empty_list_raises():
    with pytest.raises(ValidationError, match="at least one case_id"):
        await get_canlii_case(database_id="csc-scc", case_id=[])


# ──────────────────────────────────────────────────────────────────────
# Citator tools — §5.9, §5.6 cross-refs
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_canlii_cited_cases_returns_list_envelope():
    response = _FakeCitedCases(cited_cases=[_make_case_ref("2020fc1"), _make_case_ref("2021fc2")])
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_cited_cases = AsyncMock(return_value=response)

        result = await get_canlii_cited_cases(database_id="csc-scc", case_id="2008scc9")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "CanLII (Canadian Legal Information Institute)"
    assert "/v1/caseCitator/en/csc-scc/2008scc9/citedCases" in result.provenance.source_url
    assert len(result.items) == 2
    assert set(result.items[0].keys()) == {"case_id", "citation", "title", "database_id"}
    assert "2008scc9" in result.summary
    assert "cites 2 case" in result.summary


@pytest.mark.asyncio
async def test_get_canlii_citing_cases_returns_list_envelope():
    response = _FakeCitingCases(citing_cases=[_make_case_ref("2024fc1")])
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_citing_cases = AsyncMock(return_value=response)

        result = await get_canlii_citing_cases(database_id="csc-scc", case_id="2008scc9")

    assert isinstance(result, ListEnvelope)
    assert "/citingCases" in result.provenance.source_url
    assert len(result.items) == 1
    assert "cite case `2008scc9`" in result.summary


@pytest.mark.asyncio
async def test_get_canlii_cited_legislations_returns_list_envelope():
    response = _FakeCitedLegislations(
        cited_legislations=[
            _FakeCitedLegislationRef(
                database_id="cas",
                legislation_id="rsc-1985-c-p-4",
                title="Patent Act",
                citation="R.S.C., 1985, c. P-4",
                type="STATUTE",
            ),
        ]
    )
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_cited_legislations = AsyncMock(return_value=response)

        result = await get_canlii_cited_legislations(database_id="csc-scc", case_id="2008scc9")

    assert isinstance(result, ListEnvelope)
    assert "/citedLegislations" in result.provenance.source_url
    assert len(result.items) == 1
    assert result.items[0]["legislation_id"] == "rsc-1985-c-p-4"
    # Lean projection on legislation references.
    assert set(result.items[0].keys()) == {
        "legislation_id",
        "title",
        "citation",
        "type",
        "database_id",
    }


# ──────────────────────────────────────────────────────────────────────
# search_canlii_legislation — §5.9, §5.5
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_canlii_legislation_returns_lean_list_envelope_by_default():
    response = _FakeLegislationList(
        legislations=[
            _make_legislation_ref("rsc-1985-c-p-4", title="Patent Act"),
            _make_legislation_ref("rsc-1985-c-t-13", title="Trade-marks Act"),
        ]
    )
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.browse_legislation = AsyncMock(return_value=response)

        result = await search_canlii_legislation(database_id="cas")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "CanLII (Canadian Legal Information Institute)"
    assert "/v1/legislationBrowse/en/cas/" in result.provenance.source_url
    assert len(result.items) == 2
    assert set(result.items[0].keys()) == {
        "legislation_id",
        "title",
        "citation",
        "type",
        "database_id",
    }
    assert result.items[0]["legislation_id"] == "rsc-1985-c-p-4"


# ──────────────────────────────────────────────────────────────────────
# get_canlii_legislation — §5.4 list-accepting
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_canlii_legislation_single_returns_list_envelope():
    record = _make_legislation_metadata("rsc-1985-c-p-4", title="Patent Act")
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_legislation = AsyncMock(return_value=record)

        result = await get_canlii_legislation(database_id="cas", legislation_id="rsc-1985-c-p-4")

    assert isinstance(result, ListEnvelope)
    assert "/v1/legislationBrowse/en/cas/rsc-1985-c-p-4/" in result.provenance.source_url
    assert len(result.items) == 1
    assert result.items[0]["legislation_id"] == "rsc-1985-c-p-4"
    assert "rsc-1985-c-p-4" in result.summary
    assert "Patent Act" in result.summary


@pytest.mark.asyncio
async def test_get_canlii_legislation_list_preserves_order():
    ids = ["rsc-1985-c-p-4", "rsc-1985-c-t-13", "rsc-1985-c-c-42"]
    records = [_make_legislation_metadata(lid, title=f"Act {lid}") for lid in ids]
    with patch("patent_client_agents.mcp.tools.canlii.CanLIIClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_legislation = AsyncMock(side_effect=records)

        result = await get_canlii_legislation(database_id="cas", legislation_id=ids)

    assert isinstance(result, ListEnvelope)
    assert [r["legislation_id"] for r in result.items] == ids
    assert "Fetched 3" in result.summary
    for lid in ids:
        assert lid in result.summary
    assert result.provenance.source_url.endswith("/v1/legislationBrowse/en/cas/")


@pytest.mark.asyncio
async def test_get_canlii_legislation_empty_list_raises():
    with pytest.raises(ValidationError, match="at least one legislation_id"):
        await get_canlii_legislation(database_id="cas", legislation_id=[])
