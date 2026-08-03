from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
import pytest

from mcp_data_core.exceptions import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from patent_client_agents.oepm_spain.client import (
    BASE_URL,
    SERVICE_NS,
    SOAP_NS,
    OepmSpainClient,
)
from patent_client_agents.oepm_spain.models import parse_oepm_date


def _client_for(
    fixture_dir: Path,
    fixture_name: str,
    captured: list[httpx.Request] | None = None,
) -> OepmSpainClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        return httpx.Response(200, content=(fixture_dir / fixture_name).read_bytes())

    return OepmSpainClient(
        "explicit-user",
        "explicit-password",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.asyncio
async def test_patent_request_matches_wsdl_and_response_parses(fixture_dir: Path) -> None:
    captured: list[httpx.Request] = []
    async with _client_for(fixture_dir, "patent.xml", captured) as client:
        record = await client.get_patent("p202400001")

    assert len(captured) == 1
    request = captured[0]
    assert str(request.url) == BASE_URL
    assert request.headers["SOAPAction"] == ""
    assert request.headers["Content-Type"].startswith("text/xml")
    root = ET.fromstring(request.content)
    body = root.find(f"{{{SOAP_NS}}}Body")
    operation = body.find(f"{{{SERVICE_NS}}}detalleExpedienteOEPM") if body is not None else None
    assert operation is not None
    request_node = operation.find("request")
    assert request_node is not None
    assert request_node.findtext("numExpediente") == "P202400001"
    assert request_node.findtext("usuario") == "explicit-user"
    assert request_node.findtext("pass") == "explicit-password"
    assert record.identifier == "P202400001"
    assert record.modality == "P"
    assert record.title == "Controlador adaptativo"
    assert record.status == "EN VIGOR"
    assert record.publication_number == "ES3000001"
    assert record.filing_date and record.filing_date.isoformat() == "2024-01-02"
    assert record.inventors == ["Ana Inventora"]
    assert record.owner == "Necktie Labs LLC"
    assert record.representative == "Rosa Representante"
    assert record.proceedings[0].description == "Publicación"
    assert "extensionFutura" in str(record.raw)


@pytest.mark.asyncio
async def test_trademark_response_parses_documented_fields(fixture_dir: Path) -> None:
    async with _client_for(fixture_dir, "trademark.xml") as client:
        record = await client.get_trademark("M4000000")
    assert record.denomination == "NECKTIE"
    assert record.mark_type == "D_DENOMINATIVO"
    assert record.filing_date and record.filing_date.isoformat() == "2024-01-02"
    assert record.next_renewal_date and record.next_renewal_date.year == 2034
    assert record.nice_classes == ["42", "9"]
    assert record.vienna_classes == ["27.05.01"]
    assert record.owner == "Necktie Labs, LLC"


@pytest.mark.asyncio
async def test_design_response_parses_documented_fields(fixture_dir: Path) -> None:
    async with _client_for(fixture_dir, "design.xml") as client:
        record = await client.get_design("D0500000")
    assert record.application_number == "D0500000"
    assert record.status_code == "CONCEDIDO"
    assert record.filing_place == "Madrid"
    assert record.filing_date and record.filing_date.isoformat() == "2024-01-02"
    assert record.publication_date and record.publication_date.isoformat() == "2024-05-06"
    assert record.creators == ["Carmen Creadora"]


def test_credentials_https_dates_and_modality_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OEPM_CEO_USERNAME", raising=False)
    monkeypatch.delenv("OEPM_CEO_PASSWORD", raising=False)
    with pytest.raises(ConfigurationError, match="oepm.es"):
        OepmSpainClient()
    with pytest.raises(ConfigurationError, match="HTTPS"):
        OepmSpainClient("user", "password", base_url="http://example.test")
    compact_date = parse_oepm_date("20240102")
    slash_date = parse_oepm_date("02/01/2024")
    assert compact_date and compact_date.isoformat() == "2024-01-02"
    assert slash_date and slash_date.isoformat() == "2024-01-02"
    assert parse_oepm_date("bad") is None


@pytest.mark.asyncio
async def test_typed_methods_reject_wrong_or_unknown_modalities(fixture_dir: Path) -> None:
    async with _client_for(fixture_dir, "patent.xml") as client:
        with pytest.raises(ValidationError, match="does not accept"):
            await client.get_patent("M4000000")
        with pytest.raises(ValidationError, match="Unsupported"):
            await client.get_patent("ZZ4000000")
        with pytest.raises(ValidationError, match="must start"):
            await client.get_patent("4000000")


@pytest.mark.asyncio
async def test_wsdl_result_errors_and_soap_faults(fixture_dir: Path) -> None:
    async with _client_for(fixture_dir, "not_found.xml") as client:
        with pytest.raises(NotFoundError, match="no encontrado"):
            await client.get_patent("P0000001")
    async with _client_for(fixture_dir, "auth_error.xml") as client:
        with pytest.raises(AuthenticationError) as raised:
            await client.get_patent("P0000001")
    assert raised.value.response_body is None
    async with _client_for(fixture_dir, "fault.xml") as client:
        with pytest.raises(ApiError, match="Temporary failure"):
            await client.get_patent("P0000001")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "body", "error"),
    [
        (401, b"denied", AuthenticationError),
        (500, b"failed", ApiError),
        (200, b"not xml", ApiError),
        (200, b'<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"/>', ApiError),
    ],
)
async def test_http_and_malformed_errors(status: int, body: bytes, error: type[Exception]) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body)

    async with OepmSpainClient(
        "user", "password", client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    ) as client:
        with pytest.raises(error):
            await client.get_patent("P0000001")


@pytest.mark.asyncio
async def test_rate_limit_preserves_retry_after() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "7"})

    async with OepmSpainClient(
        "user", "password", client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    ) as client:
        with pytest.raises(RateLimitError) as raised:
            await client.get_patent("P0000001")
    assert raised.value.retry_after == 7
