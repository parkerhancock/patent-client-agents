"""Tests for JPO client."""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from law_tools_core.exceptions import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    RateLimitError,
)
from patent_client_agents.jpo.client import (
    BASE_URL,
    JpoClient,
    RateLimiter,
    TokenManager,
)
from patent_client_agents.jpo.models import (
    ApplicantAttorney,
    ApplicationDocumentsData,
    CitedDocumentInfo,
    DesignProgressData,
    DivisionalApplicationInfo,
    NumberReference,
    NumberType,
    PatentProgressData,
    PctNationalPhaseData,
    PriorityInfo,
    RegistrationInfo,
    SimplifiedPatentProgressData,
    TrademarkProgressData,
)


class TestBaseUrl:
    """Tests for BASE_URL constant."""

    def test_is_https(self) -> None:
        assert BASE_URL.startswith("https://")

    def test_is_jpo_domain(self) -> None:
        assert "jpo.go.jp" in BASE_URL


class TestTokenManager:
    """Tests for TokenManager."""

    @pytest.fixture
    def token_manager(self) -> TokenManager:
        return TokenManager("test_user", "test_pass")

    def test_init(self, token_manager: TokenManager) -> None:
        assert token_manager.username == "test_user"
        assert token_manager.password == "test_pass"
        assert token_manager._token is None
        assert token_manager._token_expiry == 0

    def test_init_custom_base_url(self) -> None:
        manager = TokenManager("user", "pass", base_url="https://custom.api.com/")
        assert manager.base_url == "https://custom.api.com"

    @pytest.mark.asyncio
    async def test_get_token_success(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/token" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "access_token": "test_token_123",
                        "expires_in": 3600,
                    },
                )
            return httpx.Response(404)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        manager = TokenManager("user", "pass")

        token = await manager.get_token(client)
        assert token == "test_token_123"
        assert manager._token == "test_token_123"

    @pytest.mark.asyncio
    async def test_get_token_reuses_valid_token(self) -> None:
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200,
                json={"access_token": "token", "expires_in": 3600},
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        manager = TokenManager("user", "pass")

        await manager.get_token(client)
        await manager.get_token(client)

        # Should only call API once
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_get_token_refreshes_expired(self) -> None:
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200,
                json={"access_token": f"token_{call_count}", "expires_in": 1},
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        manager = TokenManager("user", "pass")

        await manager.get_token(client)
        # Force expiry
        manager._token_expiry = time.time() - 100

        token = await manager.get_token(client)
        assert token == "token_2"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_get_token_auth_error_401(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="Invalid credentials")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        manager = TokenManager("user", "pass")

        with pytest.raises(AuthenticationError, match="Invalid JPO credentials"):
            await manager.get_token(client)

    @pytest.mark.asyncio
    async def test_get_token_auth_error_403(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, text="Forbidden")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        manager = TokenManager("user", "pass")

        with pytest.raises(AuthenticationError, match="access forbidden"):
            await manager.get_token(client)

    def test_invalidate(self, token_manager: TokenManager) -> None:
        token_manager._token = "some_token"
        token_manager._token_expiry = time.time() + 3600

        token_manager.invalidate()

        assert token_manager._token is None
        assert token_manager._token_expiry == 0


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_init_defaults(self) -> None:
        limiter = RateLimiter()
        assert limiter.max_requests == 10
        assert limiter.window_seconds == 60

    def test_init_custom(self) -> None:
        limiter = RateLimiter(max_requests=5, window_seconds=30)
        assert limiter.max_requests == 5
        assert limiter.window_seconds == 30

    @pytest.mark.asyncio
    async def test_acquire_under_limit(self) -> None:
        limiter = RateLimiter(max_requests=10, window_seconds=60)

        start = time.time()
        for _ in range(5):
            await limiter.acquire()
        elapsed = time.time() - start

        # Should be nearly instant
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_acquire_tracks_timestamps(self) -> None:
        limiter = RateLimiter(max_requests=3, window_seconds=60)

        await limiter.acquire()
        await limiter.acquire()

        assert len(limiter._timestamps) == 2

    @pytest.mark.asyncio
    async def test_acquire_removes_old_timestamps(self) -> None:
        limiter = RateLimiter(max_requests=10, window_seconds=0.05)

        await limiter.acquire()
        await asyncio.sleep(0.1)  # Wait for window to pass
        await limiter.acquire()

        # Old timestamp should be removed
        assert len(limiter._timestamps) == 1


