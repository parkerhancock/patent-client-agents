"""Behavioral tests for the TIPO module-level helpers.

Each helper is exercised end to end through a real ``TipoClient`` wired to an
``httpx2.MockTransport``: the outgoing query string, the parsed rows, and that
the client is exited after the call.
"""

from __future__ import annotations

from typing import Any

import httpx2
import pytest

import patent_client_agents.tipo_opdata.api as api
from patent_client_agents.tipo_opdata import models
from patent_client_agents.tipo_opdata.client import TipoClient


@pytest.fixture
def wire(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[httpx2.Request], list[TipoClient]]:
    """Route ``api`` through a real client answering one ``sequence: 7`` row.

    Returns ``(captured, closed)``: requests and exited clients.
    """
    captured: list[httpx2.Request] = []
    closed: list[TipoClient] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        payload = {"status": "OK", "total-count": 1, "wrapper": {"content": [{"sequence": 7}]}}
        return httpx2.Response(200, json=payload)

    class Tracked(TipoClient):
        async def __aexit__(self, *exc: object) -> None:
            await super().__aexit__(*exc)
            closed.append(self)

    def factory() -> TipoClient:
        http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        return Tracked(tk="test-tk", client=http)

    monkeypatch.setattr(api, "TipoClient", factory)
    return captured, closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("helper", "path", "row_type", "kwargs", "expected_params"),
    [
        (
            "search_tipo_patents",
            "/PatentAppl",
            models.PatentApplRow,
            {"q": "TSMC", "applclass": 1, "applicant": "TSMC", "appl_date_from": "2023/01/01"},
            {"q": "TSMC", "applclass": "1", "applicant": "TSMC", "appl-date-from": "2023/01/01"},
        ),
        (
            "search_tipo_trademarks",
            "/TmarkAppl",
            models.TmarkApplRow,
            {"q": "APPLE", "tmark_class": 9, "appl_date_to": "2024/12/31"},
            {"q": "APPLE", "tmark-class": "9", "appl-date-to": "2024/12/31"},
        ),
    ],
)
async def test_search_helpers_send_filters_and_paging(
    wire: tuple[list[httpx2.Request], list[TipoClient]],
    helper: str,
    path: str,
    row_type: type[Any],
    kwargs: dict[str, Any],
    expected_params: dict[str, str],
) -> None:
    captured, closed = wire

    rows = await getattr(api, helper)(**kwargs, top=10, skip=20, **{"extra-filter": "x"})

    assert isinstance(rows[0], row_type)
    assert rows[0].sequence == 7
    request = captured[0]
    assert request.url.path.endswith(path)
    params = dict(request.url.params)
    assert params["tk"] == "test-tk"
    assert params["top"] == "10"
    assert params["skip"] == "20"
    assert params["extra-filter"] == "x"
    for key, value in expected_params.items():
        assert params[key] == value
    assert len(closed) == 1


@pytest.mark.asyncio
async def test_search_helper_defaults_reach_the_wire(
    wire: tuple[list[httpx2.Request], list[TipoClient]],
) -> None:
    captured, closed = wire

    await api.search_tipo_patents()

    params = dict(captured[0].url.params)
    assert params["top"] == "100"
    assert params["skip"] == "0"
    assert "q" not in params
    assert len(closed) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("helper", "path", "row_type"),
    [
        ("get_tipo_patent", "/PatentAppl", models.PatentApplRow),
        ("get_tipo_patent_publication", "/PatentPub", models.PatentPubRow),
        ("get_tipo_patent_rights", "/PatentRights", models.PatentRightsRow),
        ("get_tipo_patent_priority", "/PatentPriority", models.PatentPriorityRow),
        ("get_tipo_patent_annuity", "/PatentAnnuity", models.PatentAnnuityRow),
        ("get_tipo_patent_twins", "/PatentTwins", models.PatentTwinsRow),
        ("get_tipo_patent_alteration", "/PatentAlteration", models.PatentAlterationRow),
        ("get_tipo_patent_change", "/PatentChange", models.PatentChangeRow),
        ("get_tipo_patent_divide", "/PatentDivide", models.PatentDivideRow),
        ("get_tipo_trademark", "/TmarkAppl", models.TmarkApplRow),
        ("get_tipo_trademark_rights", "/TmarkRights", models.TmarkRightsRow),
        ("get_tipo_trademark_priority", "/TmarkPriority", models.TmarkPriorityRow),
        ("get_tipo_trademark_image_urls", "/TmarkPics", models.TmarkPicsRow),
        ("get_tipo_trademark_change", "/TmarkChange", models.TmarkChangeRow),
        ("get_tipo_trademark_divide", "/TmarkDivide", models.TmarkDivideRow),
    ],
)
async def test_get_helpers_fetch_by_application_number(
    wire: tuple[list[httpx2.Request], list[TipoClient]],
    helper: str,
    path: str,
    row_type: type[Any],
) -> None:
    captured, closed = wire

    rows = await getattr(api, helper)(["112100001", "112100002"], top=5, skip=15)
    await getattr(api, helper)("112100003")

    assert isinstance(rows[0], row_type)
    assert rows[0].sequence == 7
    explicit, defaults = (dict(request.url.params) for request in captured)
    assert captured[0].url.path.endswith(path)
    assert explicit["appl-no"] == "112100001,112100002"
    assert (explicit["top"], explicit["skip"]) == ("5", "15")
    assert defaults["appl-no"] == "112100003"
    assert (defaults["top"], defaults["skip"]) == ("100", "0")
    assert len(closed) == 2


# ──────────────────────────────────────────────────────────────────────
# resources.py — usage resource scaffolding
# ──────────────────────────────────────────────────────────────────────


def test_usage_resource_uri_is_namespaced() -> None:
    from patent_client_agents.tipo_opdata.resources import USAGE_RESOURCE_URI

    assert USAGE_RESOURCE_URI.startswith("pca://tipo_opdata/")


def test_get_usage_resource_returns_text() -> None:
    from patent_client_agents.tipo_opdata.resources import get_usage_resource

    body = get_usage_resource()
    assert isinstance(body, str)
    assert "TIPO" in body
