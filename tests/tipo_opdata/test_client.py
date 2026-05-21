"""Client-level tests for the TIPO OpenData REST client.

Layers exercised:
- Constructor wiring: ``tk`` resolution order (arg > env > error).
- ``_extract_rows()`` envelope parsing across the variant TIPO shapes.
- ``_build_params()`` query composition + ``MAX_TOP`` cap.
- ``paginate()`` page-walking behaviour incl. short-page termination.
- ROC ``YYYY/MM/DD`` date validator (valid / empty / placeholder / bad).
- Per-endpoint methods using ``httpx.MockTransport`` to confirm the
  upstream call shape and parsing pipeline.
"""

from __future__ import annotations

import os
from collections.abc import Callable

import httpx
import pytest

from mcp_data_core.exceptions import ConfigurationError
from patent_client_agents.tipo_opdata import TipoClient
from patent_client_agents.tipo_opdata.client import (
    BASE_URL,
    MAX_TOP,
    _extract_rows,
    _join_list,
)
from patent_client_agents.tipo_opdata.models import _parse_tipo_date

# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _mock_http(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.AsyncClient:
    """Build an AsyncClient with a MockTransport for offline tests."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _patent_row(appl_no: str = "112100001", appl_date: str = "2023/01/05") -> dict:
    return {
        "sequence": 1,
        "appl-no": appl_no,
        "appl-date": appl_date,
        "appl-countrycode": "TW",
        "publish-flag": "1",
    }


def _tipo_envelope(
    *,
    rows: list,
    item_key: str = "patentcontent",
    wrapper: str = "tw-patent-applI",
    top: int = 100,
    skip: int = 0,
    total: int | None = None,
) -> dict:
    """Build a TIPO-style outer envelope with rows under wrapper/item_key."""
    return {
        "version": "1.0",
        "status": "OK",
        "top": top,
        "skip": skip,
        "total-count": total if total is not None else len(rows),
        wrapper: {item_key: rows},
    }


# ──────────────────────────────────────────────────────────────────────
# Constructor / auth resolution
# ──────────────────────────────────────────────────────────────────────


def test_tk_arg_wins_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "env-tk")
    client = TipoClient(tk="arg-tk")
    assert client._tk == "arg-tk"  # type: ignore[attr-defined]


def test_tk_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "env-tk")
    client = TipoClient()
    assert client._tk == "env-tk"  # type: ignore[attr-defined]


def test_tk_missing_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TIPO_API_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="TIPO_API_KEY"):
        TipoClient()


def test_tk_empty_string_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TIPO_API_KEY", raising=False)
    with pytest.raises(ConfigurationError):
        TipoClient(tk="")


def test_base_url_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")
    client = TipoClient(base_url="https://example.test")
    assert client.base_url == "https://example.test"


def test_default_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")
    client = TipoClient()
    assert client.base_url == BASE_URL


# ──────────────────────────────────────────────────────────────────────
# _extract_rows envelope parsing
# ──────────────────────────────────────────────────────────────────────


def test_extract_rows_two_level_nesting() -> None:
    payload = _tipo_envelope(rows=[_patent_row("1"), _patent_row("2"), _patent_row("3")])
    rows = _extract_rows(payload)
    assert len(rows) == 3
    assert rows[0]["appl-no"] == "1"


def test_extract_rows_empty_array() -> None:
    payload = _tipo_envelope(rows=[])
    assert _extract_rows(payload) == []


def test_extract_rows_missing_data_key() -> None:
    # TIPO returns the envelope without the data wrapper on zero-row queries.
    payload = {
        "version": "1.0",
        "status": "OK",
        "top": 100,
        "skip": 0,
        "total-count": 0,
    }
    assert _extract_rows(payload) == []


def test_extract_rows_skips_non_dict_entries() -> None:
    # Rows that aren't dicts are filtered out.
    payload = _tipo_envelope(
        rows=[_patent_row("1"), "stray-string", 42, _patent_row("2")]  # type: ignore[list-item]
    )
    rows = _extract_rows(payload)
    assert len(rows) == 2


def test_extract_rows_direct_list_under_top_level() -> None:
    # Some endpoints might inline the list directly (defensive).
    payload = {
        "version": "1.0",
        "status": "OK",
        "top": 100,
        "skip": 0,
        "total-count": 1,
        "results": [_patent_row("100")],
    }
    rows = _extract_rows(payload)
    assert rows[0]["appl-no"] == "100"


def test_extract_rows_three_level_nesting_twins() -> None:
    """``twins-announced`` shape: outer -> twins -> patentcontent."""
    payload = {
        "version": "1.0",
        "status": "OK",
        "top": 100,
        "skip": 0,
        "total-count": 1,
        "twins-announced": {
            "twins": {
                "patentcontent": [_patent_row("twin-1")],
            }
        },
    }
    rows = _extract_rows(payload)
    assert len(rows) == 1
    assert rows[0]["appl-no"] == "twin-1"


# ──────────────────────────────────────────────────────────────────────
# _build_params: tk + format always present, top clamping, dropping None
# ──────────────────────────────────────────────────────────────────────


def test_build_params_includes_tk_and_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "my-tk")
    client = TipoClient()
    params = client._build_params(top=10, skip=0, filters=None)  # type: ignore[attr-defined]
    assert params["tk"] == "my-tk"
    assert params["format"] == "json"
    assert params["top"] == 10
    assert params["skip"] == 0


def test_build_params_clamps_top_to_max(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")
    client = TipoClient()
    params = client._build_params(top=99999, skip=None, filters=None)  # type: ignore[attr-defined]
    assert params["top"] == MAX_TOP


def test_build_params_drops_none_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")
    client = TipoClient()
    params = client._build_params(  # type: ignore[attr-defined]
        top=None,
        skip=None,
        filters={"applicant": "TSMC", "q": None, "applclass": 1},
    )
    assert params["applicant"] == "TSMC"
    assert params["applclass"] == 1
    assert "q" not in params
    assert "top" not in params
    assert "skip" not in params


# ──────────────────────────────────────────────────────────────────────
# _join_list: scalar/list/empty normalization
# ──────────────────────────────────────────────────────────────────────


def test_join_list_none() -> None:
    assert _join_list(None) is None


def test_join_list_scalar_string() -> None:
    assert _join_list("abc") == "abc"


def test_join_list_empty_string() -> None:
    assert _join_list("   ") is None


def test_join_list_with_items() -> None:
    assert _join_list(["a", "b", "c"]) == "a,b,c"


def test_join_list_drops_blank_items() -> None:
    assert _join_list(["a", "", "c"]) == "a,c"


def test_join_list_empty_list() -> None:
    assert _join_list([]) is None


# ──────────────────────────────────────────────────────────────────────
# ROC YYYY/MM/DD date validator
# ──────────────────────────────────────────────────────────────────────


def test_parse_tipo_date_valid() -> None:
    from datetime import date as dt_date

    assert _parse_tipo_date("2024/12/31") == dt_date(2024, 12, 31)


def test_parse_tipo_date_iso_form() -> None:
    from datetime import date as dt_date

    assert _parse_tipo_date("2024-12-31") == dt_date(2024, 12, 31)


def test_parse_tipo_date_empty_string() -> None:
    assert _parse_tipo_date("") is None


def test_parse_tipo_date_none() -> None:
    assert _parse_tipo_date(None) is None


def test_parse_tipo_date_placeholder() -> None:
    assert _parse_tipo_date("0/0/0") is None
    assert _parse_tipo_date("0000/00/00") is None


def test_parse_tipo_date_malformed() -> None:
    assert _parse_tipo_date("not-a-date") is None
    assert _parse_tipo_date("2024-13-99") is None


def test_parse_tipo_date_passthrough_date_instance() -> None:
    from datetime import date as dt_date

    today = dt_date(2024, 1, 1)
    assert _parse_tipo_date(today) is today


def test_parse_tipo_date_unsupported_type() -> None:
    assert _parse_tipo_date(12345) is None
    assert _parse_tipo_date([2024, 1, 1]) is None


# ──────────────────────────────────────────────────────────────────────
# Per-endpoint methods — mocked transport
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_patent_appl_builds_request_and_parses_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "live-tk")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json=_tipo_envelope(rows=[_patent_row("112100001")]),
        )

    async with TipoClient(client=_mock_http(handler)) as client:
        rows = await client.search_patent_appl(q="TSMC", applclass=1, applicant="TSMC", top=50)

    assert len(captured) == 1
    req = captured[0]
    assert req.url.path.endswith("/PatentAppl")
    assert req.url.params["tk"] == "live-tk"
    assert req.url.params["format"] == "json"
    assert req.url.params["q"] == "TSMC"
    assert req.url.params["applclass"] == "1"
    assert req.url.params["applicant"] == "TSMC"
    assert req.url.params["top"] == "50"

    assert len(rows) == 1
    assert rows[0].appl_no == "112100001"


@pytest.mark.asyncio
async def test_search_patent_appl_joins_list_appl_no(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_tipo_envelope(rows=[]))

    async with TipoClient(client=_mock_http(handler)) as client:
        await client.search_patent_appl(appl_no=["A", "B", "C"])

    assert captured[0].url.params["appl-no"] == "A,B,C"


@pytest.mark.asyncio
async def test_get_patent_pub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/PatentPub")
        return httpx.Response(
            200,
            json=_tipo_envelope(
                rows=[{"sequence": 1, "patent-title": {"patent-name-chinese": "x"}}]
            ),
        )

    async with TipoClient(client=_mock_http(handler)) as client:
        rows = await client.get_patent_pub(appl_no="A1")
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_get_patent_rights(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_tipo_envelope(rows=[{"sequence": 1, "patent-right": {"patent-no": "I12345"}}]),
        )

    async with TipoClient(client=_mock_http(handler)) as client:
        rows = await client.get_patent_rights(appl_no="A1")
    assert rows[0].patent_right is not None
    assert rows[0].patent_right.patent_no == "I12345"


@pytest.mark.asyncio
async def test_get_patent_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_tipo_envelope(rows=[{"sequence": 1, "appl-no": "A1", "prioritys": []}]),
        )

    async with TipoClient(client=_mock_http(handler)) as client:
        rows = await client.get_patent_priority(appl_no="A1")
    assert rows[0].appl_no == "A1"


@pytest.mark.asyncio
async def test_get_patent_annuity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_tipo_envelope(
                rows=[
                    {
                        "sequence": 1,
                        "appl-no": "A1",
                        "patent-no": "I77",
                        "charges": [],
                    }
                ]
            ),
        )

    async with TipoClient(client=_mock_http(handler)) as client:
        rows = await client.get_patent_annuity(appl_no="A1")
    assert rows[0].patent_no == "I77"


@pytest.mark.asyncio
async def test_get_patent_twins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_tipo_envelope(rows=[{"sequence": 1, "appl-no": "X"}]),
        )

    async with TipoClient(client=_mock_http(handler)) as client:
        rows = await client.get_patent_twins(appl_no="X")
    assert rows[0].appl_no == "X"


@pytest.mark.asyncio
async def test_get_patent_alteration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_tipo_envelope(rows=[{"sequence": 1, "appl-no": "X", "alteration": []}]),
        )

    async with TipoClient(client=_mock_http(handler)) as client:
        rows = await client.get_patent_alteration(appl_no="X")
    assert rows[0].appl_no == "X"


@pytest.mark.asyncio
async def test_get_patent_change(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_tipo_envelope(
                rows=[
                    {
                        "sequence": 1,
                        "appl-no": "X",
                        "new-appl-no": "Y",
                    }
                ]
            ),
        )

    async with TipoClient(client=_mock_http(handler)) as client:
        rows = await client.get_patent_change(appl_no="X")
    assert rows[0].new_appl_no == "Y"


@pytest.mark.asyncio
async def test_get_patent_divide(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_tipo_envelope(
                rows=[
                    {
                        "sequence": 1,
                        "appl-no": "P",
                        "new-appl-no": {"patent-right-url": "x"},
                    }
                ]
            ),
        )

    async with TipoClient(client=_mock_http(handler)) as client:
        rows = await client.get_patent_divide(appl_no="P")
    assert rows[0].appl_no == "P"
    assert isinstance(rows[0].new_appl_no, dict)


@pytest.mark.asyncio
async def test_search_tmark_appl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "version": "1.0",
                "status": "OK",
                "top": 100,
                "skip": 0,
                "total-count": 1,
                "tmarkappl": {
                    "tmarkcontent": [
                        {
                            "sequence": 1,
                            "appl-no": "T1",
                            "tmark-name": "WAVE",
                            "tmark-class": "9",
                        }
                    ]
                },
            },
        )

    async with TipoClient(client=_mock_http(handler)) as client:
        rows = await client.search_tmark_appl(q="WAVE", tmark_class=9)

    assert len(rows) == 1
    assert rows[0].tmark_name == "WAVE"
    assert captured[0].url.params["q"] == "WAVE"
    assert captured[0].url.params["tmark-class"] == "9"


@pytest.mark.asyncio
async def test_get_tmark_rights(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "version": "1.0",
                "status": "OK",
                "top": 100,
                "skip": 0,
                "total-count": 1,
                "tmarkrights": {
                    "tmarkcontent": [
                        {
                            "sequence": 1,
                            "appl-no": "T1",
                            "tmark-name": "Acme",
                            "tmark-class": "9",
                        }
                    ]
                },
            },
        )

    async with TipoClient(client=_mock_http(handler)) as client:
        rows = await client.get_tmark_rights(appl_no="T1")
    assert rows[0].tmark_name == "Acme"


@pytest.mark.asyncio
async def test_get_tmark_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "version": "1.0",
                "status": "OK",
                "top": 100,
                "skip": 0,
                "total-count": 1,
                "tmarkpriority": {
                    "tmarkrightscontents": [
                        {"sequence": 1, "tmark-right-url": "x", "tmarkcontent": []}
                    ]
                },
            },
        )

    async with TipoClient(client=_mock_http(handler)) as client:
        rows = await client.get_tmark_priority(appl_no="T1")
    assert rows[0].tmark_right_url == "x"


@pytest.mark.asyncio
async def test_get_tmark_pics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "version": "1.0",
                "status": "OK",
                "top": 100,
                "skip": 0,
                "total-count": 1,
                "tmarkpics": {
                    "tmarkcontent": [
                        {
                            "sequence": 1,
                            "appl-no": "T1",
                            "tmark-image-url": ["a.png", "b.png"],
                        }
                    ]
                },
            },
        )

    async with TipoClient(client=_mock_http(handler)) as client:
        rows = await client.get_tmark_pics(appl_no="T1")
    assert rows[0].tmark_image_url == ["a.png", "b.png"]


@pytest.mark.asyncio
async def test_get_tmark_change(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "version": "1.0",
                "status": "OK",
                "top": 100,
                "skip": 0,
                "total-count": 1,
                "tmarkchange": {
                    "tmarkcontent": [
                        {
                            "sequence": 1,
                            "exam-no": "E1",
                            "tmark-name": "X",
                            "alteration": [],
                        }
                    ]
                },
            },
        )

    async with TipoClient(client=_mock_http(handler)) as client:
        rows = await client.get_tmark_change(appl_no="T1")
    assert rows[0].exam_no == "E1"


@pytest.mark.asyncio
async def test_get_tmark_divide(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "version": "1.0",
                "status": "OK",
                "top": 100,
                "skip": 0,
                "total-count": 1,
                "tmarkdivide": {
                    "tmarkcontent": [
                        {
                            "sequence": 1,
                            "exam-no": "E1",
                            "tmark-name": "X",
                            "tmark-class": "9",
                            "origin-exam-no": {"-tmark-right-url": "y"},
                            "divide-date": "2023/01/05",
                            "divide-count": 2,
                            "goodsclass": [],
                        }
                    ]
                },
            },
        )

    async with TipoClient(client=_mock_http(handler)) as client:
        rows = await client.get_tmark_divide(appl_no="T1")
    assert rows[0].exam_no == "E1"
    assert rows[0].divide_count == 2
    assert rows[0].divide_date is not None


# ──────────────────────────────────────────────────────────────────────
# paginate(): page-walking + short-page termination
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_paginate_walks_until_short_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")
    captured: list[httpx.Request] = []
    pages = [
        [_patent_row(f"page1-{i}") for i in range(3)],
        [_patent_row(f"page2-{i}") for i in range(3)],
        [_patent_row("last")],  # short page → stop
    ]
    counter = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        page = pages[counter["i"]]
        counter["i"] += 1
        return httpx.Response(200, json=_tipo_envelope(rows=page))

    async with TipoClient(client=_mock_http(handler)) as client:
        seen = []
        async for row in client.paginate("/PatentAppl", top=3):
            seen.append(row["appl-no"])

    assert seen == [
        "page1-0",
        "page1-1",
        "page1-2",
        "page2-0",
        "page2-1",
        "page2-2",
        "last",
    ]
    # 3 requests with skip values 0, 3, 6
    assert len(captured) == 3
    assert captured[0].url.params["skip"] == "0"
    assert captured[1].url.params["skip"] == "3"
    assert captured[2].url.params["skip"] == "6"


@pytest.mark.asyncio
async def test_paginate_clamps_top_to_max_top(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_tipo_envelope(rows=[]))

    async with TipoClient(client=_mock_http(handler)) as client:
        # Even though caller asks for 99999, top must clamp to MAX_TOP.
        async for _ in client.paginate("/PatentAppl", top=99999):
            break  # Won't be reached (empty page).

    assert captured[0].url.params["top"] == str(MAX_TOP)


@pytest.mark.asyncio
async def test_paginate_empty_first_page_terminates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_tipo_envelope(rows=[]))

    async with TipoClient(client=_mock_http(handler)) as client:
        rows = [r async for r in client.paginate("/PatentAppl", top=10)]
    assert rows == []


@pytest.mark.asyncio
async def test_paginate_forwards_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TIPO_API_KEY", "tk")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_tipo_envelope(rows=[]))

    async with TipoClient(client=_mock_http(handler)) as client:
        async for _ in client.paginate("/PatentAppl", top=10, applicant="TSMC"):
            break

    assert captured[0].url.params["applicant"] == "TSMC"


# ──────────────────────────────────────────────────────────────────────
# Live cassette smoke (record with TIPO_API_KEY=<real tk> --vcr-record=once)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_live_patent_appl_smoke(
    vcr_cassette: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hit /PatentAppl against the real upstream (cassette-replayed).

    The cassette is recorded once with the demo ``tk`` cited in
    data.gov.tw dataset 35466; the conftest scrubs the ``tk`` query
    parameter to ``REDACTED`` so the committed cassette is safe.
    """
    del vcr_cassette  # marker fixture; vcr is active for the test body
    # Use the conftest placeholder for replay; record mode reads the real
    # key from the process env that the operator sets when recording.
    tk = os.environ.get("TIPO_API_KEY") or "test_tipo_tk"
    async with TipoClient(tk=tk) as client:
        rows = await client.search_patent_appl(top=2)
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_live_tmark_appl_smoke(
    vcr_cassette: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hit /TmarkAppl against the real upstream (cassette-replayed)."""
    del vcr_cassette
    tk = os.environ.get("TIPO_API_KEY") or "test_tipo_tk"
    async with TipoClient(tk=tk) as client:
        rows = await client.search_tmark_appl(top=2)
    assert isinstance(rows, list)