class TestJpoClientInit:
    """Tests for JpoClient initialization."""

    def test_requires_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("JPO_API_USERNAME", raising=False)
        monkeypatch.delenv("JPO_API_PASSWORD", raising=False)

        with pytest.raises(ConfigurationError, match="credentials required"):
            JpoClient()

    def test_accepts_env_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JPO_API_USERNAME", "test_user")
        monkeypatch.setenv("JPO_API_PASSWORD", "test_pass")

        client = JpoClient()
        assert client._token_manager.username == "test_user"

    def test_accepts_direct_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("JPO_API_USERNAME", raising=False)
        monkeypatch.delenv("JPO_API_PASSWORD", raising=False)

        client = JpoClient(username="direct_user", password="direct_pass")
        assert client._token_manager.username == "direct_user"

    def test_custom_base_url(self) -> None:
        client = JpoClient(
            username="user",
            password="pass",
            base_url="https://custom.api.com/",
        )
        assert client.base_url == "https://custom.api.com"


class TestJpoClientMethods:
    """Tests for JpoClient API methods."""

    @pytest.fixture
    def mock_transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            path = str(request.url.path)

            # Token endpoint
            if "/auth/token" in path:
                return httpx.Response(
                    200,
                    json={"access_token": "test_token", "expires_in": 3600},
                )

            # Patent progress
            if "/patent/v1/app_progress/" in path and "simple" not in path:
                return httpx.Response(
                    200,
                    json={
                        "result": {
                            "statusCode": "100",
                            "data": {
                                "applicationNumber": "2020123456",
                                "inventionTitle": "Test Invention",
                            },
                        }
                    },
                )

            # Patent progress simple
            if "/patent/v1/app_progress_simple/" in path:
                return httpx.Response(
                    200,
                    json={
                        "result": {
                            "statusCode": "100",
                            "data": {"applicationNumber": "2020123456"},
                        }
                    },
                )

            # Divisional info
            if "/divisional_app_info/" in path:
                return httpx.Response(
                    200,
                    json={
                        "result": {
                            "statusCode": "100",
                            "data": {
                                "divisionalApplicationInfo": [{"applicationNumber": "2021654321"}]
                            },
                        }
                    },
                )

            # Priority info
            if "/priority_right_app_info/" in path:
                return httpx.Response(
                    200,
                    json={
                        "result": {
                            "statusCode": "100",
                            "data": {"priorityInfo": [{"priorityNumber": "US12345"}]},
                        }
                    },
                )

            # Applicant by code
            if "/applicant_attorney_cd/" in path:
                return httpx.Response(
                    200,
                    json={
                        "result": {
                            "statusCode": "100",
                            "data": {
                                "applicantAttorney": [
                                    {"applicantAttorneyCd": "123", "name": "Test Corp"}
                                ]
                            },
                        }
                    },
                )

            # Applicant by name
            if "/applicant_attorney/" in path and "_cd" not in path:
                return httpx.Response(
                    200,
                    json={
                        "result": {
                            "statusCode": "100",
                            "data": {
                                "applicantAttorney": [
                                    {"applicantAttorneyCd": "123", "name": "Test"}
                                ]
                            },
                        }
                    },
                )

            # Number reference
            if "/case_number_reference/" in path:
                return httpx.Response(
                    200,
                    json={
                        "result": {
                            "statusCode": "100",
                            "data": {"caseNumberReference": [{"applicationNumber": "2020123456"}]},
                        }
                    },
                )

            # Application documents
            if "/app_doc_cont_opinion_amendment/" in path:
                return httpx.Response(
                    200,
                    json={
                        "result": {
                            "statusCode": "100",
                            "data": {
                                "applicationNumber": "2020123456",
                                "documents": [],
                            },
                        }
                    },
                )

            # Mailed documents
            if "/app_doc_cont_refusal_reason_decision/" in path:
                return httpx.Response(
                    200,
                    json={
                        "result": {
                            "statusCode": "100",
                            "data": {
                                "applicationNumber": "2020123456",
                                "documents": [],
                            },
                        }
                    },
                )

            # Refusal notices
            if "/app_doc_cont_refusal_reason/" in path and "decision" not in path:
                return httpx.Response(
                    200,
                    json={
                        "result": {
                            "statusCode": "100",
                            "data": {
                                "applicationNumber": "2020123456",
                                "documents": [],
                            },
                        }
                    },
                )

            # Cited documents
            if "/cite_doc_info/" in path:
                return httpx.Response(
                    200,
                    json={
                        "result": {
                            "statusCode": "100",
                            "data": {"citedDocumentInfo": [{"citationDocument": "JP2019-123456A"}]},
                        }
                    },
                )

            # Registration info
            if "/registration_info/" in path:
                return httpx.Response(
                    200,
                    json={
                        "result": {
                            "statusCode": "100",
                            "data": {
                                "registrationNumber": "7000001",
                                "registrationDate": "2022-01-01",
                            },
                        }
                    },
                )

            # J-PlatPat URL
            if "/jpp_fixed_address/" in path:
                return httpx.Response(
                    200,
                    json={
                        "result": {
                            "statusCode": "100",
                            "data": {"jplatpatUrl": "https://www.j-platpat.inpit.go.jp/..."},
                        }
                    },
                )

            # PCT national phase
            if "/pct_national_phase_application_number/" in path:
                return httpx.Response(
                    200,
                    json={
                        "result": {
                            "statusCode": "100",
                            "data": {
                                "internationalApplicationNumber": "PCT/JP2020/001234",
                                "nationalApplicationNumber": "2021-550001",
                            },
                        }
                    },
                )

            # Design progress
            if "/design/v1/app_progress" in path:
                return httpx.Response(
                    200,
                    json={
                        "result": {
                            "statusCode": "100",
                            "data": {
                                "applicationNumber": "2020012345",
                                "designTitle": "Electronic Device",
                            },
                        }
                    },
                )

            # Trademark progress
            if "/trademark/v1/app_progress" in path:
                return httpx.Response(
                    200,
                    json={
                        "result": {
                            "statusCode": "100",
                            "data": {
                                "applicationNumber": "2020054321",
                                "trademarkName": "TEST MARK",
                            },
                        }
                    },
                )

            return httpx.Response(404, json={"error": "Not found"})

        return httpx.MockTransport(handler)

    @pytest.fixture
    def client(self, mock_transport: httpx.MockTransport) -> JpoClient:
        http_client = httpx.AsyncClient(transport=mock_transport)
        return JpoClient(
            username="test_user",
            password="test_pass",
            client=http_client,
        )

    @pytest.mark.asyncio
    async def test_get_patent_progress(self, client: JpoClient) -> None:
        result = await client.get_patent_progress("2020123456")
        assert isinstance(result, PatentProgressData)
        assert result.application_number == "2020123456"
        assert result.invention_title == "Test Invention"

    @pytest.mark.asyncio
    async def test_get_patent_progress_simple(self, client: JpoClient) -> None:
        result = await client.get_patent_progress_simple("2020123456")
        assert isinstance(result, SimplifiedPatentProgressData)
        assert result.application_number == "2020123456"

    @pytest.mark.asyncio
    async def test_get_patent_divisional_info(self, client: JpoClient) -> None:
        result = await client.get_patent_divisional_info("2020123456")
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], DivisionalApplicationInfo)

    @pytest.mark.asyncio
    async def test_get_patent_priority_info(self, client: JpoClient) -> None:
        result = await client.get_patent_priority_info("2020123456")
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], PriorityInfo)

    @pytest.mark.asyncio
    async def test_get_patent_applicant_by_code(self, client: JpoClient) -> None:
        result = await client.get_patent_applicant_by_code("123456789")
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], ApplicantAttorney)
        assert result[0].name == "Test Corp"

    @pytest.mark.asyncio
    async def test_get_patent_applicant_by_name(self, client: JpoClient) -> None:
        result = await client.get_patent_applicant_by_name("Test")
        assert isinstance(result, list)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_patent_number_reference_with_enum(self, client: JpoClient) -> None:
        result = await client.get_patent_number_reference(NumberType.APPLICATION, "2020123456")
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], NumberReference)

    @pytest.mark.asyncio
    async def test_get_patent_number_reference_with_string(self, client: JpoClient) -> None:
        result = await client.get_patent_number_reference("01", "2020123456")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_patent_application_documents(self, client: JpoClient) -> None:
        result = await client.get_patent_application_documents("2020123456")
        assert isinstance(result, ApplicationDocumentsData)
        assert result.application_number == "2020123456"

    @pytest.mark.asyncio
    async def test_get_patent_mailed_documents(self, client: JpoClient) -> None:
        result = await client.get_patent_mailed_documents("2020123456")
        assert isinstance(result, ApplicationDocumentsData)

    @pytest.mark.asyncio
    async def test_get_patent_refusal_notices(self, client: JpoClient) -> None:
        result = await client.get_patent_refusal_notices("2020123456")
        assert isinstance(result, ApplicationDocumentsData)

    @pytest.mark.asyncio
    async def test_get_patent_cited_documents(self, client: JpoClient) -> None:
        result = await client.get_patent_cited_documents("2020123456")
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], CitedDocumentInfo)

    @pytest.mark.asyncio
    async def test_get_patent_registration_info(self, client: JpoClient) -> None:
        result = await client.get_patent_registration_info("2020123456")
        assert isinstance(result, RegistrationInfo)
        assert result.registration_number == "7000001"

    @pytest.mark.asyncio
    async def test_get_patent_jplatpat_url(self, client: JpoClient) -> None:
        result = await client.get_patent_jplatpat_url("2020123456")
        assert result is not None
        assert result.startswith("https://")

    @pytest.mark.asyncio
    async def test_get_patent_pct_national_number(self, client: JpoClient) -> None:
        result = await client.get_patent_pct_national_number(
            NumberType.PCT_APPLICATION, "PCT/JP2020/001234"
        )
        assert isinstance(result, PctNationalPhaseData)
        assert result.national_application_number == "2021-550001"

    @pytest.mark.asyncio
    async def test_get_design_progress(self, client: JpoClient) -> None:
        result = await client.get_design_progress("2020012345")
        assert isinstance(result, DesignProgressData)
        assert result.design_title == "Electronic Device"

    @pytest.mark.asyncio
    async def test_get_trademark_progress(self, client: JpoClient) -> None:
        result = await client.get_trademark_progress("2020054321")
        assert isinstance(result, TrademarkProgressData)
        assert result.trademark_name == "TEST MARK"

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_transport: httpx.MockTransport) -> None:
        http_client = httpx.AsyncClient(transport=mock_transport)
        async with JpoClient(username="user", password="pass", client=http_client) as client:
            result = await client.get_patent_progress("2020123456")
            assert result is not None


