"""Tests for the CPC API module.

The CPC helpers run through a real ``EpoOpsClient`` whose network layer is an
``httpx.MockTransport``: the OPS OAuth token exchange, headers, URL building,
cache and XML parsing all run as in production.
"""

from __future__ import annotations

import base64
import functools
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from patent_client_agents.cpc import api as cpc_api
from patent_client_agents.epo_ops import client as epo_client
from patent_client_agents.epo_ops.client import BASE_URL, EpoOpsClient

CPC_NS = 'xmlns:ops="http://ops.epo.org" xmlns:cpc="http://www.epo.org/cpcexport"'

RETRIEVAL_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data {CPC_NS}>
  <cpc:class-scheme scheme-type="cpc" export-date="2024-01-01">
    <cpc:classification-item level="7" sort-key="A01B1/00" not-allocatable="false">
      <cpc:classification-symbol>A01B1/00</cpc:classification-symbol>
      <cpc:class-title>
        <cpc:title-part><cpc:text>Hand tools</cpc:text></cpc:title-part>
      </cpc:class-title>
      <cpc:classification-item level="8">
        <cpc:classification-symbol>A01B1/02</cpc:classification-symbol>
        <cpc:class-title>
          <cpc:title-part><cpc:text>Spades; Shovels</cpc:text></cpc:title-part>
        </cpc:class-title>
      </cpc:classification-item>
    </cpc:classification-item>
  </cpc:class-scheme>
</ops:world-patent-data>"""

SEARCH_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data {CPC_NS}>
  <ops:classification-search total-result-count="57">
    <ops:query>battery</ops:query>
    <ops:search-result>
      <ops:range begin="1" end="5"/>
      <ops:classification-statistics classification-symbol="H01M" percentage="42.5">
        <cpc:class-title>
          <cpc:title-part><cpc:text>Batteries</cpc:text></cpc:title-part>
        </cpc:class-title>
      </ops:classification-statistics>
    </ops:search-result>
  </ops:classification-search>
</ops:world-patent-data>"""

MAPPING_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data xmlns:ops="http://ops.epo.org">
  <ops:mappings inputSchema="CPC" outputSchema="IPC">
    <ops:mapping additional-only="false">
      <ops:cpc>A01B1/00</ops:cpc>
      <ops:ecla>A01B1/00</ops:ecla>
      <ops:ipc>A01B1/00</ops:ipc>
    </ops:mapping>
  </ops:mappings>
</ops:world-patent-data>"""

CPCI_BIBLIO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns="http://www.epo.org/exchange">
  <exchange-documents>
    <exchange-document country="EP" doc-number="1000000" kind="A1">
      <bibliographic-data>
        <publication-reference>
          <document-id document-id-type="docdb">
            <country>EP</country><doc-number>1000000</doc-number><kind>A1</kind>
          </document-id>
        </publication-reference>
        <patent-classifications>
          <patent-classification sequence="1">
            <section>A</section><class>01</class><subclass>B</subclass>
            <main-group>1</main-group><subgroup>00</subgroup>
            <classification-value>I</classification-value>
            <generating-office>EP, US</generating-office>
          </patent-classification>
        </patent-classifications>
      </bibliographic-data>
    </exchange-document>
  </exchange-documents>
</ops:world-patent-data>"""

GIF_BYTES = b"GIF89a\x01\x00\x01\x00fake"


class FakeOps:
    """OPS stand-in: issues an OAuth token and serves one canned data reply."""

    def __init__(self, reply: httpx.Response) -> None:
        self.reply = reply
        self.token_requests: list[httpx.Request] = []
        self.data_requests: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/3.2/auth/accesstoken":
            self.token_requests.append(request)
            return httpx.Response(
                200,
                json={
                    "issued_at": str(int(time.time() * 1000)),
                    "expires_in": "1199",
                    "access_token": "ops-token",
                },
            )
        self.data_requests.append(request)
        if request.headers.get("Authorization") != "Bearer ops-token":
            return httpx.Response(401, text="<fault>invalid_access_token</fault>")
        return self.reply

    @property
    def request(self) -> httpx.Request:
        (only,) = self.data_requests
        return only


Call = Callable[..., Awaitable[Any]]


