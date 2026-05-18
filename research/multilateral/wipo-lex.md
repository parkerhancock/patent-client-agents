# WIPO Lex — multilateral

**Layer:** multilateral
**Jurisdiction:** n/a (global; ~200 jurisdictions indexed)
**Issuing body:** World Intellectual Property Organization (WIPO)
**Rights administered:** patent, utility_model, trademark, design, copyright, plant_variety, gi, trade_secret (all eight families surfaced via the `subjectMatter` taxonomy — see §2)
**Working languages:** Arabic, English, French, Russian, Spanish, Chinese (the six WIPO official languages; the connector currently parses the `/en/` surface)
**Connector status:** **active**
**Last verified:** 2026-05-18
**Manifest entry:** [`WO/WIPO/Lex`](../../coverage/sources.yaml) — `patent_client_agents.wipo_lex`

**Detail surveys:**
- [`connectors/wipo_lex_api_discovery.md`](../connectors/wipo_lex_api_discovery.md) — 2026-05 endpoint-level survey of the WIPO Lex public surfaces (all three collections; the connector ships only the legislation slice)
- [`waves/2026-05-18-priority-1-shipped/wipo-lex.md`](../waves/2026-05-18-priority-1-shipped/wipo-lex.md) — distilled shipped-state research note backing this synopsis

