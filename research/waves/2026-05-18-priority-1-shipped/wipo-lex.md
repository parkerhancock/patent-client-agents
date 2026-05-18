# WO/WIPO/Lex — wave file (2026-05-18 priority-1 shipped)

Distillation note for **WIPO Lex** — WIPO's global IP-law database
(legislation, treaties, judgments across ~200 jurisdictions) — backing
the synopsis at [`research/multilateral/wipo-lex.md`](../../multilateral/wipo-lex.md).
Connector already shipped as
[`patent_client_agents.wipo_lex`](../../../src/patent_client_agents/wipo_lex/);
this captures operational truth for future builders.

Right covered: **substantive law** across all eight IP families. Sprint-1
connector scope is the **legislation** collection only.

---

## 1. Endpoint

Two anonymous-public endpoints under the WIPO Lex web surface:

- **Search:** `GET https://www.wipo.int/wipolex/en/legislation/results` with repeated-key query params (`countryOrgs=CA&countryOrgs=US&...`).
- **Detail:** `GET https://www.wipo.int/wipolex/en/legislation/details/{id}` where `{id}` is the WIPO Lex internal integer (e.g. `23293` for the Canadian Patent Act).

Both return server-rendered HTML. No documented JSON API; the JS frontend's `wu-*` web components consume the same HTML the connector parses. See [`connectors/wipo_lex_api_discovery.md`](../../connectors/wipo_lex_api_discovery.md) for the full surface catalog (treaties + judgments use parallel paths; `/opts` endpoints serve dropdown JSON; `/members/profile/{ISO2}` serves jurisdiction profiles).

## 2. Auth

**None.** No API key, no account, no contract. Connector ships only a polite identifying `User-Agent: patent-client-agents-wipolex/0.1 (+https://patentclient.com)` header (see [`client.py`](../../../src/patent_client_agents/wipo_lex/client.py)). Green column versus every other WIPO public database (PATENTSCOPE, Madrid Monitor, Hague Express, Global Brand/Design DBs all 🔴 / 🟡 due to explicit automated-query ToS).

## 3. Query language

Three filter families on the legislation search:

- **Jurisdiction.** `countryOrgs` — ISO 3166-1 alpha-2 + regional codes (`EU`, `GCC`, `OAPI`). **Multi-value is repeated keys, not comma-joined** — `countryOrgs=CA&countryOrgs=US`. Pinned by `test_multiple_country_codes_repeat_param` in [`test_client.py`](../../../tests/wipo_lex/test_client.py).
- **Topical.** `subjectMatter` (codes 1–21; `SubjectMatter` enum) + `typeOfText` (205 / 207 / 210 / 213 / 214 / 215; `TypeOfText` enum) in [`models.py`](../../../src/patent_client_agents/wipo_lex/models.py). Both repeat-key for multi-value.
- **Free-text + date.** `keywords` (title + notes), `sDate` / `eDate` (YYYY-MM-DD), `last=true|false` (historical toggle, default `false`).

No DSL, no boolean operators. Same filter-family pattern reappears (with collection-specific overlays) on `/treaties/results` and `/judgments/results`.

## 4. Pagination

**Not exposed in current connector.** WIPO Lex result pages are single-document HTML and the connector parses every hit returned. `/opts` JSON helpers also return un-paginated. If WIPO ever paginates legislation results (open question in the discovery survey), the parser needs a `?page=N` follow-up. No pagination observed in practice — typical legislation matches per jurisdiction-and-subject query are <100.

## 5. Response shape

Four Pydantic models in [`models.py`](../../../src/patent_client_agents/wipo_lex/models.py):

- **`LegislationSearchHit`** — `legislation_id` (string, WIPO Lex internal ID), `title`, `url`.
- **`LegislationSearchResponse`** — `hits[]` + `query_url` (for provenance).
- **`LegislationDetail`** — `legislation_id`, `title`, `jurisdiction` (parsed from `og:title`), `summary` (full `<meta name="description">`), `url`, `files[]`.
- **`WipoLexFileLink`** — `label`, `url`, `mime_type` (inferred from extension).

**Parser contract.** Search hits matched by URL shape `/wipolex/[a-z]{2}/legislation/details/(\d+)`, not by CSS class. Detail metadata from OpenGraph (`og:title`, `og:url`) + `<meta name="description">`. File attachments matched by extension substring (`.pdf` / `.docx` / `.doc`) — visible buttons are `<wu-button class="allfileLinks">` web components; backing `<a class="seo-only-link">` tags point at `wipolex-res.wipo.int` with cache-buster query strings. See [`transformers.py`](../../../src/patent_client_agents/wipo_lex/transformers.py).

## 6. Coverage scope

- **Legislation.** ~200 jurisdictions × all eight IP families (`SubjectMatter` codes 1–21 span patents, utility models, designs, trademarks, GIs, trade names, IC layouts, competition, trade secrets, plant variety, copyright, enforcement, ADR, domain names, GR, TCE, technology transfer, TK, IP regulatory body, other, industrial property). Consolidated versions maintained for frequently-amended statutes where the source legislator publishes them.
- **Treaties.** Same shape, separate collection. Full set of WIPO-administered treaties (Paris, Berne, PCT, Madrid, Hague, Lisbon, WCT, WPPT, Marrakesh, Beijing) plus regional + bilateral IP instruments. **Not shipped today.**
- **Judgments.** Partial — coverage depends on bilateral court contribution agreements. Indexed by jurisdiction, authority body, subject matter, procedure type, related laws/treaties. **Not shipped today.**