@pytest.fixture(params=["env", "client_kwarg"])
def run(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Callable[[FakeOps, Call], Awaitable[Any]]:
    """Run a CPC helper both ways a caller can: env-configured, or with client=."""
    via = request.param

    async def _run(ops: FakeOps, call: Call) -> Any:
        transport = httpx.MockTransport(ops.handle)
        if via == "env":
            monkeypatch.setenv("EPO_OPS_API_KEY", "key")
            monkeypatch.setenv("EPO_OPS_API_SECRET", "secret")
            monkeypatch.setattr(epo_client, "_shared_auth", None)
            opened: list[EpoOpsClient] = []

            def build(**kwargs: Any) -> EpoOpsClient:
                opened.append(EpoOpsClient(**kwargs, transport=transport, cache_path=tmp_path))
                return opened[-1]

            monkeypatch.setattr(epo_client, "EpoOpsClient", build)
            result = await call()
            (one_shot_client,) = opened
            assert one_shot_client._client.is_closed
            return result
        async with EpoOpsClient(
            api_key="key", api_secret="secret", transport=transport, cache_path=tmp_path
        ) as client:
            with pytest.warns(DeprecationWarning, match="client= is deprecated") as caught:
                result = await call(client=client)
            assert [w.filename for w in caught] == [__file__]
            assert not client._client.is_closed
            return result

    return _run


def _assert_authenticated(ops: FakeOps) -> None:
    (token_request,) = ops.token_requests
    assert token_request.method == "POST"
    assert token_request.headers["Authorization"] == base64.b64encode(b"key:secret").decode()
    assert token_request.content == b"grant_type=client_credentials"
    assert ops.request.headers["Authorization"] == "Bearer ops-token"


@pytest.mark.asyncio
async def test_retrieve_cpc(run: Callable[[FakeOps, Call], Awaitable[Any]]) -> None:
    ops = FakeOps(httpx.Response(200, text=RETRIEVAL_XML))

    result = await run(
        ops,
        functools.partial(cpc_api.retrieve_cpc, " a01b 1/00", depth=1, ancestors=True),
    )

    assert str(ops.request.url) == (
        f"{BASE_URL}/rest-services/classification/cpc/A01B1/00?depth=1&ancestors=true"
    )
    assert ops.request.headers["Accept"] == "application/xml"
    _assert_authenticated(ops)
    assert result.scheme.scheme_type == "cpc"
    (item,) = result.scheme.items
    assert (item.symbol, item.level, item.title) == ("A01B1/00", 7, "Hand tools")
    assert item.not_allocatable is False
    assert [(c.symbol, c.title) for c in item.children] == [("A01B1/02", "Spades; Shovels")]


@pytest.mark.asyncio
async def test_search_cpc(run: Callable[[FakeOps, Call], Awaitable[Any]]) -> None:
    ops = FakeOps(httpx.Response(200, text=SEARCH_XML))

    result = await run(ops, functools.partial(cpc_api.search_cpc, "battery", range_end=5))

    assert str(ops.request.url) == f"{BASE_URL}/rest-services/classification/cpc/search?q=battery"
    assert ops.request.headers["X-OPS-Range"] == "1-5"
    _assert_authenticated(ops)
    assert (result.query, result.total_results) == ("battery", 57)
    assert (result.range_begin, result.range_end) == (1, 5)
    (hit,) = result.results
    assert (hit.classification_symbol, hit.percentage, hit.title) == ("H01M", 42.5, "Batteries")


@pytest.mark.asyncio
async def test_map_classification(run: Callable[[FakeOps, Call], Awaitable[Any]]) -> None:
    ops = FakeOps(httpx.Response(200, text=MAPPING_XML))

    result = await run(
        ops,
        functools.partial(
            cpc_api.map_classification,
            input_schema="CPC",
            symbol="a01b1/00",
            output_schema="IPC",
            additional=True,
        ),
    )

    assert str(ops.request.url) == (
        f"{BASE_URL}/rest-services/classification/map/cpc/A01B1/00/ipc?additional=true"
    )
    _assert_authenticated(ops)
    assert (result.input_schema, result.output_schema) == ("CPC", "IPC")
    (mapping,) = result.mappings
    assert (mapping.cpc, mapping.ipc, mapping.additional_only) == ("A01B1/00", "A01B1/00", False)


@pytest.mark.asyncio
async def test_fetch_media(run: Callable[[FakeOps, Call], Awaitable[Any]]) -> None:
    ops = FakeOps(httpx.Response(200, content=GIF_BYTES, headers={"Content-Type": "image/gif"}))

    result = await run(
        ops, functools.partial(cpc_api.fetch_media, "classification/cpc/media/media123")
    )

    assert str(ops.request.url) == f"{BASE_URL}/rest-services/classification/cpc/media/media123"
    assert ops.request.headers["Accept"] == "image/gif"
    _assert_authenticated(ops)
    assert (result.media_id, result.mime_type) == ("media123", "image/gif")
    assert base64.b64decode(result.data_base64) == GIF_BYTES


@pytest.mark.asyncio
async def test_fetch_biblio_cpci(run: Callable[[FakeOps, Call], Awaitable[Any]]) -> None:
    ops = FakeOps(httpx.Response(200, text=CPCI_BIBLIO_XML))

    result = await run(
        ops, functools.partial(cpc_api.fetch_biblio_cpci, "ep 1000000", condensed=True)
    )

    assert str(ops.request.url) == (
        f"{BASE_URL}/rest-services/published-data/publication/docdb/EP1000000/biblio?cpci=condensed"
    )
    _assert_authenticated(ops)
    (record,) = result.records
    assert record.docdb_number == "EP1000000A1"
    (cls,) = record.classifications
    assert (cls.section, cls.class_code, cls.subclass, cls.main_group, cls.subgroup) == (
        "A",
        "01",
        "B",
        "1",
        "00",
    )
    assert cls.generating_offices == ["EP", "US"]


class TestGetClient:
    """Tests for get_client function."""

    def test_requires_both_credentials(self) -> None:
        with pytest.raises(ValueError, match="Both api_key and api_secret are required"):
            cpc_api.get_client(api_key="test_key")

    def test_requires_both_credentials_secret_only(self) -> None:
        with pytest.raises(ValueError, match="Both api_key and api_secret are required"):
            cpc_api.get_client(api_secret="test_secret")

    @pytest.mark.asyncio
    async def test_explicit_credentials_authenticate_requests(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        ops = FakeOps(httpx.Response(200, text=SEARCH_XML))
        monkeypatch.setattr(
            cpc_api,
            "EpoOpsClient",
            functools.partial(
                EpoOpsClient, transport=httpx.MockTransport(ops.handle), cache_path=tmp_path
            ),
        )
        client = cpc_api.get_client(api_key="explicit-key", api_secret="explicit-secret")

        with pytest.warns(DeprecationWarning, match="Passing client= is deprecated"):
            result = await cpc_api.search_cpc("battery", client=client)

        (token_request,) = ops.token_requests
        assert token_request.headers["Authorization"] == (
            base64.b64encode(b"explicit-key:explicit-secret").decode()
        )
        assert ops.request.headers["Authorization"] == "Bearer ops-token"
        assert result.total_results == 57
        await client.close()
