"""Routing contract for the consolidated bulk-data & documents facade.

The facade tools hold no business logic. Each branch forwards to an existing
per-source function. Bulk-data searches return §5.9 envelopes, while download
tools return structured signed-URL results. These tests pin the routing: that
the right ``mode``/``source`` enum value reaches the right underlying function
with the right arguments, and that the facade returns that function's result
unchanged. Targets are patched where the facade imports them
(``...mcp.facade.documents``), so no upstream HTTP is touched.

Download tools return transport records rather than §5.9 envelopes. For
``search_bulk_data`` we add an end-to-end test through
the real ``list_ipa_bulk_releases`` (mode='ipa_releases') asserting a genuine
§5.9 ``ListEnvelope`` survives the dispatch.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from mcp_data_core.mcp.downloads import download_tool_result
from patent_client_agents.facade.documents import (
    download_document,
    search_bulk_data,
)

_MOD = "patent_client_agents.facade.documents"


# ──────────────────────────────────────────────────────────────────────
# search_bulk_data — mode dispatch
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_bulk_data_routes_datasets():
    with patch(f"{_MOD}.search_bulk_datasets", new=AsyncMock(return_value="DS")) as m:
        out = await search_bulk_data(mode="datasets", query="patent grants")
    assert out == "DS"
    m.assert_awaited_once_with(query="patent grants")


@pytest.mark.asyncio
async def test_search_bulk_data_datasets_requires_query():
    from mcp_data_core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await search_bulk_data(mode="datasets")


@pytest.mark.asyncio
async def test_search_bulk_data_routes_dataset():
    with patch(f"{_MOD}._get_bulk_dataset_proxied", new=AsyncMock(return_value="ONE")) as m:
        out = await search_bulk_data(mode="dataset", product_id="PTGRXML")
    assert out == "ONE"
    m.assert_awaited_once_with("PTGRXML", False)


@pytest.mark.asyncio
async def test_search_bulk_data_dataset_requires_product_id():
    from mcp_data_core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await search_bulk_data(mode="dataset")


@pytest.mark.asyncio
async def test_search_bulk_data_routes_ipa_releases_with_dataset_id():
    with patch(f"{_MOD}.list_ipa_bulk_releases", new=AsyncMock(return_value="REL")) as m:
        out = await search_bulk_data(mode="ipa_releases", dataset_id="ipgod")
    assert out == "REL"
    m.assert_awaited_once_with(dataset_id="ipgod")


@pytest.mark.asyncio
async def test_search_bulk_data_ipa_releases_defaults_dataset_id():
    with patch(f"{_MOD}.list_ipa_bulk_releases", new=AsyncMock(return_value="REL")) as m:
        out = await search_bulk_data(mode="ipa_releases")
    assert out == "REL"
    m.assert_awaited_once_with(dataset_id="iprapid")


# ──────────────────────────────────────────────────────────────────────
# download_document source dispatch
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_download_patent_pdf_routes_positional():
    with patch(f"{_MOD}.download_patent_pdf", new=AsyncMock(return_value="PDF")) as m:
        out = await download_document(source="patent_pdf", identifier="US10123456B2")
    assert out == "PDF"
    m.assert_awaited_once_with("US10123456B2")


@pytest.mark.asyncio
async def test_download_patent_pdf_returns_structured_url_without_resource(tmp_path, monkeypatch):
    monkeypatch.setenv("LAW_TOOLS_CORE_RESOURCES_ENABLED", "0")
    monkeypatch.setenv("LAW_TOOLS_CORE_STRUCTURED_DOWNLOADS_ENABLED", "1")
    monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", "secret")
    monkeypatch.setenv("LAW_TOOLS_CORE_PUBLIC_URL", "https://mcp.example.com")
    monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))

    async def fake_download(_identifier: str):
        return await download_tool_result(
            "publications/US10123456B2",
            b"%PDF-1.4 fixture",
            filename="US10123456B2.pdf",
            content_type="application/pdf",
        )

    with patch(f"{_MOD}.download_patent_pdf", new=fake_download):
        result = await download_document(source="patent_pdf", identifier="US10123456B2")

    assert result.structured_content["download_url"].startswith("https://mcp.example.com/")
    assert result.structured_content["filename"] == "US10123456B2.pdf"
    assert "resource_uri" not in result.structured_content
    assert [block for block in result.content if block.type == "resource_link"] == []


@pytest.mark.asyncio
async def test_download_cafc_routes_positional():
    with patch(f"{_MOD}.download_cafc_pdf", new=AsyncMock(return_value="CAFC")) as m:
        out = await download_document(source="cafc", identifier="2023-1234")
    assert out == "CAFC"
    m.assert_awaited_once_with("2023-1234")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("ptab_trial", "download_ptab_trial_decisions"),
        ("ptab_trial_docs", "download_ptab_trial_documents"),
        ("ptab_appeal", "download_ptab_appeal_decisions"),
        ("ptab_interference", "download_ptab_interference_decisions"),
    ],
)
async def test_download_ptab_sources_forward_filters(source, target):
    with patch(f"{_MOD}.{target}", new=AsyncMock(return_value="PTAB")) as m:
        out = await download_document(
            source=source,
            identifier="IPR2024-00001",
            item_ids=["D1"],
            after="2020-01-01",
            before="2024-12-31",
        )
    assert out == "PTAB"
    m.assert_awaited_once_with(
        "IPR2024-00001",
        item_ids=["D1"],
        after="2020-01-01",
        before="2024-12-31",
    )


@pytest.mark.asyncio
async def test_download_usitc_attachment_routes_id_pair():
    with patch(f"{_MOD}.download_usitc_attachment", new=AsyncMock(return_value="ATT")) as m:
        out = await download_document(source="usitc_attachment", document_id=111, attachment_id=222)
    assert out == "ATT"
    m.assert_awaited_once_with(111, 222)


@pytest.mark.asyncio
async def test_download_usitc_attachment_requires_id_pair():
    from mcp_data_core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await download_document(source="usitc_attachment", document_id=111)


@pytest.mark.asyncio
async def test_download_usitc_investigation_forwards_filters():
    with patch(
        f"{_MOD}.download_usitc_investigation_documents", new=AsyncMock(return_value="INV")
    ) as m:
        out = await download_document(
            source="usitc_investigation",
            identifier="337-TA-1234",
            item_ids=["1/attachments/2"],
            document_types=["Motion"],
            after="2021-01-01",
            before="2022-01-01",
        )
    assert out == "INV"
    m.assert_awaited_once_with(
        "337-TA-1234",
        item_ids=["1/attachments/2"],
        document_types=["Motion"],
        after="2021-01-01",
        before="2022-01-01",
    )


@pytest.mark.asyncio
async def test_download_ipa_bulk_routes_with_dataset_id():
    with patch(f"{_MOD}.download_ipa_bulk", new=AsyncMock(return_value="IPA")) as m:
        out = await download_document(source="ipa_bulk", identifier="res-abc", dataset_id="ipgod")
    assert out == "IPA"
    m.assert_awaited_once_with("res-abc", dataset_id="ipgod")


@pytest.mark.asyncio
async def test_download_document_missing_identifier_raises():
    from mcp_data_core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await download_document(source="patent_pdf")


# ──────────────────────────────────────────────────────────────────────
# End-to-end: facade → real list_ipa_bulk_releases → §5.9 ListEnvelope.
# Proves the envelope contract survives the bulk-data dispatch.
# ──────────────────────────────────────────────────────────────────────


class _FakeDataset:
    def model_dump(self, by_alias=False):
        return {
            "license_title": "Creative Commons Attribution 4.0",
            "resources": [
                {
                    "id": "c79b3af6-3720-44ac-9e39-6a68f5635924",
                    "name": "IPRAPID.zip",
                    "description": "Full register",
                    "format": "ZIP",
                    "mimetype": "application/zip",
                    "size": 1300000000,
                    "last_modified": "2026-05-01T00:00:00",
                    "url": "https://data.gov.au/iprapid/IPRAPID.zip",
                }
            ],
        }


@pytest.mark.asyncio
async def test_search_bulk_data_ipa_releases_preserves_envelope_end_to_end():
    from mcp_data_core.envelope import ListEnvelope, Provenance

    with patch("patent_client_agents.mcp.tools.ip_australia_bulk.IpAustraliaBulkClient") as cls:
        client = cls.return_value.__aenter__.return_value
        client.get_dataset = AsyncMock(return_value=_FakeDataset())
        out = await search_bulk_data(mode="ipa_releases", dataset_id="iprapid")

    assert isinstance(out, ListEnvelope)
    assert isinstance(out.provenance, Provenance)
    assert out.provenance.source_name == "IP Australia — IP RAPID (data.gov.au)"
    assert "/data/dataset/iprapid" in out.provenance.source_url
    assert len(out.items) == 1
    assert out.items[0]["release_id"] == "c79b3af6-3720-44ac-9e39-6a68f5635924"
    assert out.items[0]["download_url"] == "https://data.gov.au/iprapid/IPRAPID.zip"
    assert out.more_available is False
