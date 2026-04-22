"""Async client for JPO Patent Information Retrieval API.

This client handles OAuth2 authentication and provides access to
Patent, Design, and Trademark APIs from the Japan Patent Office.

Usage:
    async with JpoClient(username="...", password="...") as client:
        progress = await client.get_patent_progress("2020123456")

Environment Variables:
    JPO_API_USERNAME: JPO-issued username/ID
    JPO_API_PASSWORD: JPO-issued password
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import deque
from typing import Any

import httpx
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential_jitter

from law_tools_core.base_client import BaseAsyncClient
from law_tools_core.exceptions import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    RateLimitError,
)

from .models import (
    ApiResult,
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
    StatusCode,
    TrademarkProgressData,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://ip-data.jpo.go.jp"
TOKEN_PATH = "/auth/token"  # Token endpoint path (exact path provided upon registration)

# Rate limiting: 10 requests per minute for Patent/Design/Trademark APIs
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW = 60  # seconds


class TokenManager:
    """Manages OAuth2 token lifecycle for JPO API.

    Handles token acquisition and automatic refresh on expiry.
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
            client: HTTP client to use for token request.

        Returns:
            Valid access token string.

        Raises:
            AuthenticationError: If token acquisition fails.
        """
        async with self._lock:
            # Check if current token is still valid (with 60s buffer)
            if self._token and time.time() < self._token_expiry - 60:
                return self._token

            # Acquire new token
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
                # Default to 1 hour if expires_in not provided
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
        """Invalidate the current token, forcing refresh on next request."""
        self._token = None
        self._token_expiry = 0


class RateLimiter:
    """Simple sliding window rate limiter.

    Enforces rate limits to comply with JPO API restrictions:
    - 10 requests per minute for Patent/Design/Trademark APIs
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
        """Wait until a request can be made within rate limits."""
        async with self._lock:
            now = time.time()

            # Remove timestamps outside the window
            while self._timestamps and self._timestamps[0] < now - self.window_seconds:
                self._timestamps.popleft()

            # If at limit, wait until oldest request exits the window
            if len(self._timestamps) >= self.max_requests:
                wait_time = self._timestamps[0] + self.window_seconds - now
                if wait_time > 0:
                    logger.debug("Rate limit reached, waiting %.2fs", wait_time)
                    await asyncio.sleep(wait_time)
                    # Re-check after waiting
                    now = time.time()
                    while self._timestamps and self._timestamps[0] < now - self.window_seconds:
                        self._timestamps.popleft()

            self._timestamps.append(time.time())


