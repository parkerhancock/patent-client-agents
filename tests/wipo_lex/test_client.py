"""Unit tests for ``patent_client_agents.wipo_lex``.

Uses ``httpx2.MockTransport`` plus minimal HTML fixtures rather than VCR
cassettes because:

1. WIPO Lex pages are large (~100 KB each) and would bloat the repo.
2. The connector's contract is "parse the stable surfaces (OpenGraph meta,
   ``/details/{id}`` anchor pattern, file-link CSS class)". Pinning that
   contract to inline fixtures is more explicit than recording snapshots.

When WIPO restyles the page, update the fixtures in this file and the
``transformers.py`` selectors together.
"""

from __future__ import annotations

import httpx2
import pytest

from patent_client_agents.wipo_lex import (
    GetLegislationInput,
    SearchLegislationInput,
    SubjectMatter,
    TypeOfText,
    WipoLexClient,
)

SEARCH_RESULTS_HTML = """\
<html><body>
  <main>
    <div class="results">
      <div class="result-row">
        <a href="/wipolex/en/legislation/members/profile/CA?activeCollection=laws">CA</a>
      </div>
      <article class="result-card">
        <a href="/wipolex/en/legislation/details/23293">
          Patent Act, (R.S.C., 1985, c. P-4, amended January 1, 2025)
        </a>
      </article>
      <article class="result-card">
        <a href="/wipolex/en/legislation/details/23437">
          Patent Rules, (SOR/2019-251, amended up to January 1, 2025)
        </a>
      </article>
      <article class="result-card">
        <a href="/wipolex/en/legislation/details/23298">
          Patented Medicines (Notice of Compliance) Regulations, (SOR/93-133)
        </a>
      </article>
      <!-- Duplicate anchor (mobile + desktop blocks render the same row twice) -->
      <article class="result-card-mobile">
        <a href="/wipolex/en/legislation/details/23293">Patent Act (duplicate)</a>
      </article>
    </div>
  </main>
</body></html>
"""

DETAIL_HTML = """\
<html><head>
  <meta property="og:title" content="Patent Act, Canada, WIPO Lex" />
  <meta property="og:url" content="https://www.wipo.int/wipolex/en/legislation/details/23293" />
  <meta name="description" content="Canada - Year of Version: 2025 - Assented: January 1, 1985 - Main IP Laws - Patents (Inventions)" />
</head><body>
  <div class="law_title">Patent Act</div>
  <a class="allfileLinks" href="/wipolex/edocs/lexdocs/laws/en/ca/ca065en.pdf">English PDF</a>
  <a class="allfileLinks" href="/wipolex/edocs/lexdocs/laws/fr/ca/ca065fr.pdf">French PDF</a>
  <a class="allfileLinks" href="/wipolex/edocs/lexdocs/laws/en/ca/ca065en.docx">Word</a>
</body></html>
"""


def _mock_client(handler) -> WipoLexClient:
    transport_client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return WipoLexClient(client=transport_client)


