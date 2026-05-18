"""Client-level tests for the KIPO KIPRIS Plus async client.

Layers exercised:

* Constructor wiring: ``service_key`` resolution order (arg > env > error).
* ``_parse_kipris_response()`` envelope parsing across normal/empty/error
  XML shapes, loaded from hand-crafted fixtures under ``fixtures/``.
* KIPRIS date parsing (``YYYYMMDD``, empty, ``"00000000"``, None).
* ``paginate()`` page-walking behaviour incl. short-page termination
  and ``max_pages`` cap.
* Per-service methods using ``httpx.MockTransport`` to confirm the
  upstream URL shape (service prefix + operation) and parsing pipeline.

No live KIPRIS traffic is recorded (no ``serviceKey`` available in v1 —
see ``tests/kipo_kipris/conftest.py`` for the rationale).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from law_tools_core.exceptions import ApiError, ConfigurationError
from patent_client_agents.kipo_kipris import KiprisClient
from patent_client_agents.kipo_kipris.client import (
    BASE_URL,
    DESIGN,
    MAX_NUM_OF_ROWS,
    PAT_UTL,
    TM,
    _element_to_dict,
)
from patent_client_agents.kipo_kipris.models import _parse_kipris_date

# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _mock_http(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.AsyncClient:
    """Build an AsyncClient with a MockTransport for offline tests."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _read_fixture(name: str) -> bytes:
    """Load a fixture file as raw bytes."""
    return (Path(__file__).parent / "fixtures" / name).read_bytes()


# ──────────────────────────────────────────────────────────────────────
# Constructor / auth resolution
# ──────────────────────────────────────────────────────────────────────


def test_service_key_arg_wins_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "env-key")
    client = KiprisClient(service_key="arg-key")
    assert client._service_key == "arg-key"  # type: ignore[attr-defined]


def test_service_key_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "env-key")
    client = KiprisClient()
    assert client._service_key == "env-key"  # type: ignore[attr-defined]


def test_service_key_missing_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KIPO_KIPRIS_API_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="KIPRIS"):
        KiprisClient()


def test_service_key_empty_string_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KIPO_KIPRIS_API_KEY", raising=False)
    with pytest.raises(ConfigurationError):
        KiprisClient(service_key="")


def test_default_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "k")
    client = KiprisClient()
    assert client.base_url == BASE_URL


def test_base_url_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "k")
    client = KiprisClient(base_url="https://example.test")
    assert client.base_url == "https://example.test"


# ──────────────────────────────────────────────────────────────────────
# _parse_kipris_response envelope parsing
# ──────────────────────────────────────────────────────────────────────


def test_parse_normal_response_two_rows() -> None:
    xml = _read_fixture("pat_utl_word_search_2rows.xml")
    items, pagination = KiprisClient._parse_kipris_response(xml)
    assert len(items) == 2
    assert items[0]["applicationNumber"] == "1020230012345"
    assert items[1]["applicationNumber"] == "1020230098765"
    assert pagination["resultCode"] == "00"
    assert pagination["resultMsg"] == "NORMAL SERVICE"
    assert pagination["numOfRows"] == 10
    assert pagination["pageNo"] == 1
    assert pagination["totalCount"] == 2


def test_parse_empty_items() -> None:
    xml = _read_fixture("pat_utl_word_search_empty.xml")
    items, pagination = KiprisClient._parse_kipris_response(xml)
    assert items == []
    assert pagination["totalCount"] == 0


def test_parse_error_response_raises_api_error() -> None:
    xml = _read_fixture("kipris_error_invalid_key.xml")
    with pytest.raises(ApiError, match="30"):
        KiprisClient._parse_kipris_response(xml)


def test_parse_malformed_xml_raises_api_error() -> None:
    with pytest.raises(ApiError, match="non-XML"):
        KiprisClient._parse_kipris_response(b"<not really xml")


def test_parse_response_without_body() -> None:
    xml = (
        b'<?xml version="1.0"?>'
        b"<response>"
        b"<header><resultCode>00</resultCode><resultMsg>OK</resultMsg></header>"
        b"</response>"
    )
    items, pagination = KiprisClient._parse_kipris_response(xml)
    assert items == []
    assert pagination["resultCode"] == "00"
    # No body → no numeric pagination fields populated.
    assert pagination["numOfRows"] is None


def test_parse_response_with_missing_header() -> None:
    xml = (
        b'<?xml version="1.0"?>'
        b"<response>"
        b"<body><items/><numOfRows>0</numOfRows><pageNo>1</pageNo><totalCount>0</totalCount></body>"
        b"</response>"
    )
    # Missing header == treat as success (some operations omit it).
    items, pagination = KiprisClient._parse_kipris_response(xml)
    assert items == []
    assert pagination["resultCode"] is None


