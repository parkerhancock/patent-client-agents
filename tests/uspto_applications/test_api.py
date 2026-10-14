"""Tests for the USPTO applications/PTAB module-level API.

The one-shot helpers run through a real ``UsptoOdpClient`` whose HTTP client
sits on an ``httpx.MockTransport``, so URL building, payloads and response
parsing run as in production.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest

from patent_client_agents.uspto_applications import api as apps_api
from patent_client_agents.uspto_odp import UsptoOdpClient

ODP = "https://api.uspto.gov/api/v1"
RECORD = {
    "applicationNumberText": "16123456",
    "applicationMetaData": {"inventionTitle": "Widget", "patentNumber": "11000000"},
}


class FakeOdp:
    """ODP stand-in: records requests and answers each with ``reply``."""

    def __init__(self) -> None:
        self.reply: dict[str, Any] = {"count": 0}
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
    monkeypatch.setattr(apps_api, "UsptoOdpClient", fake.client)
    return fake


def _body(request: httpx.Request) -> dict[str, Any]:
    return json.loads(request.content)


def _search(path: str, query: str, limit: int = 25, offset: int = 0) -> tuple[str, str, Any]:
    return "POST", f"{ODP}{path}", {"q": query, "pagination": {"offset": offset, "limit": limit}}


Call = Callable[[], Awaitable[Any]]


@pytest.mark.parametrize(
    ("call", "expected", "reply", "check"),
    [
        pytest.param(
            functools.partial(apps_api.get_application, "16123456"),
            ("GET", f"{ODP}/patent/applications/16123456", None),
            {"count": 1, "patentFileWrapperDataBag": [RECORD]},
            lambda r: r.patentBag[0]["inventionTitle"] == "Widget",
            id="get_application",
        ),
        pytest.param(
            functools.partial(apps_api.list_documents, "16123456", include_associated=False),
            ("GET", f"{ODP}/patent/applications/16123456/documents", None),
            {"documentBag": [{"documentIdentifier": "D1"}]},
            lambda r: (
                [d.documentIdentifier for d in r.documents] == ["D1"]
                and r.associatedDocuments is None
            ),
            id="list_documents",
        ),
        pytest.param(
            functools.partial(apps_api.search_trial_proceedings, query="IPR", limit=5, offset=10),
            _search("/patent/trials/proceedings/search", "IPR", limit=5, offset=10),
            {"count": 7},
            lambda r: r.count == 7,
            id="search_trial_proceedings",
        ),
        pytest.param(
            functools.partial(apps_api.get_trial_proceeding, "IPR2024-00001"),
            ("GET", f"{ODP}/patent/trials/proceedings/IPR2024-00001", None),
            {"trialNumber": "IPR2024-00001"},
            lambda r: r.patentTrialProceedingDataBag[0].trialNumber == "IPR2024-00001",
            id="get_trial_proceeding",
        ),
        pytest.param(
            functools.partial(apps_api.search_trial_decisions, query="final"),
            _search("/patent/trials/decisions/search", "final"),
            {"count": 7},
            lambda r: r.count == 7,
            id="search_trial_decisions",
        ),
        pytest.param(
            functools.partial(apps_api.get_trial_decisions_by_trial, "IPR2024-00001"),
            ("GET", f"{ODP}/patent/trials/IPR2024-00001/decisions", None),
            {"count": 7},
            lambda r: r.count == 7,
            id="get_trial_decisions_by_trial",
        ),
        pytest.param(
            functools.partial(apps_api.search_trial_documents, query="petition"),
            _search("/patent/trials/documents/search", "petition"),
            {"count": 7},
            lambda r: r.count == 7,
            id="search_trial_documents",
        ),
        pytest.param(
            functools.partial(apps_api.get_trial_documents_by_trial, "IPR2024-00001"),
            ("GET", f"{ODP}/patent/trials/IPR2024-00001/documents", None),
            {"count": 7},
            lambda r: r.count == 7,
            id="get_trial_documents_by_trial",
        ),
        pytest.param(
            functools.partial(apps_api.search_appeal_decisions, query="101"),
            _search("/patent/appeals/decisions/search", "101"),
            {"count": 7},
            lambda r: r.count == 7,
            id="search_appeal_decisions",
        ),
        pytest.param(
            functools.partial(apps_api.get_appeal_decisions_by_number, "2020-001234"),
            ("GET", f"{ODP}/patent/appeals/2020-001234/decisions", None),
            {"count": 7},
            lambda r: r.count == 7,
            id="get_appeal_decisions_by_number",
        ),
        pytest.param(
            functools.partial(apps_api.search_interference_decisions, query="priority"),
            _search("/patent/interferences/decisions/search", "priority"),
            {"count": 7},
            lambda r: r.count == 7,
            id="search_interference_decisions",
        ),
        pytest.param(
            functools.partial(apps_api.get_interference_decisions_by_number, "106001"),
            ("GET", f"{ODP}/patent/interferences/106001/decisions", None),
            {"count": 7},
            lambda r: r.count == 7,
            id="get_interference_decisions_by_number",
        ),
    ],
)
@pytest.mark.asyncio
async def test_one_shot_reaches_odp(
    odp: FakeOdp,
    call: Call,
    expected: tuple[str, str, Any],
    reply: dict[str, Any],
    check: Callable[[Any], bool],
) -> None:
    odp.reply = reply

    result = await call()

    method, url, body = expected
    request = odp.request
    assert (request.method, str(request.url)) == (method, url)
    assert request.headers["X-API-KEY"] == "test-key"
    if body is not None:
        assert _body(request) == body
    assert check(result)
    assert (len(odp.opened), odp.closes) == (1, 1)


@pytest.mark.asyncio
async def test_search_applications_maps_q_to_query(odp: FakeOdp) -> None:
    odp.reply = {"count": 1, "patentFileWrapperDataBag": [RECORD]}

    result = await apps_api.search_applications(
        q="inventor:doe", fields=["applicationNumberText"], limit=5, normalize=False
    )

    request = odp.request
    assert (request.method, str(request.url)) == ("POST", f"{ODP}/patent/applications/search")
    assert _body(request) == {
        "q": "inventor:doe",
        "fields": ["applicationNumberText"],
        "pagination": {"offset": 0, "limit": 5},
    }
    assert result.patentBag == [RECORD]
    assert (len(odp.opened), odp.closes) == (1, 1)


@pytest.mark.asyncio
async def test_get_family_resolves_patent_number_and_walks_graph(odp: FakeOdp) -> None:
    odp.reply = {"count": 1, "patentFileWrapperDataBag": [RECORD]}

    result = await apps_api.get_family("11000000")

    resolve, fetch = odp.requests
    assert _body(resolve)["q"] == 'applicationMetaData.patentNumber:"11000000"'
    assert _body(fetch)["q"] == "applicationNumberText:(16123456)"
    assert result.rootApplication == "16123456"
    assert [(n.applicationNumber, n.patentNumber) for n in result.nodes] == [
        ("16123456", "11000000")
    ]
    assert (len(odp.opened), odp.closes) == (1, 1)


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(functools.partial(apps_api.get_application, "16123456"), id="get_application"),
        pytest.param(
            functools.partial(apps_api.search_applications, q="inventor:doe"),
            id="search_applications",
        ),
    ],
)
@pytest.mark.asyncio
async def test_client_kwarg_is_deprecated_and_left_open(odp: FakeOdp, call: Call) -> None:
    client = odp.client()

    with pytest.warns(DeprecationWarning, match="Passing client= is deprecated") as caught:
        await call(client=client)

    assert [w.filename for w in caught] == [__file__]
    assert odp.request.url.path.startswith("/api/v1/patent/applications")
    assert (len(odp.opened), odp.closes) == (1, 0)
    await client.close()
