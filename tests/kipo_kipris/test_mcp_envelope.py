"""Envelope-shape tests for the KIPO KIPRIS Plus MCP tools.

Verifies the §5.9 envelope contract (Provenance ``source_name`` +
``source_url`` populated), §5.5 lean projection (drops Korean abstract
``astrt_cont``; ``full=True`` opt-in), and §5.4 list-accept on the
fetch tools. Mocks the underlying transport — no live KIPRIS traffic.

Mocks the ``api`` and ``KiprisClient`` symbols at the MCP-tool module
boundary so the upstream API is never touched. Uses plain ``_FakeRow``
classes (NOT ``BaseModel(extra='allow')``) per the chunk-4 runbook
``ty`` pitfall.
"""

from __future__ import annotations

import importlib
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, Provenance
from law_tools_core.exceptions import ValidationError

# ──────────────────────────────────────────────────────────────────────
# Plain "fake" row models — they only need to expose ``model_dump`` so
# the MCP layer can serialize them. We deliberately avoid pydantic here
# because pydantic v2 with ``extra='allow'`` propagates unknown keyword
# arguments through model_dump in ways ty flags as ``unknown-argument``.
# A plain class side-steps that pitfall.
# ──────────────────────────────────────────────────────────────────────


class _FakeRow:
    """Fake upstream response: serializes to its stored payload dict."""

    def __init__(self, **payload: Any) -> None:
        self._payload = payload

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        return dict(self._payload)


def _patent_payload(appl_no: str = "1020230012345", **overrides: Any) -> dict[str, Any]:
    base = {
        "applicationNumber": appl_no,
        "applicationDate": "2023-01-05",
        "publicationNumber": "1024567890000",
        "publicationDate": "2024-03-10",
        "registerNumber": "1024567890000",
        "registerStatus": "등록",
        "inventionTitle": "리튬 이온 배터리 모듈",
        "inventionTitleEnglish": "Lithium Ion Battery Module",
        "astrtCont": "본 발명은 ...",  # Korean abstract — dropped by lean
        "applicantName": "삼성전자",
        "inventorName": "홍길동",
        "ipcNumber": "H01M 10/0525",
    }
    base.update(overrides)
    return base


def _trademark_payload(appl_no: str = "4020230123456", **overrides: Any) -> dict[str, Any]:
    base = {
        "applicationNumber": appl_no,
        "applicationDate": "2023-03-20",
        "registrationNumber": "4000123456",
        "registrationDate": "2024-04-01",
        "title": "GALAXY",
        "classificationCode": "09;42",
        "viennaCode": "26.04.01",
        "applicantName": "삼성전자",
        "bigDrawing": "https://example.test/big.gif",
    }
    base.update(overrides)
    return base


def _design_payload(appl_no: str = "3020230012345", **overrides: Any) -> dict[str, Any]:
    base = {
        "applicationNumber": appl_no,
        "applicationDate": "2023-02-10",
        "registrationNumber": "3000987654",
        "registrationDate": "2024-01-20",
        "registerStatus": "등록",
        "articleName": "휴대용 전화기",
        "drawing": "https://example.test/drawing.jpg",
        "locCode": "14-03",
        "applicantName": "삼성전자",
        "inventorName": "박디자인",
    }
    base.update(overrides)
    return base


