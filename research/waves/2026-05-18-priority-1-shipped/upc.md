# UPC/UPC — Shipped-state research note (2026-05-18)

Cross-references the [2026-05 detail survey](../../connectors/upc.md) (668 lines
including the 2026-05-13 CMS-API enrollment probe); synopsis at
[`research/regional/upc.md`](../../regional/upc.md).

The UPC is the only **court** entity in our catalog (every other row is a
registry, statute corpus, or examining office). Two operational connectors
shipped in v0.11.0: a Drupal-Views HTML harvester for the decisions feed,
and a bundled SQLite/FTS5 corpus for UPCA + Rules of Procedure + Fees Rules
+ Code of Conduct. The CMS Public Read API v5.3 is the third surface and
is **blocked at TLS handshake** for unenrolled clients — a 2026-05-13 probe
confirmed the read API and the CMS Filing UI are separately credentialed
systems. The high-value opt-out registry (`/v5/opt-out/list`) sits behind
that block. The Unitary Patent register, often conflated with the UPC,
actually lives at the **EPO** and is already reachable via `epo_ops`.

## §1 Endpoint

Three distinct surfaces:

- **Decisions and Orders** — `https://www.unifiedpatentcourt.org/en/decisions-and-orders` (also `/fr/...`, `/de/...`). Drupal Views-backed listing table. Operational source for `upc_decisions`.
- **Legal documents** — `https://www.unifiedpatentcourt.org/en/court/legal-documents`. Static PDFs for UPCA, Statute (= Annex I), Rules of Procedure (18th draft, in force 2022-09-01), Rules on Court Fees and Recoverable Costs, Code of Conduct. Operational source for `upc_statutes`.
- **CMS Public Read API v5.3** — presumed `https://api-prod.unified-patent-court.org/upc/public/api/v5/` (Swagger `host: upcbe` is an internal placeholder). 10 GET-only paths in [`research/openapi/upc_cms_public_api_v5-3.json`](../../openapi/upc_cms_public_api_v5-3.json). **Blocked.**

## §2 Auth

- **Decisions feed / legal documents** — none. Public read.
- **CMS Public Read API** — OAuth2 bearer (1800-second lifetime; replaced legacy `X-API-KEY`). Enrollment workflow not publicly documented; the strings `client_id`, `client_secret`, `register an application`, `developer portal` appear on **none** of the relevant pages. The Athena contact form is the only known channel. mTLS via DigiCert/QuoVadis may be part of the picture per their published "[UPC Authentication Certificates](https://www.digicert.com/tls-ssl/unified-patent-court-certificates)" page, but not dispositive.

## §3 Query language

- **Decisions feed.** Filter form supports `judgement_type` (`order` | `decision`), `court_type` (`1` CoA, `2` Central CFI, `3` Local CFI, `4` Regional CFI), `division_1..division_4` (discoverable via `list_divisions()`), and `proceedings_lang` (discoverable via `list_languages()`). Free-text search exists on the UI but is unreliable for programmatic use.
- **Statutes corpus.** SQLite/FTS5 with BM25 ranking. Syntaxes: `and`, `or`, `adj`, `exact`. Instrument filter accepts aliases (`upca` / `agreement` / `statute` / `annex i`, `rop` / `rules` / `rules of procedure`, `fees` / `court fees` / `table of court fees`, `coc` / `code of conduct`). Language filter takes ISO 639-1 (`en` / `fr` / `de`); pass `None` to search all.
- **CMS Public Read API.** `/v5/cases` exposes 18 query params (number, year, type, dates, patentNumber, decisionNumber, decisionFullText, parties, representative, judge, language, paging). `/v5/opt-out/list` takes a patent number. Spec is offline at [`research/openapi/upc_cms_public_api_v5-3.json`](../../openapi/upc_cms_public_api_v5-3.json).

## §4 Pagination

