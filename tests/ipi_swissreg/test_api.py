from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import httpx2
import pytest

from patent_client_agents.ipi_swissreg import api
from patent_client_agents.ipi_swissreg.client import (
    BASE_URL,
    COMMON_NS,
    CORE_NS,
    TOKEN_URL,
    IpiSwissregClient,
)


@pytest.fixture
def wire(
    monkeypatch: pytest.MonkeyPatch, fixture_dir: Path
) -> tuple[dict[str, str], list[ET.Element], list[IpiSwissregClient]]:
    """Route ``api`` through a real client on a mock transport.

    Returns ``(served, requests, closed)``: set ``served["file"]`` to the fixture
    to answer API calls with; parsed API request bodies (token calls excluded)
    land in ``requests``; exited clients in ``closed``.
    """
    served: dict[str, str] = {}
    requests: list[ET.Element] = []
    closed: list[IpiSwissregClient] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        if str(request.url) == TOKEN_URL:
            return httpx2.Response(200, json={"access_token": "mock-access", "expires_in": 600})
        assert str(request.url) == BASE_URL
        requests.append(ET.fromstring(request.content))
        return httpx2.Response(200, content=(fixture_dir / served["file"]).read_bytes())

    class Tracked(IpiSwissregClient):
        async def __aexit__(self, *exc: object) -> None:
            await super().__aexit__(*exc)
            closed.append(self)

    def factory() -> IpiSwissregClient:
        return Tracked("api-user", "api-password", transport=httpx2.MockTransport(handler))

    monkeypatch.setattr(api, "IpiSwissregClient", factory)
    return served, requests, closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("helper", "fixture", "action", "field", "value"),
    [
        ("search_ipi_patents", "patent_search.xml", "PatentSearch", "identifier", "CH718001"),
        (
            "search_ipi_patent_publications",
            "patent_publication_search.xml",
            "PatentPublicationSearch",
            "publication_title",
            "Patent grant",
        ),
        (
            "search_ipi_trademarks",
            "trademark_search.xml",
            "TrademarkSearch",
            "word_element",
            "NECKTIE",
        ),
        ("search_ipi_spcs", "spc_search.xml", "SPCSearch", "basic_patent_number", "CH700001"),
        (
            "search_ipi_spc_publications",
            "spc_publication_search.xml",
            "SPCPublicationSearch",
            "publication_title",
            "SPC grant",
        ),
    ],
)
async def test_search_helpers_send_query_and_page_size(
    wire: tuple[dict[str, str], list[ET.Element], list[IpiSwissregClient]],
    helper: str,
    fixture: str,
    action: str,
    field: str,
    value: str,
) -> None:
    served, requests, closed = wire
    served["file"] = fixture

    rows, meta = await getattr(api, helper)("adaptive controller", limit=7)

    assert getattr(rows[0], field) == value
    assert meta.total_item_count
    action_node = requests[0].find(f"{{{CORE_NS}}}Action")
    assert action_node is not None and action_node.attrib["type"] == action
    page = action_node.find(f".//{{{COMMON_NS}}}Page")
    any_query = action_node.find(f".//{{{COMMON_NS}}}Any")
    assert page is not None and page.attrib["size"] == "7"
    assert any_query is not None and any_query.text == "adaptive controller"
    assert len(closed) == 1


@pytest.mark.asyncio
async def test_search_helper_forwards_cursor(
    wire: tuple[dict[str, str], list[ET.Element], list[IpiSwissregClient]],
) -> None:
    served, requests, closed = wire
    served["file"] = "patent_search.xml"

    _, meta = await api.search_ipi_patents("ignored", cursor="opaque-cursor")

    assert meta.next_cursor == "opaque-patent-page-2"
    continuation = requests[0].find(f"{{{CORE_NS}}}Continuation")
    assert continuation is not None and continuation.text == "opaque-cursor"
    assert len(closed) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("helper", "fixture", "request_tag", "request_field"),
    [
        ("get_ipi_patent", "patent_search.xml", "PatentSearchRequest", "PatentNumber"),
        ("get_ipi_trademark", "trademark_search.xml", "TrademarkSearchRequest", "TradeMarkNumber"),
        ("get_ipi_spc", "spc_search.xml", "SPCSearchRequest", "SPCNumber"),
    ],
)
async def test_get_helpers_query_by_identifier(
    wire: tuple[dict[str, str], list[ET.Element], list[IpiSwissregClient]],
    helper: str,
    fixture: str,
    request_tag: str,
    request_field: str,
) -> None:
    served, requests, closed = wire
    served["file"] = fixture

    record = await getattr(api, helper)("CH-MOCK")

    assert record.identifier
    search = next(node for node in requests[0].iter() if node.tag.endswith(request_tag))
    number = next(node for node in search.iter() if node.tag.endswith(request_field))
    assert number.text == "CH-MOCK"
    assert len(closed) == 1
