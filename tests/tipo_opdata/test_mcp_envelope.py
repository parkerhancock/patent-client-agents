"""Envelope-shape tests for the TIPO OpenData MCP tools.

Verifies §5.9 envelope contract (Provenance source_name + source_url
populated), §5.5 lean projection (drops ``xml-detail-url``; ``full=True``
opt-in), and §5.4 list-accept on at least one fetch tool. The lean
projection logic and the fan-out fetch helper are exercised across
three representative tools — one search and two fetches (single id +
list of ids).

Mocks ``TipoClient`` at the boundary so the upstream API is never
touched. Uses plain ``_FakeModel`` classes (NOT
``BaseModel(extra='allow')``) per the chunk-4 runbook pitfall.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from mcp_data_core.envelope import ListEnvelope, Provenance
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.mcp.tools import tipo_opdata as tipo_mcp

# ──────────────────────────────────────────────────────────────────────
# Plain "fake" row models — they only need to expose ``model_dump`` so
# the MCP layer can serialize them. We deliberately avoid pydantic here
# because pydantic v2 with ``extra='allow'`` propagates unknown
# keyword arguments through model_dump in ways ty flags as
# ``unknown-argument``. A plain class side-steps that pitfall.
# ──────────────────────────────────────────────────────────────────────


class _FakeRow:
    """Fake upstream response: serializes to its stored payload dict."""

    def __init__(self, **payload: Any) -> None:
        self._payload = payload

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        return dict(self._payload)


def _patent_payload(appl_no: str = "112100001", **overrides: Any) -> dict[str, Any]:
    base = {
        "appl-no": appl_no,
        "appl-date": "2023-01-05",
        "publish-flag": "1",
        "xml-detail-url": "ftps://ftp.tipo.gov.tw/path/x.xml",
        "applicant-name-e": None,  # null Latin — should be dropped by lean
    }
    base.update(overrides)
    return base


@pytest.fixture
def mock_client(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Patch ``TipoClient`` with an async-context AsyncMock."""
    inner = AsyncMock()

    class _MockCtx:
        async def __aenter__(self) -> AsyncMock:
            return inner

        async def __aexit__(self, *exc: Any) -> None:
            return None

    def _factory(*args: Any, **kwargs: Any) -> _MockCtx:
        return _MockCtx()

    monkeypatch.setattr(tipo_mcp, "TipoClient", _factory)
    return inner


# ──────────────────────────────────────────────────────────────────────
# search_tipo_patents — §5.5 lean projection, §5.9 envelope
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_tipo_patents_lean_drops_xml_url_and_null_latin(
    mock_client: AsyncMock,
) -> None:
    mock_client.search_patent_appl = AsyncMock(
        return_value=[
            _FakeRow(**_patent_payload("112100001")),
            _FakeRow(**_patent_payload("112100002")),
        ]
    )

    result = await tipo_mcp.search_tipo_patents(q="TSMC")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name.startswith(
        "Intellectual Property Office, Ministry of Economic Affairs"
    )
    assert "/PatentAppl" in result.provenance.source_url
    assert len(result.items) == 2
    # Lean projection: xml-detail-url dropped; null Latin fields dropped.
    assert "xml-detail-url" not in result.items[0]
    assert "applicant-name-e" not in result.items[0]
    assert result.items[0]["appl-no"] == "112100001"
    assert "TSMC" in result.summary


@pytest.mark.asyncio
async def test_search_tipo_patents_full_true_keeps_xml_url(
    mock_client: AsyncMock,
) -> None:
    mock_client.search_patent_appl = AsyncMock(
        return_value=[_FakeRow(**_patent_payload("112100001"))]
    )
    result = await tipo_mcp.search_tipo_patents(q="x", full=True)
    assert "xml-detail-url" in result.items[0]


@pytest.mark.asyncio
async def test_search_tipo_patents_applclass_label_in_summary(
    mock_client: AsyncMock,
) -> None:
    mock_client.search_patent_appl = AsyncMock(return_value=[])
    result = await tipo_mcp.search_tipo_patents(applclass=2)
    assert "utility model" in result.summary


# ──────────────────────────────────────────────────────────────────────
# get_tipo_patent — §5.4 list-accept + envelope
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_tipo_patent_single_string(mock_client: AsyncMock) -> None:
    mock_client.search_patent_appl = AsyncMock(
        return_value=[_FakeRow(**_patent_payload("112100001"))]
    )
    result = await tipo_mcp.get_tipo_patent(appl_no="112100001")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_url.endswith("/PatentAppl")
    assert len(result.items) == 1
    assert result.items[0]["appl-no"] == "112100001"
    # xml-detail-url stripped on lean (default).
    assert "xml-detail-url" not in result.items[0]
    assert "112100001" in result.summary