# ──────────────────────────────────────────────────────────────────────
# Fixture: import the env-gated MCP module fresh under set env.
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def kipo_mcp(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Import the kipo_kipris MCP module under a set env so tools register.

    Reloads against a fresh FastMCP so the ``@conditional_tool``
    decorators see an empty surface and the tool functions are
    re-bound on the module each test.
    """
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "test-key")

    import patent_client_agents.mcp.tools.kipo_kipris as kipo

    kipo.kipo_kipris_mcp = FastMCP("KIPO — KIPRIS Plus")
    importlib.reload(kipo)
    return kipo


@pytest.fixture
def mock_api(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Patch the module-level ``api`` helpers (imported by ``__import__``).

    The KIPO MCP module re-imports ``kipo_kipris.api`` via
    ``__import__("...api", fromlist=...)`` inside each search tool, so
    we patch the api module itself (not an attribute on the MCP tool
    module).
    """
    import patent_client_agents.kipo_kipris.api as api_mod

    return api_mod


@pytest.fixture
def mock_client(monkeypatch: pytest.MonkeyPatch, kipo_mcp: Any) -> AsyncMock:
    """Patch ``KiprisClient`` (used by the fetch tools) with async-context AsyncMock."""
    inner = AsyncMock()

    class _MockCtx:
        async def __aenter__(self) -> AsyncMock:
            return inner

        async def __aexit__(self, *exc: Any) -> None:
            return None

    def _factory(*args: Any, **kwargs: Any) -> _MockCtx:
        return _MockCtx()

    monkeypatch.setattr(kipo_mcp, "KiprisClient", _factory)
    return inner


# ──────────────────────────────────────────────────────────────────────
# search_kipo_patents — §5.5 lean projection, §5.9 envelope
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_kipo_patents_lean_drops_abstract(
    kipo_mcp: Any, mock_api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        mock_api,
        "search_kipo_patents",
        AsyncMock(
            return_value=(
                [_patent_payload("1020230012345"), _patent_payload("1020230098765")],
                {"totalCount": 2, "pageNo": 1, "numOfRows": 10},
            )
        ),
    )

    result = await kipo_mcp.search_kipo_patents(query="배터리")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert "KIPO" in result.provenance.source_name
    assert "Per-user API key" in result.provenance.source_name  # ToS §11 BYOK note
    assert "/patUtliInfoSearchService/getWordSearch" in result.provenance.source_url
    assert len(result.items) == 2
    # Lean projection drops Korean abstract.
    assert "astrtCont" not in result.items[0]
    assert "astrt_cont" not in result.items[0]
    # Keep useful fields.
    assert result.items[0]["application_number"] == "1020230012345"
    assert result.items[0]["invention_title_english"] == "Lithium Ion Battery Module"
    assert "배터리" in result.summary
    assert result.more_available is False  # 2 of 2 returned


@pytest.mark.asyncio
async def test_search_kipo_patents_full_true_keeps_abstract(
    kipo_mcp: Any, mock_api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        mock_api,
        "search_kipo_patents",
        AsyncMock(return_value=([_patent_payload("1020230012345")], {})),
    )
    result = await kipo_mcp.search_kipo_patents(query="x", full=True)
    # Full keeps the camelCase astrtCont alias.
    assert "astrtCont" in result.items[0]
    assert result.items[0]["astrtCont"].startswith("본 발명은")


@pytest.mark.asyncio
async def test_search_kipo_patents_right_type_filters(
    kipo_mcp: Any, mock_api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[dict[str, Any]] = []

    async def _capture(**kwargs: Any) -> tuple[list[dict], dict]:
        captured.append(kwargs)
        return [], {}

    monkeypatch.setattr(mock_api, "search_kipo_patents", _capture)

    await kipo_mcp.search_kipo_patents(query="x", right_type="patent")
    assert captured[0]["patent"] is True
    assert captured[0]["utility"] is False

    await kipo_mcp.search_kipo_patents(query="x", right_type="utility_model")
    assert captured[1]["patent"] is False
    assert captured[1]["utility"] is True

    await kipo_mcp.search_kipo_patents(query="x", right_type="both")
    assert captured[2]["patent"] is True
    assert captured[2]["utility"] is True


@pytest.mark.asyncio
async def test_search_kipo_patents_more_available_when_paged(
    kipo_mcp: Any, mock_api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        mock_api,
        "search_kipo_patents",
        AsyncMock(
            return_value=(
                [_patent_payload("A")],
                {"totalCount": 100, "pageNo": 1, "numOfRows": 10},
            )
        ),
    )
    result = await kipo_mcp.search_kipo_patents(query="x")
    assert result.more_available is True
    assert "100 hits" in result.summary


# ──────────────────────────────────────────────────────────────────────
# get_kipo_patent — §5.4 list-accept + envelope
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_kipo_patent_single_string(kipo_mcp: Any, mock_client: AsyncMock) -> None:
    mock_client.get_patent = AsyncMock(return_value=([_patent_payload("1020230012345")], {}))
    result = await kipo_mcp.get_kipo_patent(application_number="1020230012345")

    assert isinstance(result, ListEnvelope)
    assert "/patUtliInfoSearchService/" in result.provenance.source_url
    assert len(result.items) == 1
    assert result.items[0]["application_number"] == "1020230012345"
    # Default lean — Korean abstract not present.
    assert "astrtCont" not in result.items[0]


@pytest.mark.asyncio
async def test_get_kipo_patent_list_returns_combined_envelope(
    kipo_mcp: Any, mock_client: AsyncMock
) -> None:
    mock_client.get_patent = AsyncMock(
        side_effect=[
            ([_patent_payload("A1")], {}),
            ([_patent_payload("A2")], {}),
            ([_patent_payload("A3")], {}),
        ]
    )
    result = await kipo_mcp.get_kipo_patent(application_number=["A1", "A2", "A3"])

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 3
    assert {r["application_number"] for r in result.items} == {"A1", "A2", "A3"}
    assert "3" in result.summary


@pytest.mark.asyncio
async def test_get_kipo_patent_empty_list_raises(kipo_mcp: Any, mock_client: AsyncMock) -> None:
    with pytest.raises(ValidationError, match="at least one"):
        await kipo_mcp.get_kipo_patent(application_number=[])


@pytest.mark.asyncio
async def test_get_kipo_patent_list_cap_exceeded_raises(
    kipo_mcp: Any, mock_client: AsyncMock
) -> None:
    from patent_client_agents.kipo_kipris.client import LIST_ACCEPT_CAP

    too_many = [f"A{i}" for i in range(LIST_ACCEPT_CAP + 1)]
    with pytest.raises(ValidationError, match="capped at"):
        await kipo_mcp.get_kipo_patent(application_number=too_many)


@pytest.mark.asyncio
async def test_get_kipo_patent_full_keeps_abstract(kipo_mcp: Any, mock_client: AsyncMock) -> None:
    mock_client.get_patent = AsyncMock(return_value=([_patent_payload("A")], {}))
    result = await kipo_mcp.get_kipo_patent(application_number="A", full=True)
    assert "astrtCont" in result.items[0]


# ──────────────────────────────────────────────────────────────────────
# Trademarks — search + fetch coverage
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_kipo_trademarks_envelope(
    kipo_mcp: Any, mock_api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        mock_api,
        "search_kipo_trademarks",
        AsyncMock(return_value=([_trademark_payload("4020230123456")], {"totalCount": 1})),
    )

    result = await kipo_mcp.search_kipo_trademarks(query="GALAXY")
    assert isinstance(result, ListEnvelope)
    assert "/trademarkInfoSearchService/getWordSearch" in result.provenance.source_url
    assert result.items[0]["title"] == "GALAXY"
    assert "GALAXY" in result.summary


@pytest.mark.asyncio
async def test_search_kipo_trademarks_advanced_envelope(
    kipo_mcp: Any, mock_api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        mock_api,
        "search_kipo_trademarks_advanced",
        AsyncMock(return_value=([_trademark_payload("T1")], {"totalCount": 1})),
    )
    result = await kipo_mcp.search_kipo_trademarks_advanced(title="GALAXY")
    assert "/trademarkInfoSearchService/getAdvancedSearch" in result.provenance.source_url
    assert result.items[0]["title"] == "GALAXY"


@pytest.mark.asyncio
async def test_get_kipo_trademark_single(kipo_mcp: Any, mock_client: AsyncMock) -> None:
    mock_client.get_trademark = AsyncMock(return_value=([_trademark_payload("T1")], {}))
    result = await kipo_mcp.get_kipo_trademark(application_number="T1")
    assert isinstance(result, ListEnvelope)
    assert result.items[0]["application_number"] == "T1"


@pytest.mark.asyncio
async def test_get_kipo_trademark_list(kipo_mcp: Any, mock_client: AsyncMock) -> None:
    mock_client.get_trademark = AsyncMock(
        side_effect=[
            ([_trademark_payload("T1")], {}),
            ([_trademark_payload("T2")], {}),
        ]
    )
    result = await kipo_mcp.get_kipo_trademark(application_number=["T1", "T2"])
    assert len(result.items) == 2


@pytest.mark.asyncio
async def test_get_kipo_trademark_empty_list_raises(kipo_mcp: Any, mock_client: AsyncMock) -> None:
    with pytest.raises(ValidationError, match="at least one"):
        await kipo_mcp.get_kipo_trademark(application_number=[])


# ──────────────────────────────────────────────────────────────────────
# Designs — search + fetch coverage
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_kipo_designs_envelope(
    kipo_mcp: Any, mock_api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        mock_api,
        "search_kipo_designs",
        AsyncMock(return_value=([_design_payload("D1")], {"totalCount": 1})),
    )
    result = await kipo_mcp.search_kipo_designs(query="전화기")
    assert "/designInfoSearchService/getWordSearch" in result.provenance.source_url
    # Designs always keep the drawing URL in the lean projection.
    assert result.items[0]["drawing"] == "https://example.test/drawing.jpg"
    assert "전화기" in result.summary


@pytest.mark.asyncio
async def test_search_kipo_designs_advanced_envelope(
    kipo_mcp: Any, mock_api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        mock_api,
        "search_kipo_designs_advanced",
        AsyncMock(return_value=([_design_payload("D1")], {"totalCount": 1})),
    )
    result = await kipo_mcp.search_kipo_designs_advanced(article_name="전화기")
    assert "/designInfoSearchService/getAdvancedSearch" in result.provenance.source_url


@pytest.mark.asyncio
async def test_get_kipo_design_single(kipo_mcp: Any, mock_client: AsyncMock) -> None:
    mock_client.get_design = AsyncMock(return_value=([_design_payload("D1")], {}))
    result = await kipo_mcp.get_kipo_design(application_number="D1")
    assert result.items[0]["drawing"] == "https://example.test/drawing.jpg"


@pytest.mark.asyncio
async def test_get_kipo_design_list(kipo_mcp: Any, mock_client: AsyncMock) -> None:
    mock_client.get_design = AsyncMock(
        side_effect=[
            ([_design_payload("D1")], {}),
            ([_design_payload("D2")], {}),
        ]
    )
    result = await kipo_mcp.get_kipo_design(application_number=["D1", "D2"])
    assert len(result.items) == 2


@pytest.mark.asyncio
async def test_get_kipo_design_empty_list_raises(kipo_mcp: Any, mock_client: AsyncMock) -> None:
    with pytest.raises(ValidationError, match="at least one"):
        await kipo_mcp.get_kipo_design(application_number=[])


# ──────────────────────────────────────────────────────────────────────
# Provenance helper — explicit unit coverage
# ──────────────────────────────────────────────────────────────────────


def test_kipo_provenance_builds_canonical_url(kipo_mcp: Any) -> None:
    prov = kipo_mcp._kipo_provenance("patUtliInfoSearchService", "getWordSearch")
    assert isinstance(prov, Provenance)
    assert prov.source_url.endswith("/patUtliInfoSearchService/getWordSearch")
    assert "BYOK" not in prov.source_name  # marketing only — exact phrasing
    assert "Per-user API key" in prov.source_name


def test_lean_projections_omit_korean_abstract(kipo_mcp: Any) -> None:
    from patent_client_agents.kipo_kipris import PatentUtilityRow

    row = PatentUtilityRow.model_validate(_patent_payload("X"))
    lean = kipo_mcp._lean_patent(row)
    assert "astrt_cont" not in lean
    assert "astrtCont" not in lean
    assert lean["application_number"] == "X"


def test_advanced_patent_search_filters_and_summary(
    kipo_mcp: Any, mock_api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover ``search_kipo_patents_advanced`` envelope + summary path."""
    import asyncio

    monkeypatch.setattr(
        mock_api,
        "search_kipo_patents_advanced",
        AsyncMock(
            return_value=(
                [_patent_payload("ADV-1")],
                {"totalCount": 1, "pageNo": 1, "numOfRows": 10},
            )
        ),
    )
    result = asyncio.run(
        kipo_mcp.search_kipo_patents_advanced(
            invention_title="배터리",
            applicant="삼성",
            ipc="H01M",
            right_type="patent",
        )
    )
    assert "/patUtliInfoSearchService/getAdvancedSearch" in result.provenance.source_url
    assert result.items[0]["application_number"] == "ADV-1"
