from __future__ import annotations

from pathlib import Path

import httpx2
import pytest

from patent_client_agents.dpma_register import api
from patent_client_agents.dpma_register.client import DpmaRegisterClient


@pytest.fixture
def wire(
    monkeypatch: pytest.MonkeyPatch, fixture_dir: Path
) -> tuple[dict[str, str], list[httpx2.Request], list[DpmaRegisterClient]]:
    """Route ``api`` through a real client on a mock transport.

    Returns ``(served, captured, closed)``: set ``served["file"]`` to the fixture
    to answer with; requests land in ``captured``; exited clients in ``closed``.
    """
    served: dict[str, str] = {}
    captured: list[httpx2.Request] = []
    closed: list[DpmaRegisterClient] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        return httpx2.Response(200, content=(fixture_dir / served["file"]).read_bytes())

    class Tracked(DpmaRegisterClient):
        async def __aexit__(self, *exc: object) -> None:
            await super().__aexit__(*exc)
            closed.append(self)

    def factory() -> DpmaRegisterClient:
        http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        return Tracked("user", "pass", base_url="https://mock.test", client=http)

    monkeypatch.setattr(api, "DpmaRegisterClient", factory)
    return served, captured, closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("helper", "fixture", "service", "field", "value", "total"),
    [
        ("search_dpma_patents", "patent_search.xml", "DPMAregisterPatService", None, None, 2),
        (
            "search_dpma_trademarks",
            "trademark_search.xml",
            "DPMAregisterMarkeService",
            "mark_text",
            "NECKTIE",
            1,
        ),
        (
            "search_dpma_designs",
            "design_search.xml",
            "DPMAregisterGsmService",
            "product_indication",
            "Computer enclosure",
            1,
        ),
    ],
)
async def test_search_helpers_query_register_and_apply_limit(
    wire: tuple[dict[str, str], list[httpx2.Request], list[DpmaRegisterClient]],
    helper: str,
    fixture: str,
    service: str,
    field: str | None,
    value: str | None,
    total: int,
) -> None:
    served, captured, closed = wire
    served["file"] = fixture

    rows, hit_count = await getattr(api, helper)("AKZ=10 2023", limit=1)

    assert hit_count == total
    assert len(rows) == 1  # limit reached the client (patent fixture has 2 rows)
    if field is not None:
        assert getattr(rows[0], field) == value
    assert captured[0].url.raw_path == f"/{service}/search/AKZ%3D10%202023".encode()
    assert len(closed) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("helper", "fixture", "service", "field", "value"),
    [
        (
            "get_dpma_patent",
            "patent_detail.xml",
            "DPMAregisterPatService",
            "title",
            "Adaptive charging controller",
        ),
        (
            "get_dpma_trademark",
            "trademark_detail.xml",
            "DPMAregisterMarkeService",
            "nice_classification",
            "42",
        ),
        (
            "get_dpma_design",
            "design_detail.xml",
            "DPMAregisterGsmService",
            "locarno_classification",
            "14-02",
        ),
    ],
)
async def test_get_helpers_fetch_register_info(
    wire: tuple[dict[str, str], list[httpx2.Request], list[DpmaRegisterClient]],
    helper: str,
    fixture: str,
    service: str,
    field: str,
    value: str,
) -> None:
    served, captured, closed = wire
    served["file"] = fixture

    record = await getattr(api, helper)("DE 10 2023")

    assert getattr(record, field) == value
    assert captured[0].url.raw_path == f"/{service}/getRegisterInfo/DE%2010%202023".encode()
    assert len(closed) == 1