@pytest.mark.asyncio
async def test_get_tipo_patent_list_returns_combined_envelope(
    mock_client: AsyncMock,
) -> None:
    mock_client.search_patent_appl = AsyncMock(
        side_effect=[
            [_FakeRow(**_patent_payload("A1"))],
            [_FakeRow(**_patent_payload("A2"))],
            [_FakeRow(**_patent_payload("A3"))],
        ]
    )
    result = await tipo_mcp.get_tipo_patent(appl_no=["A1", "A2", "A3"])

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 3
    assert {r["appl-no"] for r in result.items} == {"A1", "A2", "A3"}
    assert "3 applications" in result.summary


@pytest.mark.asyncio
async def test_get_tipo_patent_empty_list_raises(mock_client: AsyncMock) -> None:
    with pytest.raises(ValidationError, match="at least one"):
        await tipo_mcp.get_tipo_patent(appl_no=[])


@pytest.mark.asyncio
async def test_get_tipo_patent_full_keeps_xml_url(mock_client: AsyncMock) -> None:
    mock_client.search_patent_appl = AsyncMock(return_value=[_FakeRow(**_patent_payload("A1"))])
    result = await tipo_mcp.get_tipo_patent(appl_no="A1", full=True)
    assert "xml-detail-url" in result.items[0]


# ──────────────────────────────────────────────────────────────────────
# search_tipo_trademarks — second search tool for breadth
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_tipo_trademarks_returns_envelope(
    mock_client: AsyncMock,
) -> None:
    mock_client.search_tmark_appl = AsyncMock(
        return_value=[
            _FakeRow(
                **{
                    "appl-no": "T1",
                    "tmark-name": "WAVE",
                    "tmark-class": "9",
                    "tmark-draft-e": None,  # lean drops
                }
            )
        ]
    )

    result = await tipo_mcp.search_tipo_trademarks(q="WAVE", tmark_class=9)

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name.startswith("Intellectual Property Office")
    assert "/TmarkAppl" in result.provenance.source_url
    assert "tmark-draft-e" not in result.items[0]
    assert "WAVE" in result.summary
    assert "class 9" in result.summary


# ──────────────────────────────────────────────────────────────────────
# Lean projection unit — nested dict + list recursion
# ──────────────────────────────────────────────────────────────────────


def test_lean_recurses_into_dicts_and_lists() -> None:
    row = {
        "appl-no": "X",
        "xml-detail-url": "ftps://x",
        "parties": {
            "applicants": [
                {
                    "applicant": {
                        "chinese-name": "甲",
                        "applicant-name-e": None,  # drop
                    }
                }
            ]
        },
    }
    out = tipo_mcp._lean(row)
    assert "xml-detail-url" not in out
    applicant = out["parties"]["applicants"][0]["applicant"]
    assert "applicant-name-e" not in applicant
    assert applicant["chinese-name"] == "甲"


# ──────────────────────────────────────────────────────────────────────
# _project + _dump fallbacks
# ──────────────────────────────────────────────────────────────────────


def test_dump_passthrough_dict() -> None:
    assert tipo_mcp._dump({"k": 1}) == {"k": 1}


def test_dump_invalid_type_raises() -> None:
    with pytest.raises(TypeError, match="model or dict"):
        tipo_mcp._dump(object())


def test_coerce_list_string_input() -> None:
    assert tipo_mcp._coerce_list("A1", tool="t") == ["A1"]


def test_coerce_list_mixed_blank_filtered() -> None:
    assert tipo_mcp._coerce_list(["A1", "  ", "A2"], tool="t") == ["A1", "A2"]


def test_coerce_list_all_blank_raises() -> None:
    with pytest.raises(ValidationError):
        tipo_mcp._coerce_list(["", " "], tool="t")


# ──────────────────────────────────────────────────────────────────────
# get_tipo_patent_events — combined endpoint
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_tipo_patent_events_tags_event_types(
    mock_client: AsyncMock,
) -> None:
    mock_client.get_patent_alteration = AsyncMock(
        return_value=[_FakeRow(sequence=1, alteration=[])]
    )
    mock_client.get_patent_change = AsyncMock(
        return_value=[_FakeRow(sequence=1, **{"new-appl-no": "Z"})]
    )
    mock_client.get_patent_divide = AsyncMock(return_value=[])

    result = await tipo_mcp.get_tipo_patent_events(appl_no="X1")

    types = {item["event_type"] for item in result.items}
    assert "alteration" in types
    assert "change" in types
    assert all(item["appl_no"] == "X1" for item in result.items)