Our national statute corpora (`dpma_statutes`, `legifrance_ip`, `ipo_in_statutes`, `tw_trade_secrets`) treat WIPO Lex as a primary or fallback source of record.

## 7. Rate limits / quotas

**None published.** Connector defaults to 30s timeout, identifies via User-Agent, and rides the standard `law_tools_core` hishel + tenacity cache+retry stack so repeat reads hit SQLite. WIPO Lex content updates slowly (legislative timescales) — cache hit rate is high, load on WIPO negligible.

## 8. Terms of service

**Permissive.** No published prohibition on automated access. WIPO's stated mission is "free access to legal information on intellectual property" ([WIPO Lex](https://www.wipo.int/wipolex/en/main/)); general [WIPO Terms of Use](https://www.wipo.int/portal/en/terms-of-use.html) apply. The **only green WIPO surface** in our atlas.

## 9. Operational notes

- **The single load-bearing operational fact**: WIPO Lex returns server-rendered HTML, not JSON, and the connector pins on **two stable surfaces** — (1) the `<a href="/wipolex/{lang}/legislation/details/{ID}">{Title}</a>` URL shape for hits, and (2) the OpenGraph + `<meta name="description">` tags for detail metadata. Both survive CSS restyles; only the file-link extension-match selector would need updating if WIPO changes attachment linking. A JS-SPA migration without server-rendered fallback would break the connector, but the meta-tag layer has been stable across the platform's history.
- **Multi-value query params are repeated keys, not comma-joined.** `countryOrgs=CA&countryOrgs=US`, not `countryOrgs=CA,US`. Same for `subjectMatter` and `typeOfText`. Connector passes `params=list[tuple]` to httpx with a `ty: ignore` for the widened type.
- **Result-page de-duplication.** WIPO Lex sometimes renders the same hit twice (mobile + desktop blocks). The parser dedups on `legislation_id` (see `test_search_parses_unique_hits`).
- **`og:title` parsing.** Convention is `<Law name>, <Jurisdiction>, WIPO Lex`. Parser strips the suffix and splits the remainder on the last comma to recover `title` + `jurisdiction`. Sparse pages without `og:url` get a synthesized URL from base + `legislation_id`.
- **English path today.** Connector parses `/en/` paths; `/ar/`, `/es/`, `/fr/`, `/ru/`, `/zh/` exist with localized metadata — language selection deferred.
- **PDFs at `wipolex-res.wipo.int`** — resource subdomain serves attachment binaries. Anchor `href` values may be absolute or relative; transformer normalizes via `urljoin(base_url, href)`.
- **Sprint-1 = legislation only.** Treaties + judgments share the URL/HTML shape — 1-day parser-clone, not a re-architecture.

## 10. Rating

**Rating: 🟢 green — shipped, operational, free, ToS-permissive.**

WIPO Lex is the substantive-law backbone of our catalog. The connector ships the legislation slice via a polite HTML parser pinned on OpenGraph + URL-shape contracts that have been stable for the platform's lifetime. Lack of a documented JSON API is the only "shape" complaint; the trade-off (HTML parsing vs. parsing other WIPO surfaces' ToS landmines) is overwhelmingly worth it.

Manifest fact (`coverage/sources.yaml` row `WO/WIPO/Lex`): `jurisdiction: WO`, `rights: [patent, trademark, design, copyright, gi]` (manifest is conservative — the `SubjectMatter` enum actually covers all eight families plus enforcement / ADR / GR / TK / TCE; manifest could be widened), `data_types: [statutes, treaties]`, `access.method: rest_api`, `access.auth: none`, `status: active`, `connector.module: patent_client_agents.wipo_lex`, `category: substantive_law`, `transport: mcp_proxy`, `update_strategy: live_proxy`, `update_cadence: irregular`. Synopsis matches the manifest's `active` / `green` reality.

---

## Sources (primary)

- [WIPO Lex](https://www.wipo.int/wipolex/en/main/)
- [WIPO Lex Legislation](https://www.wipo.int/wipolex/en/main/legislation)
- [WIPO Lex Treaties](https://www.wipo.int/wipolex/en/treaties/)
- [WIPO Lex Judgments](https://www.wipo.int/wipolex/en/judgments/)
- [WIPO Lex Members](https://www.wipo.int/wipolex/en/members)
- [WIPO Terms of Use](https://www.wipo.int/portal/en/terms-of-use.html)
- Connector: [`patent_client_agents.wipo_lex`](../../../src/patent_client_agents/wipo_lex/)
- Tests: [`tests/wipo_lex/test_client.py`](../../../tests/wipo_lex/test_client.py)
- Endpoint discovery survey: [`research/connectors/wipo_lex_api_discovery.md`](../../connectors/wipo_lex_api_discovery.md)
