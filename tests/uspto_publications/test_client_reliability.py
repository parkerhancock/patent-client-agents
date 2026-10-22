"""Reliability regressions for the USPTO Patent Public Search client.

Every client test drives the public ``PublicSearchClient`` methods against
``FakePpubs``, an in-process PPUBS served through ``httpx2.MockTransport``.
The real session bootstrap, session refresh, caseId rewrite, typed-error
mapping and retry decorator all run; only the network and the retry backoff
are replaced.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, call, patch

import httpx2
import pytest
import tenacity

import mcp_data_core.resilience as resilience
from mcp_data_core.exceptions import (
    RateLimitError,
    RetryableAuthenticationError,
    ServerError,
    ValidationError,
)
from patent_client_agents.uspto_publications.client import (
    PublicSearchClient,
    PublicSearchError,
    check_query_syntax,
)
from tests.uspto_publications.fake_ppubs import (
    BASE,
    COUNTS,
    HIGHLIGHT,
    SEARCH,
    SESSION,
    FakePpubs,
)


@pytest.fixture(autouse=True)
def _no_retry_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the real retry policy (attempts, retryable errors) but skip backoff."""
    real = resilience.default_retryer

    def no_wait(**kwargs: Any) -> tenacity.AsyncRetrying:
        retryer = real(**kwargs)
        retryer.wait = tenacity.wait_none()
        return retryer

    monkeypatch.setattr(resilience, "default_retryer", no_wait)


@pytest.fixture
def ppubs() -> FakePpubs:
    return FakePpubs()


def _client(ppubs: FakePpubs) -> PublicSearchClient:
    return PublicSearchClient(transport=ppubs.transport())


@pytest.mark.asyncio
async def test_search_bootstraps_session_and_sends_its_token_and_case_id(
    ppubs: FakePpubs,
) -> None:
    async with _client(ppubs) as client:
        page = await client.search_biblio(query="neural.CLM.")

    assert [d.publication_number for d in page.docs] == ["20230123456"]
    assert page.num_documents == 1
    assert [str(r.url) for r in ppubs.requests] == [
        f"{BASE}/pubwebapp/",
        f"{BASE}{SESSION}",
        f"{BASE}{COUNTS}",
        f"{BASE}{SEARCH}",
    ]
    counts, search = ppubs.hits(COUNTS)[0], ppubs.hits(SEARCH)[0]
    assert counts.headers["X-Access-Token"] == "token-123"
    assert json.loads(counts.content)["caseId"] == 123
    assert json.loads(search.content)["query"]["caseId"] == 123


@pytest.mark.asyncio
async def test_request_retries_transient_server_error(ppubs: FakePpubs) -> None:
    ppubs.queue(COUNTS, httpx2.Response(500))

    async with _client(ppubs) as client:
        page = await client.search_biblio(query="neural.CLM.")

    assert len(page.docs) == 1
    assert len(ppubs.hits(COUNTS)) == 2


@pytest.mark.asyncio
async def test_request_retries_transport_timeout(ppubs: FakePpubs) -> None:
    ppubs.queue(SEARCH, httpx2.ReadTimeout("PPUBS read timed out"))

    async with _client(ppubs) as client:
        page = await client.search_biblio(query="neural.CLM.")

    assert len(page.docs) == 1
    assert len(ppubs.hits(SEARCH)) == 2


@pytest.mark.asyncio
async def test_persistent_403_is_typed_retryable_authentication_error(ppubs: FakePpubs) -> None:
    ppubs.always(COUNTS, httpx2.Response(403))

    async with _client(ppubs) as client:
        with pytest.raises(RetryableAuthenticationError):
            await client.search_biblio(query="neural.CLM.")

    # Bootstrap, then one refresh per request attempt (4 attempts), each
    # attempt sending the request before and after its refresh.
    assert len(ppubs.hits(SESSION)) == 1 + 4
    assert len(ppubs.hits(COUNTS)) == 4 * 2
    assert ppubs.hits(SEARCH) == []


@pytest.mark.asyncio
async def test_request_uses_one_session_refresh_attempt_per_request_attempt(
    ppubs: FakePpubs,
) -> None:
    async with _client(ppubs) as client:
        await client.search_biblio(query="warm.CLM.")
        ppubs.always(COUNTS, httpx2.Response(403))
        ppubs.always(SESSION, httpx2.Response(403))
        with pytest.raises(RetryableAuthenticationError, match="session bootstrap"):
            await client.search_biblio(query="neural.CLM.")

    # The failed refresh ends the attempt; it is not retried inside it.
    assert len(ppubs.hits(SESSION)) == 1 + 4
    assert len(ppubs.hits(COUNTS)) == 1 + 4