class TestJpoClientNoData:
    """Tests for handling NO_DATA responses."""

    @pytest.fixture
    def no_data_transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/token" in str(request.url):
                return httpx.Response(
                    200,
                    json={"access_token": "token", "expires_in": 3600},
                )
            return httpx.Response(
                200,
                json={"result": {"statusCode": "107", "errorMessage": "No data"}},
            )

        return httpx.MockTransport(handler)

    @pytest.fixture
    def client(self, no_data_transport: httpx.MockTransport) -> JpoClient:
        http_client = httpx.AsyncClient(transport=no_data_transport)
        return JpoClient(username="user", password="pass", client=http_client)

    @pytest.mark.asyncio
    async def test_returns_none_for_no_data(self, client: JpoClient) -> None:
        result = await client.get_patent_progress("9999999999")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_no_data(self, client: JpoClient) -> None:
        result = await client.get_patent_divisional_info("9999999999")
        assert result == []


class TestJpoClientErrors:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_rate_limit_error_from_api(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/token" in str(request.url):
                return httpx.Response(
                    200,
                    json={"access_token": "token", "expires_in": 3600},
                )
            return httpx.Response(
                200,
                json={
                    "result": {
                        "statusCode": "203",
                        "errorMessage": "Daily limit exceeded",
                    }
                },
            )

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = JpoClient(username="user", password="pass", client=http_client)

        with pytest.raises(RateLimitError, match="daily access limit"):
            await client.get_patent_progress("2020123456")

    @pytest.mark.asyncio
    async def test_rate_limit_error_429(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/token" in str(request.url):
                return httpx.Response(
                    200,
                    json={"access_token": "token", "expires_in": 3600},
                )
            return httpx.Response(429, text="Rate limited")

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = JpoClient(username="user", password="pass", client=http_client)

        with pytest.raises(RateLimitError):
            await client.get_patent_progress("2020123456")

    @pytest.mark.asyncio
    async def test_invalid_token_error(self) -> None:
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            if "/auth/token" in str(request.url):
                call_count += 1
                return httpx.Response(
                    200,
                    json={"access_token": f"token_{call_count}", "expires_in": 3600},
                )
            return httpx.Response(
                200,
                json={
                    "result": {
                        "statusCode": "210",
                        "errorMessage": "Invalid token",
                    }
                },
            )

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = JpoClient(username="user", password="pass", client=http_client)

        with pytest.raises(AuthenticationError, match="Invalid JPO API token"):
            await client.get_patent_progress("2020123456")

    @pytest.mark.asyncio
    async def test_api_error_500(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/token" in str(request.url):
                return httpx.Response(
                    200,
                    json={"access_token": "token", "expires_in": 3600},
                )
            return httpx.Response(500, text="Internal server error")

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = JpoClient(username="user", password="pass", client=http_client)

        with pytest.raises(ApiError):
            await client.get_patent_progress("2020123456")

    @pytest.mark.asyncio
    async def test_token_refresh_on_401(self) -> None:
        call_count = 0
        token_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count, token_calls
            if "/auth/token" in str(request.url):
                token_calls += 1
                return httpx.Response(
                    200,
                    json={"access_token": f"token_{token_calls}", "expires_in": 3600},
                )

            call_count += 1
            if call_count == 1:
                return httpx.Response(401, text="Unauthorized")
            return httpx.Response(
                200,
                json={
                    "result": {
                        "statusCode": "100",
                        "data": {"applicationNumber": "2020123456"},
                    }
                },
            )

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = JpoClient(username="user", password="pass", client=http_client)

        result = await client.get_patent_progress("2020123456")
        assert result is not None
        assert token_calls == 2  # Initial + refresh


class TestBuildUrl:
    """Tests for URL building."""

    def test_build_url(self) -> None:
        client = JpoClient(username="user", password="pass")
        url = client._build_url("/patent/v1/app_progress/2020123456")
        assert url == f"{BASE_URL}/api/patent/v1/app_progress/2020123456"
