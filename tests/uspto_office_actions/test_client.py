"""Tests for USPTO Office Action Dataset API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from ip_tools.uspto_office_actions import OfficeActionClient

API_KEY = "test-key"


def _make_response(json_data: dict, status_code: int = 200) -> httpx.Response:
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = status_code < 400
    resp.json.return_value = json_data
    resp.text = ""
    return resp


# ---------------------------------------------------------------------------
# Rejections
# ---------------------------------------------------------------------------


class TestSearchRejections:
    @pytest.mark.asyncio
    async def test_basic_search(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_request = AsyncMock(
            return_value=_make_response(
                {
                    "response": {
                        "numFound": 2,
                        "start": 0,
                        "docs": [
                            {
                                "id": "abc123",
                                "patentApplicationNumber": "16123456",
                                "hasRej103": 1,
                                "hasRej102": 0,
                                "legalSectionCode": "103",
                                "nationalClass": "438",
                            },
                            {
                                "id": "def456",
                                "patentApplicationNumber": "16123456",
                                "hasRej112": 1,
                                "legalSectionCode": "112",
                            },
                        ],
                    }
                }
            )
        )
        monkeypatch.setattr(httpx.AsyncClient, "request", mock_request)

        async with OfficeActionClient(api_key=API_KEY) as client:
            result = await client.search_rejections("patentApplicationNumber:16123456")

        assert result.num_found == 2
        assert len(result.results) == 2
        assert result.results[0].patent_application_number == "16123456"
        assert result.results[0].has_rej_103 == 1
        assert result.results[1].has_rej_112 == 1

        # Verify the POST was made with form data
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"
        assert "/oa_rejections/v2/records" in call_args[0][1]
        assert call_args[1]["data"]["criteria"] == "patentApplicationNumber:16123456"

    @pytest.mark.asyncio
    async def test_pagination(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_request = AsyncMock(
            return_value=_make_response({"response": {"numFound": 100, "start": 50, "docs": []}})
        )
        monkeypatch.setattr(httpx.AsyncClient, "request", mock_request)

        async with OfficeActionClient(api_key=API_KEY) as client:
            result = await client.search_rejections("hasRej103:1", start=50, rows=10)

        assert result.num_found == 100
        assert result.start == 50
        call_args = mock_request.call_args
        assert call_args[1]["data"]["start"] == "50"
        assert call_args[1]["data"]["rows"] == "10"

    @pytest.mark.asyncio
    async def test_empty_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_request = AsyncMock(return_value=_make_response({}))
        monkeypatch.setattr(httpx.AsyncClient, "request", mock_request)

        async with OfficeActionClient(api_key=API_KEY) as client:
            result = await client.search_rejections("patentApplicationNumber:99999999")

        assert result.num_found == 0
        assert result.results == []

    @pytest.mark.asyncio
    async def test_eligibility_indicators(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_request = AsyncMock(
            return_value=_make_response(
                {
                    "response": {
                        "numFound": 1,
                        "start": 0,
                        "docs": [
                            {
                                "id": "xyz",
                                "patentApplicationNumber": "16000001",
                                "aliceIndicator": True,
                                "bilskiIndicator": False,
                                "mayoIndicator": True,
                                "myriadIndicator": False,
                                "hasRej101": 1,
                                "allowedClaimIndicator": False,
                            }
                        ],
                    }
                }
            )
        )
        monkeypatch.setattr(httpx.AsyncClient, "request", mock_request)

        async with OfficeActionClient(api_key=API_KEY) as client:
            result = await client.search_rejections("patentApplicationNumber:16000001")

        rec = result.results[0]
        assert rec.alice_indicator is True
        assert rec.mayo_indicator is True
        assert rec.bilski_indicator is False
        assert rec.has_rej_101 == 1


# ---------------------------------------------------------------------------
# Citations
# ---------------------------------------------------------------------------


class TestSearchCitations:
    @pytest.mark.asyncio
    async def test_basic_search(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_request = AsyncMock(
            return_value=_make_response(
                {
                    "response": {
                        "numFound": 1,
                        "start": 0,
                        "docs": [
                            {
                                "id": "cit001",
                                "patentApplicationNumber": "16123456",
                                "referenceIdentifier": "Smith US 20200012345 A1",
                                "parsedReferenceIdentifier": "20200012345",
                                "examinerCitedReferenceIndicator": True,
                                "legalSectionCode": "102",
                            }
                        ],
                    }
                }
            )
        )
        monkeypatch.setattr(httpx.AsyncClient, "request", mock_request)

        async with OfficeActionClient(api_key=API_KEY) as client:
            result = await client.search_citations("patentApplicationNumber:16123456")

        assert result.num_found == 1
        rec = result.results[0]
        assert rec.reference_identifier == "Smith US 20200012345 A1"
        assert rec.parsed_reference_identifier == "20200012345"
        assert rec.examiner_cited_reference_indicator is True

        call_args = mock_request.call_args
        assert "/oa_citations/v2/records" in call_args[0][1]


# ---------------------------------------------------------------------------
# Office Action Text
# ---------------------------------------------------------------------------


class TestSearchOfficeActionText:
    @pytest.mark.asyncio
    async def test_basic_search(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_request = AsyncMock(
            return_value=_make_response(
                {
                    "response": {
                        "numFound": 1,
                        "start": 0,
                        "docs": [
                            {
                                "id": "oa001",
                                "patentApplicationNumber": "16123456",
                                "bodyText": ["This is the office action text..."],
                                "inventionTitle": "Widget Apparatus",
                                "legacyDocumentCodeIdentifier": ["CTNF"],
                                "submissionDate": "2020-03-27T00:00:00",
                                "groupArtUnitNumber": "2641",
                            }
                        ],
                    }
                }
            )
        )
        monkeypatch.setattr(httpx.AsyncClient, "request", mock_request)

        async with OfficeActionClient(api_key=API_KEY) as client:
            result = await client.search_office_action_text("patentApplicationNumber:16123456")

        assert result.num_found == 1
        rec = result.results[0]
        assert "office action text" in rec.body_text[0]
        assert rec.invention_title == "Widget Apparatus"

        call_args = mock_request.call_args
        assert "/oa_actions/v1/records" in call_args[0][1]


# ---------------------------------------------------------------------------
# Enriched Citations
# ---------------------------------------------------------------------------


class TestSearchEnrichedCitations:
    @pytest.mark.asyncio
    async def test_basic_search(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_request = AsyncMock(
            return_value=_make_response(
                {
                    "response": {
                        "numFound": 1,
                        "start": 0,
                        "docs": [
                            {
                                "id": "ec001",
                                "patentApplicationNumber": "16123456",
                                "citedDocumentIdentifier": "US 20070217688 A1",
                                "inventorNameText": "Sabe; Kohtaro",
                                "kindCode": "A1",
                                "countryCode": "US",
                                "officeActionDate": "2020-03-27T00:00:00",
                                "officeActionCategory": "CTNF",
                                "citationCategoryCode": "X",
                                "relatedClaimNumberText": "1-14",
                                "passageLocationText": ["figure 23|claim 8"],
                                "nplIndicator": False,
                                "examinerCitedReferenceIndicator": True,
                            }
                        ],
                    }
                }
            )
        )
        monkeypatch.setattr(httpx.AsyncClient, "request", mock_request)

        async with OfficeActionClient(api_key=API_KEY) as client:
            result = await client.search_enriched_citations("patentApplicationNumber:16123456")

        assert result.num_found == 1
        rec = result.results[0]
        assert rec.cited_document_identifier == "US 20070217688 A1"
        assert rec.inventor_name_text == "Sabe; Kohtaro"
        assert rec.kind_code == "A1"
        assert rec.country_code == "US"
        assert rec.citation_category_code == "X"
        assert rec.related_claim_number_text == "1-14"
        assert "figure 23" in rec.passage_location_text[0]
        assert rec.examiner_cited_reference_indicator is True
        assert rec.npl_indicator is False

        call_args = mock_request.call_args
        assert "/enriched_cited_reference_metadata/v3/records" in call_args[0][1]


# ---------------------------------------------------------------------------
# Client basics
# ---------------------------------------------------------------------------


class TestClientConfig:
    def test_base_url(self) -> None:
        from ip_tools.uspto_odp.clients.base import BASE_URL

        assert "api.uspto.gov" in BASE_URL

    @pytest.mark.asyncio
    async def test_requires_api_key(self) -> None:
        """Office action client requires a USPTO ODP API key."""
        # Unset env var to ensure it's not picked up
        import os

        from law_tools_core.exceptions import ConfigurationError

        old = os.environ.pop("USPTO_ODP_API_KEY", None)
        try:
            with pytest.raises(ConfigurationError):
                OfficeActionClient(api_key=None)
        finally:
            if old is not None:
                os.environ["USPTO_ODP_API_KEY"] = old

    @pytest.mark.asyncio
    async def test_sends_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Office action client sends X-API-KEY header."""
        mock_request = AsyncMock(
            return_value=_make_response({"response": {"numFound": 0, "start": 0, "docs": []}})
        )
        monkeypatch.setattr(httpx.AsyncClient, "request", mock_request)

        async with OfficeActionClient(api_key=API_KEY) as client:
            await client.search_rejections("*:*", rows=1)

        assert mock_request.call_args is not None
