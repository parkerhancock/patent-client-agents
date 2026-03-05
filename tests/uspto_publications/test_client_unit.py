"""Unit tests for PublicSearchClient using httpx.MockTransport."""

from __future__ import annotations

import httpx
import pytest

from ip_tools.core.exceptions import ServerError
from ip_tools.uspto_publications.client import (
    PublicSearchClient,
    PublicSearchError,
)
from ip_tools.uspto_publications.models import (
    DocumentStructure,
    PublicSearchDocument,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Minimal session response matching what _refresh_session expects
_SESSION_RESPONSE = {
    "userCase": {"caseId": 42},
}

# Minimal search response that convert_biblio_page can handle
_SEARCH_RESPONSE = {
    "numFound": 1,
    "perPage": 25,
    "page": 0,
    "patents": [
        {
            "guid": "GUID-1",
            "publicationReferenceDocumentNumber": "US11111111B2",
            "datePublished": "2024-01-01",
            "inventionTitle": "Test Patent",
            "type": "USPAT",
            "databaseName": "USPAT",
            "applicantName": [],
            "assigneeName": [],
            "uspcFullClassification": [],
            "ipcCode": [],
            "cpcAdditional": [],
            "relatedApplFilingDate": [],
        }
    ],
}

_SEARCH_RESPONSE_EMPTY = {
    "numFound": 0,
    "perPage": 25,
    "page": 0,
    "patents": [],
}

_SEARCH_RESPONSE_ERROR = {
    "error": {
        "errorCode": "1234",
        "errorMessage": "Something went wrong",
    }
}

# Minimal document response for get_document
_DOCUMENT_RESPONSE = {
    "guid": "GUID-1",
    "publicationReferenceDocumentNumber": "US11111111B2",
    "datePublished": "2024-01-01",
    "inventionTitle": "Test Patent",
    "databaseName": "USPAT",
    "type": "USPAT",
}


def _build_transport(routes: dict[str, tuple[int, dict | str | list]]):
    """Build a mock transport that routes based on URL path.

    routes maps URL substrings to (status_code, body) pairs.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for pattern, (status, body) in routes.items():
            if pattern in url:
                if isinstance(body, (dict, list)):
                    return httpx.Response(
                        status,
                        json=body,
                        headers={"content-type": "application/json"},
                    )
                return httpx.Response(status, text=body)
        return httpx.Response(200, text="ok")

    return httpx.MockTransport(handler)


def _session_transport(
    search_response=None,
    document_response=None,
    extra_routes=None,
):
    """Build a transport that handles session + API endpoints."""
    routes = {
        "/pubwebapp/": (200, "ok"),
        "/api/users/me/session": (200, _SESSION_RESPONSE),
        "/api/searches/counts": (200, {"count": 1}),
        "/api/searches/searchWithBeFamily": (200, search_response or _SEARCH_RESPONSE),
        "/api/patents/highlight/": (200, document_response or _DOCUMENT_RESPONSE),
    }
    if extra_routes:
        routes.update(extra_routes)
    return _build_transport(routes)


# ---------------------------------------------------------------------------
# PublicSearchError (line 51)
# ---------------------------------------------------------------------------


class TestPublicSearchError:
    def test_inherits_from_api_error(self):
        err = PublicSearchError("test", status_code=400, response_body="body")
        assert err.status_code == 400
        assert err.response_body == "body"

    def test_str_contains_message(self):
        err = PublicSearchError("bad request")
        assert "bad request" in str(err)


# ---------------------------------------------------------------------------
# Session management (lines 84-107)
# ---------------------------------------------------------------------------


class TestSessionManagement:
    async def test_ensure_session_initializes_case_id(self):
        transport = _session_transport()
        http = httpx.AsyncClient(transport=transport)
        client = PublicSearchClient(client=http)
        assert client._case_id is None
        await client._ensure_session()
        assert client._case_id == 42

    async def test_ensure_session_skips_if_already_set(self):
        """Line 85-86 + line 88-89: double-check locking."""
        transport = _session_transport()
        http = httpx.AsyncClient(transport=transport)
        client = PublicSearchClient(client=http)
        client._case_id = 99  # Already set
        await client._ensure_session()
        assert client._case_id == 99  # Unchanged

    async def test_ensure_session_double_check_lock(self):
        """Line 88-89: second check inside the lock."""
        transport = _session_transport()
        http = httpx.AsyncClient(transport=transport)
        client = PublicSearchClient(client=http)

        # Simulate race: set case_id after lock acquired but before refresh
        async def mock_refresh():
            # Simulate another coroutine having set it
            client._case_id = 77

        client._refresh_session = mock_refresh
        client._case_id = None

        # First call: _case_id is None, enters lock, but mock sets it
        await client._ensure_session()
        assert client._case_id == 77

    async def test_refresh_session_sets_access_token(self):
        """Line 104-106: access token header."""

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/pubwebapp/" in url:
                return httpx.Response(200, text="ok")
            if "/api/users/me/session" in url:
                return httpx.Response(
                    200,
                    json=_SESSION_RESPONSE,
                    headers={
                        "content-type": "application/json",
                        "X-Access-Token": "tok123",
                    },
                )
            return httpx.Response(200, text="ok")

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = PublicSearchClient(client=http)
        await client._refresh_session()
        assert client._access_token == "tok123"
        assert client._client.headers.get("X-Access-Token") == "tok123"


# ---------------------------------------------------------------------------
# _request retry/403/429 (lines 109-119)
# ---------------------------------------------------------------------------


class TestRequestRetry:
    async def test_403_triggers_session_refresh(self):
        """Lines 112-114: 403 refreshes session and retries."""
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/pubwebapp/" in url:
                return httpx.Response(200, text="ok")
            if "/api/users/me/session" in url:
                return httpx.Response(
                    200,
                    json=_SESSION_RESPONSE,
                    headers={"content-type": "application/json"},
                )
            if "/test-endpoint" in url:
                call_count["n"] += 1
                if call_count["n"] == 1:
                    return httpx.Response(403, text="forbidden")
                return httpx.Response(200, text="success")
            return httpx.Response(200, text="ok")

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = PublicSearchClient(client=http)
        resp = await client._request("GET", "https://ppubs.uspto.gov/test-endpoint")
        assert resp.status_code == 200
        assert resp.text == "success"

    async def test_429_waits_and_retries(self):
        """Lines 115-118: 429 reads header and retries."""
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/test-endpoint" in url:
                call_count["n"] += 1
                if call_count["n"] == 1:
                    return httpx.Response(
                        429,
                        text="rate limited",
                        headers={"x-rate-limit-retry-after-seconds": "0"},
                    )
                return httpx.Response(200, text="ok")
            return httpx.Response(200, text="ok")

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = PublicSearchClient(client=http)
        resp = await client._request("GET", "https://ppubs.uspto.gov/test-endpoint")
        assert resp.status_code == 200
        assert call_count["n"] == 2


# ---------------------------------------------------------------------------
# search_biblio error path (line 189-192)
# ---------------------------------------------------------------------------


class TestSearchBiblioError:
    async def test_search_returns_error_payload(self):
        """Line 189-192: error in search response raises PublicSearchError."""
        transport = _session_transport(search_response=_SEARCH_RESPONSE_ERROR)
        http = httpx.AsyncClient(transport=transport)
        client = PublicSearchClient(client=http)
        with pytest.raises(PublicSearchError, match="1234"):
            await client.search_biblio(query="test query")


# ---------------------------------------------------------------------------
# get_document (lines 196-204)
# ---------------------------------------------------------------------------


class TestGetDocument:
    async def test_get_document_returns_model(self):
        transport = _session_transport()
        http = httpx.AsyncClient(transport=transport)
        client = PublicSearchClient(client=http)
        doc = await client.get_document("GUID-1", source="USPAT")
        assert doc.guid == "GUID-1"


# ---------------------------------------------------------------------------
# _request_save (lines 206-229)
# ---------------------------------------------------------------------------


class TestRequestSave:
    async def test_request_save_success(self):
        """Lines 207-229: successful save request."""
        transport = _session_transport(
            extra_routes={
                "/api/print/imageviewer": (200, '"job-123"'),
            }
        )
        http = httpx.AsyncClient(transport=transport)
        client = PublicSearchClient(client=http)
        client._case_id = 42

        doc = PublicSearchDocument(
            guid="GUID-1",
            type="USPAT",
            image_location="/images/path",
            document_structure=DocumentStructure(page_count=3),
        )
        job_id = await client._request_save(doc)
        assert job_id == "job-123"

    async def test_request_save_missing_page_count(self):
        """Line 207-208: raises ValueError for missing page count."""
        http = httpx.AsyncClient(transport=_session_transport())
        client = PublicSearchClient(client=http)
        client._case_id = 42

        doc = PublicSearchDocument(guid="GUID-1", type="USPAT")
        with pytest.raises(ValueError, match="page count"):
            await client._request_save(doc)

    async def test_request_save_missing_image_location(self):
        """Lines 209-210: raises ValueError for missing image location."""
        http = httpx.AsyncClient(transport=_session_transport())
        client = PublicSearchClient(client=http)
        client._case_id = 42

        doc = PublicSearchDocument(
            guid="GUID-1",
            type="USPAT",
            document_structure=DocumentStructure(page_count=3),
            image_location=None,
        )
        with pytest.raises(ValueError, match="image location"):
            await client._request_save(doc)

    async def test_request_save_500_raises(self):
        """Lines 226-227: 500 from print endpoint raises PublicSearchError."""
        transport = _session_transport(
            extra_routes={
                "/api/print/imageviewer": (500, "Internal Server Error"),
            }
        )
        http = httpx.AsyncClient(transport=transport)
        client = PublicSearchClient(client=http)
        client._case_id = 42

        doc = PublicSearchDocument(
            guid="GUID-1",
            type="USPAT",
            image_location="/images/path",
            document_structure=DocumentStructure(page_count=1),
        )
        with pytest.raises(PublicSearchError):
            await client._request_save(doc)


# ---------------------------------------------------------------------------
# _poll_print_job (lines 231-254)
# ---------------------------------------------------------------------------


class TestPollPrintJob:
    async def test_poll_completes_on_first_attempt(self):
        """Lines 231-250: immediate completion."""
        transport = _session_transport(
            extra_routes={
                "/api/print/print-process": (
                    200,
                    [{"printStatus": "COMPLETED", "pdfName": "result.pdf"}],
                ),
            }
        )
        http = httpx.AsyncClient(transport=transport)
        client = PublicSearchClient(client=http)
        pdf_name = await client._poll_print_job("job-123")
        assert pdf_name == "result.pdf"

    async def test_poll_completes_after_retry(self):
        """Poll returns PENDING then COMPLETED."""
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/api/print/print-process" in url:
                call_count["n"] += 1
                if call_count["n"] < 2:
                    return httpx.Response(
                        200,
                        json=[{"printStatus": "PENDING"}],
                        headers={"content-type": "application/json"},
                    )
                return httpx.Response(
                    200,
                    json=[{"printStatus": "COMPLETED", "pdfName": "done.pdf"}],
                    headers={"content-type": "application/json"},
                )
            return httpx.Response(200, text="ok")

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = PublicSearchClient(client=http)
        # Speed up polling for test
        client._POLL_INTERVAL = 0.01
        client._POLL_MAX_ATTEMPTS = 5
        pdf_name = await client._poll_print_job("job-456")
        assert pdf_name == "done.pdf"

    async def test_poll_timeout_raises_server_error(self):
        """Lines 252-254: exhaustion raises ServerError."""
        transport = _session_transport(
            extra_routes={
                "/api/print/print-process": (
                    200,
                    [{"printStatus": "PENDING"}],
                ),
            }
        )
        http = httpx.AsyncClient(transport=transport)
        client = PublicSearchClient(client=http)
        client._POLL_INTERVAL = 0.01
        client._POLL_MAX_ATTEMPTS = 2

        with pytest.raises(ServerError, match="did not complete"):
            await client._poll_print_job("job-never")


# ---------------------------------------------------------------------------
# _download_pdf_bytes (lines 256-269)
# ---------------------------------------------------------------------------


class TestDownloadPdfBytes:
    async def test_download_pdf_bytes_success(self):
        """Lines 256-269: download PDF bytes via streaming."""
        pdf_content = b"%PDF-1.4 fake content"

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/api/print/save/" in url:
                return httpx.Response(200, content=pdf_content)
            return httpx.Response(200, text="ok")

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = PublicSearchClient(client=http)
        result = await client._download_pdf_bytes("result.pdf")
        assert result == pdf_content

    async def test_download_pdf_bytes_raises_on_error(self):
        """Lines 263: raise_for_status in streaming download."""

        def handler(request: httpx.Request) -> httpx.Response:
            if "/api/print/save/" in str(request.url):
                return httpx.Response(404, text="not found")
            return httpx.Response(200, text="ok")

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = PublicSearchClient(client=http)
        with pytest.raises(httpx.HTTPStatusError):
            await client._download_pdf_bytes("missing.pdf")


# ---------------------------------------------------------------------------
# download_pdf + download_pdf_base64 (lines 271-280)
# ---------------------------------------------------------------------------


class TestDownloadPdf:
    async def test_download_pdf_orchestrates_save_poll_download(self):
        """Lines 271-276: full pipeline."""
        pdf_content = b"%PDF fake"
        call_order = []

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/pubwebapp/" in url:
                return httpx.Response(200, text="ok")
            if "/api/users/me/session" in url:
                return httpx.Response(
                    200,
                    json=_SESSION_RESPONSE,
                    headers={"content-type": "application/json"},
                )
            if "/api/print/imageviewer" in url:
                call_order.append("save")
                return httpx.Response(200, text='"job-1"')
            if "/api/print/print-process" in url:
                call_order.append("poll")
                return httpx.Response(
                    200,
                    json=[{"printStatus": "COMPLETED", "pdfName": "out.pdf"}],
                    headers={"content-type": "application/json"},
                )
            if "/api/print/save/" in url:
                call_order.append("download")
                return httpx.Response(200, content=pdf_content)
            return httpx.Response(200, text="ok")

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = PublicSearchClient(client=http)
        client._POLL_INTERVAL = 0.01

        doc = PublicSearchDocument(
            guid="GUID-1",
            type="USPAT",
            image_location="/images/path",
            document_structure=DocumentStructure(page_count=1),
        )
        result = await client.download_pdf(doc)
        assert result == pdf_content
        assert call_order == ["save", "poll", "download"]

    async def test_download_pdf_base64(self):
        """Lines 278-280: base64 encoding."""
        pdf_content = b"%PDF fake"

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/pubwebapp/" in url:
                return httpx.Response(200, text="ok")
            if "/api/users/me/session" in url:
                return httpx.Response(
                    200,
                    json=_SESSION_RESPONSE,
                    headers={"content-type": "application/json"},
                )
            if "/api/print/imageviewer" in url:
                return httpx.Response(200, text='"job-1"')
            if "/api/print/print-process" in url:
                return httpx.Response(
                    200,
                    json=[{"printStatus": "COMPLETED", "pdfName": "out.pdf"}],
                    headers={"content-type": "application/json"},
                )
            if "/api/print/save/" in url:
                return httpx.Response(200, content=pdf_content)
            return httpx.Response(200, text="ok")

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = PublicSearchClient(client=http)
        client._POLL_INTERVAL = 0.01

        doc = PublicSearchDocument(
            guid="GUID-1",
            type="USPAT",
            image_location="/images/path",
            document_structure=DocumentStructure(page_count=1),
        )
        import base64

        result = await client.download_pdf_base64(doc)
        assert base64.b64decode(result) == pdf_content


# ---------------------------------------------------------------------------
# resolve_document_by_publication_number (lines 282-321)
# ---------------------------------------------------------------------------


class TestResolveDocumentByPublicationNumber:
    async def test_resolve_exact_match(self):
        """Lines 306-313: exact match found in search results."""
        search_resp = {
            "numFound": 1,
            "perPage": 25,
            "page": 0,
            "patents": [
                {
                    "guid": "GUID-EXACT",
                    "publicationReferenceDocumentNumber": "US11111111B2",
                    "datePublished": "2024-01-01",
                    "inventionTitle": "Exact Match",
                    "type": "USPAT",
                    "databaseName": "USPAT",
                    "applicantName": [],
                    "assigneeName": [],
                    "uspcFullClassification": [],
                    "ipcCode": [],
                    "cpcAdditional": [],
                    "relatedApplFilingDate": [],
                },
            ],
        }
        doc_resp = {
            "guid": "GUID-EXACT",
            "publicationReferenceDocumentNumber": "US11111111B2",
            "datePublished": "2024-01-01",
            "inventionTitle": "Exact Match",
            "databaseName": "USPAT",
            "type": "USPAT",
        }
        transport = _session_transport(
            search_response=search_resp,
            document_response=doc_resp,
        )
        http = httpx.AsyncClient(transport=transport)
        client = PublicSearchClient(client=http)
        doc = await client.resolve_document_by_publication_number("US11111111B2")
        assert doc.guid == "GUID-EXACT"

    async def test_resolve_fallback_match(self):
        """Lines 315-317: no exact match, falls back to first doc with guid."""
        search_resp = {
            "numFound": 1,
            "perPage": 25,
            "page": 0,
            "patents": [
                {
                    "guid": "GUID-FALLBACK",
                    "publicationReferenceDocumentNumber": "US99999999B1",
                    "datePublished": "2024-01-01",
                    "inventionTitle": "Fallback Match",
                    "type": "USPAT",
                    "databaseName": "USPAT",
                    "applicantName": [],
                    "assigneeName": [],
                    "uspcFullClassification": [],
                    "ipcCode": [],
                    "cpcAdditional": [],
                    "relatedApplFilingDate": [],
                },
            ],
        }
        doc_resp = {
            "guid": "GUID-FALLBACK",
            "publicationReferenceDocumentNumber": "US99999999B1",
            "datePublished": "2024-01-01",
            "inventionTitle": "Fallback Match",
            "databaseName": "USPAT",
            "type": "USPAT",
        }
        transport = _session_transport(
            search_response=search_resp,
            document_response=doc_resp,
        )
        http = httpx.AsyncClient(transport=transport)
        client = PublicSearchClient(client=http)
        doc = await client.resolve_document_by_publication_number("US11111111B2")
        assert doc.guid == "GUID-FALLBACK"

    async def test_resolve_no_documents_found(self):
        """Lines 297-298: empty search results."""
        transport = _session_transport(search_response=_SEARCH_RESPONSE_EMPTY)
        http = httpx.AsyncClient(transport=transport)
        client = PublicSearchClient(client=http)
        with pytest.raises(ValueError, match="No documents found"):
            await client.resolve_document_by_publication_number("US11111111B2")

    async def test_resolve_no_guid_or_source_skips(self):
        """Lines 309-310: docs without guid/type are skipped."""
        search_resp = {
            "numFound": 1,
            "perPage": 25,
            "page": 0,
            "patents": [
                {
                    "guid": None,
                    "publicationReferenceDocumentNumber": "US11111111B2",
                    "datePublished": "2024-01-01",
                    "inventionTitle": "No GUID",
                    "type": None,
                    "databaseName": None,
                    "applicantName": [],
                    "assigneeName": [],
                    "uspcFullClassification": [],
                    "ipcCode": [],
                    "cpcAdditional": [],
                    "relatedApplFilingDate": [],
                },
            ],
        }
        transport = _session_transport(search_response=search_resp)
        http = httpx.AsyncClient(transport=transport)
        client = PublicSearchClient(client=http)
        with pytest.raises(ValueError, match="Unable to resolve"):
            await client.resolve_document_by_publication_number("US11111111B2")

    async def test_resolve_sets_publication_number_if_missing(self):
        """Lines 302-303: sets publication_number on fetched doc if missing."""
        search_resp = {
            "numFound": 1,
            "perPage": 25,
            "page": 0,
            "patents": [
                {
                    "guid": "GUID-1",
                    "publicationReferenceDocumentNumber": "US11111111B2",
                    "datePublished": "2024-01-01",
                    "inventionTitle": "Test",
                    "type": "USPAT",
                    "databaseName": "USPAT",
                    "applicantName": [],
                    "assigneeName": [],
                    "uspcFullClassification": [],
                    "ipcCode": [],
                    "cpcAdditional": [],
                    "relatedApplFilingDate": [],
                },
            ],
        }
        # Document response without publication_number
        doc_resp = {
            "guid": "GUID-1",
            "inventionTitle": "Test",
            "databaseName": "USPAT",
            "type": "USPAT",
        }
        transport = _session_transport(
            search_response=search_resp,
            document_response=doc_resp,
        )
        http = httpx.AsyncClient(transport=transport)
        client = PublicSearchClient(client=http)
        doc = await client.resolve_document_by_publication_number("US11111111B2")
        assert doc.publication_number == "US11111111B2"

    async def test_resolve_empty_string_raises(self):
        """Lines 287-288: empty publication number raises ValueError."""
        http = httpx.AsyncClient(transport=_session_transport())
        client = PublicSearchClient(client=http)
        with pytest.raises(ValueError, match="must include alphanumeric"):
            await client.resolve_document_by_publication_number("---")


# ---------------------------------------------------------------------------
# Context manager (lines 74-82)
# ---------------------------------------------------------------------------


class TestContextManager:
    async def test_aenter_returns_self(self):
        transport = _session_transport()
        http = httpx.AsyncClient(transport=transport)
        client = PublicSearchClient(client=http)
        async with client as ctx:
            assert ctx is client

    async def test_close_owned_client(self):
        """Line 80-82: closes client if owned."""
        transport = _session_transport()
        http = httpx.AsyncClient(transport=transport)
        client = PublicSearchClient(client=http)
        # Not owned since we passed in client
        assert client._owns_client is False
        await client.close()
        assert not http.is_closed

    async def test_close_owned_client_true(self):
        """close() closes client when _owns_client is True."""
        client = PublicSearchClient()
        assert client._owns_client is True
        await client.close()
        assert client._client.is_closed
