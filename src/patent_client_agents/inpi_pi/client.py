"""Async client for JPO Patent Information Retrieval API.

This client handles OAuth2 authentication and provides access to
Patent, Design, and Trademark APIs from the Japan Patent Office.

Usage:
    async with InpiPiClient(username="...", password="...") as client:
        progress = await client.get_patent_progress("2020123456")

Environment Variables:
    INPI_USERNAME: JPO-issued username/ID
    INPI_PASSWORD: JPO-issued password
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import deque
from typing import Any

import httpx

from law_tools_core.base_client import BaseAsyncClient
from law_tools_core.exceptions import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    NotFoundError,
    RateLimitError,
)
from law_tools_core.resilience import default_retryer

from .models import (
    ApiResult,
    ApplicantAttorney,
    CaseNumberKind,
    CitedDocumentsData,
    DesignProgressData,
    DivisionalAppInfoData,
    DocumentBundleResult,
    NumberReference,
    NumberType,
    PatentProgressData,
    PctKind,
    PctNationalPhaseData,
    PriorityInfo,
    RegistrationInfo,
    SimplifiedPatentProgressData,
    StatusCode,
    TrademarkProgressData,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://ip-data.jpo.go.jp"
TOKEN_PATH = "/auth/token"  # OAuth2 password-grant endpoint

# Rate limiting: 10 requests per minute for Patent/Design/Trademark APIs
# (handbook v14 §3 — "adjust the total number of accesses per minute to 10
# or less mechanically"). Daily caps are enforced server-side per endpoint.
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW = 60  # seconds


# Status codes that mean "no result for this query"; we return None / [].
_EMPTY_STATUS_CODES = frozenset(
    {
        StatusCode.NO_DATA.value,
        StatusCode.NO_DOCUMENT.value,
        StatusCode.UNAVAILABLE_NUMBER.value,
    }
)


def _kind_value(kind: NumberType | CaseNumberKind | PctKind | str) -> str:
    """Normalize a kind argument to its string value.

    Accepts any of the three kind enums or a raw string.
    """
    if isinstance(kind, NumberType | CaseNumberKind | PctKind):
        return kind.value
    return kind


class TokenManager:
    """Manages OAuth2 token lifecycle for JPO API.

    The JPO token endpoint is a Keycloak password-grant flow returning
    a JWT access token plus refresh token. We don't use the refresh token
    here — getting a fresh access token via password grant is cheap and
    avoids storing refresh tokens at rest.
    """

    def __init__(
        self,
        username: str,
        password: str,
        *,
        base_url: str = BASE_URL,
        token_path: str = TOKEN_PATH,
    ) -> None:
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self.token_path = token_path
        self._token: str | None = None
        self._token_expiry: float = 0
        self._lock = asyncio.Lock()

    async def get_token(self, client: httpx.AsyncClient) -> str:
        """Get a valid access token, refreshing if needed.

        Args:
            client: HTTP client to use for the token request.

        Returns:
            Valid access token string.

        Raises:
            AuthenticationError: If token acquisition fails.
        """
        async with self._lock:
            # Reuse if still valid (with 60s safety buffer).
            if self._token and time.time() < self._token_expiry - 60:
                return self._token

            token_url = f"{self.base_url}{self.token_path}"
            logger.debug("Acquiring new JPO API token")

            try:
                response = await client.post(
                    token_url,
                    data={
                        "grant_type": "password",
                        "username": self.username,
                        "password": self.password,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                if response.status_code == 401:
                    raise AuthenticationError(
                        "Invalid JPO credentials", response.status_code, response.text
                    )
                if response.status_code == 403:
                    raise AuthenticationError(
                        "JPO API access forbidden", response.status_code, response.text
                    )
                response.raise_for_status()

                data = response.json()
                self._token = data["access_token"]
                expires_in = data.get("expires_in", 3600)
                self._token_expiry = time.time() + expires_in
                logger.debug("Successfully acquired JPO API token (expires in %ds)", expires_in)
                if self._token is None:
                    raise RuntimeError("Token acquisition failed")
                return self._token

            except httpx.HTTPStatusError as e:
                raise AuthenticationError(
                    f"Failed to acquire JPO token: {e}",
                    e.response.status_code,
                    e.response.text,
                ) from e

    def invalidate(self) -> None:
        """Drop the cached token, forcing refresh on next request."""
        self._token = None
        self._token_expiry = 0


class RateLimiter:
    """Simple sliding-window rate limiter.

    Enforces JPO's documented 10 requests/minute cap on Patent/Design/
    Trademark APIs.
    """

    def __init__(
        self,
        max_requests: int = RATE_LIMIT_REQUESTS,
        window_seconds: float = RATE_LIMIT_WINDOW,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a request can be made within the rate limit."""
        async with self._lock:
            now = time.time()

            while self._timestamps and self._timestamps[0] < now - self.window_seconds:
                self._timestamps.popleft()

            if len(self._timestamps) >= self.max_requests:
                wait_time = self._timestamps[0] + self.window_seconds - now
                if wait_time > 0:
                    logger.debug("Rate limit reached, waiting %.2fs", wait_time)
                    await asyncio.sleep(wait_time)
                    now = time.time()
                    while self._timestamps and self._timestamps[0] < now - self.window_seconds:
                        self._timestamps.popleft()

            self._timestamps.append(time.time())


