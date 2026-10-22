"""Request-path tests for the EUIPO Design (RCD) Search client.

Each test drives a public client method through a fake network (see
``tests/euipo_common/transport.py``) and checks the request the client sends
and how it parses the response. OAuth, headers, config and error mapping are
covered for both EUIPO clients in ``tests/euipo_common/test_auth.py``.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx2
import pytest

from patent_client_agents.euipo_designs import EuipoDesignsClient, Status
from tests.euipo_common.transport import api_requests, euipo_transport

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "euipo"
BASE = "https://api-sandbox.euipo.europa.eu/design-search"

# Detail record shaped on the Design schema in
# research/openapi/euipo_design_search.json.
DESIGN_DETAIL = {
    "designNumber": "099037115-0001",
    "applicationNumber": "099037115",
    "applicationDate": "2024-03-11",
    "applicationLanguage": "en",
    "secondLanguage": "fr",
    "publicationDefermentIndicator": True,
    "defermentExpirationDate": "2026-09-11",
    "registrationDate": "2024-03-11",
    "effectiveDate": "2024-03-11",
    "expiryDate": "2029-03-11",
    "renewalStatus": "RENEWAL_PERIOD_TO_START",
    "status": "REGISTERED_AND_SUBJECT_TO_DEFERMENT",
    "statusDate": "2024-03-20",
    "verbalElement": "AURORA",
    "views": [{"order": 1, "imageFormat": "JPG"}, {"order": 2, "imageFormat": "JPG"}],
    "model": {"modelFormat": "OBJ"},
    "productIndications": [
        {"language": "en", "terms": ["Lamps"]},
        {"language": "fr", "terms": ["Lampes"]},
    ],
    "locarnoClasses": ["26.05"],
    "publications": [
        {"bulletinNumber": "2024/054", "publicationSection": "A.1", "publicationDate": "2024-03-20"}
    ],
    "applicants": [{"office": "EM", "identifier": "854815", "name": "Lumen Studio GmbH"}],
    "representatives": [{"office": "EM", "identifier": "40347", "name": "Example & Partner"}],
    "designers": [{"identifier": "D-1", "name": "Ada Example"}],
}


def _client(handler, seen: list[httpx2.Request]) -> EuipoDesignsClient:
    return EuipoDesignsClient(
        client_id="id",
        client_secret="secret",
        environment="sandbox",
        transport=euipo_transport(handler, seen),
        use_cache=False,
    )


async def test_search_sends_rsql_query_paging_sort_and_fields() -> None:
    fixture = json.loads((FIXTURES / "design_list_size10.json").read_text())
    seen: list[httpx2.Request] = []
    query = "applicants.name==*Apple* and locarnoClasses=in=(14.03,14.04)"

    async with _client(lambda r: httpx2.Response(200, json=fixture), seen) as client:
        result = await client.search(
            query=query, page=3, size=100, sort="applicationDate:asc", fields="!(views)"
        )

    (request,) = api_requests(seen)
    assert request.method == "GET"
    assert str(request.url.copy_with(query=None)) == f"{BASE}/designs"
    assert dict(request.url.params) == {
        "query": query,
        "page": "3",
        "size": "100",
        "sort": "applicationDate:asc",
        "fields": "!(views)",
    }

    assert result.total_elements == 1_517_413
    assert result.total_pages == 151_741
    assert len(result.designs) == 10
    first = result.designs[0]
    assert first.design_number == "004247823-0007"
    assert first.application_number == "004247823"
    assert first.status is Status.EXPIRED
    assert first.locarno_classes == ["08.06"]
    assert first.applicants[0].identifier == "854815"
    assert first.application_date == date(2017, 9, 8)


async def test_search_defaults_send_only_page_and_size() -> None:
    fixture = json.loads((FIXTURES / "design_list_size10.json").read_text())
    seen: list[httpx2.Request] = []

    async with _client(lambda r: httpx2.Response(200, json=fixture), seen) as client:
        await client.search()

    (request,) = api_requests(seen)
    assert dict(request.url.params) == {"page": "0", "size": "25"}


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [({"size": 9}, "size must be"), ({"size": 101}, "size must be"), ({"page": -1}, "page must")],
)
async def test_search_rejects_out_of_range_paging_without_a_request(
    kwargs: dict, message: str
) -> None:
    seen: list[httpx2.Request] = []
    async with _client(lambda r: httpx2.Response(200, json={}), seen) as client:
        with pytest.raises(ValueError, match=message):
            await client.search(**kwargs)
    assert seen == []


async def test_get_design_requests_detail_path_and_parses_record() -> None:
    seen: list[httpx2.Request] = []

    async with _client(lambda r: httpx2.Response(200, json=DESIGN_DETAIL), seen) as client:
        design = await client.get_design("099037115-0001")

    (request,) = api_requests(seen)
    assert request.method == "GET"
    assert str(request.url) == f"{BASE}/designs/099037115-0001"

    assert design.design_number == "099037115-0001"
    assert design.status is Status.REGISTERED_AND_SUBJECT_TO_DEFERMENT
    assert design.is_registered
    assert design.publication_deferment_indicator is True
    assert design.deferment_expiration_date == date(2026, 9, 11)
    assert design.effective_date == date(2024, 3, 11)
    assert design.verbal_element == "AURORA"
    assert [(v.order, v.image_format) for v in design.views] == [(1, "JPG"), (2, "JPG")]
    assert design.model is not None
    assert design.model.model_format == "OBJ"
    assert design.product_terms_in("fr") == ["Lampes"]
    assert design.locarno_classes == ["26.05"]
    assert design.designers[0].name == "Ada Example"
    assert design.applicants[0].name == "Lumen Studio GmbH"
    assert design.publications[0].bulletin_number == "2024/054"


@pytest.mark.parametrize(
    ("method", "args", "path", "content_type"),
    [
        ("get_view", (2,), "/views/2", "image/jpeg"),
        ("get_view_thumbnail", (3,), "/views/3/thumbnail", "image/jpeg"),
        ("get_model", (), "/model", "model/obj"),
    ],
)
async def test_media_methods_request_media_path_and_return_raw_bytes(
    method: str, args: tuple, path: str, content_type: str
) -> None:
    body = b"\x00\x01binary-" + method.encode()
    seen: list[httpx2.Request] = []

    async with _client(
        lambda r: httpx2.Response(200, content=body, headers={"Content-Type": content_type}), seen
    ) as client:
        result = await getattr(client, method)("099037115-0001", *args)

    (request,) = api_requests(seen)
    assert request.method == "GET"
    assert str(request.url) == f"{BASE}/designs/099037115-0001{path}"
    assert result == body
