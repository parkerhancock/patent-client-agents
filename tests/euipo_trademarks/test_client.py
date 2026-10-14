"""Request-path tests for the EUIPO Trademark Search client.

Each test drives a public client method through a fake network (see
``tests/euipo_common/transport.py``) and checks the request the client sends
and how it parses the response. OAuth, headers, config and error mapping are
covered for both EUIPO clients in ``tests/euipo_common/test_auth.py``.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from patent_client_agents.euipo_trademarks import (
    EuipoTrademarksClient,
    MarkBasis,
    MarkFeature,
    MarkKind,
    Status,
)
from tests.euipo_common.transport import api_requests, euipo_transport

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "euipo"
BASE = "https://api.euipo.europa.eu/trademark-search"

# Detail record shaped on the Trademark schema in
# research/openapi/euipo_trademark_search.json, extending the captured
# search row for 000428557 ("Golden Apple").
TRADEMARK_DETAIL = {
    "applicationNumber": "000428557",
    "applicationDate": "1996-12-02",
    "applicationLanguage": "de",
    "secondLanguage": "en",
    "markKind": "INDIVIDUAL",
    "markFeature": "WORD",
    "markBasis": "EU_TRADEMARK",
    "wordMarkSpecification": {"verbalElement": "Golden Apple"},
    "applicants": [
        {"office": "EM", "identifier": "18363", "name": "Berentzen-Gruppe Aktiengesellschaft"}
    ],
    "representatives": [{"office": "EM", "identifier": "40347", "name": "Example & Partner"}],
    "receiptDate": "1996-12-02",
    "registrationDate": "1998-10-30",
    "publicationDate": "1998-04-27",
    "expiryDate": "2026-12-02",
    "status": "REGISTERED",
    "statusDate": "2016-12-07",
    "niceClasses": [30, 32, 33],
    "goodsAndServices": [
        {
            "classNumber": 33,
            "description": [
                {"language": "en", "terms": ["Alcoholic beverages (except beers)"]},
                {"language": "de", "terms": ["Alkoholische Getränke (ausgenommen Biere)"]},
            ],
        }
    ],
    "oppositionPeriodStartDate": "1998-04-28",
    "oppositionPeriodEndDate": "1998-07-27",
    "renewalStatus": "RENEWAL_PERIOD_TO_START",
    "fastTrackIndicator": False,
    "tradeDistinctivenessIndicator": False,
    "publications": [
        {"bulletinNumber": "1998/030", "publicationSection": "A.1", "publicationDate": "1998-04-27"}
    ],
}


def _client(handler, seen: list[httpx.Request]) -> EuipoTrademarksClient:
    return EuipoTrademarksClient(
        client_id="id",
        client_secret="secret",
        environment="production",
        transport=euipo_transport(handler, seen),
        use_cache=False,
    )


async def test_search_sends_rsql_query_paging_sort_and_fields() -> None:
    fixture = json.loads((FIXTURES / "tm_apple_size10.json").read_text())
    seen: list[httpx.Request] = []
    query = "wordMarkSpecification.verbalElement==*Apple* and status==REGISTERED"

    async with _client(lambda r: httpx.Response(200, json=fixture), seen) as client:
        result = await client.search(
            query=query, page=2, size=10, sort="applicationDate:desc", fields="!(goodsAndServices)"
        )

    (request,) = api_requests(seen)
    assert request.method == "GET"
    assert str(request.url.copy_with(query=None)) == f"{BASE}/trademarks"
    assert dict(request.url.params) == {
        "query": query,
        "page": "2",
        "size": "10",
        "sort": "applicationDate:desc",
        "fields": "!(goodsAndServices)",
    }

    assert result.total_elements == 739
    assert result.total_pages == 74
    assert len(result.trademarks) == 10
    first = result.trademarks[0]
    assert first.application_number == "000428557"
    assert first.status is Status.REGISTERED
    assert first.mark_feature is MarkFeature.WORD
    assert first.word_mark_specification is not None
    assert first.word_mark_specification.verbal_element == "Golden Apple"
    assert first.applicants[0].name == "Berentzen-Gruppe Aktiengesellschaft"
    assert first.nice_classes == [30, 32, 33]


async def test_search_defaults_send_only_page_and_size() -> None:
    fixture = json.loads((FIXTURES / "tm_list_size10.json").read_text())
    seen: list[httpx.Request] = []

    async with _client(lambda r: httpx.Response(200, json=fixture), seen) as client:
        result = await client.search()

    (request,) = api_requests(seen)
    assert dict(request.url.params) == {"page": "0", "size": "25"}
    assert result.total_elements == 2_354_583


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [({"size": 5}, "size must be"), ({"size": 200}, "size must be"), ({"page": -1}, "page must")],
)
async def test_search_rejects_out_of_range_paging_without_a_request(
    kwargs: dict, message: str
) -> None:
    seen: list[httpx.Request] = []
    async with _client(lambda r: httpx.Response(200, json={}), seen) as client:
        with pytest.raises(ValueError, match=message):
            await client.search(**kwargs)
    assert seen == []


async def test_get_trademark_requests_detail_path_and_parses_record() -> None:
    seen: list[httpx.Request] = []

    async with _client(lambda r: httpx.Response(200, json=TRADEMARK_DETAIL), seen) as client:
        tm = await client.get_trademark("000428557")

    (request,) = api_requests(seen)
    assert request.method == "GET"
    assert str(request.url) == f"{BASE}/trademarks/000428557"

    assert tm.application_number == "000428557"
    assert tm.status is Status.REGISTERED
    assert tm.mark_kind is MarkKind.INDIVIDUAL
    assert tm.mark_basis is MarkBasis.EU_TRADEMARK
    assert tm.application_language == "de"
    assert tm.second_language == "en"
    assert tm.receipt_date == date(1996, 12, 2)
    assert tm.status_date == date(2016, 12, 7)
    assert tm.expiry_date == date(2026, 12, 2)
    assert tm.opposition_period_end_date == date(1998, 7, 27)
    assert tm.renewal_status == "RENEWAL_PERIOD_TO_START"
    assert tm.fast_track_indicator is False
    assert tm.representatives[0].identifier == "40347"
    assert tm.goods_and_services[0].class_number == 33
    assert tm.goods_and_services[0].terms_in("en") == ["Alcoholic beverages (except beers)"]
    assert tm.publications[0].publication_date == date(1998, 4, 27)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Source bug: Trademark.description/disclaimer are typed `str | None`, but the "
        "EUIPO spec defines both as MultilingualElement (array of {language, text}), "
        "so any detail record carrying them fails validation."
    ),
)
async def test_get_trademark_parses_multilingual_description_and_disclaimer() -> None:
    payload = {
        **TRADEMARK_DETAIL,
        "description": [{"language": "en", "text": "The mark is golden."}],
        "disclaimer": [{"language": "en", "text": "No exclusive right to 'Apple'."}],
    }
    seen: list[httpx.Request] = []
    async with _client(lambda r: httpx.Response(200, json=payload), seen) as client:
        tm = await client.get_trademark("000428557")
    assert tm.description is not None


@pytest.mark.parametrize(
    ("method", "path", "content_type"),
    [
        ("get_image", "/image", "image/jpeg"),
        ("get_image_thumbnail", "/image/thumbnail", "image/jpeg"),
        ("get_sound", "/sound", "audio/mpeg"),
        ("get_video", "/video", "video/mp4"),
        ("get_model", "/model", "model/obj"),
    ],
)
async def test_media_methods_request_media_path_and_return_raw_bytes(
    method: str, path: str, content_type: str
) -> None:
    body = b"\x00\x01binary-" + method.encode()
    seen: list[httpx.Request] = []

    async with _client(
        lambda r: httpx.Response(200, content=body, headers={"Content-Type": content_type}), seen
    ) as client:
        result = await getattr(client, method)("W01234567")

    (request,) = api_requests(seen)
    assert request.method == "GET"
    assert str(request.url) == f"{BASE}/trademarks/W01234567{path}"
    assert result == body