def test_parse_pagination_non_int_text_preserved_as_string() -> None:
    """When numOfRows/pageNo/totalCount aren't pure ints, fall back to string."""
    xml = (
        b'<?xml version="1.0"?>'
        b"<response>"
        b"<header><resultCode>00</resultCode><resultMsg>OK</resultMsg></header>"
        b"<body><items/><numOfRows>n/a</numOfRows><pageNo>1</pageNo>"
        b"<totalCount>?</totalCount></body>"
        b"</response>"
    )
    _, pagination = KiprisClient._parse_kipris_response(xml)
    assert pagination["numOfRows"] == "n/a"
    assert pagination["pageNo"] == 1
    assert pagination["totalCount"] == "?"


# ──────────────────────────────────────────────────────────────────────
# _element_to_dict helper
# ──────────────────────────────────────────────────────────────────────


def test_element_to_dict_flat_strings() -> None:
    import xml.etree.ElementTree as ET

    el = ET.fromstring("<item><a>1</a><b>two</b><c></c></item>")
    out = _element_to_dict(el)
    assert out == {"a": "1", "b": "two", "c": None}


def test_element_to_dict_whitespace_only_becomes_none() -> None:
    import xml.etree.ElementTree as ET

    el = ET.fromstring("<item><a>   </a><b>x</b></item>")
    out = _element_to_dict(el)
    assert out["a"] is None
    assert out["b"] == "x"


# ──────────────────────────────────────────────────────────────────────
# Date parsing
# ──────────────────────────────────────────────────────────────────────


def test_kipris_date_parsing_valid() -> None:
    from datetime import date as dt_date

    assert _parse_kipris_date("20240315") == dt_date(2024, 3, 15)


def test_kipris_date_parsing_empty() -> None:
    assert _parse_kipris_date("") is None
    assert _parse_kipris_date(None) is None


def test_kipris_date_parsing_sentinel_zero() -> None:
    assert _parse_kipris_date("00000000") is None


# ──────────────────────────────────────────────────────────────────────
# paginate() — page-walking
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_paginate_walks_pages_and_terminates_on_short(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``paginate`` should yield rows across pages and stop on a short page."""
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "k")
    page_xmls = [
        _read_fixture("pat_utl_word_search_page1_full.xml"),
        _read_fixture("pat_utl_word_search_page2_short.xml"),
    ]
    page_iter = iter(page_xmls)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=next(page_iter))

    async with KiprisClient(client=_mock_http(handler)) as client:
        rows = []
        async for row in client.paginate(
            client.search_patents_word,
            word="battery",
            num_of_rows=2,
        ):
            rows.append(row)

    assert len(rows) == 3
    assert [r["applicationNumber"] for r in rows] == [
        "1020230000001",
        "1020230000002",
        "1020230000003",
    ]


@pytest.mark.asyncio
async def test_paginate_max_pages_caps_iteration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``max_pages`` should stop iteration even if more pages exist."""
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "k")
    # If we kept fetching we'd hit page 2; max_pages=1 cuts it off.
    page_xmls = [_read_fixture("pat_utl_word_search_page1_full.xml")]
    page_iter = iter(page_xmls)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=next(page_iter))

    async with KiprisClient(client=_mock_http(handler)) as client:
        rows = []
        async for row in client.paginate(
            client.search_patents_word,
            word="x",
            num_of_rows=2,
            max_pages=1,
        ):
            rows.append(row)

    assert len(rows) == 2


