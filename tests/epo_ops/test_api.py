"""Tests for the EPO OPS module-level API.

The one-shot helpers run through a real ``EpoOpsClient`` built by
``client_from_env`` whose network layer is an ``httpx2.MockTransport``: the OPS
OAuth token exchange, URL building and XML parsing all run as in production.
"""

from __future__ import annotations

import base64
import functools
import time
from collections.abc import Awaitable, Callable
from io import BytesIO
from pathlib import Path
from typing import Any, cast

import httpx2
import pytest
from pypdf import PdfReader, PdfWriter

from mcp_data_core.exceptions import NotFoundError
from patent_client_agents.epo_ops import api as ops_api
from patent_client_agents.epo_ops import client as epo_client
from patent_client_agents.epo_ops.client import BASE_URL, EpoOpsClient
from patent_client_agents.epo_ops.models import (
    BiblioResponse,
    CitationResponse,
    EquivalentsResponse,
    FamilyResponse,
    FullTextResponse,
    LegalEventsResponse,
    RegisterBiblioResponse,
    RegisterEventsResponse,
    RegisterProceduralStepsResponse,
)

OPS_NS = 'xmlns:ops="http://ops.epo.org" xmlns="http://www.epo.org/exchange"'
EMPTY_XML = f"<ops:world-patent-data {OPS_NS}/>"

SEARCH_XML = f"""<ops:world-patent-data {OPS_NS}>
  <ops:biblio-search total-result-count="1">
    <ops:query>ti=solar</ops:query>
    <ops:range begin="5" end="10"/>
    <ops:search-result>
      <ops:publication-reference family-id="42">
        <document-id document-id-type="docdb">
          <country>EP</country><doc-number>1000000</doc-number><kind>A1</kind>
        </document-id>
      </ops:publication-reference>
    </ops:search-result>
  </ops:biblio-search>
</ops:world-patent-data>"""

BIBLIO_XML = f"""<ops:world-patent-data {OPS_NS}>
  <exchange-documents>
    <exchange-document country="EP" doc-number="1000000" kind="A1">
      <bibliographic-data>
        <publication-reference>
          <document-id document-id-type="docdb">
            <country>EP</country><doc-number>1000000</doc-number><kind>A1</kind>
          </document-id>
        </publication-reference>
      </bibliographic-data>
    </exchange-document>
  </exchange-documents>
</ops:world-patent-data>"""

NUMBER_XML = f"""<ops:world-patent-data {OPS_NS}>
  <ops:standardization>
    <ops:input><ops:publication-reference>
      <document-id document-id-type="original"><doc-number>US20050262543</doc-number></document-id>
    </ops:publication-reference></ops:input>
    <ops:output><ops:publication-reference>
      <document-id document-id-type="epodoc"><doc-number>US2005262543</doc-number></document-id>
    </ops:publication-reference></ops:output>
  </ops:standardization>
</ops:world-patent-data>"""

IMAGES_XML = f"""<ops:world-patent-data {OPS_NS}>
  <ops:document-inquiry>
    <ops:inquiry-result>
      <ops:document-instance desc="FullDocument" number-of-pages="2"
          link="published-data/images/EP/1000000/A1/fullimage"/>
    </ops:inquiry-result>
  </ops:document-inquiry>
</ops:world-patent-data>"""

REGISTER_XML = "<reg:register-documents xmlns:reg='http://www.epo.org/register'/>"


class FakeOps:
    """OPS stand-in: issues an OAuth token and answers data requests with ``reply``."""

    def __init__(self, reply: Callable[[httpx2.Request], httpx2.Response]) -> None:
        self.reply = reply
        self.token_requests: list[httpx2.Request] = []
        self.data_requests: list[httpx2.Request] = []

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/3.2/auth/accesstoken":
            self.token_requests.append(request)
            return httpx2.Response(
                200,
                json={
                    "issued_at": str(int(time.time() * 1000)),
                    "expires_in": "1199",
                    "access_token": "ops-token",
                },
            )
        self.data_requests.append(request)
        if request.headers.get("Authorization") != "Bearer ops-token":
            return httpx2.Response(401, text="<fault>invalid_access_token</fault>")
        return self.reply(request)

    @property
    def request(self) -> httpx2.Request:
        (only,) = self.data_requests
        return only


def _xml(body: str) -> Callable[[httpx2.Request], httpx2.Response]:
    return lambda _request: httpx2.Response(200, text=body)