@pytest.mark.asyncio
async def test_429_is_typed_rate_limit_error(ppubs: FakePpubs) -> None:
    ppubs.always(COUNTS, httpx2.Response(429, headers={"x-rate-limit-retry-after-seconds": "3"}))

    with patch("asyncio.sleep", new=AsyncMock()) as sleep:
        async with _client(ppubs) as client:
            with pytest.raises(RateLimitError) as exc_info:
                await client.search_biblio(query="neural.CLM.")

    assert exc_info.value.retry_after == 3
    assert len(ppubs.hits(COUNTS)) == 4
    # PPUBS's own retry-after header is honored before every attempt gives up.
    assert sleep.await_args_list.count(call(3.0)) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "nested"),
    [(COUNTS, False), (SEARCH, True)],
    ids=["top-level-case-id", "nested-case-id"],
)
async def test_request_updates_case_id_after_session_refresh(
    ppubs: FakePpubs, path: str, nested: bool
) -> None:
    async def expire_then_reject(request: httpx2.Request) -> httpx2.Response:
        ppubs.expire_session()
        return httpx2.Response(403)

    ppubs.queue(path, expire_then_reject)

    async with _client(ppubs) as client:
        page = await client.search_biblio(query="neural.CLM.")

    assert len(page.docs) == 1
    assert len(ppubs.hits(SESSION)) == 2
    stale, retried = ppubs.hits(path)
    body = json.loads(retried.content)
    assert (body["query"]["caseId"] if nested else body["caseId"]) == 456
    assert stale.headers["X-Access-Token"] == "token-123"
    assert retried.headers["X-Access-Token"] == "token-456"


@pytest.mark.asyncio
async def test_document_fetch_recovers_from_expired_session(ppubs: FakePpubs) -> None:
    async with _client(ppubs) as client:
        await client.search_biblio(query="warm.CLM.")
        ppubs.expire_session()
        document = await client.get_document("US-20230123456-A1", source="US-PGPUB")

    assert document.publication_number == "20230123456"
    assert len(ppubs.hits(SESSION)) == 2
    stale, retried = ppubs.hits(f"{HIGHLIGHT}/US-20230123456-A1")
    assert stale.headers["X-Access-Token"] == "token-123"
    assert retried.headers["X-Access-Token"] == "token-456"


async def _two_requests_in_flight_then_403(ppubs: FakePpubs) -> None:
    """Make the next two COUNTS calls both arrive before either is rejected."""
    both_in_flight = asyncio.Event()
    arrived = 0

    async def reject_when_both_arrived(request: httpx2.Request) -> httpx2.Response:
        nonlocal arrived
        arrived += 1
        if arrived == 2:
            both_in_flight.set()
        await both_in_flight.wait()
        return httpx2.Response(403)

    ppubs.queue(COUNTS, reject_when_both_arrived, reject_when_both_arrived)


@pytest.mark.asyncio
async def test_concurrent_403s_share_one_refreshed_session(ppubs: FakePpubs) -> None:
    async with _client(ppubs) as client:
        await client.search_biblio(query="warm.CLM.")
        ppubs.expire_session()
        await _two_requests_in_flight_then_403(ppubs)

        pages = await asyncio.gather(
            client.search_biblio(query="neural.CLM."),
            client.search_biblio(query="network.CLM."),
        )

    assert [len(p.docs) for p in pages] == [1, 1]
    # Warm-up bootstrap plus exactly one refresh shared by both requests.
    assert len(ppubs.hits(SESSION)) == 2
    retried = ppubs.hits(COUNTS)[-2:]
    assert [json.loads(r.content)["caseId"] for r in retried] == [456, 456]


@pytest.mark.asyncio
async def test_waiting_request_recovers_after_concurrent_refresh_failure(
    ppubs: FakePpubs,
) -> None:
    async with _client(ppubs) as client:
        await client.search_biblio(query="warm.CLM.")
        ppubs.expire_session()
        await _two_requests_in_flight_then_403(ppubs)
        ppubs.queue(SESSION, httpx2.Response(403))

        pages = await asyncio.gather(
            client.search_biblio(query="neural.CLM."),
            client.search_biblio(query="network.CLM."),
        )

    assert [len(p.docs) for p in pages] == [1, 1]
    # Each request's accepted call (the last one per query) left the expired
    # caseId behind; the fake only answers 200 for the then-current session.
    last_counts = {json.loads(r.content)["q"]: r for r in ppubs.hits(COUNTS)}
    assert json.loads(last_counts["neural.CLM."].content)["caseId"] != 123
    assert json.loads(last_counts["network.CLM."].content)["caseId"] != 123