class InpiPiClient(BaseAsyncClient):
    """Async client for JPO Patent Information Retrieval API.

    Handles OAuth2 authentication, in-process rate limiting, and exposes
    typed methods for all 36 patent/design/trademark endpoints in handbook
    v14. Document-download endpoints (``app_doc_cont_*``) return a
    :class:`DocumentBundleResult` because they yield raw ZIP bytes (or a
    download URL when the archive exceeds 10 MB), not JSON.

    Example:
        async with InpiPiClient() as client:
            progress = await client.get_patent_progress("2020123456")
            applicant_name = await client.get_patent_applicant_by_code(
                "000003207"
            )
            url = await client.get_patent_jplatpat_url("2020123456")
    """

    DEFAULT_BASE_URL = BASE_URL
    CACHE_NAME = "jpo"
    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        *,
        base_url: str | None = None,
        token_path: str = TOKEN_PATH,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize the JPO API client.

        Args:
            username: JPO-issued username. Falls back to ``INPI_USERNAME``.
            password: JPO-issued password. Falls back to ``INPI_PASSWORD``.
            base_url: Override the default API base URL.
            token_path: Override the token endpoint path.
            client: Existing httpx.AsyncClient to use (for testing).

        Raises:
            ConfigurationError: If credentials are not provided.
        """
        resolved_username = username or os.getenv("INPI_USERNAME")
        resolved_password = password or os.getenv("INPI_PASSWORD")

        if not resolved_username or not resolved_password:
            raise ConfigurationError(
                "JPO API credentials required. "
                "Set INPI_USERNAME and INPI_PASSWORD environment variables "
                "or pass username and password parameters."
            )

        # Enable hishel caching: the JPO API includes Cache-Control headers
        # so legitimate cache use saves quota. Tokens carry ``Cache-Control:
        # no-store`` so they're never cached. The cache also routes us
        # through httpcore directly, which vcrpy can intercept reliably.
        super().__init__(
            base_url=base_url,
            client=client,
            use_cache=True,
            headers={"Accept": "application/json"},
            timeout=self.DEFAULT_TIMEOUT,
        )

        self._token_manager = TokenManager(
            resolved_username,
            resolved_password,
            base_url=self.base_url,
            token_path=token_path,
        )
        self._rate_limiter = RateLimiter()

    # ------------------------------------------------------------------
    # Low-level transport
    # ------------------------------------------------------------------

    def _build_url(self, path: str) -> str:
        """Build full URL from API path, prepending ``/api``."""
        return f"{self.base_url}/api{path}"

    async def _raw_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> httpx.Response:
        """Make an authenticated raw request and return the httpx response.

        This is the path used by document-download endpoints that may return
        non-JSON (ZIP) bodies. JSON endpoints use :meth:`_request` which
        wraps this and decodes the body.

        Raises:
            AuthenticationError: On 401/403 after one retry.
            RateLimitError: On HTTP 429.
            ApiError: On any other non-success status.
        """
        await self._rate_limiter.acquire()
        token = await self._token_manager.get_token(self._client)
        url = self._build_url(path)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, application/zip",
        }

        # JPO-specific concerns live inline (rate-limit acquire above,
        # token refresh on 401/403 below, 429→RateLimitError mapping). The
        # backoff and retry-filter behavior is delegated to
        # ``default_retryer`` — it retries on RateLimitError,
        # TransportError, and 5xx HTTPStatusError, and *doesn't* retry on
        # plain ApiError, which is the right call for 4xx responses.
        async for attempt in default_retryer(max_attempts=3, max_wait=10.0):
            with attempt:
                response = await self._client.request(method, url, params=params, headers=headers)

                if response.status_code in (401, 403) and retry_auth:
                    self._token_manager.invalidate()
                    return await self._raw_request(method, path, params=params, retry_auth=False)

                if response.status_code == 429:
                    raise RateLimitError(
                        "JPO API rate limit exceeded",
                        response.status_code,
                        response.text[:500],
                    )

                if not response.is_success:
                    raise ApiError(
                        f"JPO API error: {response.status_code}",
                        response.status_code,
                        response.text[:500],
                    )

                return response

        raise RuntimeError("Unexpected retry exhaustion")

    async def _request(  # ty: ignore[invalid-method-override]
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> dict[str, Any]:
        """Make an authenticated JSON API request and return the parsed body.

        Raises:
            ApiError: On non-success HTTP status or non-JSON body.
            AuthenticationError: On authentication failures.
            RateLimitError: When rate limited by the API.
        """
        response = await self._raw_request(method, path, params=params, retry_auth=retry_auth)
        try:
            return response.json()
        except ValueError as e:
            raise ApiError(
                f"JPO API returned non-JSON body: {e}",
                response.status_code,
                response.text[:500],
            ) from e

    def _parse_result(self, data: dict[str, Any]) -> ApiResult:
        """Extract the ``result`` envelope from a JPO API response."""
        return ApiResult.model_validate(data.get("result", data))

    def _check_result(self, result: ApiResult, context: str = "") -> None:
        """Map status-code errors to the appropriate exception.

        ``107`` / ``108`` / ``111`` are *not* errors — callers handle empty
        results via :meth:`ApiResult.has_data`.

        ``303`` (concentrated access) is mapped to :class:`RateLimitError`
        — it's transient and the API itself recommends back-off.
        """
        sc = result.status_code

        if sc == StatusCode.DAILY_LIMIT_EXCEEDED.value:
            raise RateLimitError(
                f"JPO daily access limit exceeded{f' for {context}' if context else ''}",
                int(sc),
                result.error_message,
            )

        if sc == StatusCode.CONCENTRATED_ACCESS.value:
            raise RateLimitError(
                f"JPO API access concentrated{f' for {context}' if context else ''}; retry later",
                int(sc),
                result.error_message,
            )

        if sc == StatusCode.INVALID_TOKEN.value:
            raise AuthenticationError("Invalid JPO API token", int(sc), result.error_message)

        if sc == StatusCode.INVALID_AUTH.value:
            raise AuthenticationError(
                "Invalid JPO API authentication", int(sc), result.error_message
            )

        if sc in (
            StatusCode.INVALID_PARAMETER.value,
            StatusCode.INVALID_CHARACTERS.value,
            StatusCode.INVALID_REQUEST.value,
        ):
            raise ApiError(
                f"JPO API invalid request{f' for {context}' if context else ''}: "
                f"{result.error_message}",
                int(sc),
                result.error_message,
            )

        if sc == StatusCode.URL_NOT_FOUND.value:
            raise NotFoundError(
                f"JPO API URL not found{f' for {context}' if context else ''}",
                int(sc),
                result.error_message,
            )

        if sc in (StatusCode.TIMEOUT.value, StatusCode.UNEXPECTED_ERROR.value):
            raise ApiError(
                f"JPO API server error{f' for {context}' if context else ''}: "
                f"{result.error_message}",
                int(sc),
                result.error_message,
            )

    async def _fetch_document_bundle(
        self, application_number: str, path: str
    ) -> DocumentBundleResult:
        """Fetch a document-download endpoint that returns ZIP-or-JSON.

        ``app_doc_cont_*`` endpoints return one of three things:

        1. ``Content-Type: application/zip`` with the archive body inline
           (when the ZIP is < 10 MB);
        2. ``Content-Type: application/json`` with ``data.URL`` pointing at
           a hosted ZIP (when the archive is > 10 MB);
        3. ``Content-Type: application/json`` with an empty ``data`` object
           and an error status code (107 / 108) when there are no
           documents.
        """
        response = await self._raw_request("GET", path)
        content_type = response.headers.get("content-type", "").lower()

        if "zip" in content_type:
            return DocumentBundleResult(
                application_number=application_number,
                zip_bytes=response.content,
                content_type=content_type,
            )

        # JSON path — either oversize redirect or empty result.
        body = response.json()
        result = self._parse_result(body)
        self._check_result(result, "document bundle")

        if not result.has_data or not result.data:
            return DocumentBundleResult(
                application_number=application_number,
                content_type=content_type,
            )

        # JPO returns "URL" (uppercase) for the oversize redirect.
        url = result.data.get("URL", "")
        return DocumentBundleResult(
            application_number=application_number,
            download_url=url,
            content_type=content_type,
        )

    # ==================================================================
    # Patent APIs
    # ==================================================================

    async def get_patent_progress(self, application_number: str) -> PatentProgressData | None:
        """``GET /patent/v1/app_progress/{n}`` — full patent progress.

        Args:
            application_number: 10-digit application number (e.g. ``2020123456``).

        Returns:
            Parsed progress data, or ``None`` when the API has no data
            for this number.
        """
        path = f"/patent/v1/app_progress/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "patent progress")
        if not result.has_data or not result.data:
            return None
        return PatentProgressData.model_validate(result.data)

    async def get_patent_progress_simple(
        self, application_number: str
    ) -> SimplifiedPatentProgressData | None:
        """``GET /patent/v1/app_progress_simple/{n}`` — simplified progress.

        Same shape as :meth:`get_patent_progress` minus priority,
        parent-application, and divisional information.
        """
        path = f"/patent/v1/app_progress_simple/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "simplified patent progress")
        if not result.has_data or not result.data:
            return None
        return SimplifiedPatentProgressData.model_validate(result.data)

    async def get_patent_divisional_info(
        self, application_number: str
    ) -> DivisionalAppInfoData | None:
        """``GET /patent/v1/divisional_app_info/{n}`` — divisional family.

        Returns parent application info + the list of divisional descendants.
        Returns ``None`` when no data is available.
        """
        path = f"/patent/v1/divisional_app_info/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "divisional info")
        if not result.has_data or not result.data:
            return None
        return DivisionalAppInfoData.model_validate(result.data)

    async def get_patent_priority_info(self, application_number: str) -> list[PriorityInfo]:
        """``GET /patent/v1/priority_right_app_info/{n}`` — priority basis."""
        path = f"/patent/v1/priority_right_app_info/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "priority info")
        if not result.has_data or not result.data:
            return []
        priorities = result.data.get("priorityRightInformation", [])
        return [PriorityInfo.model_validate(p) for p in priorities]

    async def get_patent_applicant_by_code(self, applicant_code: str) -> str | None:
        """``GET /patent/v1/applicant_attorney_cd/{code}`` — name from code.

        Returns the applicant's name (a single string), or ``None`` if not
        found. Matches the live API which returns
        ``{"applicantAttorneyName": "<name>"}`` — *not* a list.
        """
        path = f"/patent/v1/applicant_attorney_cd/{applicant_code}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "applicant by code")
        if not result.has_data or not result.data:
            return None
        return result.data.get("applicantAttorneyName") or None

    async def get_patent_applicant_by_name(self, applicant_name: str) -> list[ApplicantAttorney]:
        """``GET /patent/v1/applicant_attorney/{name}`` — code from exact name.

        The endpoint requires an *exact* match; partial / fuzzy matches
        return ``107`` (no data). Returns the matching codes.
        """
        path = f"/patent/v1/applicant_attorney/{applicant_name}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "applicant by name")
        if not result.has_data or not result.data:
            return []
        applicants = result.data.get("applicantAttorney", [])
        return [ApplicantAttorney.model_validate(a) for a in applicants]

    async def get_patent_number_reference(
        self,
        kind: CaseNumberKind | str,
        number: str,
    ) -> NumberReference | None:
        """``GET /patent/v1/case_number_reference/{kind}/{n}`` — number cross-ref.

        Args:
            kind: One of :class:`CaseNumberKind` (``application`` /
                ``publication`` / ``registration``) or its string value.
                The numeric :class:`NumberType` codes do **not** apply here
                — the endpoint requires the descriptive strings.
            number: The number to look up. Format depends on ``kind``.

        Returns:
            A single cross-reference object (the endpoint returns one
            row, not a list), or ``None`` if not found.
        """
        kind_value = _kind_value(kind)
        path = f"/patent/v1/case_number_reference/{kind_value}/{number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "number reference")
        if not result.has_data or not result.data:
            return None
        return NumberReference.model_validate(result.data)

    async def get_patent_application_documents(
        self, application_number: str
    ) -> DocumentBundleResult:
        """``GET /patent/v1/app_doc_cont_opinion_amendment/{n}``.

        Returns the applicant-filed documents (opinions and amendments)
        as a ZIP archive of XML files. See :class:`DocumentBundleResult`
        for the bytes-vs-URL fallback semantics.
        """
        path = f"/patent/v1/app_doc_cont_opinion_amendment/{application_number}"
        return await self._fetch_document_bundle(application_number, path)

    async def get_patent_mailed_documents(self, application_number: str) -> DocumentBundleResult:
        """``GET /patent/v1/app_doc_cont_refusal_reason_decision/{n}``.

        Returns mailed JPO documents (notices of reasons for refusal,
        decisions of refusal, decisions of grant) as a ZIP of XML files.
        """
        path = f"/patent/v1/app_doc_cont_refusal_reason_decision/{application_number}"
        return await self._fetch_document_bundle(application_number, path)

    async def get_patent_refusal_notices(self, application_number: str) -> DocumentBundleResult:
        """``GET /patent/v1/app_doc_cont_refusal_reason/{n}``.

        Returns notices of reasons for refusal (rejections only — no
        grants) as a ZIP of XML files.
        """
        path = f"/patent/v1/app_doc_cont_refusal_reason/{application_number}"
        return await self._fetch_document_bundle(application_number, path)

    async def get_patent_cited_documents(
        self, application_number: str
    ) -> CitedDocumentsData | None:
        """``GET /patent/v1/cite_doc_info/{n}`` — patent + non-patent citations.

        Returns the combined citations bundle (patent and non-patent)
        or ``None`` if the API has no citation data.

        Note: the live API returns ``patentDoc`` and ``nonPatentDoc`` as
        *arrays*, not the singleton objects the OpenAPI spec describes.
        """
        path = f"/patent/v1/cite_doc_info/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "cited documents")
        if not result.has_data or not result.data:
            return None
        return CitedDocumentsData.model_validate(result.data)

    async def get_patent_registration_info(
        self, application_number: str
    ) -> RegistrationInfo | None:
        """``GET /patent/v1/registration_info/{n}`` — registration record."""
        path = f"/patent/v1/registration_info/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "registration info")
        if not result.has_data or not result.data:
            return None
        return RegistrationInfo.model_validate(result.data)

    async def get_patent_jplatpat_url(self, application_number: str) -> str | None:
        """``GET /patent/v1/jpp_fixed_address/{n}`` — J-PlatPat permalink.

        The live response uses ``URL`` (uppercase) — the OpenAPI spec is
        wrong about the field name being ``jplatpatUrl``.
        """
        path = f"/patent/v1/jpp_fixed_address/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "J-PlatPat URL")
        if not result.has_data or not result.data:
            return None
        return result.data.get("URL") or result.data.get("jplatpatUrl") or None

    async def get_patent_pct_national_number(
        self,
        kind: PctKind | str,
        number: str,
    ) -> PctNationalPhaseData | None:
        """``GET /patent/v1/pct_national_phase_application_number/{kind}/{n}``.

        Args:
            kind: One of :class:`PctKind` (``international_application`` /
                ``international_publication``) or its string value.
            number: PCT international application or publication number.

        Returns:
            National-phase application number wrapper, or ``None`` if not
            found.
        """
        kind_value = _kind_value(kind)
        path = f"/patent/v1/pct_national_phase_application_number/{kind_value}/{number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "PCT national phase")
        if not result.has_data or not result.data:
            return None
        return PctNationalPhaseData.model_validate(result.data)

    # ==================================================================
    # Design APIs
    # ==================================================================

    async def get_design_progress(self, application_number: str) -> DesignProgressData | None:
        """``GET /design/v1/app_progress/{n}`` — full design progress."""
        path = f"/design/v1/app_progress/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "design progress")
        if not result.has_data or not result.data:
            return None
        return DesignProgressData.model_validate(result.data)

    async def get_design_progress_simple(
        self, application_number: str
    ) -> DesignProgressData | None:
        """``GET /design/v1/app_progress_simple/{n}``."""
        path = f"/design/v1/app_progress_simple/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "simplified design progress")
        if not result.has_data or not result.data:
            return None
        return DesignProgressData.model_validate(result.data)

    async def get_design_priority_info(self, application_number: str) -> list[PriorityInfo]:
        """``GET /design/v1/priority_right_app_info/{n}``."""
        path = f"/design/v1/priority_right_app_info/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "design priority")
        if not result.has_data or not result.data:
            return []
        priorities = result.data.get("priorityRightInformation", [])
        return [PriorityInfo.model_validate(p) for p in priorities]

    async def get_design_applicant_by_code(self, applicant_code: str) -> str | None:
        """``GET /design/v1/applicant_attorney_cd/{code}`` — name from code."""
        path = f"/design/v1/applicant_attorney_cd/{applicant_code}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "design applicant by code")
        if not result.has_data or not result.data:
            return None
        return result.data.get("applicantAttorneyName") or None

    async def get_design_applicant_by_name(self, applicant_name: str) -> list[ApplicantAttorney]:
        """``GET /design/v1/applicant_attorney/{name}`` — code from exact name."""
        path = f"/design/v1/applicant_attorney/{applicant_name}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "design applicant by name")
        if not result.has_data or not result.data:
            return []
        applicants = result.data.get("applicantAttorney", [])
        return [ApplicantAttorney.model_validate(a) for a in applicants]

    async def get_design_number_reference(
        self,
        kind: CaseNumberKind | str,
        number: str,
    ) -> NumberReference | None:
        """``GET /design/v1/case_number_reference/{kind}/{n}``."""
        kind_value = _kind_value(kind)
        path = f"/design/v1/case_number_reference/{kind_value}/{number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "design number reference")
        if not result.has_data or not result.data:
            return None
        return NumberReference.model_validate(result.data)

    async def get_design_application_documents(
        self, application_number: str
    ) -> DocumentBundleResult:
        """``GET /design/v1/app_doc_cont_opinion_amendment/{n}``."""
        path = f"/design/v1/app_doc_cont_opinion_amendment/{application_number}"
        return await self._fetch_document_bundle(application_number, path)

    async def get_design_mailed_documents(self, application_number: str) -> DocumentBundleResult:
        """``GET /design/v1/app_doc_cont_refusal_reason_decision/{n}``."""
        path = f"/design/v1/app_doc_cont_refusal_reason_decision/{application_number}"
        return await self._fetch_document_bundle(application_number, path)

    async def get_design_refusal_notices(self, application_number: str) -> DocumentBundleResult:
        """``GET /design/v1/app_doc_cont_refusal_reason/{n}``."""
        path = f"/design/v1/app_doc_cont_refusal_reason/{application_number}"
        return await self._fetch_document_bundle(application_number, path)

    async def get_design_registration_info(
        self, application_number: str
    ) -> RegistrationInfo | None:
        """``GET /design/v1/registration_info/{n}``."""
        path = f"/design/v1/registration_info/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "design registration")
        if not result.has_data or not result.data:
            return None
        return RegistrationInfo.model_validate(result.data)

    async def get_design_jplatpat_url(self, application_number: str) -> str | None:
        """``GET /design/v1/jpp_fixed_address/{n}``."""
        path = f"/design/v1/jpp_fixed_address/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "design J-PlatPat URL")
        if not result.has_data or not result.data:
            return None
        return result.data.get("URL") or result.data.get("jplatpatUrl") or None

    # ==================================================================
    # Trademark APIs
    # ==================================================================

    async def get_trademark_progress(self, application_number: str) -> TrademarkProgressData | None:
        """``GET /trademark/v1/app_progress/{n}``."""
        path = f"/trademark/v1/app_progress/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "trademark progress")
        if not result.has_data or not result.data:
            return None
        return TrademarkProgressData.model_validate(result.data)

    async def get_trademark_progress_simple(
        self, application_number: str
    ) -> TrademarkProgressData | None:
        """``GET /trademark/v1/app_progress_simple/{n}``."""
        path = f"/trademark/v1/app_progress_simple/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "simplified trademark progress")
        if not result.has_data or not result.data:
            return None
        return TrademarkProgressData.model_validate(result.data)

    async def get_trademark_priority_info(self, application_number: str) -> list[PriorityInfo]:
        """``GET /trademark/v1/priority_right_app_info/{n}``."""
        path = f"/trademark/v1/priority_right_app_info/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "trademark priority")
        if not result.has_data or not result.data:
            return []
        priorities = result.data.get("priorityRightInformation", [])
        return [PriorityInfo.model_validate(p) for p in priorities]

    async def get_trademark_applicant_by_code(self, applicant_code: str) -> str | None:
        """``GET /trademark/v1/applicant_attorney_cd/{code}``."""
        path = f"/trademark/v1/applicant_attorney_cd/{applicant_code}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "trademark applicant by code")
        if not result.has_data or not result.data:
            return None
        return result.data.get("applicantAttorneyName") or None

    async def get_trademark_applicant_by_name(self, applicant_name: str) -> list[ApplicantAttorney]:
        """``GET /trademark/v1/applicant_attorney/{name}``."""
        path = f"/trademark/v1/applicant_attorney/{applicant_name}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "trademark applicant by name")
        if not result.has_data or not result.data:
            return []
        applicants = result.data.get("applicantAttorney", [])
        return [ApplicantAttorney.model_validate(a) for a in applicants]

    async def get_trademark_number_reference(
        self,
        kind: CaseNumberKind | str,
        number: str,
    ) -> NumberReference | None:
        """``GET /trademark/v1/case_number_reference/{kind}/{n}``."""
        kind_value = _kind_value(kind)
        path = f"/trademark/v1/case_number_reference/{kind_value}/{number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "trademark number reference")
        if not result.has_data or not result.data:
            return None
        return NumberReference.model_validate(result.data)

    async def get_trademark_application_documents(
        self, application_number: str
    ) -> DocumentBundleResult:
        """``GET /trademark/v1/app_doc_cont_opinion_amendment/{n}``."""
        path = f"/trademark/v1/app_doc_cont_opinion_amendment/{application_number}"
        return await self._fetch_document_bundle(application_number, path)

    async def get_trademark_mailed_documents(self, application_number: str) -> DocumentBundleResult:
        """``GET /trademark/v1/app_doc_cont_refusal_reason_decision/{n}``."""
        path = f"/trademark/v1/app_doc_cont_refusal_reason_decision/{application_number}"
        return await self._fetch_document_bundle(application_number, path)

    async def get_trademark_refusal_notices(self, application_number: str) -> DocumentBundleResult:
        """``GET /trademark/v1/app_doc_cont_refusal_reason/{n}``."""
        path = f"/trademark/v1/app_doc_cont_refusal_reason/{application_number}"
        return await self._fetch_document_bundle(application_number, path)

    async def get_trademark_registration_info(
        self, application_number: str
    ) -> RegistrationInfo | None:
        """``GET /trademark/v1/registration_info/{n}``."""
        path = f"/trademark/v1/registration_info/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "trademark registration")
        if not result.has_data or not result.data:
            return None
        return RegistrationInfo.model_validate(result.data)

    async def get_trademark_jplatpat_url(self, application_number: str) -> str | None:
        """``GET /trademark/v1/jpp_fixed_address/{n}``."""
        path = f"/trademark/v1/jpp_fixed_address/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "trademark J-PlatPat URL")
        if not result.has_data or not result.data:
            return None
        return result.data.get("URL") or result.data.get("jplatpatUrl") or None


__all__ = [
    "InpiPiClient",
    "TokenManager",
    "RateLimiter",
    "BASE_URL",
    "RATE_LIMIT_REQUESTS",
    "RATE_LIMIT_WINDOW",
]
