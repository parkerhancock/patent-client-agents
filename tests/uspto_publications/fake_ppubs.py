"""In-process fake of USPTO Patent Public Search (PPUBS) for transport tests."""

from __future__ import annotations

import itertools
import json
from collections.abc import Awaitable, Callable

import httpx

BASE = "https://ppubs.uspto.gov"
SESSION = "/api/users/me/session"
COUNTS = "/api/searches/counts"
SEARCH = "/api/searches/searchWithBeFamily"
HIGHLIGHT = "/api/patents/highlight"
PRINT_REQUEST = "/api/print/imageviewer"
PRINT_STATUS = "/api/print/print-process"
PRINT_SAVE = "/api/print/save"
PDF_BYTES = b"%PDF-1.4 fake ppubs pdf"

SEARCH_PAGE = {
    "numFound": 1,
    "perPage": 20,
    "page": 0,
    "patents": [
        {
            "guid": "US-20230123456-A1",
            "publicationReferenceDocumentNumber": "20230123456",
            "type": "US-PGPUB",
            "inventionTitle": "Neural widget",
        }
    ],
}

DOCUMENT = {
    "guid": "US-20230123456-A1",
    "pubRefDocNumber": "20230123456",
    "inventionTitle": "Neural widget",
    "type": "US-PGPUB",
    "pageCount": 2,
    "imageLocation": "pgpub/2023/0123/456",
}

Reply = httpx.Response | Exception | Callable[[httpx.Request], Awaitable[httpx.Response]]


class FakePpubs:
    """In-process PPUBS: issues sessions and enforces them on API calls.

    A session is a ``caseId`` plus an ``X-Access-Token``. API calls must carry
    the current token, and any ``caseId`` in the JSON body (top level or under
    ``query``) must match the current session, otherwise the fake answers 403
    like PPUBS does for an expired browser session.
    """

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self._case_ids = itertools.chain((123, 456, 789), itertools.count(1000))
        self.case_id: int | None = None
        self.token: str | None = None
        self._queued: dict[str, list[Reply]] = {}

    def queue(self, path: str, *replies: Reply) -> None:
        """Answer the next requests to ``path`` with ``replies``, in order."""
        self._queued.setdefault(path, []).extend(replies)

    def always(self, path: str, reply: httpx.Response) -> None:
        self.queue(path, *[reply] * 50)

    def expire_session(self) -> None:
        self.case_id = None
        self.token = None

    def hits(self, path: str) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.path == path]

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    async def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        queued = self._queued.get(path)
        if queued:
            reply = queued.pop(0)
            if isinstance(reply, Exception):
                raise reply
            if isinstance(reply, httpx.Response):
                return reply
            return await reply(request)
        if path == "/pubwebapp/":
            return httpx.Response(200, text="<html></html>")
        if path == SESSION:
            self.case_id = next(self._case_ids)
            self.token = f"token-{self.case_id}"
            return httpx.Response(
                200,
                json={"userCase": {"caseId": self.case_id}},
                headers={"X-Access-Token": self.token},
            )
        if not self.session_ok(request):
            return httpx.Response(403, text="session expired")
        return self.default_api_reply(request)

    def session_ok(self, request: httpx.Request) -> bool:
        if self.token is None or request.headers.get("X-Access-Token") != self.token:
            return False
        return case_id_of(request) in (None, self.case_id)

    def default_api_reply(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == COUNTS:
            return httpx.Response(200, json={"numResults": 1})
        if path == SEARCH:
            return httpx.Response(200, json=SEARCH_PAGE)
        if path == f"{HIGHLIGHT}/{DOCUMENT['guid']}":
            return httpx.Response(200, json=DOCUMENT)
        if path == PRINT_REQUEST:
            return httpx.Response(200, text='"job-1"')
        if path == PRINT_STATUS:
            return httpx.Response(200, json=[{"printStatus": "COMPLETED", "pdfName": "doc.pdf"}])
        if path == f"{PRINT_SAVE}/doc.pdf":
            return httpx.Response(200, content=PDF_BYTES)
        return httpx.Response(404)


def case_id_of(request: httpx.Request) -> int | None:
    if not request.content:
        return None
    body = json.loads(request.content)
    if not isinstance(body, dict):
        return None
    if "caseId" in body:
        return body["caseId"]
    query = body.get("query")
    return query.get("caseId") if isinstance(query, dict) else None
