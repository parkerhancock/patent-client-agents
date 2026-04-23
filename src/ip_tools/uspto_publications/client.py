from __future__ import annotations

import asyncio
import base64
import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from law_tools_core.exceptions import ApiError

from .models import PublicSearchBiblioPage, PublicSearchDocument
from .transformers import convert_biblio_page, convert_document_payload
from .utils import normalize_publication_number

logger = logging.getLogger(__name__)

_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    ),
    "Origin": "https://ppubs.uspto.gov",
    "Referer": "https://ppubs.uspto.gov/pubwebapp/",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "Priority": "u=1, i",
}

_BASE_URL = "https://ppubs.uspto.gov"
_DATA_PATH = Path(__file__).resolve().parent / "data" / "search_query.json"


class PublicSearchError(ApiError):
    """Raised when USPTO Public Search returns an error payload.

    Inherits from ApiError for unified exception handling.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message, status_code, response_body)


class PublicSearchClient:
    """Async client for USPTO Patent Public Search (PPUBS).

    Can be used as a context manager for proper resource cleanup::

        async with PublicSearchClient() as client:
            results = await client.search_biblio(query="machine learning")
            doc = await client.get_document(guid, source="US-PGPUB")
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            headers=_HEADERS.copy(), http2=True, follow_redirects=True
        )
        self._owns_client = client is None
        self._session_lock = asyncio.Lock()
        self._case_id: int | None = None
        self._access_token: str | None = None
        self._search_template = json.loads(_DATA_PATH.read_text())

    async def __aenter__(self) -> PublicSearchClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _ensure_session(self) -> None:
        if self._case_id is not None:
            return
        async with self._session_lock:
            if self._case_id is not None:
                return
            await self._refresh_session()

    async def _refresh_session(self) -> None:
        self._client.cookies = httpx.Cookies()
        await self._client.get(f"{_BASE_URL}/pubwebapp/")
        response = await self._client.post(
            f"{_BASE_URL}/api/users/me/session",
            json=-1,
            headers={"referer": f"{_BASE_URL}/pubwebapp/"},
        )
        response.raise_for_status()
        session = response.json()
        self._case_id = session["userCase"]["caseId"]
        self._access_token = response.headers.get("X-Access-Token")
        if self._access_token:
            self._client.headers["X-Access-Token"] = self._access_token

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        response = await self._client.request(method, url, **kwargs)
        if response.status_code == 403:
            await self._refresh_session()
            response = await self._client.request(method, url, **kwargs)
        if response.status_code == 429:
            wait_time = int(response.headers.get("x-rate-limit-retry-after-seconds", "1")) + 1
            await asyncio.sleep(wait_time)
            response = await self._client.request(method, url, **kwargs)
        return response

    def _build_search_payload(
        self,
        query: str,
        *,
        start: int,
        limit: int,
        sort: str,
        default_operator: str,
        sources: list[str],
        expand_plurals: bool,
        british_equivalents: bool,
    ) -> dict[str, Any]:
        data = deepcopy(self._search_template)
        data["start"] = start
        data["pageCount"] = limit
        data["sort"] = sort
        data["query"]["caseId"] = self._case_id
        data["query"]["op"] = default_operator
        data["query"]["q"] = query
        data["query"]["queryName"] = query
        data["query"]["userEnteredQuery"] = query
        data["query"]["databaseFilters"] = [
            {"databaseName": name, "countryCodes": []} for name in sources
        ]
        data["query"]["plurals"] = expand_plurals
        data["query"]["britishEquivalents"] = british_equivalents
        return data

    async def search_biblio(
        self,
        *,
        query: str,
        start: int = 0,
        limit: int = 500,
        sort: str = "date_publ desc",
        default_operator: str = "OR",
        sources: list[str] | None = None,
        expand_plurals: bool = True,
        british_equivalents: bool = True,
    ) -> PublicSearchBiblioPage:
        if not query:
            raise ValueError("query must be provided")
        await self._ensure_session()
        payload = self._build_search_payload(
            query,
            start=start,
            limit=min(limit, 500),
            sort=sort,
            default_operator=default_operator,
            sources=sources or ["US-PGPUB", "USPAT", "USOCR"],
            expand_plurals=expand_plurals,
            british_equivalents=british_equivalents,
        )
        counts = await self._request(
            "POST", f"{_BASE_URL}/api/searches/counts", json=payload["query"]
        )
        counts.raise_for_status()
        response = await self._request(
            "POST",
            f"{_BASE_URL}/api/searches/searchWithBeFamily",
            json=payload,
        )
        response.raise_for_status()
        result = response.json()
        if result.get("error"):
            raise PublicSearchError(
                f"Error #{result['error'].get('errorCode')}: {result['error'].get('errorMessage')}"
            )
        converted = convert_biblio_page(result)
        return PublicSearchBiblioPage.model_validate(converted)

    async def get_document(self, guid: str, *, source: str) -> PublicSearchDocument:
        await self._ensure_session()
        url = f"{_BASE_URL}/api/patents/highlight/{guid}"
        params = {"queryId": 1, "source": source, "includeSections": True, "uniqueId": None}
        response = await self._request("GET", url, params=params)
        response.raise_for_status()
        converted = convert_document_payload(response.json())
        return PublicSearchDocument.model_validate(converted)

    async def _request_save(self, document: PublicSearchDocument) -> str:
        if not document.document_structure or not document.document_structure.page_count:
            raise ValueError("document must include page count information")
        if not document.image_location:
            raise ValueError("document missing image location")
        page_keys = [
            f"{document.image_location}/{i:0>8}.tif"
            for i in range(1, document.document_structure.page_count + 1)
        ]
        response = await self._request(
            "POST",
            f"{_BASE_URL}/api/print/imageviewer",
            json={
                "caseId": self._case_id,
                "pageKeys": page_keys,
                "patentGuid": document.guid,
                "saveOrPrint": "save",
                "source": document.type,
            },
        )
        if response.status_code == 500:
            raise PublicSearchError(response.text)
        response.raise_for_status()
        return response.text.strip().strip('"')

    _POLL_TIMEOUT_SECONDS = 300  # 5 min — long docs take ~30s; 5 min is 10x typical
    _POLL_INTERVAL_SECONDS = 1

    async def _poll_print_job(self, job_id: str) -> str:
        """Poll the PPUBS print-job endpoint until the PDF is ready.

        Bounded by ``_POLL_TIMEOUT_SECONDS`` — a stuck job raises
        ``PublicSearchError`` instead of hanging forever.
        """
        async def _loop() -> str:
            while True:
                response = await self._request(
                    "POST",
                    f"{_BASE_URL}/api/print/print-process",
                    json=[job_id],
                )
                response.raise_for_status()
                data = response.json()
                status = data[0].get("printStatus")
                if status == "COMPLETED":
                    return data[0]["pdfName"]
                await asyncio.sleep(self._POLL_INTERVAL_SECONDS)

        try:
            return await asyncio.wait_for(_loop(), timeout=self._POLL_TIMEOUT_SECONDS)
        except TimeoutError as exc:
            raise PublicSearchError(
                f"PPUBS print job {job_id} did not complete within "
                f"{self._POLL_TIMEOUT_SECONDS}s. USPTO's print service may be "
                f"degraded — retry later."
            ) from exc

    async def _download_pdf_bytes(self, pdf_name: str) -> bytes:
        request = self._client.build_request(
            "GET",
            f"{_BASE_URL}/api/print/save/{pdf_name}",
        )
        response = await self._client.send(request, stream=True)
        try:
            response.raise_for_status()
            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
            return bytes(chunks)
        finally:
            await response.aclose()

    async def download_pdf(self, document: PublicSearchDocument) -> bytes:
        await self._ensure_session()
        job_id = await self._request_save(document)
        pdf_name = await self._poll_print_job(job_id)
        return await self._download_pdf_bytes(pdf_name)

    async def download_pdf_base64(self, document: PublicSearchDocument) -> str:
        pdf_bytes = await self.download_pdf(document)
        return base64.b64encode(pdf_bytes).decode("ascii")

    async def resolve_document_by_publication_number(
        self,
        publication_number: str,
    ) -> PublicSearchDocument:
        normalized = normalize_publication_number(publication_number)
        if not normalized:
            raise ValueError("publication_number must include alphanumeric characters")

        query = f"{normalized}.pn."
        page = await self.search_biblio(
            query=query,
            start=0,
            limit=25,
            sources=["US-PGPUB", "USPAT", "USOCR"],
        )
        if not page.docs:
            raise ValueError(f"No documents found for publication number {publication_number!r}")

        async def _fetch(doc_guid: str, doc_source: str) -> PublicSearchDocument:
            document = await self.get_document(doc_guid, source=doc_source)
            if not document.publication_number:
                document.publication_number = publication_number
            return document

        for doc in page.docs:
            guid_value = doc.guid
            source_value = doc.type
            if not guid_value or not source_value:
                continue
            doc_number = normalize_publication_number(doc.publication_number or "")
            if doc_number == normalized:
                return await _fetch(guid_value, source_value)

        fallback = next((doc for doc in page.docs if doc.guid and doc.type), None)
        if fallback and fallback.guid and fallback.type:
            return await _fetch(fallback.guid, fallback.type)

        raise ValueError(
            f"Unable to resolve GUID/source for publication number {publication_number!r}"
        )
