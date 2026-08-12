"""Async client for interacting with the EPO OPS REST API."""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Any

import hishel
import httpx
import lxml.etree as etree  # ty: ignore[unresolved-import]  # lxml lacks PEP 561 stubs
from pypdf import PdfReader, PdfWriter

from mcp_data_core.base_client import BaseAsyncClient
from mcp_data_core.cache import build_cached_http_client
from mcp_data_core.exceptions import AuthenticationError, RateLimitError

try:
    from mcp_data_core.exceptions import RetryableAuthenticationError
except ImportError:  # Compatibility until the new core release reaches package CI.
    from mcp_data_core.exceptions import ServerError as RetryableAuthenticationError

from .models import (
    BiblioResponse,
    CitationResponse,
    ClassificationMappingResponse,
    CpciBiblioResponse,
    CpcMediaResponse,
    CpcRetrievalResponse,
    CpcSearchResponse,
    EquivalentsResponse,
    FamilyResponse,
    FamilySearchEntry,
    FamilySearchResponse,
    FullTextResponse,
    LegalEventsResponse,
    NumberConversionResponse,
    PdfDownloadResponse,
    RegisterBiblioResponse,
    RegisterEventsResponse,
    RegisterProceduralStepsResponse,
    SearchResponse,
    UnitaryPatentPackage,
)
from .parsing import (
    NS,
    parse_biblio_response,
    parse_citations,
    parse_claims,
    parse_classification_mapping,
    parse_cpc_retrieval,
    parse_cpc_search,
    parse_cpci_biblio,
    parse_equivalents,
    parse_family,
    parse_legal_events,
    parse_number_conversion,
    parse_register_biblio,
    parse_register_events,
    parse_register_procedural_steps,
    parse_search_response,
    parse_unitary_patent_package,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://ops.epo.org/3.2"
CACHE_DIR = Path.home() / ".cache" / "epo_ops_mcp"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class OpsAuthenticationError(AuthenticationError):
    """Raised when OPS authentication fails.

    Inherits from AuthenticationError for unified exception handling.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = 401,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message, status_code, response_body)


class OpsForbiddenError(RateLimitError):
    """Raised when OPS returns 403 (usually rate limiting/quota).

    Inherits from RateLimitError for unified exception handling.
    """

    def __init__(
        self,
        message: str,
        *,
        headers: dict[str, str] | None = None,
        status_code: int | None = 403,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message, status_code, response_body)
        self.headers = headers or {}


class OpsAuth(httpx.Auth):
    requires_response_body = True
    token_url = f"{BASE_URL}/auth/accesstoken"

    def __init__(self, key: str, secret: str) -> None:
        self.key = key
        self.secret = secret
        self.authorization_header: str | None = None
        self._expires: dt.datetime | None = None
        self._refresh_lock = asyncio.Lock()

    async def async_auth_flow(self, request: httpx.Request):  # type: ignore[override]
        async with self._refresh_lock:
            if self._token_expired():
                token_response = yield self._build_refresh_request()
                self._store_token(token_response)

        assert self.authorization_header is not None
        token_used = self.authorization_header
        request.headers["Authorization"] = token_used
        response = yield request
        if not self._invalid_access_token(response):
            return

        async with self._refresh_lock:
            if self.authorization_header == token_used:
                token_response = yield self._build_refresh_request()
                self._store_token(token_response)

        assert self.authorization_header is not None
        request.headers["Authorization"] = self.authorization_header
        retry_response = yield request
        if self._invalid_access_token(retry_response):
            raise RetryableAuthenticationError(
                "EPO OPS rejected an access token after refresh",
                retry_response.status_code,
                retry_response.text[:500],
            )

    def _store_token(self, response: httpx.Response) -> None:
        if response.status_code != 200:
            logger.warning(
                "EPO OPS token request failed with HTTP %s: %s",
                response.status_code,
                response.text[:500],
            )
            if response.status_code == 429 or response.status_code >= 500:
                raise RetryableAuthenticationError(
                    "EPO OPS token request failed",
                    response.status_code,
                    response.text[:500],
                )
            raise OpsAuthenticationError(
                "EPO OPS rejected the configured credentials",
                response.status_code,
                response.text[:500],
            )

        data = response.json()
        issued_at = dt.datetime.fromtimestamp(int(data["issued_at"]) / 1000, tz=dt.UTC)
        expires_in = dt.timedelta(seconds=int(data["expires_in"]))
        self._expires = issued_at + expires_in
        self.authorization_header = f"Bearer {data['access_token']}"

    @staticmethod
    def _invalid_access_token(response: httpx.Response) -> bool:
        return response.status_code == 401 or (
            response.status_code == 400 and "invalid_access_token" in response.text
        )

    def _token_expired(self) -> bool:
        if self._expires is None:
            return True
        return dt.datetime.now(dt.UTC) >= self._expires - dt.timedelta(seconds=30)

    def _build_refresh_request(self) -> httpx.Request:
        credentials = f"{self.key}:{self.secret}".encode()
        token = base64.b64encode(credentials).decode("ascii")
        return httpx.Request(
            "POST",
            self.token_url,
            headers={"Authorization": token},
            data={"grant_type": "client_credentials"},
        )


class EpoOpsClient(BaseAsyncClient):
    DEFAULT_BASE_URL = BASE_URL
    CACHE_NAME = "epo_ops"
    DEFAULT_TIMEOUT = 60.0

    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        cache_path: Path | None = None,
        timeout: float = 60.0,
        auth: OpsAuth | None = None,
    ) -> None:
        # Build the HTTP client directly to pass EPO-specific kwargs
        # (base_url, policy, http2) that BaseAsyncClient doesn't forward.
        cache_dir = cache_path or CACHE_DIR
        cache_dir.mkdir(parents=True, exist_ok=True)
        headers = {
            "Accept": "application/xml",
            "User-Agent": "patent-client-agents-epo-ops/0.2",
        }
        self.base_url = self.DEFAULT_BASE_URL.rstrip("/")
        self._owns_client = True
        self._max_retries = 4
        self._timeout = timeout
        self._client, self._cache_manager = build_cached_http_client(
            use_cache=True,
            cache_name=self.CACHE_NAME,
            cache_dir=cache_dir,
            headers=headers,
            auth=auth or OpsAuth(api_key, api_secret),
            timeout=timeout,
            base_url=BASE_URL,
            policy=hishel.SpecificationPolicy(),
            http2=False,
        )

    def _build_url(self, path: str) -> str:
        """Build a full URL, passing through absolute URLs unchanged."""
        if path.startswith("http"):
            return path
        return f"{self.base_url}{path}"

    def _raise_for_status(self, response: httpx.Response, context: str = "") -> None:
        """Check for 403 (EPO rate limiting) before standard error handling."""
        if response.status_code == 403:
            raise self._build_forbidden_error(response)
        super()._raise_for_status(response, context)

    @staticmethod
    def _build_forbidden_error(response: httpx.Response) -> OpsForbiddenError:
        headers = {k: v for k, v in response.headers.items()}
        details = []
        reason = headers.get("X-Rejection-Reason")
        throttling = headers.get("X-Throttling-Control")
        hourly = headers.get("X-IndividualQuotaPerHour-Used")
        weekly = headers.get("X-RegisteredQuotaPerWeek-Used")
        paid = headers.get("X-RegisteredPayingQuotaPerWeek-Used")
        if reason:
            details.append(f"reason={reason}")
        if throttling:
            details.append(f"throttling={throttling}")
        if hourly:
            details.append(f"hourly_used={hourly}")
        if weekly:
            details.append(f"weekly_used={weekly}")
        if paid:
            details.append(f"paid_used={paid}")
        base = "EPO OPS returned 403"
        if details:
            base = f"{base} ({'; '.join(details)})"
        else:
            base = f"{base} – likely rate limited or quota exceeded."
        return OpsForbiddenError(base, headers=headers)

    @staticmethod
    def _normalize_number(number: str) -> str:
        return number.strip().replace(" ", "").upper()

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        return symbol.strip().replace(" ", "").upper()

    async def search_published(
        self,
        *,
        query: str,
        range_begin: int = 1,
        range_end: int = 25,
    ) -> SearchResponse:
        params = {"q": query, "Range": f"{range_begin}-{range_end}"}
        response = await self._request("GET", "/rest-services/published-data/search", params=params)
        return parse_search_response(response.text)

    async def search_families(
        self,
        *,
        query: str,
        range_begin: int = 1,
        range_end: int = 100,
    ) -> FamilySearchResponse:
        search = await self.search_published(
            query=query, range_begin=range_begin, range_end=range_end
        )
        families: dict[str, FamilySearchEntry] = {}
        for result in search.results:
            family_id = result.family_id or "unknown"
            entry = families.setdefault(
                family_id, FamilySearchEntry(family_id=family_id, members=[])
            )
            entry.members.append(result)
        return FamilySearchResponse(
            query=search.query,
            total_results=search.total_results,
            range_begin=search.range_begin,
            range_end=search.range_end,
            families=list(families.values()),
        )

    async def fetch_biblio(
        self,
        *,
        number: str,
        doc_type: str = "publication",
        fmt: str = "docdb",
    ) -> BiblioResponse:
        normalized = self._normalize_number(number)
        path = f"/rest-services/published-data/{doc_type}/{fmt}/{normalized}/biblio"
        response = await self._request("GET", path)
        return parse_biblio_response(response.text)

    async def fetch_citations(
        self,
        *,
        number: str,
        doc_type: str = "publication",
        fmt: str = "docdb",
    ) -> CitationResponse:
        """Fetch structured backward citations from an OPS biblio record."""
        normalized = self._normalize_number(number)
        path = f"/rest-services/published-data/{doc_type}/{fmt}/{normalized}/biblio"
        response = await self._request("GET", path)
        return parse_citations(response.text, publication_number=normalized)

    async def fetch_equivalents(
        self,
        *,
        number: str,
        doc_type: str = "publication",
        fmt: str = "docdb",
    ) -> EquivalentsResponse:
        """Fetch simple-family equivalent publications."""
        normalized = self._normalize_number(number)
        path = f"/rest-services/published-data/{doc_type}/{fmt}/{normalized}/equivalents"
        response = await self._request("GET", path)
        return parse_equivalents(response.text)

    async def fetch_fulltext(
        self,
        *,
        number: str,
        section: str = "claims",
        doc_type: str = "publication",
        fmt: str = "docdb",
    ) -> FullTextResponse:
        if section not in {"claims", "description"}:
            raise ValueError("section must be either 'claims' or 'description'")
        normalized = self._normalize_number(number)
        path = f"/rest-services/published-data/{doc_type}/{fmt}/{normalized}/{section}"
        response = await self._request("GET", path)
        return parse_claims(response.text, section=section)

    async def fetch_family(
        self,
        *,
        number: str,
        doc_type: str = "publication",
        fmt: str = "docdb",
        constituents: str | None = None,
    ) -> FamilyResponse:
        normalized = self._normalize_number(number)
        path = f"/rest-services/family/{doc_type}/{fmt}/{normalized}"
        if constituents:
            path = f"{path}/{constituents}"
        response = await self._request("GET", path)
        return parse_family(response.text)

    async def fetch_legal_events(
        self,
        *,
        number: str,
        doc_type: str = "publication",
        fmt: str = "docdb",
    ) -> LegalEventsResponse:
        normalized = self._normalize_number(number)
        path = f"/rest-services/legal/{doc_type}/{fmt}/{normalized}"
        response = await self._request("GET", path)
        return parse_legal_events(response.text)

    async def fetch_register(
        self,
        *,
        number: str,
        doc_type: str = "publication",
        fmt: str = "epodoc",
        sub: str = "biblio",
    ) -> str:
        """Fetch raw XML from the EPO Register service.

        ``sub`` is one of ``biblio``, ``events``, ``procedural-steps``,
        or ``upp``. ``upp`` (Unitary Patent Package) returns the biblio
        plus a ``<reg:unitary-patent>`` block when the EP has been
        elected for unitary effect — use :meth:`get_unitary_patent_package`
        for a structured-out view.
        """
        valid = {"biblio", "events", "procedural-steps", "upp"}
        if sub not in valid:
            raise ValueError(f"sub must be one of {sorted(valid)}; got {sub!r}")
        normalized = self._normalize_number(number)
        path = f"/rest-services/register/{doc_type}/{fmt}/{normalized}/{sub}"
        response = await self._request("GET", path)
        return response.text

    async def get_unitary_patent_package(
        self,
        epo_number: str,
        *,
        doc_type: str = "publication",
        fmt: str = "epodoc",
    ) -> UnitaryPatentPackage | None:
        """Return the Unitary Patent Package for an EP patent, if any.

        Calls the register's ``/upp`` sub-endpoint and parses out the
        ``<reg:unitary-patent>`` block. Returns ``None`` when the EP
        was never elected for unitary effect or the registration hasn't
        been recorded yet.

        Note: this answers "is patent X a Unitary Patent and when?".
        UPC opt-out status is **not** exposed by the OPS Register;
        it requires the UPC CMS Public API (separate enrollment).
        """
        xml = await self.fetch_register(number=epo_number, doc_type=doc_type, fmt=fmt, sub="upp")
        return parse_unitary_patent_package(xml, epo_number=epo_number)

    async def fetch_register_events(
        self,
        *,
        number: str,
        doc_type: str = "publication",
        fmt: str = "epodoc",
    ) -> RegisterEventsResponse:
        """Fetch structured dossier events from the European Patent Register."""
        normalized = self._normalize_number(number)
        xml = await self.fetch_register(
            number=normalized,
            doc_type=doc_type,
            fmt=fmt,
            sub="events",
        )
        return parse_register_events(xml, epo_number=normalized)

    async def fetch_register_biblio(
        self,
        *,
        number: str,
        doc_type: str = "publication",
        fmt: str = "epodoc",
    ) -> RegisterBiblioResponse:
        """Fetch correction-aware bibliographic data from the EP Register.

        Register designation data reflects application designations. Term-of-grant
        lapse snapshots cover the opposition period and are not current national
        validation or lapse status.
        """
        normalized = self._normalize_number(number)
        xml = await self.fetch_register(
            number=normalized,
            doc_type=doc_type,
            fmt=fmt,
            sub="biblio",
        )
        return parse_register_biblio(xml, epo_number=normalized)

    async def fetch_register_procedural_steps(
        self,
        *,
        number: str,
        doc_type: str = "publication",
        fmt: str = "epodoc",
    ) -> RegisterProceduralStepsResponse:
        """Fetch structured procedural steps from the European Patent Register."""
        normalized = self._normalize_number(number)
        xml = await self.fetch_register(
            number=normalized,
            doc_type=doc_type,
            fmt=fmt,
            sub="procedural-steps",
        )
        return parse_register_procedural_steps(xml, epo_number=normalized)

    async def convert_number(
        self,
        *,
        number: str,
        doc_type: str = "publication",
        input_format: str = "original",
        output_format: str = "docdb",
    ) -> NumberConversionResponse:
        normalized = number.strip()
        path = (
            f"/rest-services/number-service/{doc_type}/{input_format}/{normalized}/{output_format}"
        )
        response = await self._request("GET", path)
        return parse_number_conversion(response.text)

    async def retrieve_cpc(
        self,
        *,
        symbol: str,
        depth: int | str | None = None,
        ancestors: bool = False,
        navigation: bool = False,
    ) -> CpcRetrievalResponse:
        normalized = self._normalize_symbol(symbol)
        params: dict[str, Any] = {}
        if depth is not None:
            params["depth"] = depth
        if ancestors:
            params["ancestors"] = "true"
        if navigation:
            params["navigation"] = "true"
        path = f"/rest-services/classification/cpc/{normalized}"
        response = await self._request("GET", path, params=params)
        return parse_cpc_retrieval(response.text)

    async def search_cpc(
        self,
        *,
        query: str,
        range_begin: int = 1,
        range_end: int = 10,
    ) -> CpcSearchResponse:
        params = {"q": query}
        headers = {"X-OPS-Range": f"{range_begin}-{range_end}"}
        path = "/rest-services/classification/cpc/search"
        response = await self._request("GET", path, params=params, headers=headers)
        return parse_cpc_search(response.text)

    async def map_classification(
        self,
        *,
        input_schema: str,
        symbol: str,
        output_schema: str,
        additional: bool = False,
    ) -> ClassificationMappingResponse:
        normalized_symbol = self._normalize_symbol(symbol)
        params = {"additional": "true"} if additional else None
        path = (
            "/rest-services/classification/map/"
            f"{input_schema.lower()}/{normalized_symbol}/{output_schema.lower()}"
        )
        response = await self._request("GET", path, params=params)
        if not response.text or not response.text.strip().startswith("<"):
            return ClassificationMappingResponse(mappings=[])
        return parse_classification_mapping(response.text)

    async def fetch_cpc_media(self, *, media_id: str, accept: str) -> CpcMediaResponse:
        headers = {"Accept": accept}
        normalized_id = media_id.replace("classification/cpc/media/", "").lstrip("/")
        path = f"/rest-services/classification/cpc/media/{normalized_id}"
        response = await self._request("GET", path, headers=headers)
        mime_type = response.headers.get("Content-Type", accept)
        data_base64 = base64.b64encode(response.content).decode("ascii")
        return CpcMediaResponse(
            media_id=normalized_id, mime_type=mime_type, data_base64=data_base64
        )

    async def fetch_cpci_biblio(
        self,
        *,
        number: str,
        doc_type: str = "publication",
        fmt: str = "docdb",
        condensed: bool = False,
    ) -> CpciBiblioResponse:
        normalized = self._normalize_number(number)
        params = {"cpci": "condensed"} if condensed else None
        path = f"/rest-services/published-data/{doc_type}/{fmt}/{normalized}/biblio"
        response = await self._request("GET", path, params=params)
        return parse_cpci_biblio(response.text)

    async def download_pdf(
        self,
        *,
        number: str,
        doc_type: str = "publication",
        fmt: str = "docdb",
    ) -> PdfDownloadResponse:
        normalized = self._normalize_number(number)
        path = f"/rest-services/published-data/{doc_type}/{fmt}/{normalized}/images"
        response = await self._request("GET", path)
        root = etree.fromstring(response.content)
        full_document = root.xpath('.//ops:document-instance[@desc="FullDocument"]', namespaces=NS)
        if not full_document:
            raise RuntimeError("FullDocument images are not available for this publication.")
        doc_node = full_document[0]
        link = doc_node.get("link")
        num_pages_str = doc_node.get("number-of-pages")
        if not link or not num_pages_str or not num_pages_str.isdigit():
            raise RuntimeError("Incomplete image metadata returned by OPS.")
        num_pages = int(num_pages_str)
        pdf_writer = PdfWriter()
        for page in range(1, num_pages + 1):
            page_url = self._build_url(f"/rest-services/{link}.pdf")
            page_response = await self._client.request(
                "GET",
                page_url,
                params={"Range": page},
                extensions={"force_cache": True},
            )
            self._raise_for_status(page_response)
            reader = PdfReader(BytesIO(page_response.content))
            page_obj = reader.pages[0]
            rotation = page_obj.get("/Rotate")
            if rotation == 90:
                page_obj.rotate(-90)
            pdf_writer.add_page(page_obj)
        buffer = BytesIO()
        pdf_writer.write(buffer)
        pdf_bytes = buffer.getvalue()
        return PdfDownloadResponse(
            publication_number=normalized,
            num_pages=num_pages,
            pdf_base64=base64.b64encode(pdf_bytes).decode("ascii"),
        )


_shared_auth: OpsAuth | None = None


def _get_shared_auth(key: str, secret: str) -> OpsAuth:
    global _shared_auth
    if _shared_auth is None or _shared_auth.key != key or _shared_auth.secret != secret:
        _shared_auth = OpsAuth(key, secret)
    return _shared_auth


def client_from_env() -> EpoOpsClient:
    """Instantiate an EpoOpsClient using the standard environment variables."""

    key = os.getenv("EPO_OPS_API_KEY") or os.getenv("EPO_API_KEY")
    secret = os.getenv("EPO_OPS_API_SECRET") or os.getenv("EPO_API_SECRET")
    if not key or not secret:
        raise RuntimeError(
            "Set EPO_OPS_API_KEY/EPO_OPS_API_SECRET (or legacy EPO_API_KEY/EPO_API_SECRET)."
        )
    return EpoOpsClient(api_key=key, api_secret=secret, auth=_get_shared_auth(key, secret))
