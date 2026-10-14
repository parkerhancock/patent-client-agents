from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
import pytest

from patent_client_agents.oepm_spain import api
from patent_client_agents.oepm_spain.client import BASE_URL, SERVICE_NS, OepmSpainClient


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("helper", "fixture", "identifier", "field", "value"),
    [
        ("get_oepm_patent", "patent.xml", "P202400001", "title", "Controlador adaptativo"),
        ("get_oepm_trademark", "trademark.xml", "M4000000", "denomination", "NECKTIE"),
        ("get_oepm_design", "design.xml", "D0500000", "creators", ["Carmen Creadora"]),
    ],
)
async def test_get_helpers_send_soap_lookup_and_parse(
    monkeypatch: pytest.MonkeyPatch,
    fixture_dir: Path,
    helper: str,
    fixture: str,
    identifier: str,
    field: str,
    value: object,
) -> None:
    captured: list[httpx.Request] = []
    closed: list[OepmSpainClient] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=(fixture_dir / fixture).read_bytes())

    class Tracked(OepmSpainClient):
        async def __aexit__(self, *exc: object) -> None:
            await super().__aexit__(*exc)
            closed.append(self)

    def factory() -> OepmSpainClient:
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return Tracked("user", "password", client=http)

    monkeypatch.setattr(api, "OepmSpainClient", factory)

    record = await getattr(api, helper)(identifier)

    assert getattr(record, field) == value
    assert str(captured[0].url) == BASE_URL
    body = ET.fromstring(captured[0].content)
    assert body.findtext(f".//{{{SERVICE_NS}}}detalleExpedienteOEPM/request/numExpediente") == (
        identifier
    )
    assert len(closed) == 1