**Sibling layers carrying overlapping data:**
- **National statute corpora.** Where we ship a bundled SQLite/FTS5 corpus over national IP statutes — DPMA Germany ([`patent_client_agents.dpma_statutes`](../../src/patent_client_agents/dpma_statutes/)), Légifrance France ([`patent_client_agents.legifrance_ip`](../../src/patent_client_agents/legifrance_ip/)), IPO India ([`patent_client_agents.ipo_in_statutes`](../../src/patent_client_agents/ipo_in_statutes/)), Taiwan Trade Secrets Act ([`patent_client_agents.tw_trade_secrets`](../../src/patent_client_agents/tw_trade_secrets/)) — WIPO Lex is the primary or fallback **source of record** for those builds (statutes are public-domain; the WIPO-curated English translations are often the fastest route to a clean bilingual snapshot).
- **WIPO Treaties database.** Treaty-instrument metadata at [`wipo.int/treaties`](https://www.wipo.int/treaties/en/) overlaps with the WIPO Lex `treaties` collection. The Lex surface is the unified-search path; the treaties site is the per-instrument deep-dive.

---

## §1 Mission

WIPO Lex is WIPO's global legal-information database, the canonical
single-point source for **substantive IP law text across ~200
jurisdictions**. It indexes three collections — **legislation** (national
+ regional statutes and regulations), **treaties** (multilateral and
bilateral IP instruments), and **judgments** (court decisions on IP
matters, where contributing courts supply them) — under one search
taxonomy and ID space, with full attachments (PDF / DOC / TXT) on every
entry. Per the [WIPO Lex landing page](https://www.wipo.int/wipolex/en/main/),
the database is built to provide "free access to legal information on
intellectual property" worldwide; it is the substantive-law backbone of
our atlas, complementing the registers, examining offices, and courts
covered elsewhere.

For agents, WIPO Lex is the answer to two recurring questions: *"what
statute / treaty / decision governs this IP question in jurisdiction
X?"* and *"give me the canonical text."* Every national statute corpus
we ship transitively (DPMA, Légifrance, IPO India, Taiwan trade
secrets) treats WIPO Lex as a primary or fallback source of record —
this row is the *foundation* on which the substantive-law tier of the
catalog rests.

## §2 What's unique here

- **The only single-point source for IP law text at this breadth** — ~200 jurisdictions, all eight IP-rights families, one taxonomy and one ID space. National offices each host their own statute text in their own format; WIPO Lex normalizes them.
- **Treaty registry.** The `treaties` collection covers every WIPO-administered treaty (Paris, Berne, PCT, Madrid, Hague, Lisbon, WCT, WPPT, Marrakesh, Beijing, …) plus regional and bilateral IP instruments. Per-treaty metadata, contracting parties, and full text. See [WIPO Lex Treaties](https://www.wipo.int/wipolex/en/treaties/).
- **Judgments collection.** Partial — coverage depends on bilateral contribution agreements with national courts — but the only multilateral index of national IP case law that exists. Indexed by jurisdiction, authority body, subject matter, and procedure type.
- **Consolidated versions for major statutes.** WIPO Lex maintains consolidated / amended-up-to-date versions of frequently-amended IP statutes where the source legislator publishes them.
- **Stable taxonomy across all three collections.** `SubjectMatter` codes 1–21 and `TypeOfText` codes (205, 207, 210, 213, 214, 215) are shared — see [`models.py`](../../src/patent_client_agents/wipo_lex/models.py). One filter set, three collections.
- **Green ToS posture among WIPO surfaces.** [PATENTSCOPE](wipo-patentscope.md), [Madrid Monitor](wipo-madrid.md), [Hague Express](wipo-hague.md), [Global Brand DB](wipo-global-brand-db.md), and [Global Design DB](wipo-global-design-db.md) are all 🔴 / 🟡 due to explicit automated-query prohibitions. WIPO Lex carries no such prohibition — it is the **single 🟢 WIPO surface** in our atlas.

## §3 Programmatic surfaces

### Legislation search + detail (the connector's primary surface)

| Field | Value |
|---|---|
| Endpoints | `GET https://www.wipo.int/wipolex/en/legislation/results` (search) + `GET https://www.wipo.int/wipolex/en/legislation/details/{id}` (detail) |
| Auth | none (public, no API key, no account) |
| Format | server-rendered HTML; canonical metadata on OpenGraph + `<meta name>` tags |
| Rate limit | not published; polite User-Agent + aggressive SQLite caching is sufficient |
| ToS posture | permissive — no published automated-query prohibition |
| Rating (zero-infra proxy) | 🟢 **Green** — shipped at [`patent_client_agents.wipo_lex`](../../src/patent_client_agents/wipo_lex/) |
| Primary source | [WIPO Lex Legislation](https://www.wipo.int/wipolex/en/main/legislation) |

The connector parses two stable surfaces: each search hit is an `<a href="/wipolex/en/legislation/details/{ID}">{Title}</a>` anchor (pin on URL shape, not CSS class) and the detail page carries canonical metadata on OpenGraph `og:title` + `og:url` + `<meta name="description">`. PDF/DOC attachments matched by extension. See [`transformers.py`](../../src/patent_client_agents/wipo_lex/transformers.py).

### Treaties search + detail (shape known, not shipped)

| Field | Value |
|---|---|
| Endpoints | `GET https://www.wipo.int/wipolex/en/treaties/results` + `/treaties/details/{id}` |
| Auth | none |
| Format | HTML, identical shape to legislation |
| Rating | 🟢 **Green** — same shape as legislation; same parser pattern would work |
| Primary source | [WIPO Lex Treaties](https://www.wipo.int/wipolex/en/treaties/) |

The connector docstrings explicitly note treaties + judgments are same-shape next-up additions; sprint 1 scoped to legislation.

### Judgments search + detail (shape known, not shipped)

| Field | Value |
|---|---|
| Endpoints | `GET https://www.wipo.int/wipolex/en/judgments/results` + `/judgments/details/{id}` |
| Auth | none |
| Format | HTML, same shape as legislation; richer filter set (authority body, procedure type, related-law cross-references) |
| Rating | 🟢 **Green** — same shape as legislation |
| Primary source | [WIPO Lex Judgments](https://www.wipo.int/wipolex/en/judgments/) |

### Adjacent surfaces (`/opts` JSON + jurisdiction browse)

`POST /wipolex/en/bodyissuer/opts` and `POST /wipolex/en/laws/opts` return clean JSON `[{label, value}]` for UI dropdown population — the cleanest WIPO Lex JSON surfaces if dynamic filter discovery is ever needed. `GET /wipolex/en/members/profile/{ISO2}` is the jurisdiction-profile entry point ("show me everything on Canada"). Not wrapped today; documented in the [endpoint discovery survey](../connectors/wipo_lex_api_discovery.md).

## §4 Fees

**Policy: link only.** WIPO Lex is **free of charge** for both human
and programmatic access. There is no API key, no metered tier, no paid
bulk product, and no contract gate. WIPO's stated mission for the
service is *free access to legal information on intellectual property*
(see [WIPO Lex landing page](https://www.wipo.int/wipolex/en/main/)).
The connector ships with no auth-related env vars.

- **Official surface:** [WIPO Lex](https://www.wipo.int/wipolex/en/main/)
- **WIPO public-information policy basis:** [WIPO Terms of Use](https://www.wipo.int/portal/en/terms-of-use.html)

The underlying statutes and treaties carry the copyright posture of
their source legislator / treaty depository (typically public domain
or government-work exception in their home jurisdiction); WIPO's
curatorial layer (metadata, translations) is published under WIPO's
general terms.

## §5 Connector strategy

### What we cover today

[`patent_client_agents.wipo_lex`](../../src/patent_client_agents/wipo_lex/)
— async client wrapping the **legislation** collection. Surface:

- `search_legislation(...)` — filter by `country_codes` (ISO 3166-1
  alpha-2 + regional org codes like `EU`, `GCC`), `subject_matter`
  (`SubjectMatter` enum, codes 1–21), `type_of_text` (`TypeOfText`
  enum, codes 205 / 207 / 210 / 213 / 214 / 215), free-text `keywords`,
  date bounds (`start_date` / `end_date`), and `include_historical`
  (toggles WIPO's `last=true` flag for superseded texts).
- `get_legislation(legislation_id)` — fetch metadata + downloadable
  attachment list for a single entry by its WIPO Lex internal ID
  (e.g. `"23293"` for the Canadian Patent Act).

The connector returns Pydantic models — `LegislationSearchResponse`,
`LegislationSearchHit`, `LegislationDetail`, `WipoLexFileLink` — with
absolute URLs, ISO-style date strings, and mime types inferred from
attachment extensions. Manifest row: `WO/WIPO/Lex`,
`access.method: rest_api`, `access.auth: none`, `category:
substantive_law`, `transport: mcp_proxy`, `update_strategy: live_proxy`,
`update_cadence: irregular`.

### What we could add

- **Treaties collection.** Same parser pattern, different URL prefix. Would unlock unified queries across the treaty register (PCT, Madrid, Hague, Lisbon, WCT, WPPT, Marrakesh, Beijing, regional conventions) — currently missing from our multilateral tier.
- **Judgments collection.** Same parser pattern; the additional filter axes (`authority` body, `procType`, related-law cross-references) need a small dropdown-discovery step via the `bodyissuer/opts` JSON endpoint.
- **Citation resolver.** Free-form statute citation ("Canadian Patent Act § 27") → WIPO Lex `legislation_id` + PDF anchor. Would compose with our national-statute corpora to provide single-canonical citation-to-text resolution.
- **Cross-link to national-statute corpora.** Surface the WIPO Lex ID inside DPMA / Légifrance / IPO India / Taiwan rows so an agent can pivot from local FTS to canonical metadata at WIPO.

### What we should NOT add

- **Bulk mirror of WIPO Lex.** WIPO Lex *is* the index; mirroring duplicates WIPO infrastructure with no upside given the permissive ToS + aggressive SQLite caching.
- **PDF-to-plaintext extraction in this connector.** Separate concern; the connector exposes the canonical PDF URLs and downstream consumers handle extraction.

### Next steps

1. Promote treaties + judgments to shipped collections — identical parser shape; small sprint cost.
2. Add `members/profile/{ISO2}` as a jurisdiction-profile tool.
3. Re-verify selector stability on each WIPO Lex redesign; OpenGraph + URL shape are the load-bearing contracts.

## §6 Open questions

- **Platform-migration risk.** WIPO Lex is a server-rendered stack today. A migration to a JS SPA without server-rendered fallback breaks the current parser shape. No public roadmap signal as of 2026-05-18 — re-check the [WIPO Lex landing page](https://www.wipo.int/wipolex/en/main/) release notes quarterly.
- **Multilingual surface coverage.** Connector parses `/en/` paths; same pages exist at `/ar/`, `/es/`, `/fr/`, `/ru/`, `/zh/`. Expose as language variants or normalize through English? Design choice deferred.
- **WIPO Lex curator metadata licensing.** Statute *text* is public-domain in its source jurisdiction; WIPO's *metadata layer* (translations, subject classification, consolidation notes) sits under WIPO general terms. For systematic metadata mirroring at scale, confirm posture with WIPO directly — open since the [`wipo.md` connector survey](../connectors/wipo.md) raised it in 2026-05.
- **`SubjectMatter` enum drift.** WIPO occasionally adds codes (current set runs 1–21). Re-verify on each search-form release.

## §7 References

Primary sources only (all on `wipo.int`).

**Service surfaces:**
- [WIPO Lex](https://www.wipo.int/wipolex/en/main/) — landing page
- [WIPO Lex Legislation](https://www.wipo.int/wipolex/en/main/legislation)
- [WIPO Lex Treaties](https://www.wipo.int/wipolex/en/treaties/)
- [WIPO Lex Judgments](https://www.wipo.int/wipolex/en/judgments/)
- [WIPO Lex Members](https://www.wipo.int/wipolex/en/members)

**Related WIPO services:**
- [WIPO Treaties Database](https://www.wipo.int/treaties/en/) — sibling treaty-instrument site
- [WIPO Terms of Use](https://www.wipo.int/portal/en/terms-of-use.html)

**Connector:**
- [`patent_client_agents.wipo_lex`](../../src/patent_client_agents/wipo_lex/) — async client + models + transformers
- [`tests/wipo_lex/test_client.py`](../../tests/wipo_lex/test_client.py) — mock-transport unit tests

**Related research:**
- [`connectors/wipo_lex_api_discovery.md`](../connectors/wipo_lex_api_discovery.md) — endpoint-level discovery
- [`connectors/wipo.md`](../connectors/wipo.md) — broader WIPO surfaces survey
- [`multilateral/wipo-patentscope.md`](wipo-patentscope.md) / [`wipo-madrid.md`](wipo-madrid.md) / [`wipo-hague.md`](wipo-hague.md) — sibling WIPO synopses (all 🔴 / 🟡 by contrast)

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-18 | Initial synopsis. Documented the legislation surface as shipped (search + detail via stable URL anchor + OpenGraph meta), the treaties + judgments collections as same-shape next-up additions, the all-eight-rights coverage via the `SubjectMatter` enum (1–21), and the green ToS posture distinguishing WIPO Lex from the other WIPO public databases. Flagged platform-migration risk + metadata licensing as the principal open questions. | Connector source ([`patent_client_agents.wipo_lex`](../../src/patent_client_agents/wipo_lex/)), [endpoint discovery survey](../connectors/wipo_lex_api_discovery.md), and primary sources above |
