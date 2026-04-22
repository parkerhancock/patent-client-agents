"""Tests for ApplicationsClient identifier resolution."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ip_tools.uspto_odp.clients.applications import (
    ApplicationsClient,
    _clean_patent_identifier,
)
from law_tools_core.exceptions import ValidationError

# ---------------------------------------------------------------------------
# _clean_patent_identifier
# ---------------------------------------------------------------------------


class TestCleanPatentIdentifier:
    def test_strips_us_prefix(self) -> None:
        assert _clean_patent_identifier("US10123456") == "10123456"

    def test_strips_kind_code_b2(self) -> None:
        assert _clean_patent_identifier("US12036255B2") == "12036255"

    def test_strips_kind_code_a1(self) -> None:
        assert _clean_patent_identifier("US20220340882A1") == "20220340882"

    def test_strips_kind_code_b1(self) -> None:
        assert _clean_patent_identifier("US9876543B1") == "9876543"

    def test_bare_number_unchanged(self) -> None:
        assert _clean_patent_identifier("10123456") == "10123456"

    def test_strips_separators(self) -> None:
        assert _clean_patent_identifier("US 10,123,456 B2") == "10123456"

    def test_case_insensitive(self) -> None:
        assert _clean_patent_identifier("us12036255b2") == "12036255"


# ---------------------------------------------------------------------------
# resolve_identifier
# ---------------------------------------------------------------------------


def _make_client() -> ApplicationsClient:
    return ApplicationsClient(api_key="test", base_url="https://test.api.com")


def _search_response(app_number: str | None = None):
    """Build a fake search response with an applicationNumberText."""
    from unittest.mock import MagicMock

    resp = MagicMock()
    if app_number:
        resp.patentBag = [{"applicationNumberText": app_number}]
    else:
        resp.patentBag = []
    return resp


class TestResolveIdentifierApplication:
    """identifier_type='application' — direct app lookup."""

    @pytest.mark.asyncio
    async def test_resolves_application_number(self) -> None:
        client = _make_client()
        record = {"applicationNumberText": "16890123"}
        with patch.object(
            client, "_fetch_single_application_record", new_callable=AsyncMock, return_value=record
        ):
            result = await client.resolve_identifier("16890123", "application")
        assert result == "16890123"

    @pytest.mark.asyncio
    async def test_application_not_found_raises(self) -> None:
        client = _make_client()
        with patch.object(
            client, "_fetch_single_application_record", new_callable=AsyncMock, return_value=None
        ):
            with pytest.raises(ValidationError, match="not found"):
                await client.resolve_identifier("99999999", "application")

    @pytest.mark.asyncio
    async def test_does_not_search_patent_number(self) -> None:
        """Application type should never fall through to patent search."""
        client = _make_client()
        with (
            patch.object(
                client,
                "_fetch_single_application_record",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch.object(client, "search", new_callable=AsyncMock) as mock_search,
        ):
            with pytest.raises(ValidationError):
                await client.resolve_identifier("16890123", "application")
        mock_search.assert_not_called()


class TestResolveIdentifierPatent:
    """identifier_type='patent' — search by patentNumber."""

    @pytest.mark.asyncio
    async def test_resolves_bare_patent_number(self) -> None:
        client = _make_client()
        with patch.object(
            client, "search", new_callable=AsyncMock, return_value=_search_response("16890123")
        ) as mock_search:
            result = await client.resolve_identifier("10123456", "patent")
        assert result == "16890123"
        call_args = mock_search.call_args
        assert "patentNumber" in call_args.kwargs.get("query", call_args[1].get("query", ""))

    @pytest.mark.asyncio
    async def test_resolves_full_publication_number(self) -> None:
        """US12036255B2 should be cleaned to 12036255 for patent search."""
        client = _make_client()
        with patch.object(
            client, "search", new_callable=AsyncMock, return_value=_search_response("17456789")
        ) as mock_search:
            result = await client.resolve_identifier("US12036255B2", "patent")
        assert result == "17456789"
        query = mock_search.call_args.kwargs.get("query", mock_search.call_args[1].get("query", ""))
        assert '"12036255"' in query

    @pytest.mark.asyncio
    async def test_patent_not_found_raises(self) -> None:
        client = _make_client()
        with patch.object(
            client, "search", new_callable=AsyncMock, return_value=_search_response(None)
        ):
            with pytest.raises(ValidationError, match="patent number"):
                await client.resolve_identifier("99999999", "patent")

    @pytest.mark.asyncio
    async def test_does_not_try_app_lookup(self) -> None:
        """Patent type should never try direct application lookup."""
        client = _make_client()
        with (
            patch.object(
                client, "_fetch_single_application_record", new_callable=AsyncMock
            ) as mock_fetch,
            patch.object(
                client, "search", new_callable=AsyncMock, return_value=_search_response("16890123")
            ),
        ):
            await client.resolve_identifier("12036255", "patent")
        mock_fetch.assert_not_called()


class TestResolveIdentifierPublication:
    """identifier_type='publication' — search by publicationNumber."""

    @pytest.mark.asyncio
    async def test_resolves_publication_number(self) -> None:
        client = _make_client()
        with patch.object(
            client, "search", new_callable=AsyncMock, return_value=_search_response("17111222")
        ) as mock_search:
            result = await client.resolve_identifier("US20230012345A1", "publication")
        assert result == "17111222"
        query = mock_search.call_args.kwargs.get("query", mock_search.call_args[1].get("query", ""))
        assert "publicationNumber" in query

    @pytest.mark.asyncio
    async def test_publication_not_found_raises(self) -> None:
        client = _make_client()
        with patch.object(
            client, "search", new_callable=AsyncMock, return_value=_search_response(None)
        ):
            with pytest.raises(ValidationError, match="publication number"):
                await client.resolve_identifier("US20990099999A1", "publication")


class TestResolveIdentifierInvalidType:
    @pytest.mark.asyncio
    async def test_unknown_type_raises(self) -> None:
        client = _make_client()
        with pytest.raises(ValidationError, match="Unknown identifier_type"):
            await client.resolve_identifier("12345", "bogus")


_GRANT_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<us-patent-grant>
<claims id="claims">
<claim id="CLM-00001" num="00001">
<claim-text>1. A thing comprising a widget.</claim-text>
</claim>
</claims>
</us-patent-grant>
"""