- **Decisions feed.** `?page=N` (0-indexed). **Drupal Views quirk**: `?page=0` renders the View's *empty* template — omit the param entirely for the first page. The harvester's `total_pages` is recovered from the pager's "Last page" link (`pager__item--last`); falls back to 1 when the listing fits on a single page.
- **Statutes corpus.** `page` (1-indexed) + `per_page` (1-100); `has_more` flag returned.
- **CMS Public Read API.** Standard `page` / `size` params on the list endpoints per Swagger v5.3.

## §5 Response shape

- **Decisions feed.** Per-row Pydantic `UpcDecision` with `case_id` (canonical), `raw_references` (verbatim source strings), `detail_url` (Cloudflare-gated `/en/node/<id>`), `court`, `type_of_action`, `parties` (split on `v.`), `pdf_urls` (PDF/A binaries; NOT Cloudflare-gated). Case-ID canonicalization handles `UPC_CFI_n/yyyy`, `UPC-CFI-n/yyyy`, `UPC_CoA_n/yyyy`, `UPC-COA-n/yyyy`, `ACT_NNNNNN/yyyy`, with zero-padding preserved when present.
- **Statutes corpus.** `UpcInstrument` / `UpcInstrumentText` carry `instrument` (stable key), `short_name`, `title`, `language`, `source_url`, `source_version`, `pdf_pages`, `text`. `UpcStatuteSearchHit` returns `<mark>...</mark>`-wrapped snippets with BM25 `rank`.
- **CMS Public Read API.** JSON per Swagger v5.3 (64 schema definitions; not exercised live).

## §6 Coverage scope

