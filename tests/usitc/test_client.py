"""Tests for USITC clients."""

from __future__ import annotations

import base64
import json

import httpx
import pytest

from mcp_data_core.exceptions import AuthenticationError
from patent_client_agents.usitc.client import DataWebClient, EdisClient, HtsClient, IdsClient
from patent_client_agents.usitc.models import (
    DataWebReport,
    DownloadedAttachment,
    EdisAttachment,
    EdisDocument,
    EdisInvestigation,
    HtsExportResponse,
    HtsSearchResult,
    IdsInvestigation,
    SavedQuerySummary,
)


def _make_jwt(exp_epoch: int) -> str:
    """Build an unsigned JWT with the given ``exp`` claim for tests."""
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    body = (
        base64.urlsafe_b64encode(json.dumps({"sub": "TEST", "exp": exp_epoch}).encode())
        .rstrip(b"=")
        .decode()
    )
    return f"{header}.{body}.signature"


class TestEdisClient:
    """Tests for EdisClient."""

    @pytest.fixture(autouse=True)
    def _isolate_token_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Keep the developer's real (possibly expired) USITC_EDIS_TOKEN
        # from leaking into mock-transport tests and tripping the
        # JWT-exp pre-flight check.
        monkeypatch.delenv("USITC_EDIS_TOKEN", raising=False)

    @pytest.fixture
    def mock_client(self) -> httpx.AsyncClient:
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path

            if "/investigation" in path:
                return httpx.Response(
                    200,
                    text="""
                    <root>
                        <investigation>
                            <investigationNumber>337-TA-1234</investigationNumber>
                            <investigationTitle>Test Investigation</investigationTitle>
                            <investigationStatus>Active</investigationStatus>
                        </investigation>
                    </root>
                    """,
                )
            elif "/document" in path and "/download" not in path and "/attachment" not in path:
                return httpx.Response(
                    200,
                    text="""
                    <root>
                        <document>
                            <id>12345</id>
                            <documentTitle>Test Document</documentTitle>
                            <securityLevel>Public</securityLevel>
                        </document>
                    </root>
                    """,
                )
            elif "/attachment" in path and "/download" not in path:
                return httpx.Response(
                    200,
                    text="""
                    <root>
                        <attachment>
                            <id>999</id>
                            <documentId>12345</documentId>
                            <title>Test Attachment</title>
                        </attachment>
                    </root>
                    """,
                )
            elif "/download" in path:
                return httpx.Response(
                    200,
                    content=b"PDF content",
                    headers={
                        "Content-Type": "application/pdf",
                        "Content-Disposition": "attachment; filename=test.pdf",
                    },
                )

            return httpx.Response(404, text="Not found")

        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    def test_init_without_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("USITC_EDIS_TOKEN", raising=False)
        client = EdisClient()
        assert client._client is not None

    def test_init_with_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("USITC_EDIS_TOKEN", "test_token")
        client = EdisClient()
        assert client._client is not None

    def test_init_does_not_send_browser_user_agent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """edis.usitc.gov (Akamai) 403s any User-Agent that looks like a
        browser-impersonator OR an unrecognized custom UA. PCA v0.6.6+
        no longer injects a Chrome UA; EdisClient passes no UA either,
        so httpx's native ``python-httpx/...`` UA goes through — which
        Akamai allows as a known programmatic consumer. Earlier we
        tried ``law-tools-edis/1.0`` (issue #16) and that 403d too."""
        monkeypatch.delenv("USITC_EDIS_TOKEN", raising=False)
        client = EdisClient()
        ua = client._client.headers.get("user-agent", "")
        assert "Mozilla" not in ua, f"browser-impersonator UA leaked back: {ua}"
        assert "Chrome" not in ua, f"browser-impersonator UA leaked back: {ua}"
        assert "law-tools-edis" not in ua, f"the Akamai-blocked law-tools-edis UA snuck back: {ua}"

    @pytest.mark.asyncio
    async def test_list_investigations(self, mock_client: httpx.AsyncClient) -> None:
        client = EdisClient(client=mock_client)
        result = await client.list_investigations()
        assert len(result) == 1
        assert isinstance(result[0], EdisInvestigation)
        assert result[0].investigation_number == "337-TA-1234"

    @pytest.mark.asyncio
    async def test_list_documents(self, mock_client: httpx.AsyncClient) -> None:
        client = EdisClient(client=mock_client)
        result = await client.list_documents()
        assert len(result) == 1
        assert isinstance(result[0], EdisDocument)
        assert result[0].id == 12345

    @pytest.mark.asyncio
    async def test_list_attachments(self, mock_client: httpx.AsyncClient) -> None:
        client = EdisClient(client=mock_client)
        result = await client.list_attachments(document_id=12345)
        assert len(result) == 1
        assert isinstance(result[0], EdisAttachment)
        assert result[0].id == 999

    @pytest.mark.asyncio
    async def test_download_attachment(
        self, mock_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("USITC_EDIS_TOKEN", "test_token")
        client = EdisClient(client=mock_client)
        result = await client.download_attachment(document_id=12345, attachment_id=999)
        assert isinstance(result, DownloadedAttachment)
        assert result.document_id == 12345
        assert result.attachment_id == 999

    @pytest.mark.asyncio
    async def test_download_attachment_uses_correct_accept_header(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify download uses Accept: */* header (not application/xml)."""
        monkeypatch.setenv("USITC_EDIS_TOKEN", "test_token")
        captured_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if "/download" in request.url.path:
                captured_headers.update(request.headers)
                return httpx.Response(
                    200,
                    content=b"PDF content",
                    headers={"Content-Type": "application/pdf"},
                )
            return httpx.Response(404)

        mock = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = EdisClient(client=mock)
        await client.download_attachment(document_id=12345, attachment_id=999)

        # Download endpoint requires Accept: */* to avoid 406 errors
        assert captured_headers.get("accept") == "*/*"

    @pytest.mark.asyncio
    async def test_list_investigations_with_number_uses_path(self) -> None:
        """Verify investigation_number is sent as a path segment, not a query param."""
        captured_paths: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_paths.append(request.url.path)
            return httpx.Response(
                200,
                text="<root><investigation><investigationNumber>337-1234</investigationNumber></investigation></root>",
            )

        mock = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = EdisClient(client=mock)
        await client.list_investigations(investigation_number="337-1234")
        assert captured_paths[0].endswith("/investigation/337-1234")

    @pytest.mark.asyncio
    async def test_list_investigations_with_number_and_phase_uses_path(self) -> None:
        """Verify number + phase are both path segments."""
        captured_paths: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_paths.append(request.url.path)
            return httpx.Response(
                200,
                text="<root><investigation><investigationNumber>337-1234</investigationNumber></investigation></root>",
            )

        mock = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = EdisClient(client=mock)
        await client.list_investigations(
            investigation_number="337-1234", investigation_phase="Final"
        )
        assert captured_paths[0].endswith("/investigation/337-1234/Final")

    @pytest.mark.asyncio
    async def test_download_requires_auth(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify download_attachment raises without USITC_EDIS_TOKEN."""
        monkeypatch.delenv("USITC_EDIS_TOKEN", raising=False)
        client = EdisClient()
        with pytest.raises(RuntimeError, match="USITC_EDIS_TOKEN"):
            await client.download_attachment(document_id=1, attachment_id=2)

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_client: httpx.AsyncClient) -> None:
        async with EdisClient(client=mock_client) as client:
            result = await client.list_investigations()
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_expired_jwt_raises_authentication_error_before_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Expired EDIS tokens surface as Akamai 503/403; pre-check exp."""
        monkeypatch.setenv("USITC_EDIS_TOKEN", _make_jwt(exp_epoch=1))  # 1970-01-01

        request_attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_attempts
            request_attempts += 1
            return httpx.Response(200, text="<root/>")

        mock = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = EdisClient(client=mock)
        with pytest.raises(AuthenticationError, match="USITC_EDIS_TOKEN expired"):
            await client.list_investigations()
        assert request_attempts == 0, "should short-circuit before HTTP call"

    @pytest.mark.asyncio
    async def test_fresh_jwt_passes_through(
        self, monkeypatch: pytest.MonkeyPatch, mock_client: httpx.AsyncClient
    ) -> None:
        monkeypatch.setenv("USITC_EDIS_TOKEN", _make_jwt(exp_epoch=9999999999))
        client = EdisClient(client=mock_client)
        result = await client.list_investigations()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_non_jwt_token_does_not_break(
        self, monkeypatch: pytest.MonkeyPatch, mock_client: httpx.AsyncClient
    ) -> None:
        """A non-JWT token (no exp to decode) must not block requests."""
        monkeypatch.setenv("USITC_EDIS_TOKEN", "plain-opaque-token")
        client = EdisClient(client=mock_client)
        assert client._token_expires_at is None
        result = await client.list_investigations()
        assert len(result) == 1


class TestDataWebClient:
    """Tests for DataWebClient."""

    @pytest.fixture
    def mock_client(self) -> httpx.AsyncClient:
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path

            if "/runReport" in path:
                return httpx.Response(
                    200,
                    json={"dto": {"columns": ["a", "b"], "rows": [[1, 2]]}},
                )
            elif "/getAllSavedQueries" in path:
                return httpx.Response(
                    200,
                    json=[{"id": 1, "name": "Test Query"}],
                )

            return httpx.Response(404)

        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    def test_requires_auth_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("USITC_DATAWEB_TOKEN", raising=False)
        client = DataWebClient()
        with pytest.raises(RuntimeError, match="USITC_DATAWEB_TOKEN"):
            client.require_auth()

    def test_requires_auth_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("USITC_DATAWEB_TOKEN", "test_token")
        client = DataWebClient()
        client.require_auth()  # Should not raise

    @pytest.mark.asyncio
    async def test_run_report(
        self, mock_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("USITC_DATAWEB_TOKEN", "test_token")
        client = DataWebClient(client=mock_client)
        client._token = "test_token"  # Set token directly for test
        result = await client.run_report({"query": "test"})
        assert isinstance(result, DataWebReport)
        assert "columns" in result.dto

    @pytest.mark.asyncio
    async def test_list_saved_queries(
        self, mock_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("USITC_DATAWEB_TOKEN", "test_token")
        client = DataWebClient(client=mock_client)
        client._token = "test_token"
        result = await client.list_saved_queries()
        assert len(result) == 1
        assert isinstance(result[0], SavedQuerySummary)


class TestIdsClient:
    """Tests for IdsClient."""

    @pytest.fixture
    def mock_client(self) -> httpx.AsyncClient:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "Investigation ID": 1234,
                            "Investigation Number": "337-TA-1234",
                            "Product Group Code Description": "Electronics",
                        }
                    ]
                },
            )

        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    @pytest.mark.asyncio
    async def test_list_investigations(self, mock_client: httpx.AsyncClient) -> None:
        client = IdsClient(client=mock_client)
        result = await client.list_investigations()
        assert len(result) == 1
        assert isinstance(result[0], IdsInvestigation)
        assert result[0].investigation_number == "337-TA-1234"

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_client: httpx.AsyncClient) -> None:
        async with IdsClient(client=mock_client) as client:
            result = await client.list_investigations()
            assert len(result) == 1


class TestHtsClient:
    """Tests for HtsClient."""

    @pytest.fixture
    def mock_client(self) -> httpx.AsyncClient:
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path

            if "/search" in path:
                return httpx.Response(
                    200,
                    json={"results": [{"htsno": "8471.30.01", "description": "Computers"}]},
                )
            elif "/exportList" in path:
                return httpx.Response(
                    200,
                    json=[{"hts": "8471.30.01", "rate": "Free"}],
                )

            return httpx.Response(404)

        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    @pytest.mark.asyncio
    async def test_search(self, mock_client: httpx.AsyncClient) -> None:
        client = HtsClient(client=mock_client)
        result = await client.search("computers")
        assert len(result) == 1
        assert isinstance(result[0], HtsSearchResult)
        assert result[0].hts_number == "8471.30.01"

    @pytest.mark.asyncio
    async def test_export_range(self, mock_client: httpx.AsyncClient) -> None:
        client = HtsClient(client=mock_client)
        result = await client.export_range("8471.30.01", "8471.30.99")
        assert isinstance(result, HtsExportResponse)
        assert len(result.entries) == 1

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_client: httpx.AsyncClient) -> None:
        async with HtsClient(client=mock_client) as client:
            result = await client.search("test")
            assert isinstance(result, list)