class Harness:
    """Routes every ``EpoOpsClient`` built from env through a ``FakeOps``."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self.ops = FakeOps(_xml(EMPTY_XML))
        self.opened: list[EpoOpsClient] = []
        self.closes = 0
        harness = self

        class TrackedClient(EpoOpsClient):
            def __init__(self, **kwargs: Any) -> None:
                super().__init__(
                    **kwargs,
                    transport=httpx2.MockTransport(harness.ops.handle),
                    cache_path=tmp_path,
                )
                harness.opened.append(self)

            async def close(self) -> None:
                harness.closes += 1
                await super().close()

        self.client_class = TrackedClient
        monkeypatch.setenv("EPO_OPS_API_KEY", "key")
        monkeypatch.setenv("EPO_OPS_API_SECRET", "secret")
        monkeypatch.setattr(epo_client, "_shared_auth", None)
        monkeypatch.setattr(epo_client, "EpoOpsClient", TrackedClient)

    def assert_one_shot(self) -> None:
        """Exactly one client was opened, authenticated with the env key, and closed."""
        assert len(self.opened) == 1
        assert self.closes == 1
        assert self.opened[0]._client.is_closed
        (token_request,) = self.ops.token_requests
        assert token_request.headers["Authorization"] == base64.b64encode(b"key:secret").decode()


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Harness:
    return Harness(monkeypatch, tmp_path)


Call = Callable[[], Awaitable[Any]]
PUB = f"{BASE_URL}/rest-services/published-data/publication"
REG = f"{BASE_URL}/rest-services/register/publication/epodoc/EP1000000"


@pytest.mark.parametrize(
    ("call", "url", "params", "reply", "check"),
    [
        pytest.param(
            functools.partial(ops_api.search_published, "ti=solar", 5, 10),
            f"{BASE_URL}/rest-services/published-data/search",
            {"q": "ti=solar", "Range": "5-10"},
            SEARCH_XML,
            lambda r: (
                (r.total_results, r.range_begin, r.range_end) == (1, 5, 10)
                and [x.docdb_number for x in r.results] == ["EP1000000A1"]
            ),
            id="search_published",
        ),
        pytest.param(
            functools.partial(ops_api.search_families, "ti=solar", range_end=50),
            f"{BASE_URL}/rest-services/published-data/search",
            {"q": "ti=solar", "Range": "1-50"},
            SEARCH_XML,
            lambda r: [(f.family_id, len(f.members)) for f in r.families] == [("42", 1)],
            id="search_families",
        ),
        pytest.param(
            functools.partial(ops_api.fetch_biblio, "ep 1000000 a1", fmt="epodoc"),
            f"{PUB}/epodoc/EP1000000A1/biblio",
            {},
            BIBLIO_XML,
            lambda r: (
                isinstance(r, BiblioResponse)
                and [d.docdb_number for d in r.documents] == ["EP1000000A1"]
            ),
            id="fetch_biblio",
        ),
        pytest.param(
            functools.partial(ops_api.fetch_citations, "EP1000000A1"),
            f"{PUB}/docdb/EP1000000A1/biblio",
            {},
            EMPTY_XML,
            lambda r: isinstance(r, CitationResponse) and r.publication_number == "EP1000000A1",
            id="fetch_citations",
        ),
        pytest.param(
            functools.partial(ops_api.fetch_equivalents, "EP1000000A1", "application"),
            f"{BASE_URL}/rest-services/published-data/application/docdb/EP1000000A1/equivalents",
            {},
            EMPTY_XML,
            lambda r: isinstance(r, EquivalentsResponse),
            id="fetch_equivalents",
        ),
        pytest.param(
            functools.partial(ops_api.fetch_family, "EP1000000A1", constituents="biblio"),
            f"{BASE_URL}/rest-services/family/publication/docdb/EP1000000A1/biblio",
            {},
            EMPTY_XML,
            lambda r: isinstance(r, FamilyResponse),
            id="fetch_family",
        ),
        pytest.param(
            functools.partial(ops_api.fetch_family_details, "EP1000000A1", "application"),
            f"{BASE_URL}/rest-services/family/application/docdb/EP1000000A1",
            {},
            EMPTY_XML,
            lambda r: isinstance(r, FamilyResponse),
            id="fetch_family_details",
        ),
        pytest.param(
            functools.partial(ops_api.fetch_legal_events, "EP1000000A1"),
            f"{BASE_URL}/rest-services/legal/publication/docdb/EP1000000A1",
            {},
            EMPTY_XML,
            lambda r: isinstance(r, LegalEventsResponse),
            id="fetch_legal_events",
        ),
        pytest.param(
            functools.partial(ops_api.fetch_register, "EP1000000", sub="events"),
            f"{REG}/events",
            {},
            REGISTER_XML,
            lambda r: r == REGISTER_XML,
            id="fetch_register",
        ),
        pytest.param(
            functools.partial(ops_api.fetch_register_events, "ep1000000"),
            f"{REG}/events",
            {},
            REGISTER_XML,
            lambda r: isinstance(r, RegisterEventsResponse) and r.epo_number == "EP1000000",
            id="fetch_register_events",
        ),
        pytest.param(
            functools.partial(ops_api.fetch_register_biblio, "EP1000000"),
            f"{REG}/biblio",
            {},
            REGISTER_XML,
            lambda r: isinstance(r, RegisterBiblioResponse) and r.epo_number == "EP1000000",
            id="fetch_register_biblio",
        ),
        pytest.param(
            functools.partial(ops_api.fetch_register_procedural_steps, "EP1000000"),
            f"{REG}/procedural-steps",
            {},
            REGISTER_XML,
            lambda r: (
                isinstance(r, RegisterProceduralStepsResponse) and r.epo_number == "EP1000000"
            ),
            id="fetch_register_procedural_steps",
        ),
        pytest.param(
            functools.partial(ops_api.get_unitary_patent_package, "EP1000000"),
            f"{REG}/upp",
            {},
            REGISTER_XML,
            lambda r: r is None,
            id="get_unitary_patent_package",
        ),
        pytest.param(
            functools.partial(ops_api.convert_number, "US20050262543", output_format="epodoc"),
            f"{BASE_URL}/rest-services/number-service/publication/original/US20050262543/epodoc",
            {},
            NUMBER_XML,
            lambda r: (
                (r.input_document.doc_number, r.output_document.doc_number)
                == ("US20050262543", "US2005262543")
            ),
            id="convert_number",
        ),
        pytest.param(
            functools.partial(
                ops_api.number_service, "US20050262543", "application", "docdb", "epodoc"
            ),
            f"{BASE_URL}/rest-services/number-service/application/docdb/US20050262543/epodoc",
            {},
            NUMBER_XML,
            lambda r: r.output_document.doc_number == "US2005262543",
            id="number_service",
        ),
    ],
)
@pytest.mark.asyncio
async def test_one_shot_reaches_ops(
    harness: Harness,
    call: Call,
    url: str,
    params: dict[str, str],
    reply: str,
    check: Callable[[Any], bool],
) -> None:
    harness.ops.reply = _xml(reply)

    result = await call()

    request = harness.ops.request
    assert request.method == "GET"
    assert str(request.url.copy_with(query=None)) == url
    assert dict(request.url.params) == params
    assert request.headers["Authorization"] == "Bearer ops-token"
    assert check(result)
    harness.assert_one_shot()


def _blank_pdf_page() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_download_pdf_stitches_pages(harness: Harness) -> None:
    page = _blank_pdf_page()

    def reply(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/images"):
            return httpx2.Response(200, text=IMAGES_XML)
        return httpx2.Response(200, content=page, headers={"Content-Type": "application/pdf"})

    harness.ops.reply = reply

    result = await ops_api.download_pdf("ep 1000000 a1")

    inquiry, *pages = harness.ops.data_requests
    assert str(inquiry.url) == f"{PUB}/docdb/EP1000000A1/images"
    image_url = f"{BASE_URL}/rest-services/published-data/images/EP/1000000/A1/fullimage.pdf"
    assert [str(p.url) for p in pages] == [f"{image_url}?Range=1", f"{image_url}?Range=2"]
    assert (result.publication_number, result.num_pages) == ("EP1000000A1", 2)
    assert len(PdfReader(BytesIO(base64.b64decode(result.pdf_base64))).pages) == 2
    harness.assert_one_shot()


@pytest.mark.asyncio
async def test_client_kwarg_is_deprecated_and_left_open(harness: Harness) -> None:
    harness.ops.reply = _xml(BIBLIO_XML)
    client = harness.client_class(api_key="other", api_secret="pair")

    with pytest.warns(DeprecationWarning, match="Passing client= is deprecated") as caught:
        result = await ops_api.fetch_biblio("EP1000000A1", client=client)

    assert [w.filename for w in caught] == [__file__]
    assert [d.docdb_number for d in result.documents] == ["EP1000000A1"]
    assert str(harness.ops.request.url) == f"{PUB}/docdb/EP1000000A1/biblio"
    (token_request,) = harness.ops.token_requests
    assert token_request.headers["Authorization"] == base64.b64encode(b"other:pair").decode()
    assert harness.closes == 0
    assert not client._client.is_closed
    await client.close()


@pytest.mark.asyncio
async def test_fetch_fulltext_translates_404_to_friendly_value_error() -> None:
    # EPO returns 404 for publications without indexed full text
    # (especially older or non-EP/non-WO documents). The library-level
    # NotFoundError carries an internal log-path hint via ApiError.__str__
    # which is unhelpful for that domain failure — surface a clean
    # ValueError that a tool / agent can show to the user verbatim.
    class DummyClient:
        async def fetch_fulltext(self, **kwargs: object) -> FullTextResponse:
            raise NotFoundError("HTTP 404", 404, "")

    with pytest.raises(ValueError, match="EPO has no claims full text"):
        await ops_api.fetch_fulltext("EP1000000", section="claims", client=cast(Any, DummyClient()))
