"""Client-level tests for :class:`InpiPiClient`.

Uses :class:`httpx.MockTransport` everywhere — no live INPI traffic.
Covers:

* SolR query builder (``_build_solr_query``) — q only, q + filters,
  edge cases.
* ST.66 + ST.86 XML notice parsing — alias roundtrip, multi-applicant
  lists, image-URL list shape.
* Search envelope parsing across the candidate row keys.
* Throttle (``_SlidingWindowThrottle``) with an injectable clock — no
  real sleeps; the wait math is asserted directly.
* Credential resolution: arg → env → ConfigurationError.
* Happy-path per endpoint (search + get × TM + design), including the
  list-accept cap on ``get_*``.
* Pagination bounds (offset / limit) raise ValidationError on overflow.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx
import pytest

from law_tools_core.exceptions import (
    ApiError,
    ConfigurationError,
    RateLimitError,
    ValidationError,
)
from patent_client_agents.inpi_pi.client import (
    BASE_URL,
    MAX_LIST_ACCEPT,
    MAX_OFFSET,
    InpiPiClient,
    _build_solr_query,
    _coerce_list,
    _SlidingWindowThrottle,
    _solr_escape,
)
from patent_client_agents.inpi_pi.models import InpiDesignRow, InpiTrademarkRow
from patent_client_agents.inpi_pi.session import (
    BOOTSTRAP_PATH,
    LOGIN_PATH,
    XSRF_COOKIE_NAME,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _set_cookie(name: str, value: str) -> str:
    return f"{name}={value}; Path=/"


def _make_auth_handler(
    extra_handlers: dict[str, Callable[[httpx.Request], httpx.Response]] | None = None,
    *,
    require_bearer: bool = True,
) -> Callable[[httpx.Request], httpx.Response]:
    """Build a MockTransport handler that handles XSRF + login + custom routes.

    The returned callable services:

    * ``GET BOOTSTRAP_PATH`` → set XSRF-TOKEN cookie
    * ``POST LOGIN_PATH`` → set access_token + refresh_token + JSON body
    * Anything else → dispatched into ``extra_handlers`` keyed by path
      prefix. If no prefix matches, a 404 is returned to make the
      mistake visible.

    When ``require_bearer`` is True, every non-auth call must carry
    ``Authorization: Bearer ...`` — guards against forgetting the
    bearer header in the request path.
    """
    extras = extra_handlers or {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == BOOTSTRAP_PATH:
            return httpx.Response(
                200,
                headers=[("Set-Cookie", _set_cookie(XSRF_COOKIE_NAME, "xsrf-001"))],
                json={},
            )
        if path == LOGIN_PATH:
            return httpx.Response(
                200,
                headers=[
                    ("Set-Cookie", _set_cookie("access_token", "AAA")),
                    ("Set-Cookie", _set_cookie("refresh_token", "BBB")),
                ],
                json={
                    "access_token": "AAA",
                    "refresh_token": "BBB",
                    "expires_in": 1800,
                },
            )
        if require_bearer:
            auth = request.headers.get("Authorization", "")
            assert auth.startswith("Bearer "), f"missing bearer on {path!r}"
        for prefix, fn in extras.items():
            if path.startswith(prefix):
                return fn(request)
        return httpx.Response(404, text=f"unhandled mock path {path!r}")

    return handler


# ---------------------------------------------------------------------------
# Construction & credential resolution
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_explicit_args_take_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("INPI_USERNAME", raising=False)
        monkeypatch.delenv("INPI_PASSWORD", raising=False)
        client = InpiPiClient(username="alice", password="hunter2")
        assert client._username == "alice"
        assert client._password == "hunter2"  # noqa: S105 — placeholder

    def test_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("INPI_USERNAME", "env-user")
        monkeypatch.setenv("INPI_PASSWORD", "env-pass")
        client = InpiPiClient()
        assert client._username == "env-user"
        assert client._password == "env-pass"  # noqa: S105

    def test_missing_credentials_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("INPI_USERNAME", raising=False)
        monkeypatch.delenv("INPI_PASSWORD", raising=False)
        with pytest.raises(ConfigurationError) as exc:
            InpiPiClient()
        assert "INPI_USERNAME" in str(exc.value)
        assert "INPI_PASSWORD" in str(exc.value)

    def test_partial_credentials_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("INPI_USERNAME", "only-user")
        monkeypatch.delenv("INPI_PASSWORD", raising=False)
        with pytest.raises(ConfigurationError):
            InpiPiClient()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestCoerceList:
    def test_string_wraps_to_list(self) -> None:
        assert _coerce_list("X") == ["X"]

    def test_list_unchanged(self) -> None:
        assert _coerce_list(["A", "B"]) == ["A", "B"]

    def test_tuple_coerces_to_str_list(self) -> None:
        assert _coerce_list(("A", "B")) == ["A", "B"]


class TestSolrEscape:
    def test_plain_value_unquoted(self) -> None:
        assert _solr_escape("Apple") == "Apple"

    def test_whitespace_quoted(self) -> None:
        assert _solr_escape("Apple Inc") == '"Apple Inc"'

    def test_inner_quotes_escaped(self) -> None:
        assert _solr_escape('a"b') == '"a\\"b"'

    def test_reserved_chars_quoted(self) -> None:
        # Colon is a reserved Lucene char
        assert _solr_escape("a:b") == '"a:b"'

    def test_backslash_doubled(self) -> None:
        assert _solr_escape("a\\b") == '"a\\\\b"'


class TestBuildSolrQuery:
    def test_default_is_match_all(self) -> None:
        assert _build_solr_query() == "*:*"

    def test_q_only(self) -> None:
        assert _build_solr_query(q="Apple") == "Apple"

    def test_q_strip_whitespace(self) -> None:
        assert _build_solr_query(q="  Apple  ") == "Apple"

    def test_nice_classes_or(self) -> None:
        out = _build_solr_query(q="X", nice_class=["9", "42"])
        assert out == "X AND (ClassNumber:9 OR ClassNumber:42)"

    def test_locarno_classes_or(self) -> None:
        out = _build_solr_query(locarno_class=["0601", "0602"])
        assert out == "(ClassNumber:0601 OR ClassNumber:0602)"

    def test_applicant_with_whitespace_quoted(self) -> None:
        out = _build_solr_query(applicant="Apple Inc")
        assert out == 'DEPOSANT:"Apple Inc"'

    def test_status_field(self) -> None:
        out = _build_solr_query(status="registered")
        assert out == "MarkCurrentStatusCode:registered"

    def test_date_range_both(self) -> None:
        out = _build_solr_query(date_from="20100101", date_to="20201231")
        assert "ApplicationDate:[20100101 TO 20201231]" in out

    def test_date_range_open_lower(self) -> None:
        out = _build_solr_query(date_to="20201231")
        assert "ApplicationDate:[* TO 20201231]" in out

    def test_date_range_open_upper(self) -> None:
        out = _build_solr_query(date_from="20100101")
        assert "ApplicationDate:[20100101 TO *]" in out

    def test_multi_clause_ands(self) -> None:
        out = _build_solr_query(
            q="Apple",
            nice_class=["9"],
            applicant="Acme",
            status="registered",
        )
        parts = out.split(" AND ")
        assert parts[0] == "Apple"
        # remaining clauses present in any order so long as separated by AND
        assert "(ClassNumber:9)" in out
        assert "DEPOSANT:Acme" in out
        assert "MarkCurrentStatusCode:registered" in out


# ---------------------------------------------------------------------------
# Throttle with injectable clock
# ---------------------------------------------------------------------------


class _FakeClock:
    """Deterministic monotonic-style clock with controlled advance."""

    def __init__(self, start: float = 1_000.0) -> None:
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


class TestSlidingWindowThrottle:
    @pytest.mark.asyncio
    async def test_under_cap_no_wait(self) -> None:
        """First N-1 acquires within window return without sleeping."""
        clock = _FakeClock()
        throttle = _SlidingWindowThrottle(max_requests=3, window_seconds=60.0, clock=clock)
        # First three should be instant
        for _ in range(3):
            await throttle.acquire()
        # Throttle does NOT block until the cap is exceeded — by this
        # point the deque holds the 3 timestamps it has logged.
        assert len(throttle._timestamps) == 3

    @pytest.mark.asyncio
    async def test_eleven_rapid_calls_force_wait(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """10 cap → call #11 inside the window forces a sleep ~= window_seconds.

        With ``max_requests=10`` and ``window_seconds=60`` and no real
        clock advance, the throttle must call ``asyncio.sleep`` once for
        the 11th acquire. We intercept ``asyncio.sleep`` to record the
        wait without actually sleeping.
        """
        clock = _FakeClock()
        sleep_calls: list[float] = []

        async def _fake_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)
            # Advance the clock so the throttle exits its loop on the next iter
            clock.advance(seconds)

        monkeypatch.setattr("patent_client_agents.inpi_pi.client.asyncio.sleep", _fake_sleep)

        throttle = _SlidingWindowThrottle(max_requests=10, window_seconds=60.0, clock=clock)
        # First 10 are free
        for _ in range(10):
            await throttle.acquire()
        # 11th forces a wait
        await throttle.acquire()

        assert sleep_calls, "throttle did not invoke sleep on 11th acquire"
        # First timestamp was at t=1000; window is 60s; 11th call still at
        # t=1000 → wait_for ~= 60s (within tiny float drift).
        assert 59.0 <= sleep_calls[0] <= 61.0

    @pytest.mark.asyncio
    async def test_old_entries_drop_after_window(self) -> None:
        """After advancing past the window, old timestamps are pruned."""
        clock = _FakeClock()
        throttle = _SlidingWindowThrottle(max_requests=3, window_seconds=60.0, clock=clock)
        for _ in range(3):
            await throttle.acquire()
        clock.advance(120.0)  # walk past the window
        await throttle.acquire()
        # The first three should be dropped; only the most-recent remains
        assert len(throttle._timestamps) == 1

    def test_default_clock_is_time_monotonic(self) -> None:
        """No clock arg → uses ``time.monotonic``."""
        import time as _time

        throttle = _SlidingWindowThrottle()
        assert throttle._clock is _time.monotonic


# ---------------------------------------------------------------------------
# XML notice parsing
# ---------------------------------------------------------------------------


class TestParseSt66Notice:
    def test_parses_xml_to_trademark_row(self) -> None:
        xml = (FIXTURES_DIR / "tm_notice_st66.xml").read_bytes()
        row = InpiPiClient._parse_st66_notice(xml)
        assert isinstance(row, InpiTrademarkRow)
        assert row.application_number == "4216963"
        assert row.mark_text == "EXAMPLE"
        assert row.applicant_names == ["ACME SAS", "ACME Holdings"]
        assert row.nice_classes == ["9", "42"]
        assert row.status == "registered"

    def test_dates_round_trip(self) -> None:
        xml = (FIXTURES_DIR / "tm_notice_st66.xml").read_bytes()
        row = InpiPiClient._parse_st66_notice(xml)
        assert row.application_date is not None
        assert row.application_date.year == 2015
        assert row.registration_date is not None
        assert row.expiry_date is not None
        assert row.expiry_date.year == 2026

    def test_empty_holdername_is_ignored(self) -> None:
        """Empty ``<HolderName></HolderName>`` → empty list, not [''] ."""
        xml = (FIXTURES_DIR / "tm_notice_st66.xml").read_bytes()
        row = InpiPiClient._parse_st66_notice(xml)
        assert row.holder_names == []

    def test_invalid_xml_raises(self) -> None:
        with pytest.raises(ET.ParseError):
            InpiPiClient._parse_st66_notice(b"<not-xml")

    def test_missing_record_element_raises(self) -> None:
        # XML root contains no recognized notice element
        bad = b"<root>plain</root>"
        # _xml_to_dict returns 'plain' (a string); the dispatcher then sees
        # a non-dict and raises ValidationError. _parse_st66 first probes
        # for "TradeMark" key in dict; here the entire payload is a str.
        with pytest.raises(ValidationError):
            InpiPiClient._parse_st66_notice(bad)


class TestParseSt86Notice:
    def test_parses_xml_to_design_row(self) -> None:
        xml = (FIXTURES_DIR / "design_notice_st86.xml").read_bytes()
        row = InpiPiClient._parse_st86_notice(xml)
        assert isinstance(row, InpiDesignRow)
        assert row.application_number == "FR20140182"
        assert row.design_reference == "001"
        assert row.design_title == "Chaise pliante"
        assert row.applicant_names == ["Mobilier France"]
        assert row.designer_names == ["Jean Designer"]
        assert row.loc_classes == ["0601"]

    def test_repeated_image_urls_become_list(self) -> None:
        xml = (FIXTURES_DIR / "design_notice_st86.xml").read_bytes()
        row = InpiPiClient._parse_st86_notice(xml)
        assert len(row.image_urls) == 2
        assert all("/dessins/image/" in u for u in row.image_urls)

    def test_invalid_xml_raises(self) -> None:
        with pytest.raises(ET.ParseError):
            InpiPiClient._parse_st86_notice(b"<not-xml")


class TestXmlToDict:
    def test_strip_namespace(self) -> None:
        assert InpiPiClient._strip_namespace("{urn:x}Foo") == "Foo"
        assert InpiPiClient._strip_namespace("Foo") == "Foo"

    def test_empty_leaf_returns_none(self) -> None:
        elem = ET.fromstring("<root><x></x></root>")
        out = InpiPiClient._xml_to_dict(elem)
        assert out == {"x": None}


# ---------------------------------------------------------------------------
# Search envelope parsing
# ---------------------------------------------------------------------------


class TestParseSearchEnvelope:
    def test_bare_list_falls_back(self) -> None:
        rows, total = InpiPiClient._parse_search_envelope([{"a": 1}, {"b": 2}])
        assert len(rows) == 2
        assert total == 2

    def test_hits_envelope(self) -> None:
        body = {"total": 5, "hits": [{"a": 1}]}
        rows, total = InpiPiClient._parse_search_envelope(body)
        assert rows == [{"a": 1}]
        assert total == 5

    def test_rows_envelope(self) -> None:
        body = {"totalCount": 3, "rows": [{"a": 1}]}
        rows, total = InpiPiClient._parse_search_envelope(body)
        assert rows == [{"a": 1}]
        assert total == 3

    def test_numfound_envelope(self) -> None:
        body = {"numFound": 7, "docs": [{"a": 1}]}
        rows, total = InpiPiClient._parse_search_envelope(body)
        assert rows == [{"a": 1}]
        assert total == 7

    def test_unknown_envelope_returns_empty(self) -> None:
        rows, total = InpiPiClient._parse_search_envelope({"surprise": []})
        assert rows == []
        assert total is None

    def test_non_dict_non_list_returns_empty(self) -> None:
        rows, total = InpiPiClient._parse_search_envelope("nope")
        assert rows == []
        assert total is None


# ---------------------------------------------------------------------------
# Endpoint integration via MockTransport
# ---------------------------------------------------------------------------


def _make_client(handler: Callable[[httpx.Request], httpx.Response]) -> InpiPiClient:
    """Build an InpiPiClient backed by a mocked transport."""
    transport = httpx.MockTransport(handler)
    httpx_client = httpx.AsyncClient(transport=transport, base_url=BASE_URL)
    return InpiPiClient(username="u", password="p", client=httpx_client)


@pytest.mark.asyncio
async def test_search_trademarks_happy_path() -> None:
    body = json.loads((FIXTURES_DIR / "tm_search_2hits.json").read_text())

    def search_handler(request: httpx.Request) -> httpx.Response:
        # Confirm SolR query + pagination params plumbed through
        params = dict(request.url.params)
        assert "q" in params
        return httpx.Response(200, json=body)

    handler = _make_auth_handler({"/services/apidiffusion/api/marques/search": search_handler})
    async with _make_client(handler) as client:
        rows, total = await client.search_trademarks("EXAMPLE", nice_class=["9"])
    assert total == 2
    assert len(rows) == 2
    assert rows[0].mark_text == "EXAMPLE"
    assert rows[0].applicant_names == ["ACME SAS", "ACME Holdings"]


@pytest.mark.asyncio
async def test_search_trademarks_empty_result() -> None:
    body = json.loads((FIXTURES_DIR / "tm_search_empty.json").read_text())

    def search_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    handler = _make_auth_handler({"/services/apidiffusion/api/marques/search": search_handler})
    async with _make_client(handler) as client:
        rows, total = await client.search_trademarks()
    assert rows == []
    assert total == 0


@pytest.mark.asyncio
async def test_search_trademarks_offset_overflow_raises() -> None:
    async with _make_client(_make_auth_handler({})) as client:
        with pytest.raises(ValidationError):
            await client.search_trademarks(offset=MAX_OFFSET + 1)


@pytest.mark.asyncio
async def test_search_trademarks_limit_overflow_raises() -> None:
    async with _make_client(_make_auth_handler({})) as client:
        with pytest.raises(ValidationError):
            await client.search_trademarks(limit=999)


@pytest.mark.asyncio
async def test_search_trademarks_negative_offset_raises() -> None:
    async with _make_client(_make_auth_handler({})) as client:
        with pytest.raises(ValidationError):
            await client.search_trademarks(offset=-1)


@pytest.mark.asyncio
async def test_search_trademarks_zero_limit_raises() -> None:
    async with _make_client(_make_auth_handler({})) as client:
        with pytest.raises(ValidationError):
            await client.search_trademarks(limit=0)


@pytest.mark.asyncio
async def test_get_trademark_single_json() -> None:
    # JSON body matching one hit from the search fixture
    notice_body = {
        "ApplicationNumber": "4216963",
        "Mark": "EXAMPLE",
        "ApplicantName": ["ACME SAS"],
        "MarkCurrentStatusCode": "registered",
    }

    def notice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers=[("Content-Type", "application/json")],
            json=notice_body,
        )

    handler = _make_auth_handler({"/services/apidiffusion/api/marques/": notice_handler})
    async with _make_client(handler) as client:
        results = await client.get_trademark("4216963")
    assert len(results) == 1
    assert results[0].application_number == "4216963"


@pytest.mark.asyncio
async def test_get_trademark_serial_list_calls() -> None:
    notice_body = {
        "ApplicationNumber": "X",
        "Mark": "Y",
    }

    calls: list[str] = []

    def notice_handler(request: httpx.Request) -> httpx.Response:
        # Path looks like /services/apidiffusion/api/marques/<appno>
        calls.append(request.url.path.rsplit("/", 1)[-1])
        notice_body["ApplicationNumber"] = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=dict(notice_body))

    handler = _make_auth_handler({"/services/apidiffusion/api/marques/": notice_handler})
    async with _make_client(handler) as client:
        results = await client.get_trademark(["A", "B", "C"])
    assert calls == ["A", "B", "C"]
    assert [r.application_number for r in results] == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_get_trademark_xml_body_parsed() -> None:
    xml_bytes = (FIXTURES_DIR / "tm_notice_st66.xml").read_bytes()

    def notice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers=[("Content-Type", "application/xml")],
            content=xml_bytes,
        )

    handler = _make_auth_handler({"/services/apidiffusion/api/marques/": notice_handler})
    async with _make_client(handler) as client:
        results = await client.get_trademark("4216963")
    assert results[0].applicant_names == ["ACME SAS", "ACME Holdings"]


@pytest.mark.asyncio
async def test_get_trademark_empty_list_raises() -> None:
    async with _make_client(_make_auth_handler({})) as client:
        with pytest.raises(ValidationError, match="at least one"):
            await client.get_trademark([])


@pytest.mark.asyncio
async def test_get_trademark_too_many_raises() -> None:
    async with _make_client(_make_auth_handler({})) as client:
        with pytest.raises(ValidationError, match="at most"):
            await client.get_trademark([str(i) for i in range(MAX_LIST_ACCEPT + 1)])


@pytest.mark.asyncio
async def test_search_designs_happy_path() -> None:
    body = json.loads((FIXTURES_DIR / "design_search_2hits.json").read_text())

    def search_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    handler = _make_auth_handler({"/services/apidiffusion/api/dessins/search": search_handler})
    async with _make_client(handler) as client:
        rows, total = await client.search_designs(locarno_class=["0601"])
    assert total == 2
    assert rows[0].design_title == "Chaise pliante"
    assert rows[0].design_reference == "001"
    assert len(rows[0].image_urls) == 2


@pytest.mark.asyncio
async def test_search_designs_offset_overflow_raises() -> None:
    async with _make_client(_make_auth_handler({})) as client:
        with pytest.raises(ValidationError):
            await client.search_designs(offset=MAX_OFFSET + 1)


@pytest.mark.asyncio
async def test_search_designs_limit_overflow_raises() -> None:
    async with _make_client(_make_auth_handler({})) as client:
        with pytest.raises(ValidationError):
            await client.search_designs(limit=0)


@pytest.mark.asyncio
async def test_get_design_xml_body() -> None:
    xml_bytes = (FIXTURES_DIR / "design_notice_st86.xml").read_bytes()

    def notice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers=[("Content-Type", "application/xml")],
            content=xml_bytes,
        )

    handler = _make_auth_handler({"/services/apidiffusion/api/dessins/": notice_handler})
    async with _make_client(handler) as client:
        results = await client.get_design("FR20140182")
    assert results[0].design_reference == "001"


@pytest.mark.asyncio
async def test_get_design_empty_list_raises() -> None:
    async with _make_client(_make_auth_handler({})) as client:
        with pytest.raises(ValidationError, match="at least one"):
            await client.get_design([])


@pytest.mark.asyncio
async def test_get_design_too_many_raises() -> None:
    async with _make_client(_make_auth_handler({})) as client:
        with pytest.raises(ValidationError, match="at most"):
            await client.get_design([str(i) for i in range(MAX_LIST_ACCEPT + 1)])


# ---------------------------------------------------------------------------
# Auth retry behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_401_retries_with_fresh_session() -> None:
    """A 401 on a search request invalidates the session and retries once."""
    body = json.loads((FIXTURES_DIR / "tm_search_empty.json").read_text())
    attempt_counter = {"n": 0}

    def search_handler(request: httpx.Request) -> httpx.Response:
        attempt_counter["n"] += 1
        if attempt_counter["n"] == 1:
            return httpx.Response(401, text="expired")
        return httpx.Response(200, json=body)

    handler = _make_auth_handler(
        {"/services/apidiffusion/api/marques/search": search_handler},
        require_bearer=False,  # 401 path still tested
    )
    async with _make_client(handler) as client:
        rows, total = await client.search_trademarks()
    assert rows == []
    assert total == 0
    assert attempt_counter["n"] >= 2  # at least one retry


@pytest.mark.asyncio
async def test_429_raises_rate_limit_error() -> None:
    def search_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="throttled")

    handler = _make_auth_handler({"/services/apidiffusion/api/marques/search": search_handler})
    async with _make_client(handler) as client:
        with pytest.raises(RateLimitError):
            await client.search_trademarks()


@pytest.mark.asyncio
async def test_5xx_raises_api_error() -> None:
    def search_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    handler = _make_auth_handler({"/services/apidiffusion/api/marques/search": search_handler})
    async with _make_client(handler) as client:
        with pytest.raises(ApiError):
            await client.search_trademarks()


@pytest.mark.asyncio
async def test_get_design_non_json_non_xml_body_raises() -> None:
    def notice_handler(request: httpx.Request) -> httpx.Response:
        # Content-type says text/plain → ``_coerce_notice`` falls into
        # the json branch and raises ApiError on parse failure.
        return httpx.Response(
            200,
            headers=[("Content-Type", "text/plain")],
            content=b"not-json-or-xml",
        )

    handler = _make_auth_handler({"/services/apidiffusion/api/dessins/": notice_handler})
    async with _make_client(handler) as client:
        with pytest.raises(ApiError):
            await client.get_design("FR20140182")


@pytest.mark.asyncio
async def test_session_reuse_skips_relogin(monkeypatch: pytest.MonkeyPatch) -> None:
    """A second search reuses the cached session — no second login call."""
    body = json.loads((FIXTURES_DIR / "tm_search_empty.json").read_text())
    login_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == BOOTSTRAP_PATH:
            return httpx.Response(
                200,
                headers=[("Set-Cookie", _set_cookie(XSRF_COOKIE_NAME, "xsrf"))],
            )
        if path == LOGIN_PATH:
            login_calls["n"] += 1
            return httpx.Response(
                200,
                headers=[
                    ("Set-Cookie", _set_cookie("access_token", "AAA")),
                    ("Set-Cookie", _set_cookie("refresh_token", "BBB")),
                ],
                json={"access_token": "AAA", "refresh_token": "BBB", "expires_in": 1800},
            )
        return httpx.Response(200, json=body)

    async with _make_client(handler) as client:
        await client.search_trademarks()
        await client.search_trademarks()
    assert login_calls["n"] == 1


@pytest.mark.asyncio
async def test_invalidate_session_drops_cache() -> None:
    async with _make_client(_make_auth_handler({})) as client:
        # Force a session warmup
        await client._ensure_session()
        assert client._session is not None
        await client._invalidate_session()
        assert client._session is None


# ---------------------------------------------------------------------------
# Pydantic model behaviour shared across both rows
# ---------------------------------------------------------------------------


class TestModelBehaviorViaClient:
    def test_search_envelope_dict_alone_yields_no_rows(self) -> None:
        """{'docs': [...]} → rows captured; {'unknown': [...]} → empty."""
        rows, _ = InpiPiClient._parse_search_envelope({"docs": [{"x": 1}]})
        assert rows == [{"x": 1}]

    def test_total_coerced_to_int(self) -> None:
        rows, total = InpiPiClient._parse_search_envelope({"total": 5.0, "hits": []})
        assert total == 5


# Silence ruff: imported helper is used in TestSlidingWindowThrottle indirectly.
_ = asyncio