class TestSearchLegislation:
    @pytest.mark.asyncio
    async def test_search_parses_unique_hits(self) -> None:
        captured: list[httpx2.Request] = []

        def handler(request: httpx2.Request) -> httpx2.Response:
            captured.append(request)
            return httpx2.Response(200, text=SEARCH_RESULTS_HTML)

        async with _mock_client(handler) as client:
            result = await client.search_legislation(
                country_codes=["CA"],
                subject_matter=[SubjectMatter.PATENTS],
                type_of_text=[TypeOfText.MAIN_IP_LAWS],
                keywords="patent",
            )

        # Three distinct hits — the mobile duplicate of 23293 is dedup'd.
        ids = [hit.legislation_id for hit in result.hits]
        assert ids == ["23293", "23437", "23298"]
        assert result.hits[0].title.startswith("Patent Act")
        assert result.hits[0].url.endswith("/wipolex/en/legislation/details/23293")
        # Query parameters flowed through correctly.
        req = captured[0]
        params = req.url.params
        assert params["countryOrgs"] == "CA"
        assert params["subjectMatter"] == "1"
        assert params["typeOfText"] == "205"
        assert params["keywords"] == "patent"
        assert params["last"] == "false"

    @pytest.mark.asyncio
    async def test_include_historical_flag(self) -> None:
        captured: list[httpx2.Request] = []

        def handler(request: httpx2.Request) -> httpx2.Response:
            captured.append(request)
            return httpx2.Response(200, text=SEARCH_RESULTS_HTML)

        async with _mock_client(handler) as client:
            await client.search_legislation(country_codes=["CA"], include_historical=True)

        assert captured[0].url.params["last"] == "true"

    @pytest.mark.asyncio
    async def test_multiple_country_codes_repeat_param(self) -> None:
        captured: list[httpx2.Request] = []

        def handler(request: httpx2.Request) -> httpx2.Response:
            captured.append(request)
            return httpx2.Response(200, text=SEARCH_RESULTS_HTML)

        async with _mock_client(handler) as client:
            await client.search_legislation(country_codes=["CA", "US"])

        # WIPO Lex expects repeated keys, not comma-joined values.
        country_values = [
            v for (k, v) in captured[0].url.params.multi_items() if k == "countryOrgs"
        ]
        assert country_values == ["CA", "US"]


class TestGetLegislationDetail:
    @pytest.mark.asyncio
    async def test_detail_parses_meta_and_files(self) -> None:
        async with _mock_client(lambda r: httpx2.Response(200, text=DETAIL_HTML)) as client:
            detail = await client.get_legislation("23293")

        assert detail.legislation_id == "23293"
        assert detail.title == "Patent Act"
        assert detail.jurisdiction == "Canada"
        assert detail.summary is not None and "Patents (Inventions)" in detail.summary
        assert detail.url == "https://www.wipo.int/wipolex/en/legislation/details/23293"
        # All three attachments captured, mime types inferred from extension.
        mime_types = sorted([f.mime_type for f in detail.files])
        assert mime_types == [
            "application/pdf",
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ]

    @pytest.mark.asyncio
    async def test_detail_url_is_constructed_when_canonical_missing(self) -> None:
        sparse_html = """<html><head>
            <meta property="og:title" content="Foo Law, Ruritania, WIPO Lex" />
            <meta name="description" content="Ruritania - whatever" />
        </head><body></body></html>"""

        async with _mock_client(lambda r: httpx2.Response(200, text=sparse_html)) as client:
            detail = await client.get_legislation("99999")

        assert detail.title == "Foo Law"
        assert detail.jurisdiction == "Ruritania"
        # No og:url present → URL synthesized from base + id.
        assert detail.url.endswith("/wipolex/en/legislation/details/99999")
        assert detail.files == []


class TestModuleLevelApi:
    @pytest.mark.asyncio
    async def test_search_via_module_api(self, monkeypatch) -> None:
        from patent_client_agents.wipo_lex import api as lex_api

        def handler(request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(200, text=SEARCH_RESULTS_HTML)

        def _factory(*args, **kwargs):
            return WipoLexClient(client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)))

        monkeypatch.setattr(lex_api, "WipoLexClient", _factory)

        result = await lex_api.search_legislation(
            SearchLegislationInput(country_codes=["CA"], subject_matter=[SubjectMatter.PATENTS])
        )
        assert len(result.hits) == 3

    @pytest.mark.asyncio
    async def test_get_legislation_accepts_bare_id(self, monkeypatch) -> None:
        from patent_client_agents.wipo_lex import api as lex_api

        def handler(request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(200, text=DETAIL_HTML)

        def _factory(*args, **kwargs):
            return WipoLexClient(client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)))

        monkeypatch.setattr(lex_api, "WipoLexClient", _factory)

        detail = await lex_api.get_legislation("23293")
        assert detail.title == "Patent Act"

        detail2 = await lex_api.get_legislation(GetLegislationInput(legislation_id="23293"))
        assert detail2.title == "Patent Act"
