from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from patent_client_agents.iponz_new_zealand import api
from patent_client_agents.iponz_new_zealand.client import PRODUCTION_BASE_URL, IponzClient


@pytest.fixture
def wire(
    monkeypatch: pytest.MonkeyPatch, fixture_dir: Path
) -> tuple[dict[str, str], list[httpx.Request], list[IponzClient]]:
    """Route ``api`` through a real client on a mock transport.

    Returns ``(served, captured, closed)``: set ``served["file"]`` to the fixture
    to answer with; requests land in ``captured``; exited clients in ``closed``.
    """
    served: dict[str, str] = {}
    captured: list[httpx.Request] = []
    closed: list[IponzClient] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=(fixture_dir / served["file"]).read_bytes())

    class Tracked(IponzClient):
        async def __aexit__(self, *exc: object) -> None:
            await super().__aexit__(*exc)
            closed.append(self)

    def factory() -> IponzClient:
        return Tracked(
            "mock-subscription", environment="production", transport=httpx.MockTransport(handler)
        )

    monkeypatch.setattr(api, "IponzClient", factory)
    return served, captured, closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("helper", "fixture", "number", "path", "title"),
    [
        (
            "get_iponz_patent",
            "patent_information.xml",
            "765432",
            "/patent/765432",
            "Adaptive necktie controller",
        ),
        (
            "get_iponz_trademark",
            "trademark_information.xml",
            "1234567",
            "/trademarks/1234567",
            "NECKTIE LABS",
        ),
        (
            "get_iponz_design",
            "design_information.xml",
            "998877",
            "/design/998877",
            "Necktie clasp",
        ),
    ],
)
async def test_get_helpers_fetch_record(
    wire: tuple[dict[str, str], list[httpx.Request], list[IponzClient]],
    helper: str,
    fixture: str,
    number: str,
    path: str,
    title: str,
) -> None:
    served, captured, closed = wire
    served["file"] = fixture

    record = await getattr(api, helper)(number)

    assert record.title == title
    assert str(captured[0].url) == f"{PRODUCTION_BASE_URL}{path}"
    assert len(closed) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("helper", "fixture", "path", "right_type"),
    [
        (
            "list_iponz_patents_updated",
            "patents_updated.xml",
            "/patents/updated/20260801-20260803",
            "patent",
        ),
        (
            "list_iponz_trademarks_updated",
            "trademarks_updated.xml",
            "/trademarks/updated/20260801-20260803",
            "trademark",
        ),
        (
            "list_iponz_designs_updated",
            "designs_updated.xml",
            "/designs/updated/20260801-20260803",
            "design",
        ),
        (
            "list_iponz_designs_registered",
            "designs_registered.xml",
            "/designs/registered/20260801-20260803",
            "design",
        ),
    ],
)
async def test_list_helpers_send_date_range(
    wire: tuple[dict[str, str], list[httpx.Request], list[IponzClient]],
    helper: str,
    fixture: str,
    path: str,
    right_type: str,
) -> None:
    served, captured, closed = wire
    served["file"] = fixture

    rows = await getattr(api, helper)(date(2026, 8, 1), date(2026, 8, 3))

    assert rows[0].right_type == right_type
    assert rows[0].event_date
    assert str(captured[0].url) == f"{PRODUCTION_BASE_URL}{path}"
    assert len(closed) == 1