@pytest.mark.asyncio
async def test_failed_refresh_does_not_force_an_extra_session(ppubs: FakePpubs) -> None:
    async with _client(ppubs) as client:
        await client.search_biblio(query="warm.CLM.")
        ppubs.expire_session()
        await _two_requests_in_flight_then_403(ppubs)
        ppubs.queue(SESSION, httpx2.Response(403))

        await asyncio.gather(
            client.search_biblio(query="neural.CLM."),
            client.search_biblio(query="network.CLM."),
        )

    # Warm-up bootstrap, the failed refresh, and one successful refresh.
    assert len(ppubs.hits(SESSION)) == 3


@pytest.mark.asyncio
async def test_session_bootstrap_retries_server_error(ppubs: FakePpubs) -> None:
    ppubs.queue(SESSION, httpx2.Response(500))

    async with _client(ppubs) as client:
        page = await client.search_biblio(query="neural.CLM.")

    assert len(page.docs) == 1
    assert len(ppubs.hits(SESSION)) == 2
    assert json.loads(ppubs.hits(COUNTS)[0].content)["caseId"] == 123


@pytest.mark.asyncio
async def test_search_caps_one_upstream_page_at_twenty(ppubs: FakePpubs) -> None:
    async with _client(ppubs) as client:
        await client.search_biblio(query="neural.CLM.", limit=25)

    assert json.loads(ppubs.hits(SEARCH)[0].content)["pageCount"] == 20


@pytest.mark.asyncio
async def test_search_rejects_non_positive_limit_before_network_call(ppubs: FakePpubs) -> None:
    async with _client(ppubs) as client:
        with pytest.raises(ValidationError, match="limit must be at least 1"):
            await client.search_biblio(query="neural.CLM.", limit=0)

    assert ppubs.requests == []


# Query pre-flight and upstream error context (#92). Cases mirror live PPUBS
# behavior observed on 2026-10-07.


@pytest.mark.parametrize(
    "query",
    [
        'motion ADJ compensat$ AND "reference picture"',
        "neural and network",
        "interpolation adj filter$",
        "NOT neural",
        "(neural ADJ2 network) SAME picture",
        "(without OR (avoid$ ADJ stor$))",
        "@AD>=19760101<=20120112 AND neural.CLM.",
    ],
)
def test_query_syntax_accepts_valid_queries(query: str) -> None:
    check_query_syntax(query)


@pytest.mark.parametrize(
    "query,match",
    [
        ('"motion compensat$" AND "reference picture"', "motion ADJ compensat\\$"),
        ('"neural networ?"', "wildcards inside quoted phrases"),
        ("(without OR (not ADJ stor$) OR avoid$)", "'not' as the NOT operator.*'ADJ'"),
        ("neural AND NOT network", "'AND' as the AND operator"),
        ("neural AND", "ends a query or group"),
        ("(neural OR) AND x", "'OR' as the OR operator.*ends"),
        ("(or neural) AND x", "starts a query or group"),
    ],
)
def test_query_syntax_names_the_problem(query: str, match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        check_query_syntax(query)


@pytest.mark.asyncio
async def test_search_stops_on_counts_error_payload(ppubs: FakePpubs) -> None:
    ppubs.queue(
        COUNTS,
        httpx2.Response(
            200, json={"error": {"errorCode": 121, "errorMessage": "Cannot start a group"}}
        ),
    )

    async with _client(ppubs) as client:
        with pytest.raises(PublicSearchError, match="Error #121: Cannot start a group"):
            await client.search_biblio(query="neural")

    assert len(ppubs.hits(COUNTS)) == 1
    assert ppubs.hits(SEARCH) == []


@pytest.mark.asyncio
async def test_counts_server_error_explains_query_was_not_run(ppubs: FakePpubs) -> None:
    body = '{"status":"INTERNAL_SERVER_ERROR","developerMessage":"Unable to Process"}'
    ppubs.always(COUNTS, httpx2.Response(500, text=body))

    async with _client(ppubs) as client:
        with pytest.raises(
            PublicSearchError, match="at /counts, so no search ran.*Unable to Process"
        ):
            await client.search_biblio(query="neural")

    assert len(ppubs.hits(COUNTS)) == 4
    assert ppubs.hits(SEARCH) == []


@pytest.mark.asyncio
async def test_search_server_error_after_counts_stays_retryable(ppubs: FakePpubs) -> None:
    ppubs.queue(COUNTS, httpx2.Response(200, json={"numResults": 214}))
    ppubs.always(SEARCH, httpx2.Response(500, text="{}"))

    async with _client(ppubs) as client:
        with pytest.raises(ServerError, match="accepted the query at /counts \\(214 documents\\)"):
            await client.search_biblio(query="neural")

    assert len(ppubs.hits(SEARCH)) == 4
