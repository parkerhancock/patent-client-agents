"""Envelope-shape tests for the IP Australia IP RAPID bulk MCP tools.

``list_ipa_bulk_releases`` is a §5.9 ListEnvelope (catalog list).
``download_ipa_bulk`` is a Shape E payload (raw dict carrying
``download_url`` + metadata; not wrapped in an envelope per §7.2).

Mocks ``IpAustraliaBulkClient`` at the boundary.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from mcp_data_core.envelope import ListEnvelope, Provenance
from mcp_data_core.exceptions import NotFoundError
from patent_client_agents.mcp.tools.ip_australia_bulk import (
    download_ipa_bulk,
    list_ipa_bulk_releases,
)


class _FakeModel:
    """Fake upstream response: round-trips arbitrary camelCase fields via model_dump."""

    def __init__(self, **kwargs: Any) -> None:
        self._payload = kwargs

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        return dict(self._payload)


def _make_dataset(resources: list[dict]) -> _FakeModel:
    return _FakeModel(
        id="423000b8-5735-4447-bcb9-792644bcd7ea",
        name="iprapid",
        title="IP RAPID",
        license_id="cc-by-4.0",
        license_title="Creative Commons Attribution 4.0 International",
        resources=resources,
    )


def _make_resource(rid: str, *, name: str = "IPRAPID.zip", size: int = 1_318_890_174) -> dict:
    return {
        "id": rid,
        "name": name,
        "description": name,
        "format": "ZIP",
        "mimetype": "application/zip",
        "size": size,
        "url": f"https://data.gov.au/data/dataset/x/resource/{rid}/download/{name.lower()}",
        "last_modified": "2026-05-12T02:49:34.617084",
    }


# ──────────────────────────────────────────────────────────────────────
# list_ipa_bulk_releases — ListEnvelope
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_ipa_bulk_releases_returns_list_envelope():
    resources = [
        _make_resource(
            "f4750acd-decc-4b7b-99c9-4ed1c3c43441", name="data-dictionary.pdf", size=939_148
        ),
        _make_resource("c79b3af6-3720-44ac-9e39-6a68f5635924"),
    ]
    dataset = _make_dataset(resources)

    with patch(
        "patent_client_agents.mcp.tools.ip_australia_bulk.IpAustraliaBulkClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_dataset = AsyncMock(return_value=dataset)

        result = await list_ipa_bulk_releases()

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "IP Australia — IP RAPID (data.gov.au)"
    assert "/data/dataset/iprapid" in result.provenance.source_url
    assert len(result.items) == 2
    assert {r["release_id"] for r in result.items} == {
        "f4750acd-decc-4b7b-99c9-4ed1c3c43441",
        "c79b3af6-3720-44ac-9e39-6a68f5635924",
    }
    # Lean projection
    assert set(result.items[0].keys()) == {
        "release_id",
        "name",
        "description",
        "format",
        "mimetype",
        "size_bytes",
        "last_modified",
        "download_url",
    }
    assert "Creative Commons Attribution 4.0 International" in result.summary
    assert "iprapid" in result.summary


@pytest.mark.asyncio
async def test_list_ipa_bulk_releases_custom_dataset_id():
    dataset = _make_dataset([_make_resource("abc-123")])

    with patch(
        "patent_client_agents.mcp.tools.ip_australia_bulk.IpAustraliaBulkClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_dataset = AsyncMock(return_value=dataset)

        result = await list_ipa_bulk_releases(dataset_id="ipgod-2022")

    mock_client.get_dataset.assert_awaited_once_with("ipgod-2022")
    assert "/data/dataset/ipgod-2022" in result.provenance.source_url


# ──────────────────────────────────────────────────────────────────────
# download_ipa_bulk — Shape E (raw dict)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_download_ipa_bulk_returns_url_and_metadata():
    rid = "c79b3af6-3720-44ac-9e39-6a68f5635924"
    dataset = _make_dataset([_make_resource(rid)])

    with patch(
        "patent_client_agents.mcp.tools.ip_australia_bulk.IpAustraliaBulkClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_dataset = AsyncMock(return_value=dataset)

        result = await download_ipa_bulk(release_id=rid)

    assert result["release_id"] == rid
    assert result["dataset_id"] == "iprapid"
    assert result["format"] == "ZIP"
    assert result["download_url"].startswith("https://data.gov.au/")
    assert result["license"] == "Creative Commons Attribution 4.0 International"
    assert result["source_name"] == "IP Australia — IP RAPID (data.gov.au)"


@pytest.mark.asyncio
async def test_download_ipa_bulk_unknown_release_raises():
    dataset = _make_dataset([_make_resource("aaa-111")])

    with patch(
        "patent_client_agents.mcp.tools.ip_australia_bulk.IpAustraliaBulkClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_dataset = AsyncMock(return_value=dataset)

        with pytest.raises(NotFoundError, match="not found"):
            await download_ipa_bulk(release_id="bbb-222")
