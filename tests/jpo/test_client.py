"""Mocked unit tests for JpoClient.

These tests use ``httpx.MockTransport`` to simulate live JPO responses,
so they run without credentials or network. The mocked payloads mirror
what the *real* API returns (validated 2026-05-07).
"""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from mcp_data_core.exceptions import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    NotFoundError,
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
    CaseNumberKind,
    CitedDocumentsData,
    DesignProgressData,
    DivisionalAppInfoData,
    DocumentBundleResult,
    NumberReference,
    PatentProgressData,
    PctKind,
    PctNationalPhaseData,
    PriorityInfo,
    RegistrationInfo,
    SimplifiedPatentProgressData,
    TrademarkProgressData,
)

# =============================================================================
# BASE_URL
# =============================================================================


class TestBaseUrl:
    def test_is_https(self) -> None:
        assert BASE_URL.startswith("https://")

    def test_is_jpo_domain(self) -> None:
        assert "jpo.go.jp" in BASE_URL


# =============================================================================
# TokenManager
# =============================================================================


class TestTokenManager:
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
                    json={"access_token": "test_token_123", "expires_in": 3600},
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
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        manager = TokenManager("user", "pass")
        await manager.get_token(client)
        await manager.get_token(client)
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


# =============================================================================
# RateLimiter
# =============================================================================


class TestRateLimiter:
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
        assert time.time() - start < 0.1

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
        await asyncio.sleep(0.1)
        await limiter.acquire()
        assert len(limiter._timestamps) == 1


# =============================================================================
# JpoClient init
# =============================================================================


class TestJpoClientInit:
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


# =============================================================================
# JpoClient methods (with mocked transport)
# =============================================================================


