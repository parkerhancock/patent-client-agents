"""Exact CAFC PDF retrieval avoids first-opinion selection."""

from unittest.mock import AsyncMock, patch

import pytest

from patent_client_agents.mcp.tools import cafc


@pytest.mark.asyncio
async def test_exact_url_bypasses_ambiguous_appeal_and_versions_bytes():
    async def response(path, content, **metadata):
        return {"resource": path, **metadata}

    url = "https://www.cafc.uscourts.gov/opinions-orders/23-1.ORDER.pdf"
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.download_pdf.side_effect = [b"old", b"new"]
    with (
        patch.object(cafc, "CAFCClient", return_value=client),
        patch.object(cafc, "download_response", response),
    ):
        first = await cafc.download_cafc_pdf("23-1", document_url=url)
        second = await cafc.download_cafc_pdf("23-1", document_url=url)
    client.search.assert_not_called()
    assert first["document_id"] == second["document_id"] == url
    assert first["content_sha256"] != second["content_sha256"]
    assert first["resource"] != second["resource"]
    assert first["bytes_retrieved_at"] == first["source_checked_at"]


@pytest.mark.asyncio
async def test_exact_url_rejects_other_hosts():
    with pytest.raises(ValueError):
        await cafc.download_cafc_pdf("23-1", document_url="https://example.com/test.pdf")
