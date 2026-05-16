"""Envelope-shape tests for the ILPO TM feed MCP tools.

``list_ilpo_tm_releases`` is a §5.9 ListEnvelope (catalog list).
``download_ilpo_tm`` is a Shape E payload (raw dict carrying
``download_url`` + metadata; not wrapped in an envelope per §7.2).

Mocks the upstream client at the boundary so tests don't hit data.gov.il.
``ilpo_statutes`` corpus does not participate here — the TM tools live
under ``mcp_proxy`` (no corpus_* provenance), so we don't need to seed a
statutes corpus.

Note: the envelope corpus_status seeding from
``test_mcp_envelope.py`` in ``tests/ilpo_statutes/`` does not apply here
because we patch ``IlpoTmClient`` itself and the TM tool path never
touches the statutes corpus.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from law_tools_core.envelope import ListEnvelope, Provenance
from law_tools_core.exceptions import NotFoundError
from patent_client_agents.mcp.tools.ilpo import (
    download_ilpo_tm,
    list_ilpo_tm_releases,
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
        name="trade-marks",
        title="Israeli Trade Marks Register",
        license_id="cc-by-4.0",
        license_title="Creative Commons Attribution 4.0",
        resources=resources,
    )


def _make_resource(
    rid: str, *, name: str = "trade-marks-current.csv", size: int = 12_345_678
) -> dict:
    return {
        "id": rid,
        "name": name,
        "description": name,
        "format": "CSV",
        "mimetype": "text/csv",
        "size": size,
        "url": f"https://data.gov.il/dataset/x/resource/{rid}/download/{name}",
        "last_modified": "2026-05-12T02:00:00",
    }


# ──────────────────────────────────────────────────────────────────────
# list_ilpo_tm_releases — ListEnvelope
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_ilpo_tm_releases_returns_list_envelope():
    resources = [_make_resource("r-1"), _make_resource("r-2", name="dictionary.pdf", size=999)]
    dataset = _make_dataset(resources)

    with patch("patent_client_agents.mcp.tools.ilpo.IlpoTmClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_dataset = AsyncMock(return_value=dataset)

        result = await list_ilpo_tm_releases()

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "ILPO Israel — Trade Marks (data.gov.il)"
    assert "/dataset/trade-marks" in result.provenance.source_url
    assert len(result.items) == 2
    assert {r["resource_id"] for r in result.items} == {"r-1", "r-2"}
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
    assert "Creative Commons Attribution 4.0" in result.summary
    assert "trade-marks" in result.summary


@pytest.mark.asyncio
async def test_list_ilpo_tm_releases_custom_dataset_id():
    dataset = _make_dataset([_make_resource("aaa-111")])

    with patch("patent_client_agents.mcp.tools.ilpo.IlpoTmClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_dataset = AsyncMock(return_value=dataset)

        result = await list_ilpo_tm_releases(dataset_id="trademark-history")

    mock_client.get_dataset.assert_awaited_once_with("trademark-history")
    assert "/dataset/trademark-history" in result.provenance.source_url


# ──────────────────────────────────────────────────────────────────────
# download_ilpo_tm — Shape E (raw dict)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_download_ilpo_tm_returns_url_and_metadata():
    rid = "r-1"
    dataset = _make_dataset([_make_resource(rid)])

    with patch("patent_client_agents.mcp.tools.ilpo.IlpoTmClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_dataset = AsyncMock(return_value=dataset)

        result = await download_ilpo_tm(resource_id=rid)

    assert result["resource_id"] == rid
    assert result["dataset_id"] == "trade-marks"
    assert result["format"] == "CSV"
    assert result["download_url"].startswith("https://data.gov.il/")
    assert result["license"] == "Creative Commons Attribution 4.0"
    assert result["source_name"] == "ILPO Israel — Trade Marks (data.gov.il)"


@pytest.mark.asyncio
async def test_download_ilpo_tm_unknown_resource_raises():
    dataset = _make_dataset([_make_resource("aaa-111")])

    with patch("patent_client_agents.mcp.tools.ilpo.IlpoTmClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_dataset = AsyncMock(return_value=dataset)

        with pytest.raises(NotFoundError, match="not found"):
            await download_ilpo_tm(resource_id="bbb-222")
