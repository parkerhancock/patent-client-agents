"""Tests for CopyrightClient with mocked HTTP responses."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from patent_client_agents.copyright.client import CopyrightClient, CopyrightError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SEARCH_RESPONSE = {
    "metadata": {
        "took_ms": 39,
        "hit_count": 856,
        "hit_count_relation": "eq",
        "max_score": 28.44,
        "query": "gatsby",
        "fields": "title",
        "histogram": {
            "filtered": {
                "type_of_record": {"registration": 534, "recordation": 322},
                "type_of_work": {"text": 200, "visual_material": 100},
                "registration_class": {"TX": 172, "VA": 142},
                "registration_status": {"published": 346, "unpublished": 188},
                "system_of_origin": {"voyager": 849, "card_catalog": 7},
                "recordation_item_type": {"assignment": 50},
            },
            "unfiltered": {},
        },
    },
    "data": [
        {
            "score": 28.44,
            "hit": {
                "public_records_id": "voyager_12345",
                "title_of_work": ["The Great Gatsby"],
                "registration_number": ["TX 1234567"],
                "copyright_number_for_display": "TX 1234567",
                "type_of_record": "registration",
                "registration_status": "published",
                "registration_class": ["TX"],
                "claimant": ["F. Scott Fitzgerald Estate"],
                "claimants": [{"claimant_full_name": "F. Scott Fitzgerald Estate"}],
                "publisher_name": ["Scribner"],
                "type_of_work": "text",
                "all_type_of_work": ["text"],
                "system_of_origin": "voyager",
                "application_date": ["2020-01-15"],
                "first_published_date": ["1925-04-10"],
                "fee_date": ["2020-01-15"],
                "deposit_received_date": ["2020-01-20"],
                "representative_date": "2020-01-15",
                "link_to_image_url": [],
            },
        },
        {
            "score": 25.10,
            "hit": {
                "public_records_id": "voyager_67890",
                "title_of_work": ["Gatsby: An American Story"],
                "registration_number": ["PA 9876543"],
                "copyright_number_for_display": "PA 9876543",
                "type_of_record": "registration",
                "registration_status": "published",
                "registration_class": ["PA"],
                "claimant": ["Some Studio LLC"],
                "claimants": [{"claimant_full_name": "Some Studio LLC"}],
                "publisher_name": [],
                "type_of_work": "motion_picture",
                "all_type_of_work": ["motion_picture"],
                "system_of_origin": "voyager",
                "application_date": ["2022-06-01"],
                "first_published_date": ["2022-05-15"],
                "fee_date": ["2022-06-01"],
                "deposit_received_date": [],
                "representative_date": "2022-06-01",
                "link_to_image_url": [],
            },
        },
    ],
}

_EMPTY_RESPONSE = {
    "metadata": {
        "took_ms": 5,
        "hit_count": 0,
        "hit_count_relation": "eq",
        "max_score": 0.0,
        "query": "zzzznotfound",
        "fields": "all_fields",
        "histogram": {"filtered": {}, "unfiltered": {}},
    },
    "data": [],
}


def _mock_response(data: dict) -> httpx.Response:
    """Create a mock httpx.Response with JSON data."""
    request = httpx.Request("GET", "https://api.publicrecords.copyright.gov/")
    return httpx.Response(
        200,
        content=json.dumps(data).encode(),
        headers={"content-type": "application/json"},
        request=request,
    )


def _mock_error_response(status: int = 500, text: str = "Error") -> httpx.Response:
    request = httpx.Request("GET", "https://api.publicrecords.copyright.gov/")
    return httpx.Response(status, text=text, request=request)


@pytest.fixture
def mock_request():
    """Patch BaseAsyncClient's underlying httpx.AsyncClient.request.

    BaseAsyncClient routes everything through ``self._client.request(...)``
    rather than ``.get(...)``, so we patch at that seam.
    """
    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock:
        yield mock


# ---------------------------------------------------------------------------
# Search tests
# ---------------------------------------------------------------------------


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_returns_records(self, mock_request):
        mock_request.return_value = _mock_response(_SEARCH_RESPONSE)
        async with CopyrightClient(use_cache=False) as client:
            response = await client.search("gatsby", field="title")
        assert len(response.records) == 2
        assert response.metadata.hit_count == 856

    @pytest.mark.asyncio
    async def test_first_record_fields(self, mock_request):
        mock_request.return_value = _mock_response(_SEARCH_RESPONSE)
        async with CopyrightClient(use_cache=False) as client:
            response = await client.search("gatsby", field="title")
        rec = response.records[0]
        assert rec.title_of_work == ["The Great Gatsby"]
        assert rec.registration_number == ["TX 1234567"]
        assert rec.copyright_number_for_display == "TX 1234567"
        assert rec.type_of_record == "registration"
        assert rec.registration_status == "published"
        assert rec.claimant == ["F. Scott Fitzgerald Estate"]
        assert rec.publisher_name == ["Scribner"]
        assert rec.type_of_work == "text"
        assert rec.system_of_origin == "voyager"
        assert rec.score == 28.44

    @pytest.mark.asyncio
    async def test_metadata(self, mock_request):
        mock_request.return_value = _mock_response(_SEARCH_RESPONSE)
        async with CopyrightClient(use_cache=False) as client:
            response = await client.search("gatsby", field="title")
        assert response.metadata.took_ms == 39
        assert response.metadata.query == "gatsby"
        assert response.metadata.max_score == 28.44

    def test_record_accepts_scalar_for_list_fields(self):
        """Some upstream records send scalars for fields typed as list[str]
        (e.g. SR-prefix sound recordings have a single registration_number).
        The model must coerce these to one-element lists rather than reject
        the row, otherwise search_copyright errors on the whole page."""
        from patent_client_agents.copyright.models import CopyrightRecord

        rec = CopyrightRecord(
            public_records_id="card_catalog_test.1",
            registration_number="SR0000035099",  # type: ignore[arg-type]
            title_of_work="Single Title",  # type: ignore[arg-type]
            claimant=None,  # type: ignore[arg-type]
        )
        assert rec.registration_number == ["SR0000035099"]
        assert rec.title_of_work == ["Single Title"]
        assert rec.claimant == []

    @pytest.mark.asyncio
    async def test_histogram(self, mock_request):
        mock_request.return_value = _mock_response(_SEARCH_RESPONSE)
        async with CopyrightClient(use_cache=False) as client:
            response = await client.search("gatsby", field="title")
        assert response.histogram.type_of_record == {
            "registration": 534,
            "recordation": 322,
        }
        assert response.histogram.system_of_origin == {
            "voyager": 849,
            "card_catalog": 7,
        }

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_request):
        mock_request.return_value = _mock_response(_EMPTY_RESPONSE)
        async with CopyrightClient(use_cache=False) as client:
            response = await client.search("zzzznotfound")
        assert len(response.records) == 0
        assert response.metadata.hit_count == 0

    @pytest.mark.asyncio
    async def test_sends_correct_params(self, mock_request):
        mock_request.return_value = _mock_response(_EMPTY_RESPONSE)
        async with CopyrightClient(use_cache=False) as client:
            await client.search("test", field="name", page=3, page_size=25)
        _, kwargs = mock_request.call_args
        params = kwargs["params"]
        assert params["query"] == "test"
        assert params["field_type"] == "name"
        assert params["page_number"] == "3"
        assert params["records_per_page"] == "25"
        assert params["model"] == ""

    @pytest.mark.asyncio
    async def test_invalid_field_raises(self, mock_request):
        async with CopyrightClient(use_cache=False) as client:
            with pytest.raises(ValueError, match="Invalid field"):
                await client.search("test", field="invalid")

    @pytest.mark.asyncio
    async def test_api_error_raises(self, mock_request):
        from mcp_data_core.exceptions import ServerError

        mock_request.return_value = _mock_error_response(500, "Internal Server Error")
        async with CopyrightClient(use_cache=False, max_retries=1) as client:
            # BaseAsyncClient raises ServerError for 5xx; the legacy
            # CopyrightError type also still works as a catch-all alias
            # for users who imported it directly.
            with pytest.raises((CopyrightError, ServerError)):
                await client.search("test")


# ---------------------------------------------------------------------------
# Convenience method tests
# ---------------------------------------------------------------------------


class TestConvenienceMethods:
    @pytest.mark.asyncio
    async def test_search_by_title(self, mock_request):
        mock_request.return_value = _mock_response(_SEARCH_RESPONSE)
        async with CopyrightClient(use_cache=False) as client:
            await client.search_by_title("gatsby")
        _, kwargs = mock_request.call_args
        assert kwargs["params"]["field_type"] == "title"

    @pytest.mark.asyncio
    async def test_search_by_name(self, mock_request):
        mock_request.return_value = _mock_response(_SEARCH_RESPONSE)
        async with CopyrightClient(use_cache=False) as client:
            await client.search_by_name("Disney")
        _, kwargs = mock_request.call_args
        assert kwargs["params"]["field_type"] == "name"


# ---------------------------------------------------------------------------
# Get record tests
# ---------------------------------------------------------------------------


class TestGetRecord:
    @pytest.mark.asyncio
    async def test_get_record_found(self, mock_request):
        mock_request.return_value = _mock_response(_SEARCH_RESPONSE)
        async with CopyrightClient(use_cache=False) as client:
            record = await client.get_record("voyager_12345")
        assert record is not None
        assert record.title_of_work == ["The Great Gatsby"]

    @pytest.mark.asyncio
    async def test_get_record_not_found(self, mock_request):
        mock_request.return_value = _mock_response(_EMPTY_RESPONSE)
        async with CopyrightClient(use_cache=False) as client:
            record = await client.get_record("nonexistent_id")
        assert record is None
