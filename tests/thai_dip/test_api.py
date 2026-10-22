from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx2
import pytest

from patent_client_agents.thai_dip import api
from patent_client_agents.thai_dip.client import BASE_URL, ThaiDipClient

_FIXTURE_BY_ENDPOINT = {
    "PATENT_NOIP": "patent.json",
    "PRODUCTPATENT": "patent.json",
    "PETTYPATENT": "patent.json",
    "TM": "trademark.json",
    "CPR": "copyright.json",
    "CPRSONG": "song.json",
    "GI": "gi.json",
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("helper", "argument", "kwargs", "endpoint", "body", "field", "value"),
    [
        (
            "search_thai_dip_patents",
            "sensor",
            {"right_type": "design", "field": "title", "limit": 1},
            "PRODUCTPATENT",
            {"patent_name": "%sensor%"},
            "right_type",
            "design",
        ),
        (
            "get_thai_dip_patent",
            "2501000001",
            {"right_type": "petty_patent"},
            "PETTYPATENT",
            {"app_no": "2501000001"},
            "right_type",
            "petty_patent",
        ),
        (
            "search_thai_dip_trademarks",
            "TH-90001",
            {"field": "registration_number", "limit": 1},
            "TM",
            {"regis_no": "TH-90001"},
            "mark_name",
            "SYNTHETIC MARK",
        ),
        (
            "get_thai_dip_trademark",
            "250000001",
            {},
            "TM",
            {"req_no": "%250000001%"},
            "mark_name",
            "SYNTHETIC MARK",
        ),
        (
            "search_thai_dip_copyrights",
            "Synthetic",
            {"field": "owner", "limit": 1},
            "CPR",
            {"owner_name": "%Synthetic%"},
            "work_name",
            "Synthetic handbook",
        ),
        (
            "get_thai_dip_copyright",
            "CR-250001",
            {},
            "CPR",
            {"request_no": "CR-250001"},
            "request_number",
            "CR-250001",
        ),
        (
            "search_thai_dip_songs",
            "Composer",
            {"field": "composer", "limit": 1},
            "CPRSONG",
            {"compose_author_name": "%Composer%"},
            "song_name",
            "Synthetic melody",
        ),
        (
            "search_thai_dip_geographical_indications",
            "90001",
            {"field": "application_id", "limit": 1},
            "GI",
            {"app_no_number": "90001"},
            "name",
            "Synthetic Highland Rice",
        ),
        (
            "get_thai_dip_geographical_indication",
            "90001",
            {},
            "GI",
            {"app_no_number": "90001"},
            "identifier",
            "90001",
        ),
    ],
)
async def test_helpers_post_dataset_query_and_parse(
    monkeypatch: pytest.MonkeyPatch,
    fixture_dir: Path,
    helper: str,
    argument: str,
    kwargs: dict[str, Any],
    endpoint: str,
    body: dict[str, str],
    field: str,
    value: str,
) -> None:
    captured: list[httpx2.Request] = []
    closed: list[ThaiDipClient] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        filename = _FIXTURE_BY_ENDPOINT[request.url.path.rsplit("/", 1)[-1]]
        return httpx2.Response(200, content=(fixture_dir / filename).read_bytes())

    class Tracked(ThaiDipClient):
        async def __aexit__(self, *exc: object) -> None:
            await super().__aexit__(*exc)
            closed.append(self)

    monkeypatch.setattr(
        api, "ThaiDipClient", lambda: Tracked("token", transport=httpx2.MockTransport(handler))
    )

    result = await getattr(api, helper)(argument, **kwargs)

    if isinstance(result, tuple):
        rows, _total = result
        assert len(rows) == 1  # limit=1 reached the client
        record = rows[0]
    else:
        record = result
    assert getattr(record, field) == value
    assert str(captured[0].url) == f"{BASE_URL}/{endpoint}"
    assert json.loads(captured[0].content) == body
    assert len(closed) == 1


@pytest.mark.asyncio
async def test_search_patents_limit_truncates_rows(
    monkeypatch: pytest.MonkeyPatch, fixture_dir: Path
) -> None:
    async def handler(_: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=(fixture_dir / "patent.json").read_bytes())

    monkeypatch.setattr(
        api,
        "ThaiDipClient",
        lambda: ThaiDipClient("token", transport=httpx2.MockTransport(handler)),
    )

    rows, total = await api.search_thai_dip_patents("sensor", limit=1)
    all_rows, _ = await api.search_thai_dip_patents("sensor")

    assert total == 2
    assert len(rows) == 1
    assert len(all_rows) == 2