@pytest.mark.asyncio
async def test_paginate_clamps_num_of_rows_to_max(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``num_of_rows`` over ``MAX_NUM_OF_ROWS`` is clamped before the request."""
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "k")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=_read_fixture("pat_utl_word_search_empty.xml"))

    async with KiprisClient(client=_mock_http(handler)) as client:
        async for _ in client.paginate(
            client.search_patents_word,
            word="x",
            num_of_rows=999_999,
        ):
            pass  # pragma: no cover — empty fixture yields nothing.

    assert captured, "expected at least one request"
    assert int(captured[0].url.params["numOfRows"]) == MAX_NUM_OF_ROWS


# ──────────────────────────────────────────────────────────────────────
# Patents / Utility Models — request shape + parsing
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_patents_word_url_and_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "live-key")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=_read_fixture("pat_utl_word_search_2rows.xml"))

    async with KiprisClient(client=_mock_http(handler)) as client:
        items, pagination = await client.search_patents_word(
            word="배터리", patent=True, utility=False, num_of_rows=10, page_no=1
        )

    assert len(items) == 2
    assert pagination["totalCount"] == 2
    req = captured[0]
    assert f"/{PAT_UTL}/getWordSearch" in str(req.url)
    assert req.url.params["serviceKey"] == "live-key"
    assert req.url.params["word"] == "배터리"
    assert req.url.params["patent"] == "Y"
    assert req.url.params["utility"] == "N"


@pytest.mark.asyncio
async def test_search_patents_advanced_passes_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "k")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=_read_fixture("pat_utl_word_search_2rows.xml"))

    async with KiprisClient(client=_mock_http(handler)) as client:
        await client.search_patents_advanced(
            invention_title="배터리",
            applicant="삼성",
            ipc="H01M",
            patent=True,
            utility=True,
        )

    req = captured[0]
    assert f"/{PAT_UTL}/getAdvancedSearch" in str(req.url)
    assert req.url.params["inventionTitle"] == "배터리"
    assert req.url.params["applicant"] == "삼성"
    assert req.url.params["ipcNumber"] == "H01M"
    # ``None`` filters get dropped, not sent as the literal string "None".
    assert "astrtCont" not in req.url.params


@pytest.mark.asyncio
async def test_get_patent_by_number(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "k")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=_read_fixture("pat_utl_get_single.xml"))

    async with KiprisClient(client=_mock_http(handler)) as client:
        items, _ = await client.get_patent("1020230012345")

    assert len(items) == 1
    assert items[0]["applicationNumber"] == "1020230012345"
    assert captured[0].url.params["applicationNumber"] == "1020230012345"


# ──────────────────────────────────────────────────────────────────────
# Trademarks — request shape + parsing
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_trademarks_word_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "k")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=_read_fixture("tm_word_search_2rows.xml"))

    async with KiprisClient(client=_mock_http(handler)) as client:
        items, _ = await client.search_trademarks_word(word="GALAXY")

    assert len(items) == 2
    assert items[0]["title"] == "GALAXY"
    req = captured[0]
    assert f"/{TM}/getWordSearch" in str(req.url)
    assert req.url.params["word"] == "GALAXY"


@pytest.mark.asyncio
async def test_search_trademarks_advanced_passes_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "k")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=_read_fixture("tm_word_search_2rows.xml"))

    async with KiprisClient(client=_mock_http(handler)) as client:
        await client.search_trademarks_advanced(
            title="GALAXY",
            applicant="삼성",
            classification="09",
            vienna_code="26.04.01",
        )

    req = captured[0]
    assert f"/{TM}/getAdvancedSearch" in str(req.url)
    assert req.url.params["title"] == "GALAXY"
    assert req.url.params["applicantName"] == "삼성"
    assert req.url.params["classification"] == "09"
    assert req.url.params["viennaCode"] == "26.04.01"


@pytest.mark.asyncio
async def test_get_trademark_by_number(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "k")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=_read_fixture("tm_get_single.xml"))

    async with KiprisClient(client=_mock_http(handler)) as client:
        items, _ = await client.get_trademark("4020230123456")

    assert len(items) == 1
    assert items[0]["registrationNumber"] == "4000123456"
    assert captured[0].url.params["applicationNumber"] == "4020230123456"


# ──────────────────────────────────────────────────────────────────────
# Designs — request shape + parsing
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_designs_word_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "k")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=_read_fixture("design_word_search_1row.xml"))

    async with KiprisClient(client=_mock_http(handler)) as client:
        items, _ = await client.search_designs_word(word="휴대용 전화기")

    assert len(items) == 1
    assert items[0]["articleName"] == "휴대용 전화기"
    assert f"/{DESIGN}/getWordSearch" in str(captured[0].url)


@pytest.mark.asyncio
async def test_search_designs_advanced_passes_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "k")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=_read_fixture("design_word_search_1row.xml"))

    async with KiprisClient(client=_mock_http(handler)) as client:
        await client.search_designs_advanced(
            article_name="전화기",
            applicant="삼성",
            loc_code="14-03",
        )

    req = captured[0]
    assert f"/{DESIGN}/getAdvancedSearch" in str(req.url)
    assert req.url.params["articleName"] == "전화기"
    assert req.url.params["locCode"] == "14-03"


@pytest.mark.asyncio
async def test_get_design_by_number(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "k")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=_read_fixture("design_get_single.xml"))

    async with KiprisClient(client=_mock_http(handler)) as client:
        items, _ = await client.get_design("3020230012345")

    assert len(items) == 1
    assert items[0]["registrationNumber"] == "3000987654"
    assert captured[0].url.params["applicationNumber"] == "3020230012345"


# ──────────────────────────────────────────────────────────────────────
# Error responses — non-2xx upstream
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_non_success_status_raises_api_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "k")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream blew up")

    async with KiprisClient(client=_mock_http(handler)) as client:
        with pytest.raises(ApiError, match="500"):
            await client.search_patents_word(word="x")


@pytest.mark.asyncio
async def test_rate_limit_raises_rate_limit_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "k")
    from law_tools_core.exceptions import RateLimitError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="slow down")

    async with KiprisClient(client=_mock_http(handler)) as client:
        with pytest.raises(RateLimitError):
            await client.search_patents_word(word="x")