def _build_handler(
    *,
    cite_doc_ok: bool = True,
):
    """Build an httpx mock handler reflecting real JPO response shapes."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = str(request.url.path)

        # Token endpoint
        if "/auth/token" in path:
            return httpx.Response(200, json={"access_token": "test_token", "expires_in": 3600})

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
                            "filingDate": "20200720",
                            "applicantAttorney": [
                                {"applicantAttorneyCd": "000003207", "name": "Test Co"}
                            ],
                            "priorityRightInformation": [],
                            "parentApplicationInformation": {},
                            "divisionalApplicationInformation": [],
                            "bibliographyInformation": [],
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
                        "data": {
                            "applicationNumber": "2020123456",
                            "inventionTitle": "Test Invention",
                            "filingDate": "20200720",
                            "bibliographyInformation": [],
                        },
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
                            "applicationNumber": "2020123456",
                            "parentApplicationInformation": {},
                            "divisionalApplicationInformation": [
                                {
                                    "applicationNumber": "2021100000",
                                    "divisionalGeneration": "1",
                                }
                            ],
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
                        "data": {
                            "applicationNumber": "2020123456",
                            "priorityRightInformation": [
                                {
                                    "nationalPriorityLawCd": "1",
                                    "nationalPriorityApplicationNumber": "2019210418",
                                    "nationalPriorityDate": "20191121",
                                }
                            ],
                        },
                    }
                },
            )

        # Applicant by code (returns single name string)
        if "/applicant_attorney_cd/" in path:
            return httpx.Response(
                200,
                json={
                    "result": {
                        "statusCode": "100",
                        "data": {"applicantAttorneyName": "Test Corp"},
                    }
                },
            )

        # Applicant by name (returns list of code+name)
        if "/applicant_attorney/" in path and "_cd" not in path:
            return httpx.Response(
                200,
                json={
                    "result": {
                        "statusCode": "100",
                        "data": {
                            "applicantAttorney": [
                                {"applicantAttorneyCd": "000003207", "name": "Test"}
                            ]
                        },
                    }
                },
            )

        # case_number_reference (returns single object)
        if "/case_number_reference/" in path:
            return httpx.Response(
                200,
                json={
                    "result": {
                        "statusCode": "100",
                        "data": {
                            "applicationNumber": "2020123456",
                            "publicationNumber": "2021090037",
                            "registrationNumber": "7533889",
                        },
                    }
                },
            )

        # Document download endpoints — return ZIP (fake but valid PK header)
        if (
            "/app_doc_cont_opinion_amendment/" in path
            or "/app_doc_cont_refusal_reason_decision/" in path
            or "/app_doc_cont_refusal_reason/" in path
        ):
            zip_body = b"PK\x03\x04\x14\x00\x00\x00\x08\x00fakezip"
            return httpx.Response(
                200, content=zip_body, headers={"content-type": "application/zip"}
            )

        # Cited documents
        if "/cite_doc_info/" in path:
            if cite_doc_ok:
                return httpx.Response(
                    200,
                    json={
                        "result": {
                            "statusCode": "100",
                            "data": {
                                "applicationNumber": "2020123456",
                                "patentDoc": [
                                    {
                                        "draftDate": "20240220",
                                        "citationType": "19",
                                        "citationOrder": "1",
                                        "documentNumber": "JPA 414233033",
                                    }
                                ],
                                "nonPatentDoc": [],
                            },
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
                            "registrationDate": "20220101",
                        },
                    }
                },
            )

        # J-PlatPat URL — uses "URL" key (uppercase)
        if "/jpp_fixed_address/" in path:
            return httpx.Response(
                200,
                json={
                    "result": {
                        "statusCode": "100",
                        "data": {
                            "URL": "https://www.j-platpat.inpit.go.jp/c1800/PU/JP-2020-123456/.../10/ja"
                        },
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
                        "data": {"applicationNumber": "2021550001"},
                    }
                },
            )

        # Design progress (full + simple)
        if "/design/v1/app_progress" in path:
            return httpx.Response(
                200,
                json={
                    "result": {
                        "statusCode": "100",
                        "data": {
                            "applicationNumber": "2020012345",
                            "designArticle": "Electronic Device",
                            "designClass": "E2112",
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
                            "trademarkForDisplay": "TEST MARK",
                            "transliteration": {"0": "TESTOMAAKU"},
                            "viennaClass": {},
                            "goodsServiceInformation": [],
                        },
                    }
                },
            )

        return httpx.Response(404, json={"error": "Not found"})

    return handler


@pytest.fixture
def mock_transport() -> httpx.MockTransport:
    return httpx.MockTransport(_build_handler())


@pytest.fixture
def client(mock_transport: httpx.MockTransport) -> JpoClient:
    http_client = httpx.AsyncClient(transport=mock_transport)
    return JpoClient(username="user", password="pass", client=http_client)


class TestPatentMethods:
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
        assert isinstance(result, DivisionalAppInfoData)
        assert len(result.divisional_application_information) == 1
        assert result.divisional_application_information[0].divisional_generation == "1"

    @pytest.mark.asyncio
    async def test_get_patent_priority_info(self, client: JpoClient) -> None:
        result = await client.get_patent_priority_info("2020123456")
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], PriorityInfo)
        assert result[0].national_priority_application_number == "2019210418"

    @pytest.mark.asyncio
    async def test_get_patent_applicant_by_code(self, client: JpoClient) -> None:
        # Now returns a single string (the name).
        result = await client.get_patent_applicant_by_code("000003207")
        assert result == "Test Corp"

    @pytest.mark.asyncio
    async def test_get_patent_applicant_by_name(self, client: JpoClient) -> None:
        result = await client.get_patent_applicant_by_name("Test")
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], ApplicantAttorney)

    @pytest.mark.asyncio
    async def test_get_patent_number_reference_with_enum(self, client: JpoClient) -> None:
        # Now returns a single NumberReference (not a list).
        result = await client.get_patent_number_reference(CaseNumberKind.APPLICATION, "2020123456")
        assert isinstance(result, NumberReference)
        assert result.application_number == "2020123456"

    @pytest.mark.asyncio
    async def test_get_patent_number_reference_with_string(self, client: JpoClient) -> None:
        result = await client.get_patent_number_reference("application", "2020123456")
        assert isinstance(result, NumberReference)

    @pytest.mark.asyncio
    async def test_get_patent_application_documents(self, client: JpoClient) -> None:
        result = await client.get_patent_application_documents("2020123456")
        assert isinstance(result, DocumentBundleResult)
        assert result.zip_bytes is not None
        assert result.zip_bytes.startswith(b"PK\x03\x04")
        assert result.is_empty is False

    @pytest.mark.asyncio
    async def test_get_patent_mailed_documents(self, client: JpoClient) -> None:
        result = await client.get_patent_mailed_documents("2020123456")
        assert isinstance(result, DocumentBundleResult)
        assert result.zip_bytes is not None

    @pytest.mark.asyncio
    async def test_get_patent_refusal_notices(self, client: JpoClient) -> None:
        result = await client.get_patent_refusal_notices("2020123456")
        assert isinstance(result, DocumentBundleResult)
        assert result.zip_bytes is not None

    @pytest.mark.asyncio
    async def test_get_patent_cited_documents(self, client: JpoClient) -> None:
        result = await client.get_patent_cited_documents("2020123456")
        assert isinstance(result, CitedDocumentsData)
        assert len(result.patent_doc) == 1
        assert result.patent_doc[0].document_number == "JPA 414233033"

    @pytest.mark.asyncio
    async def test_get_patent_registration_info(self, client: JpoClient) -> None:
        result = await client.get_patent_registration_info("2020123456")
        assert isinstance(result, RegistrationInfo)
        assert result.registration_number == "7000001"

    @pytest.mark.asyncio
    async def test_get_patent_jplatpat_url(self, client: JpoClient) -> None:
        result = await client.get_patent_jplatpat_url("2020123456")
        assert result is not None
        assert result.startswith("https://www.j-platpat.inpit.go.jp/")

    @pytest.mark.asyncio
    async def test_get_patent_pct_national_number_with_enum(self, client: JpoClient) -> None:
        result = await client.get_patent_pct_national_number(
            PctKind.INTERNATIONAL_APPLICATION, "JP2020001234"
        )
        assert isinstance(result, PctNationalPhaseData)
        assert result.application_number == "2021550001"

    @pytest.mark.asyncio
    async def test_get_patent_pct_national_number_with_string(self, client: JpoClient) -> None:
        result = await client.get_patent_pct_national_number(
            "international_application", "JP2020001234"
        )
        assert isinstance(result, PctNationalPhaseData)


class TestDesignAndTrademarkMethods:
    @pytest.mark.asyncio
    async def test_get_design_progress(self, client: JpoClient) -> None:
        result = await client.get_design_progress("2020012345")
        assert isinstance(result, DesignProgressData)
        assert result.design_article == "Electronic Device"
        # Backwards-compat alias.
        assert result.design_title == "Electronic Device"

    @pytest.mark.asyncio
    async def test_get_design_applicant_by_code(self, client: JpoClient) -> None:
        result = await client.get_design_applicant_by_code("000003207")
        assert result == "Test Corp"

    @pytest.mark.asyncio
    async def test_get_design_application_documents(self, client: JpoClient) -> None:
        result = await client.get_design_application_documents("2020012345")
        assert isinstance(result, DocumentBundleResult)
        assert result.zip_bytes is not None

    @pytest.mark.asyncio
    async def test_get_trademark_progress(self, client: JpoClient) -> None:
        result = await client.get_trademark_progress("2020054321")
        assert isinstance(result, TrademarkProgressData)
        assert result.trademark_for_display == "TEST MARK"
        # Backwards-compat alias.
        assert result.trademark_name == "TEST MARK"

    @pytest.mark.asyncio
    async def test_get_trademark_applicant_by_code(self, client: JpoClient) -> None:
        result = await client.get_trademark_applicant_by_code("000003207")
        assert result == "Test Corp"


class TestContextManager:
    @pytest.mark.asyncio
    async def test_context_manager(self, mock_transport: httpx.MockTransport) -> None:
        http_client = httpx.AsyncClient(transport=mock_transport)
        async with JpoClient(username="user", password="pass", client=http_client) as client:
            result = await client.get_patent_progress("2020123456")
            assert result is not None


# =============================================================================
# No-data handling
# =============================================================================


class TestJpoClientNoData:
    @pytest.fixture
    def no_data_transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/token" in str(request.url):
                return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
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
        assert await client.get_patent_progress("9999999999") is None

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_priority(self, client: JpoClient) -> None:
        assert await client.get_patent_priority_info("9999999999") == []

    @pytest.mark.asyncio
    async def test_returns_none_for_divisional(self, client: JpoClient) -> None:
        assert await client.get_patent_divisional_info("9999999999") is None

    @pytest.mark.asyncio
    async def test_returns_none_for_applicant_by_code(self, client: JpoClient) -> None:
        assert await client.get_patent_applicant_by_code("999999999") is None

    @pytest.mark.asyncio
    async def test_returns_none_for_number_reference(self, client: JpoClient) -> None:
        assert await client.get_patent_number_reference("application", "9999999999") is None

    @pytest.mark.asyncio
    async def test_returns_none_for_jplatpat_url(self, client: JpoClient) -> None:
        assert await client.get_patent_jplatpat_url("9999999999") is None


class TestJpoClientNoDocument:
    """Status code 108 ('no substantial document') is also no-data."""

    @pytest.mark.asyncio
    async def test_108_returns_empty_bundle(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/token" in str(request.url):
                return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
            # JSON path — content-type application/json, status 200, code 108
            return httpx.Response(
                200,
                json={"result": {"statusCode": "108", "errorMessage": "No doc", "data": {}}},
                headers={"content-type": "application/json"},
            )

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = JpoClient(username="u", password="p", client=http_client)
        result = await client.get_patent_application_documents("2020123456")
        assert isinstance(result, DocumentBundleResult)
        assert result.is_empty is True


class TestJpoClientUnavailableNumber:
    """Status code 111 ('out of scope') should also map to None / empty."""

    @pytest.mark.asyncio
    async def test_111_returns_none(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/token" in str(request.url):
                return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
            return httpx.Response(
                200,
                json={
                    "result": {
                        "statusCode": "111",
                        "errorMessage": "Out of scope",
                        "data": {},
                    }
                },
            )

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = JpoClient(username="u", password="p", client=http_client)
        assert await client.get_patent_progress("1900000000") is None


# =============================================================================
# Error handling
# =============================================================================


class TestJpoClientErrors:
    @pytest.mark.asyncio
    async def test_rate_limit_error_from_api(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/token" in str(request.url):
                return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
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
    async def test_concentrated_access_303(self) -> None:
        """303 = transient concentration; map to RateLimitError so callers retry."""

        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/token" in str(request.url):
                return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
            return httpx.Response(
                200,
                json={
                    "result": {
                        "statusCode": "303",
                        "errorMessage": "アクセスが集中しています",
                    }
                },
            )

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = JpoClient(username="user", password="pass", client=http_client)
        with pytest.raises(RateLimitError, match="concentrated"):
            await client.get_patent_progress("2020123456")

    @pytest.mark.asyncio
    async def test_invalid_parameter_204(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/token" in str(request.url):
                return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
            return httpx.Response(
                200,
                json={
                    "result": {
                        "statusCode": "204",
                        "errorMessage": "Bad parameter",
                    }
                },
            )

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = JpoClient(username="user", password="pass", client=http_client)
        with pytest.raises(ApiError, match="invalid request"):
            await client.get_patent_progress("2020123456")

    @pytest.mark.asyncio
    async def test_url_not_found_301(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/token" in str(request.url):
                return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
            return httpx.Response(
                200,
                json={
                    "result": {
                        "statusCode": "301",
                        "errorMessage": "URL does not exist",
                    }
                },
            )

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = JpoClient(username="user", password="pass", client=http_client)
        with pytest.raises(NotFoundError):
            await client.get_patent_progress("2020123456")

    @pytest.mark.asyncio
    async def test_unexpected_error_999(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/token" in str(request.url):
                return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
            return httpx.Response(
                200,
                json={
                    "result": {
                        "statusCode": "999",
                        "errorMessage": "Server hiccup",
                    }
                },
            )

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = JpoClient(username="user", password="pass", client=http_client)
        with pytest.raises(ApiError, match="server error"):
            await client.get_patent_progress("2020123456")

    @pytest.mark.asyncio
    async def test_rate_limit_error_429(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/token" in str(request.url):
                return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
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
                json={"result": {"statusCode": "210", "errorMessage": "Invalid token"}},
            )

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = JpoClient(username="user", password="pass", client=http_client)
        with pytest.raises(AuthenticationError, match="Invalid JPO API token"):
            await client.get_patent_progress("2020123456")

    @pytest.mark.asyncio
    async def test_api_error_500(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/token" in str(request.url):
                return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
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
        assert token_calls == 2


# =============================================================================
# URL building
# =============================================================================


class TestBuildUrl:
    def test_build_url(self) -> None:
        client = JpoClient(username="user", password="pass")
        url = client._build_url("/patent/v1/app_progress/2020123456")
        assert url == f"{BASE_URL}/api/patent/v1/app_progress/2020123456"


# =============================================================================
# Document bundle oversize redirect (JSON path with URL field)
# =============================================================================


class TestDocumentBundleOversize:
    @pytest.mark.asyncio
    async def test_oversize_json_redirect(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/token" in str(request.url):
                return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
            return httpx.Response(
                200,
                json={
                    "result": {
                        "statusCode": "100",
                        "data": {"URL": "https://example.com/big.zip"},
                    }
                },
                headers={"content-type": "application/json"},
            )

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = JpoClient(username="u", password="p", client=http_client)
        result = await client.get_patent_application_documents("2020123456")
        assert isinstance(result, DocumentBundleResult)
        assert result.zip_bytes is None
        assert result.download_url == "https://example.com/big.zip"