@pytest.mark.asyncio
async def test_get_tipo_trademark_events_tags_event_types(
    mock_client: AsyncMock,
) -> None:
    mock_client.get_tmark_change = AsyncMock(return_value=[_FakeRow(sequence=1, alteration=[])])
    mock_client.get_tmark_divide = AsyncMock(
        return_value=[_FakeRow(sequence=1, **{"divide-count": 1})]
    )
    result = await tipo_mcp.get_tipo_trademark_events(appl_no=["T1", "T2"])
    types = {item["event_type"] for item in result.items}
    assert types == {"change", "divide"}
    # Order preserved per appl_no.
    appl_order = [item["appl_no"] for item in result.items]
    assert appl_order[0] == "T1"


# ──────────────────────────────────────────────────────────────────────
# Trademark fetch tools — single + list smoke tests
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_tipo_trademark_single(mock_client: AsyncMock) -> None:
    mock_client.search_tmark_appl = AsyncMock(
        return_value=[_FakeRow(**{"appl-no": "T1", "tmark-name": "X"})]
    )
    result = await tipo_mcp.get_tipo_trademark(appl_no="T1")
    assert isinstance(result, ListEnvelope)
    assert result.items[0]["appl-no"] == "T1"


@pytest.mark.asyncio
async def test_get_tipo_trademark_rights(mock_client: AsyncMock) -> None:
    mock_client.get_tmark_rights = AsyncMock(return_value=[_FakeRow(**{"appl-no": "T1"})])
    result = await tipo_mcp.get_tipo_trademark_rights(appl_no="T1")
    assert "/TmarkRights" in result.provenance.source_url


@pytest.mark.asyncio
async def test_get_tipo_trademark_image_urls(mock_client: AsyncMock) -> None:
    mock_client.get_tmark_pics = AsyncMock(
        return_value=[_FakeRow(**{"appl-no": "T1", "tmark-image-url": ["a.png"]})]
    )
    result = await tipo_mcp.get_tipo_trademark_image_urls(appl_no="T1")
    assert result.items[0]["tmark-image-url"] == ["a.png"]


@pytest.mark.asyncio
async def test_get_tipo_trademark_priority(mock_client: AsyncMock) -> None:
    mock_client.get_tmark_priority = AsyncMock(
        return_value=[_FakeRow(sequence=1, **{"tmark-right-url": "x"})]
    )
    result = await tipo_mcp.get_tipo_trademark_priority(appl_no="T1")
    assert "/TmarkPriority" in result.provenance.source_url


# ──────────────────────────────────────────────────────────────────────
# Remaining patent fetch tools — smoke for coverage
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_tipo_patent_publication(mock_client: AsyncMock) -> None:
    mock_client.get_patent_pub = AsyncMock(return_value=[_FakeRow(sequence=1)])
    result = await tipo_mcp.get_tipo_patent_publication(appl_no="A1")
    assert "/PatentPub" in result.provenance.source_url


@pytest.mark.asyncio
async def test_get_tipo_patent_rights(mock_client: AsyncMock) -> None:
    mock_client.get_patent_rights = AsyncMock(return_value=[_FakeRow(sequence=1)])
    result = await tipo_mcp.get_tipo_patent_rights(appl_no="A1")
    assert "/PatentRights" in result.provenance.source_url


@pytest.mark.asyncio
async def test_get_tipo_patent_priority(mock_client: AsyncMock) -> None:
    mock_client.get_patent_priority = AsyncMock(return_value=[_FakeRow(sequence=1)])
    result = await tipo_mcp.get_tipo_patent_priority(appl_no="A1")
    assert "/PatentPriority" in result.provenance.source_url


@pytest.mark.asyncio
async def test_get_tipo_patent_annuity(mock_client: AsyncMock) -> None:
    mock_client.get_patent_annuity = AsyncMock(return_value=[_FakeRow(sequence=1)])
    result = await tipo_mcp.get_tipo_patent_annuity(appl_no="A1")
    assert "/PatentAnnuity" in result.provenance.source_url


@pytest.mark.asyncio
async def test_get_tipo_patent_twins(mock_client: AsyncMock) -> None:
    mock_client.get_patent_twins = AsyncMock(return_value=[_FakeRow(sequence=1)])
    result = await tipo_mcp.get_tipo_patent_twins(appl_no="A1")
    assert "/PatentTwins" in result.provenance.source_url
