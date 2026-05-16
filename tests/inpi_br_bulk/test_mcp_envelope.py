"""Envelope-shape tests for the INPI Brazil RPI bulk MCP tools.

``list_inpi_br_bulk_releases`` is a §5.9 ListEnvelope (catalog list).
``download_inpi_br_bulk`` is a Shape E payload (raw dict carrying
``download_url`` + metadata; not wrapped in an envelope per §7.2).

Mocks ``InpiBrBulkClient`` at the boundary.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from law_tools_core.envelope import ListEnvelope, Provenance
from law_tools_core.exceptions import NotFoundError
from patent_client_agents.mcp.tools.inpi_br_bulk import (
    download_inpi_br_bulk,
    list_inpi_br_bulk_releases,
)


class _FakeModel:
    """Fake upstream response: round-trips arbitrary fields via model_dump."""

    def __init__(self, **kwargs: Any) -> None:
        self._payload = kwargs

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        return dict(self._payload)


def _make_dataset(resources: list[dict]) -> _FakeModel:
    return _FakeModel(
        id="abc-123",
        name="revista-da-propriedade-industrial-rpi",
        title="Revista da Propriedade Industrial",
        license_id="odc-odbl",
        license_title="Open Database License (Decreto 8.777/2016)",
        resources=resources,
    )


def _make_resource(rid: str, *, name: str = "RPI2879_Patentes.zip", size: int = 25_000_000) -> dict:
    return {
        "id": rid,
        "name": name,
        "description": name,
        "format": "ZIP",
        "mimetype": "application/zip",
        "size": size,
        "url": f"https://revistas.inpi.gov.br/xml/{name}",
        "last_modified": "2026-03-10T03:00:00",
    }


# ──────────────────────────────────────────────────────────────────────
# list_inpi_br_bulk_releases — ListEnvelope
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_inpi_br_bulk_releases_returns_list_envelope():
    resources = [
        _make_resource("rpi-2879-patentes"),
        _make_resource("rpi-2879-marcas", name="RPI2879_Marcas.zip", size=80_000_000),
    ]
    dataset = _make_dataset(resources)

    with patch("patent_client_agents.mcp.tools.inpi_br_bulk.InpiBrBulkClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_dataset = AsyncMock(return_value=dataset)

        result = await list_inpi_br_bulk_releases()

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "INPI Brazil — RPI (dados.gov.br)"
    assert "/dataset/revista-da-propriedade-industrial-rpi" in result.provenance.source_url
    assert len(result.items) == 2
    assert {r["resource_id"] for r in result.items} == {
        "rpi-2879-patentes",
        "rpi-2879-marcas",
    }
    # Lean projection
    assert set(result.items[0].keys()) == {
        "resource_id",
        "name",
        "description",
        "format",
        "mimetype",
        "size_bytes",
        "last_modified",
        "download_url",
    }
    assert "Open Database License" in result.summary
    assert "revista-da-propriedade-industrial-rpi" in result.summary


@pytest.mark.asyncio
async def test_list_inpi_br_bulk_releases_custom_dataset_id():
    dataset = _make_dataset([_make_resource("abc-123")])

    with patch("patent_client_agents.mcp.tools.inpi_br_bulk.InpiBrBulkClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_dataset = AsyncMock(return_value=dataset)

        result = await list_inpi_br_bulk_releases(dataset_id="bw-p-2020")

    mock_client.get_dataset.assert_awaited_once_with("bw-p-2020")
    assert "/dataset/bw-p-2020" in result.provenance.source_url


# ──────────────────────────────────────────────────────────────────────
# download_inpi_br_bulk — Shape E (raw dict)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_download_inpi_br_bulk_returns_url_and_metadata():
    rid = "rpi-2879-patentes"
    dataset = _make_dataset([_make_resource(rid)])

    with patch("patent_client_agents.mcp.tools.inpi_br_bulk.InpiBrBulkClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_dataset = AsyncMock(return_value=dataset)

        result = await download_inpi_br_bulk(resource_id=rid)

    assert result["resource_id"] == rid
    assert result["dataset_id"] == "revista-da-propriedade-industrial-rpi"
    assert result["format"] == "ZIP"
    assert result["download_url"].startswith("https://revistas.inpi.gov.br/")
    assert result["license"] == "Open Database License (Decreto 8.777/2016)"
    assert result["source_name"] == "INPI Brazil — RPI (dados.gov.br)"


@pytest.mark.asyncio
async def test_download_inpi_br_bulk_unknown_resource_raises():
    dataset = _make_dataset([_make_resource("aaa-111")])

    with patch("patent_client_agents.mcp.tools.inpi_br_bulk.InpiBrBulkClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_dataset = AsyncMock(return_value=dataset)

        with pytest.raises(NotFoundError, match="not found"):
            await download_inpi_br_bulk(resource_id="bbb-222")