class TestGetGrantedClaims:
    @pytest.mark.asyncio
    async def test_returns_parsed_claims(self) -> None:
        from unittest.mock import MagicMock

        client = _make_client()
        docs = MagicMock()
        docs.associatedDocuments = [
            {"grantDocumentMetaData": {"fileLocationURI": "https://api.uspto.gov/grant.xml"}}
        ]
        response = MagicMock()
        response.text = _GRANT_XML

        with (
            patch.object(
                client, "resolve_identifier", new_callable=AsyncMock, return_value="16890123"
            ),
            patch.object(client, "get_documents", new_callable=AsyncMock, return_value=docs),
            patch.object(client, "_request", new_callable=AsyncMock, return_value=response),
        ):
            result = await client.get_granted_claims("US10123456B2")

        assert result is not None
        assert len(result) == 1
        assert result[0]["claim_number"] == 1
        assert "widget" in result[0]["claim_text"]

    @pytest.mark.asyncio
    async def test_returns_none_when_no_grant_url(self) -> None:
        from unittest.mock import MagicMock

        client = _make_client()
        docs = MagicMock()
        docs.associatedDocuments = []

        with (
            patch.object(
                client, "resolve_identifier", new_callable=AsyncMock, return_value="16890123"
            ),
            patch.object(client, "get_documents", new_callable=AsyncMock, return_value=docs),
        ):
            result = await client.get_granted_claims("US10123456B2")

        assert result is None


class TestResolveIdentifierDefault:
    """Default identifier_type should be 'patent'."""

    @pytest.mark.asyncio
    async def test_default_is_patent(self) -> None:
        client = _make_client()
        with patch.object(
            client, "search", new_callable=AsyncMock, return_value=_search_response("16890123")
        ) as mock_search:
            result = await client.resolve_identifier("10123456")
        assert result == "16890123"
        query = mock_search.call_args.kwargs.get("query", mock_search.call_args[1].get("query", ""))
        assert "patentNumber" in query
