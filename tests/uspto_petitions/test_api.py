"""Tests for the USPTO petitions module-level API.

The one-shot helpers run through a real ``UsptoOdpClient`` whose HTTP client
sits on an ``httpx.MockTransport``, so URL building, payloads and response
parsing run as in production.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from patent_client_agents.uspto_odp import UsptoOdpClient
from patent_client_agents.uspto_petitions import api as petitions_api

PETITIONS = "https://api.uspto.gov/api/v1/petition/decisions"
DECISION = {"petitionDecisionRecordIdentifier": "abc", "finalDecidingOfficeName": "OFFICE"}


class FakeOdp:
    """ODP stand-in: records requests and answers each with ``reply``."""

    def __init__(self) -> None:
        self.reply: dict[str, Any] = {"count": 1, "petitionDecisionDataBag": [DECISION]}
        self.requests: list[httpx.Request] = []
        self.opened: list[UsptoOdpClient] = []
        self.closes = 0

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json=self.reply)

    @property
    def request(self) -> httpx.Request:
        (only,) = self.requests
        return only

    def client(self) -> UsptoOdpClient:
        fake = self

        class TrackedClient(UsptoOdpClient):
            async def close(self) -> None:
                fake.closes += 1
                await super().close()

        http = httpx.AsyncClient(transport=httpx.MockTransport(self.handle))
        client = TrackedClient(api_key="test-key", client=http)
        self.opened.append(client)
        return client


@pytest.fixture
def odp(monkeypatch: pytest.MonkeyPatch) -> FakeOdp:
    fake = FakeOdp()
    monkeypatch.setattr(petitions_api, "UsptoOdpClient", fake.client)
    return fake


def _assert_one_shot(odp: FakeOdp) -> None:
    assert (len(odp.opened), odp.closes) == (1, 1)
    assert odp.request.headers["X-API-KEY"] == "test-key"


@pytest.mark.asyncio
async def test_search_petitions(odp: FakeOdp) -> None:
    result = await petitions_api.search_petitions(
        q="finalDecidingOfficeName:OFFICE", fields=["petitionDecisionRecordIdentifier"], limit=5
    )

    request = odp.request
    assert (request.method, str(request.url)) == ("POST", f"{PETITIONS}/search")
    assert json.loads(request.content) == {
        "q": "finalDecidingOfficeName:OFFICE",
        "fields": ["petitionDecisionRecordIdentifier"],
        "pagination": {"offset": 0, "limit": 5},
    }
    assert result.count == 1
    assert [d.petitionDecisionRecordIdentifier for d in result.petitionDecisionDataBag] == ["abc"]
    _assert_one_shot(odp)


@pytest.mark.asyncio
async def test_get_petition(odp: FakeOdp) -> None:
    result = await petitions_api.get_petition("abc", include_documents=True)

    request = odp.request
    assert (request.method, str(request.url)) == ("GET", f"{PETITIONS}/abc?includeDocuments=true")
    assert result.petitionDecisionDataBag[0].petitionDecisionRecordIdentifier == "abc"
    _assert_one_shot(odp)


@pytest.mark.asyncio
async def test_download_petitions(odp: FakeOdp) -> None:
    result = await petitions_api.download_petitions(q="decisionTypeCode:G", file_format="json")

    request = odp.request
    assert (request.method, str(request.url)) == ("POST", f"{PETITIONS}/search/download")
    assert json.loads(request.content) == {"q": "decisionTypeCode:G", "format": "json"}
    assert result.petitionDecisionDataBag[0].finalDecidingOfficeName == "OFFICE"
    _assert_one_shot(odp)


@pytest.mark.asyncio
async def test_client_kwarg_is_deprecated_and_left_open(odp: FakeOdp) -> None:
    client = odp.client()

    with pytest.warns(DeprecationWarning, match="Passing client= is deprecated") as caught:
        result = await petitions_api.get_petition("abc", client=client)

    assert [w.filename for w in caught] == [__file__]
    assert str(odp.request.url) == f"{PETITIONS}/abc"
    assert result.count == 1
    assert (len(odp.opened), odp.closes) == (1, 0)
    await client.close()
