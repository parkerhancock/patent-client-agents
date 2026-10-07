"""Reliability regressions for the USPTO Patent Public Search client."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from mcp_data_core.exceptions import (
    RateLimitError,
    RetryableAuthenticationError,
    ValidationError,
)
from patent_client_agents.uspto_publications.client import PublicSearchClient


def _response(status_code: int, *, json: object | None = None) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=json,
        request=httpx.Request("POST", "https://ppubs.uspto.gov/api/test"),
    )


@pytest.mark.asyncio
async def test_request_retries_transient_server_error() -> None:
    http = AsyncMock(spec=httpx.AsyncClient)
    http.request = AsyncMock(side_effect=[_response(500), _response(200, json={})])
    client = PublicSearchClient(client=http)

    response = await client._request("POST", "https://ppubs.uspto.gov/api/test")

    assert response.status_code == 200
    assert http.request.await_count == 2


@pytest.mark.asyncio
async def test_request_retries_transport_timeout() -> None:
    http = AsyncMock(spec=httpx.AsyncClient)
    http.request = AsyncMock(
        side_effect=[
            httpx.ReadTimeout("PPUBS read timed out"),
            _response(200, json={}),
        ]
    )
    client = PublicSearchClient(client=http)

    response = await client._request("POST", "https://ppubs.uspto.gov/api/test")

    assert response.status_code == 200
    assert http.request.await_count == 2


@pytest.mark.asyncio
async def test_persistent_403_is_typed_retryable_authentication_error() -> None:
    http = AsyncMock(spec=httpx.AsyncClient)
    http.request = AsyncMock(side_effect=[_response(403), _response(403)])
    client = PublicSearchClient(client=http)
    client._refresh_session_once = AsyncMock()

    with pytest.raises(RetryableAuthenticationError):
        await client._request.__wrapped__(client, "POST", "https://ppubs.uspto.gov/api/test")

    client._refresh_session_once.assert_awaited_once()


@pytest.mark.asyncio
async def test_429_is_typed_rate_limit_error() -> None:
    http = AsyncMock(spec=httpx.AsyncClient)
    http.request = AsyncMock(
        return_value=httpx.Response(
            429,
            headers={"x-rate-limit-retry-after-seconds": "3"},
            request=httpx.Request("POST", "https://ppubs.uspto.gov/api/test"),
        )
    )
    client = PublicSearchClient(client=http)

    with patch(
        "patent_client_agents.uspto_publications.client.asyncio.sleep",
        new=AsyncMock(),
    ) as sleep:
        with pytest.raises(RateLimitError) as exc_info:
            await client._request.__wrapped__(client, "POST", "https://ppubs.uspto.gov/api/test")

    assert exc_info.value.retry_after == 3
    sleep.assert_awaited_once_with(3)


@pytest.mark.asyncio
@pytest.mark.parametrize("nested", [False, True])
async def test_request_updates_case_id_after_session_refresh(nested: bool) -> None:
    http = AsyncMock(spec=httpx.AsyncClient)
    http.request = AsyncMock(side_effect=[_response(403), _response(200, json={})])
    client = PublicSearchClient(client=http)
    client._case_id = 123

    async def refresh() -> None:
        client._case_id = 456

    client._refresh_session_once = AsyncMock(side_effect=refresh)
    payload = {"query": {"caseId": 123}} if nested else {"caseId": 123}

    await client._request.__wrapped__(
        client,
        "POST",
        "https://ppubs.uspto.gov/api/test",
        json=payload,
    )

    second_payload = http.request.await_args_list[1].kwargs["json"]
    expected = second_payload["query"]["caseId"] if nested else second_payload["caseId"]
    assert expected == 456


@pytest.mark.asyncio
async def test_request_uses_one_session_refresh_attempt_per_request_attempt() -> None:
    http = AsyncMock(spec=httpx.AsyncClient)
    http.request = AsyncMock(return_value=_response(403))
    client = PublicSearchClient(client=http)
    client._refresh_session_once = AsyncMock(
        side_effect=RetryableAuthenticationError("bootstrap failed", status_code=403)
    )

    with pytest.raises(RetryableAuthenticationError):
        await client._request.__wrapped__(client, "POST", "https://ppubs.uspto.gov/api/test")

    client._refresh_session_once.assert_awaited_once()


@pytest.mark.asyncio
async def test_concurrent_403s_share_one_refreshed_session() -> None:
    http = AsyncMock(spec=httpx.AsyncClient)
    both_old_requests_started = asyncio.Event()
    old_request_count = 0

    async def request(method: str, url: str, **kwargs: object) -> httpx.Response:
        nonlocal old_request_count
        payload = kwargs["json"]
        assert isinstance(payload, dict)
        if payload["caseId"] == 123:
            old_request_count += 1
            if old_request_count == 2:
                both_old_requests_started.set()
            await both_old_requests_started.wait()
            return _response(403)
        return _response(200, json={})

    http.request = AsyncMock(side_effect=request)
    client = PublicSearchClient(client=http)
    client._case_id = 123

    async def refresh() -> None:
        client._case_id = 456

    client._refresh_session_once = AsyncMock(side_effect=refresh)
    payloads = [{"caseId": 123}, {"caseId": 123}]

    responses = await asyncio.gather(
        *(
            client._request.__wrapped__(
                client,
                "POST",
                "https://ppubs.uspto.gov/api/test",
                json=payload,
            )
            for payload in payloads
        )
    )

    assert [response.status_code for response in responses] == [200, 200]
    assert payloads == [{"caseId": 456}, {"caseId": 456}]
    client._refresh_session_once.assert_awaited_once()


@pytest.mark.asyncio
async def test_waiting_request_recovers_after_concurrent_refresh_failure() -> None:
    http = AsyncMock(spec=httpx.AsyncClient)
    both_old_requests_started = asyncio.Event()
    old_request_count = 0

    async def request(method: str, url: str, **kwargs: object) -> httpx.Response:
        nonlocal old_request_count
        payload = kwargs["json"]
        assert isinstance(payload, dict)
        if payload["caseId"] == 123:
            old_request_count += 1
            if old_request_count == 2:
                both_old_requests_started.set()
            await both_old_requests_started.wait()
            return _response(403)
        if payload["caseId"] == 456:
            return _response(200, json={})
        return _response(403)

    http.request = AsyncMock(side_effect=request)
    client = PublicSearchClient(client=http)
    client._case_id = 123
    refresh_attempt = 0

    async def refresh() -> None:
        nonlocal refresh_attempt
        refresh_attempt += 1
        client._case_id = None
        if refresh_attempt == 1:
            raise RetryableAuthenticationError("bootstrap failed", status_code=403)
        client._case_id = 456

    client._refresh_session_once = AsyncMock(side_effect=refresh)
    payloads = [{"caseId": 123}, {"caseId": 123}]

    results = await asyncio.gather(
        *(
            client._request.__wrapped__(
                client,
                "POST",
                "https://ppubs.uspto.gov/api/test",
                json=payload,
            )
            for payload in payloads
        ),
        return_exceptions=True,
    )

    assert sum(isinstance(result, RetryableAuthenticationError) for result in results) == 1
    assert sum(isinstance(result, httpx.Response) for result in results) == 1
    assert sum(payload["caseId"] == 456 for payload in payloads) == 1
    assert client._refresh_session_once.await_count == 2


@pytest.mark.asyncio
async def test_session_bootstrap_retries_server_error() -> None:
    http = AsyncMock(spec=httpx.AsyncClient)
    http.cookies = httpx.Cookies()
    http.headers = httpx.Headers()
    http.get = AsyncMock(return_value=_response(200, json={}))
    http.post = AsyncMock(
        side_effect=[
            _response(500),
            httpx.Response(
                200,
                json={"userCase": {"caseId": 123}},
                headers={"X-Access-Token": "token"},
                request=httpx.Request("POST", "https://ppubs.uspto.gov/api/users/me/session"),
            ),
        ]
    )
    client = PublicSearchClient(client=http)

    await client._refresh_session()

    assert client._case_id == 123
    assert http.post.await_count == 2


@pytest.mark.asyncio
async def test_search_caps_one_upstream_page_at_twenty() -> None:
    http = AsyncMock(spec=httpx.AsyncClient)
    client = PublicSearchClient(client=http)
    client._case_id = 123
    client._request = AsyncMock(
        side_effect=[
            _response(200, json={}),
            _response(200, json={"results": []}),
        ]
    )

    with patch(
        "patent_client_agents.uspto_publications.client.convert_biblio_page",
        return_value={"num_found": 0, "per_page": 20, "page": 0, "docs": []},
    ):
        await client.search_biblio(query="neural.CLM.", limit=25)

    search_payload = client._request.await_args_list[1].kwargs["json"]
    assert search_payload["pageCount"] == 20


@pytest.mark.asyncio
async def test_search_rejects_non_positive_limit_before_network_call() -> None:
    http = AsyncMock(spec=httpx.AsyncClient)
    client = PublicSearchClient(client=http)

    with pytest.raises(ValidationError, match="limit must be at least 1"):
        await client.search_biblio(query="neural.CLM.", limit=0)

    http.request.assert_not_awaited()