class JpoClient(BaseAsyncClient):
    """Async client for JPO Patent Information Retrieval API.

    Handles OAuth2 authentication, rate limiting, and provides methods
    for all Patent, Design, and Trademark API endpoints.

    Example:
        async with JpoClient() as client:
            # Get patent status
            progress = await client.get_patent_progress("2020123456")

            # Look up applicant by code
            applicants = await client.get_patent_applicant_by_code("123456789")

            # Get J-PlatPat URL
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
            username: JPO-issued username. Falls back to JPO_API_USERNAME env var.
            password: JPO-issued password. Falls back to JPO_API_PASSWORD env var.
            base_url: Override the default API base URL.
            token_path: Override the token endpoint path.
            client: Existing httpx.AsyncClient to use (for testing).

        Raises:
            ConfigurationError: If credentials are not provided.
        """
        resolved_username = username or os.getenv("JPO_API_USERNAME")
        resolved_password = password or os.getenv("JPO_API_PASSWORD")

        if not resolved_username or not resolved_password:
            raise ConfigurationError(
                "JPO API credentials required. "
                "Set JPO_API_USERNAME and JPO_API_PASSWORD environment variables "
                "or pass username and password parameters."
            )

        super().__init__(
            base_url=base_url,
            client=client,
            use_cache=False,
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

    def _build_url(self, path: str) -> str:
        """Build full URL from API path, prepending /api."""
        return f"{self.base_url}/api{path}"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> dict[str, Any]:
        """Make an authenticated API request.

        Args:
            method: HTTP method.
            path: API path (e.g., "/patent/v1/app_progress/2020123456").
            params: Query parameters.
            retry_auth: Whether to retry once on auth failure.

        Returns:
            Parsed JSON response.

        Raises:
            ApiError: On API errors.
            AuthenticationError: On authentication failures.
            RateLimitError: When rate limited by the API.
        """
        # Apply rate limiting
        await self._rate_limiter.acquire()

        # Get auth token
        token = await self._token_manager.get_token(self._client)

        url = self._build_url(path)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential_jitter(initial=1, max=10),
            reraise=True,
        ):
            with attempt:
                response = await self._client.request(method, url, params=params, headers=headers)

                # Handle auth errors with token refresh
                if response.status_code in (401, 403) and retry_auth:
                    self._token_manager.invalidate()
                    return await self._request(method, path, params=params, retry_auth=False)

                # Handle rate limiting
                if response.status_code == 429:
                    raise RateLimitError(
                        "JPO API rate limit exceeded",
                        response.status_code,
                        response.text,
                    )

                # Handle other errors
                if not response.is_success:
                    raise ApiError(
                        f"JPO API error: {response.status_code}",
                        response.status_code,
                        response.text,
                    )

                return response.json()

        raise RuntimeError("Unexpected retry exhaustion")

    def _parse_result(self, data: dict[str, Any]) -> ApiResult:
        """Parse the result wrapper from API response."""
        return ApiResult.model_validate(data.get("result", data))

    def _check_result(self, result: ApiResult, context: str = "") -> None:
        """Check API result for errors.

        Raises:
            RateLimitError: If daily limit exceeded.
            ApiError: If API returned an error status.
        """
        if result.status_code == StatusCode.DAILY_LIMIT_EXCEEDED.value:
            raise RateLimitError(
                f"JPO daily access limit exceeded{f' for {context}' if context else ''}",
                203,
                result.error_message,
            )

        if result.status_code == StatusCode.INVALID_TOKEN.value:
            raise AuthenticationError("Invalid JPO API token", 210, result.error_message)

        # Note: NO_DATA and NO_DOCUMENT are not errors, just empty results

    # =========================================================================
    # Patent APIs
    # =========================================================================

    async def get_patent_progress(self, application_number: str) -> PatentProgressData | None:
        """Get full patent progress/status information.

        Args:
            application_number: 10-digit application number (e.g., "2020123456").

        Returns:
            Patent progress data or None if not found.
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
        """Get simplified patent progress information (without priority/classification).

        Args:
            application_number: 10-digit application number.

        Returns:
            Simplified progress data or None if not found.
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
    ) -> list[DivisionalApplicationInfo]:
        """Get divisional application information.

        Args:
            application_number: 10-digit application number.

        Returns:
            List of divisional application information.
        """
        path = f"/patent/v1/divisional_app_info/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "divisional info")

        if not result.has_data or not result.data:
            return []
        divisionals = result.data.get("divisionalApplicationInfo", [])
        return [DivisionalApplicationInfo.model_validate(d) for d in divisionals]

    async def get_patent_priority_info(self, application_number: str) -> list[PriorityInfo]:
        """Get priority basic application information.

        Args:
            application_number: 10-digit application number.

        Returns:
            List of priority claim information.
        """
        path = f"/patent/v1/priority_right_app_info/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "priority info")

        if not result.has_data or not result.data:
            return []
        priorities = result.data.get("priorityInfo", [])
        return [PriorityInfo.model_validate(p) for p in priorities]

    async def get_patent_applicant_by_code(self, applicant_code: str) -> list[ApplicantAttorney]:
        """Get applicant name by applicant code.

        Args:
            applicant_code: 9-digit applicant code.

        Returns:
            List of applicant information.
        """
        path = f"/patent/v1/applicant_attorney_cd/{applicant_code}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "applicant by code")

        if not result.has_data or not result.data:
            return []
        applicants = result.data.get("applicantAttorney", [])
        return [ApplicantAttorney.model_validate(a) for a in applicants]

    async def get_patent_applicant_by_name(self, applicant_name: str) -> list[ApplicantAttorney]:
        """Get applicant code by applicant name.

        Args:
            applicant_name: Applicant name to search.

        Returns:
            List of applicant information with codes.
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
        self, kind: NumberType | str, number: str
    ) -> list[NumberReference]:
        """Get cross-reference of application, publication, and registration numbers.

        Args:
            kind: Number type code (e.g., NumberType.APPLICATION or "01").
            number: The number to look up.

        Returns:
            List of number references.
        """
        kind_code = kind.value if isinstance(kind, NumberType) else kind
        path = f"/patent/v1/case_number_reference/{kind_code}/{number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "number reference")

        if not result.has_data or not result.data:
            return []
        refs = result.data.get("caseNumberReference", [])
        return [NumberReference.model_validate(r) for r in refs]

    async def get_patent_application_documents(
        self, application_number: str
    ) -> ApplicationDocumentsData | None:
        """Get patent application documents (filed by applicant).

        Args:
            application_number: 10-digit application number.

        Returns:
            Application documents data or None if not found.
        """
        path = f"/patent/v1/app_doc_cont_opinion_amendment/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "application documents")

        if not result.has_data or not result.data:
            return None
        return ApplicationDocumentsData.model_validate(result.data)

    async def get_patent_mailed_documents(
        self, application_number: str
    ) -> ApplicationDocumentsData | None:
        """Get mailed patent documents (office actions, decisions).

        Args:
            application_number: 10-digit application number.

        Returns:
            Mailed documents data or None if not found.
        """
        path = f"/patent/v1/app_doc_cont_refusal_reason_decision/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "mailed documents")

        if not result.has_data or not result.data:
            return None
        return ApplicationDocumentsData.model_validate(result.data)

    async def get_patent_refusal_notices(
        self, application_number: str
    ) -> ApplicationDocumentsData | None:
        """Get notices of reasons for refusal.

        Args:
            application_number: 10-digit application number.

        Returns:
            Refusal notice documents or None if not found.
        """
        path = f"/patent/v1/app_doc_cont_refusal_reason/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "refusal notices")

        if not result.has_data or not result.data:
            return None
        return ApplicationDocumentsData.model_validate(result.data)

    async def get_patent_cited_documents(self, application_number: str) -> list[CitedDocumentInfo]:
        """Get cited documents information.

        Args:
            application_number: 10-digit application number.

        Returns:
            List of cited document information.
        """
        path = f"/patent/v1/cite_doc_info/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "cited documents")

        if not result.has_data or not result.data:
            return []
        cites = result.data.get("citedDocumentInfo", [])
        return [CitedDocumentInfo.model_validate(c) for c in cites]

    async def get_patent_registration_info(
        self, application_number: str
    ) -> RegistrationInfo | None:
        """Get patent registration information.

        Args:
            application_number: 10-digit application number.

        Returns:
            Registration information or None if not registered.
        """
        path = f"/patent/v1/registration_info/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "registration info")

        if not result.has_data or not result.data:
            return None
        return RegistrationInfo.model_validate(result.data)

    async def get_patent_jplatpat_url(self, application_number: str) -> str | None:
        """Get the J-PlatPat fixed URL for a patent application.

        Args:
            application_number: 10-digit application number.

        Returns:
            J-PlatPat URL or None if not available.
        """
        path = f"/patent/v1/jpp_fixed_address/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "J-PlatPat URL")

        if not result.has_data or not result.data:
            return None
        return result.data.get("jplatpatUrl")

    async def get_patent_pct_national_number(
        self, kind: NumberType | str, number: str
    ) -> PctNationalPhaseData | None:
        """Get national phase application number from PCT number.

        Args:
            kind: Number type (PCT_APPLICATION or PCT_PUBLICATION).
            number: PCT application or publication number.

        Returns:
            PCT national phase data or None if not found.
        """
        kind_code = kind.value if isinstance(kind, NumberType) else kind
        path = f"/patent/v1/pct_national_phase_application_number/{kind_code}/{number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "PCT national phase")

        if not result.has_data or not result.data:
            return None
        return PctNationalPhaseData.model_validate(result.data)

    # =========================================================================
    # Design APIs
    # =========================================================================

    async def get_design_progress(self, application_number: str) -> DesignProgressData | None:
        """Get design application progress information.

        Args:
            application_number: 10-digit application number.

        Returns:
            Design progress data or None if not found.
        """
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
        """Get simplified design progress information.

        Args:
            application_number: 10-digit application number.

        Returns:
            Simplified design progress data or None if not found.
        """
        path = f"/design/v1/app_progress_simple/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "simplified design progress")

        if not result.has_data or not result.data:
            return None
        return DesignProgressData.model_validate(result.data)

    async def get_design_priority_info(self, application_number: str) -> list[PriorityInfo]:
        """Get design priority information.

        Args:
            application_number: 10-digit application number.

        Returns:
            List of priority information.
        """
        path = f"/design/v1/priority_right_app_info/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "design priority")

        if not result.has_data or not result.data:
            return []
        priorities = result.data.get("priorityInfo", [])
        return [PriorityInfo.model_validate(p) for p in priorities]

    async def get_design_applicant_by_code(self, applicant_code: str) -> list[ApplicantAttorney]:
        """Get design applicant name by code."""
        path = f"/design/v1/applicant_attorney_cd/{applicant_code}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "design applicant by code")

        if not result.has_data or not result.data:
            return []
        applicants = result.data.get("applicantAttorney", [])
        return [ApplicantAttorney.model_validate(a) for a in applicants]

    async def get_design_applicant_by_name(self, applicant_name: str) -> list[ApplicantAttorney]:
        """Get design applicant code by name."""
        path = f"/design/v1/applicant_attorney/{applicant_name}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "design applicant by name")

        if not result.has_data or not result.data:
            return []
        applicants = result.data.get("applicantAttorney", [])
        return [ApplicantAttorney.model_validate(a) for a in applicants]

    async def get_design_number_reference(
        self, kind: NumberType | str, number: str
    ) -> list[NumberReference]:
        """Get design number cross-reference."""
        kind_code = kind.value if isinstance(kind, NumberType) else kind
        path = f"/design/v1/case_number_reference/{kind_code}/{number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "design number reference")

        if not result.has_data or not result.data:
            return []
        refs = result.data.get("caseNumberReference", [])
        return [NumberReference.model_validate(r) for r in refs]

    async def get_design_application_documents(
        self, application_number: str
    ) -> ApplicationDocumentsData | None:
        """Get design application documents."""
        path = f"/design/v1/app_doc_cont_opinion_amendment/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "design application documents")

        if not result.has_data or not result.data:
            return None
        return ApplicationDocumentsData.model_validate(result.data)

    async def get_design_mailed_documents(
        self, application_number: str
    ) -> ApplicationDocumentsData | None:
        """Get mailed design documents."""
        path = f"/design/v1/app_doc_cont_refusal_reason_decision/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "design mailed documents")

        if not result.has_data or not result.data:
            return None
        return ApplicationDocumentsData.model_validate(result.data)

    async def get_design_refusal_notices(
        self, application_number: str
    ) -> ApplicationDocumentsData | None:
        """Get design refusal notices."""
        path = f"/design/v1/app_doc_cont_refusal_reason/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "design refusal notices")

        if not result.has_data or not result.data:
            return None
        return ApplicationDocumentsData.model_validate(result.data)

    async def get_design_registration_info(
        self, application_number: str
    ) -> RegistrationInfo | None:
        """Get design registration information."""
        path = f"/design/v1/registration_info/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "design registration")

        if not result.has_data or not result.data:
            return None
        return RegistrationInfo.model_validate(result.data)

    async def get_design_jplatpat_url(self, application_number: str) -> str | None:
        """Get J-PlatPat URL for a design application."""
        path = f"/design/v1/jpp_fixed_address/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "design J-PlatPat URL")

        if not result.has_data or not result.data:
            return None
        return result.data.get("jplatpatUrl")

    # =========================================================================
    # Trademark APIs
    # =========================================================================

    async def get_trademark_progress(self, application_number: str) -> TrademarkProgressData | None:
        """Get trademark application progress information.

        Args:
            application_number: 10-digit application number.

        Returns:
            Trademark progress data or None if not found.
        """
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
        """Get simplified trademark progress information."""
        path = f"/trademark/v1/app_progress_simple/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "simplified trademark progress")

        if not result.has_data or not result.data:
            return None
        return TrademarkProgressData.model_validate(result.data)

    async def get_trademark_priority_info(self, application_number: str) -> list[PriorityInfo]:
        """Get trademark priority information."""
        path = f"/trademark/v1/priority_right_app_info/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "trademark priority")

        if not result.has_data or not result.data:
            return []
        priorities = result.data.get("priorityInfo", [])
        return [PriorityInfo.model_validate(p) for p in priorities]

    async def get_trademark_applicant_by_code(self, applicant_code: str) -> list[ApplicantAttorney]:
        """Get trademark applicant name by code."""
        path = f"/trademark/v1/applicant_attorney_cd/{applicant_code}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "trademark applicant by code")

        if not result.has_data or not result.data:
            return []
        applicants = result.data.get("applicantAttorney", [])
        return [ApplicantAttorney.model_validate(a) for a in applicants]

    async def get_trademark_applicant_by_name(self, applicant_name: str) -> list[ApplicantAttorney]:
        """Get trademark applicant code by name."""
        path = f"/trademark/v1/applicant_attorney/{applicant_name}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "trademark applicant by name")

        if not result.has_data or not result.data:
            return []
        applicants = result.data.get("applicantAttorney", [])
        return [ApplicantAttorney.model_validate(a) for a in applicants]

    async def get_trademark_number_reference(
        self, kind: NumberType | str, number: str
    ) -> list[NumberReference]:
        """Get trademark number cross-reference."""
        kind_code = kind.value if isinstance(kind, NumberType) else kind
        path = f"/trademark/v1/case_number_reference/{kind_code}/{number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "trademark number reference")

        if not result.has_data or not result.data:
            return []
        refs = result.data.get("caseNumberReference", [])
        return [NumberReference.model_validate(r) for r in refs]

    async def get_trademark_application_documents(
        self, application_number: str
    ) -> ApplicationDocumentsData | None:
        """Get trademark application documents."""
        path = f"/trademark/v1/app_doc_cont_opinion_amendment/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "trademark application documents")

        if not result.has_data or not result.data:
            return None
        return ApplicationDocumentsData.model_validate(result.data)

    async def get_trademark_mailed_documents(
        self, application_number: str
    ) -> ApplicationDocumentsData | None:
        """Get mailed trademark documents."""
        path = f"/trademark/v1/app_doc_cont_refusal_reason_decision/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "trademark mailed documents")

        if not result.has_data or not result.data:
            return None
        return ApplicationDocumentsData.model_validate(result.data)

    async def get_trademark_refusal_notices(
        self, application_number: str
    ) -> ApplicationDocumentsData | None:
        """Get trademark refusal notices."""
        path = f"/trademark/v1/app_doc_cont_refusal_reason/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "trademark refusal notices")

        if not result.has_data or not result.data:
            return None
        return ApplicationDocumentsData.model_validate(result.data)

    async def get_trademark_registration_info(
        self, application_number: str
    ) -> RegistrationInfo | None:
        """Get trademark registration information."""
        path = f"/trademark/v1/registration_info/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "trademark registration")

        if not result.has_data or not result.data:
            return None
        return RegistrationInfo.model_validate(result.data)

    async def get_trademark_jplatpat_url(self, application_number: str) -> str | None:
        """Get J-PlatPat URL for a trademark application."""
        path = f"/trademark/v1/jpp_fixed_address/{application_number}"
        data = await self._request("GET", path)
        result = self._parse_result(data)
        self._check_result(result, "trademark J-PlatPat URL")

        if not result.has_data or not result.data:
            return None
        return result.data.get("jplatpatUrl")


__all__ = [
    "JpoClient",
    "TokenManager",
    "RateLimiter",
    "BASE_URL",
]