- **Decisions feed.** Full operational corpus from 2023-06-01 launch onward. ~946 CFI cases by end-2025 per [Bird & Bird's UPC in numbers](https://www.twobirds.com/en/insights/2026/the-upc-in-numbers-32-months-of-action); 2025 alone saw 239 infringement (+54.2% YoY), 27 standalone revocations, 83 counterclaim-revocations, 36 PI applications. Court of Appeal is now running **three panels** (third stood up early 2026). Includes Central Division (Munich/Paris/**Milan** — Milan operational since 2024-07-01 covering IPC sections A/C), 13 Local Divisions, 1 Nordic-Baltic Regional Division (Stockholm seat, Tallinn hearings).
- **Statutes corpus.** UPCA + Statute (Annex I) + Rules of Procedure (18th draft, in force 2022-09-01) + Rules on Court Fees and Recoverable Costs + Code of Conduct, EN/FR/DE parallel. Frozen snapshot — `corpus_synced_at` / `corpus_version` reflect the last build refresh.
- **CMS Public Read API (if it were accessible).** Cases search + per-case documents + opt-out list + opt-out status taxonomy + representatives. The Filing UI's backends (`addressbook-api`, `dtk-api`, `epct-integration-api`, `npefiling-api`, `user-api`) **do not include** any path from the v5.3 spec — Filing UI and Public Read API are different systems.
- **Out of scope** (covered transitively or skipped): Unitary Patent register (lives at the EPO — already wrapped via `epo_ops`); A2A write-side filing API (regulated, skip); hearing calendars (HTML-only, per-division pages); PACER-style pleadings (RoP 262 / 262A confidentiality — presumptively private).

## §7 Rate limits / quotas

- **Decisions feed.** None published. Polite empirical limit 1 RPS, no observed 429s. Cloudflare in front of the site challenges per-decision detail pages (`/en/node/<id>`) but not the listing pages or PDF binaries.
- **Statutes corpus.** Local; n/a.
- **CMS Public Read API.** Not published. Spec has no `securityDefinitions` block — auth is layered at the gateway.

## §8 Terms of service

- **Decisions feed + legal documents.** Public court records and treaty text. No published API ToS; standard public-record use posture. PDF/A is the format mandated by the RoP for all UPC documents.
- **CMS Public Read API.** ToS would attach via the enrollment workflow (not publicly documented). Open question for the CoWork allowlist's cache-and-serve model.

## §9 Operational notes

- **The single load-bearing operational fact**: the decisions feed's per-row data is *complete enough* that the harvester never needs to follow the Cloudflare-gated `/en/node/<id>` detail link. Every structured field (case ID, court/division, type of action, parties, PDF URL) lives in the listing row. This is why the connector ships green despite Cloudflare's interactive challenge on the detail pages.
- **The second load-bearing fact**: `?page=0` triggers a Drupal-Views empty-template render. Omit the `page` param entirely for the first page; use `?page=N` for `N >= 1`. The harvester encodes this in `UpcDecisionsClient.search()`.
- **Case-ID hygiene.** Source rows mix `UPC_CFI_n/yyyy`, `UPC-CFI-n/yyyy`, `UPC_CoA_n/yyyy`, `UPC-COA-n/yyyy`, `ACT_NNNNNN/yyyy` (with 7-digit zero-padding in some recent rows). The `_canonicalize_case_id` regex normalizes to underscored form, preserving zero-padding when present and resurfacing `UPC_CoA` (mixed-case) from any hyphenated source variant.
- **Multilingual content.** Procedural language is per-division: Central / CoA use EN/FR/DE; Local Divisions use the local language plus EN (DE for DE LDs, IT for Milan, NL for The Hague, FR for Paris, EN dominant overall in practice). The connector exposes `proceedings_lang` filter IDs via `list_languages()`; surface what the UI offers rather than synthesizing our own taxonomy.
- **English has emerged as the dominant procedural language** across the UPC, even at non-English Local Divisions — relevant context for analytics consumers.
- **PDF/A throughout.** Every UPC-issued document is PDF/A by RoP mandate. No need to detect format; OCR isn't required but layout extraction quality varies (Open Q #5 in the detail survey — spot-check 10 decisions per division before committing to a structured text feed).
- **The opt-out registry is the highest-value piece of the UPC data stack** — once the CMS Read API enrolls, `/v5/opt-out/list` becomes the canonical answer to *"is this EP opted out?"*, a question of escalating commercial importance through the transitional period.
- **Unitary Patent ≠ UPC.** The UP register is at the EPO (already wrapped). Many users conflate them; the connector docstrings and synopsis should keep the boundary explicit.

## §10 Rating

**Decisions feed (`upc_decisions`): 🟢 green** — shipped, listing rows are structurally complete, PDF/A binaries stream directly, case-ID canonicalization handles every observed source variant, Cloudflare doesn't block the listing or the PDFs. The Drupal `?page=0` quirk and the Cloudflare-gated detail page are documented in the client and worked around.

**Statutes corpus (`upc_statutes`): 🟢 green** — shipped, follows the established `StaticLawCorpus` shape (same pattern as `mpep`, `epc`, `ipo_in_statutes`, `dpma_statutes`, `legifrance_ip`, `tw_trade_secrets`), EN/FR/DE parallel, FTS5/BM25 search with instrument aliasing, `get_corpus_status()` for §4 provenance stamping.

**CMS Public Read API: 🔴 red today** — enrollment workflow undocumented, read-API host rejects TLS at the network layer for unenrolled clients (no `ServerHello` returned in TLSv1.2 / TLSv1.3 handshakes), Filing-UI Keycloak credentials don't bootstrap into read-API access. Pending the Athena contact-form response on (a) separate enrollment, (b) mTLS / source-IP allowlist / OAuth-only auth model, (c) canonical base URL. Material upgrade once unblocked: opt-out registry coverage (`/v5/opt-out/list`) would be the single highest-leverage public-API asset in the UPC stack.

**Opt-out registry coverage: planned but blocked.** Not shipped in v0.11.0. The opt-out UI is reachable today at `unifiedpatentcourt.org/en/registry/opt-out` for manual lookups; the structured surface (`/v5/opt-out/list`, `/v5/opt-out/patentStatus`) is blocked behind the same enrollment wall. Tracking under §6 of the detail survey.
