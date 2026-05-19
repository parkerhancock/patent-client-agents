# EUIPO European Union Intellectual Property Office (EM) — regional

**Layer:** regional
**Jurisdiction:** 27 EU member states
**Issuing body:** European Union Intellectual Property Office (Alicante, Spain)
**Rights administered:** trademark (EUTM — EU Trade Mark), industrial_design (REUD — Registered European Union Design, formerly RCD)
**Working languages:** All 24 EU official languages
**Connector status:** **active**
**Last verified:** 2026-05-16
**Manifest entries:**
- [`EM/EUIPO/Trademarks`](../../coverage/sources.yaml) — `patent_client_agents.euipo_trademarks`
- [`EM/EUIPO/Designs`](../../coverage/sources.yaml) — `patent_client_agents.euipo_designs` (note: terminology change — see §3)

**Detail surveys:**
- [`connectors/euipo.md`](../connectors/euipo.md) — 2026-05 detail survey (172 lines)
- [`euipo_api_authoritative.md`](../euipo_api_authoritative.md) — earlier authoritative API research

**Sibling layers carrying overlapping data:**
- **National TM offices** — for national-only TMs filed at DE/FR/IT/etc. offices (not via EUTM). EUIPO does NOT cover these.
- **TMview** (EUIPO-hosted, federated search frontend over national TM registers) — adjacent surface but no public API as of 2026-05-16.
- **WIPO Madrid** — for Madrid IRs designating EU; EUIPO returns these in EUTM searches.
- **WIPO Hague** — for Hague IRs designating EU; EUIPO returns these in REUD searches.

---

## §1 Mission

EUIPO is the EU-wide TM and design office. One EUTM application gives
protection across all 27 EU member states; one REUD does the same for
designs. EUIPO does **not** examine or register national TMs/designs —
those stay at member-state offices (DPMA, INPI France, etc.). EUIPO's
search surfaces also host TMview and DesignView (federated frontends
over national registers), but those are search-only over national-office
data, not unified registers.

For agents working on EU TMs and designs, EUIPO is the primary stop.
For national-only EU TMs and designs, national connectors are still
required and most are not proxyable under current ToS constraints (see
[`COVERAGE_STRATEGY.md`](../COVERAGE_STRATEGY.md) §3).

## §2 What's unique here
- **EUTMs** — single application across all 27 EU states (1996+, ~3.7M marks)
- **REUDs** (Registered European Union Designs) — single application across all 27 EU states (2003+, ~1.7M designs)
- **EUTM oppositions / invalidity proceedings**
- **REUD invalidity proceedings**
- **TMview / DesignView federations** — search-only access (no underlying register API)
- **EUIPO Guidelines** (substantive law layer, separate connector)
- **EUIPO Boards of Appeal decisions**

## §3 Programmatic surfaces

### EUIPO Trade Mark Search API

| Field | Value |
|---|---|
| Endpoint | `https://api.ipo.euipo.europa.eu/trademark-search/` |
| Auth | OAuth2 client credentials (sandbox + prod split) |
| Format | JSON (REST) — OpenAPI 3 spec published |
| Rate limit | Not publicly documented; only the 429 error contract is published; real plan limits via sandbox app or `apiteam@euipo.europa.eu` |
| ToS posture | Permissive within auth model; commercial use is contemplated |
| Verdict | 🟢 Green |
| Primary sources | [EUIPO Developer](https://www.euipo.europa.eu/en/about-us/services/developers) · OpenAPI specs in [`research/openapi/euipo_trademark_search.json`](../openapi/euipo_trademark_search.json) |

### EUIPO Design Search API (REUD)

| Field | Value |
|---|---|
| Endpoint | `https://api.ipo.euipo.europa.eu/design-search/` |
| Auth | Same OAuth2 client credentials |
| Format | JSON |
| Verdict | 🟢 Green |
| Primary sources | OpenAPI in [`research/openapi/euipo_design_search.json`](../openapi/euipo_design_search.json) |

**Terminology change (2025-05-01):**
Under [Regulation (EU) 2024/2822](https://eur-lex.europa.eu/eli/reg/2024/2822/oj),
"Registered Community Design (RCD)" was renamed to **"Registered European
Union Design (REUD)"** effective Phase I 2025-05-01. Existing rights are
not invalidated; the terminology is changing in EUIPO documents,
EUIPO communications, and EU regulations. Our connector's `EM/EUIPO/Designs`
manifest entry and tool docstrings still reference "RCD" in places —
**queued for cleanup** to align with current terminology.

### TMview

| Field | Value |
|---|---|
| Status | Federated search frontend hosted by EUIPO; no documented public API |
| Verdict | 🟡 Yellow — **highest-leverage open question** for cross-EU TM coverage; see [COVERAGE_STRATEGY](../COVERAGE_STRATEGY.md) §8 |

### DesignView

| Field | Value |
|---|---|
| Status | Likely EUIPO-hosted; design analogue of TMview; not yet investigated |
| Verdict | 🟡 Yellow — research target |

### EUIPO Open Data Platform (bulk)

| Field | Value |
|---|---|
| Endpoint | Open Data Platform; daily XML dumps |
| Auth | none |
| Format | XML (ST.66 TMs, ST.86 designs) |
| Verdict | 🟢 Green for bulk-shaped workflows; bulk doesn't fit zero-infra constraint for live proxy, but a `euipo_bulkdata` connector mirrors the `uspto_bulkdata` pattern (BACKLOG Tier 1 Rank 3) |

### EUIPO Document Repository

OpenAPI in [`research/openapi/euipo_document_repository.json`](../openapi/euipo_document_repository.json).
Used for fetching prosecution-record documents.

### Goods & Services / Persons / Product Indications

OpenAPIs in [`research/openapi/`](../openapi/). Auxiliary lookups for
Nice classification, applicant normalization, Locarno classification.

## §4 Fees

EUIPO publishes two schedules — EUTM (trade marks) and REUD (Registered
EU Design, post-reform name for RCD).

- **EUTM fees:** application (per class), opposition, renewal (10-year term).
  - [EUIPO TM fees](https://www.euipo.europa.eu/en/trade-marks/before-applying/fees-payable-direct-to-the-euipo)
- **REUD fees:** application (combined registration + publication after Reg. (EU) 2024/2822), deferment, renewal in a back-loaded curve across years 5/10/15/20. Design rights terminate after 25 years.
  - [EUIPO Design fees](https://www.euipo.europa.eu/en/designs/before-applying/fees-payable-direct-to-the-euipo)
- **Legal basis:** [Regulation (EU) 2024/2822](https://eur-lex.europa.eu/eli/reg/2024/2822/oj) (REUD reform); EUTMR ([Reg. 2017/1001](https://eur-lex.europa.eu/eli/reg/2017/1001/oj)) for EUTM.

*(frozen at the date written; consult the official URLs above for current figures).*

## §5 Connector strategy

### What we cover today

- [`patent_client_agents.euipo_trademarks`](../../src/patent_client_agents/euipo_trademarks/) — EUTM search + fetch + opposition
- [`patent_client_agents.euipo_designs`](../../src/patent_client_agents/euipo_designs/) — REUD search + fetch
- (Both env-gated on `EUIPO_CLIENT_ID` + `EUIPO_CLIENT_SECRET`)

### What we should improve

- **Terminology cleanup** — update `EM/EUIPO/Designs` manifest entry and connector code to reflect **REUD** rather than RCD throughout. The old RCD language is grandfathered but new code should use the current term. ([Reconciliation log entry in BACKLOG.md](../BACKLOG.md).)
- **§5.9 envelope sweep on EUIPO tools** — completed 2026-05-15 ✅. Tools are envelope-compliant.
- **Fee modeling** — the REUD reform back-loaded the renewal curve significantly (4th renewal at year 20 is now a multiple of the old fee). If we expose fees via API/MCP, that curve needs to be modeled accurately — see the EUIPO design fees page linked above for current figures.

### What we should NOT add

- **TMview HTML scraping** — brittle and contract-drift risk per BACKLOG Tier 1 hard-skip list. **However**, TMview API discovery is a high-leverage open question — see [`COVERAGE_STRATEGY.md`](../COVERAGE_STRATEGY.md) §8.

### What we *could* add

- **`euipo_bulkdata`** — EUIPO Open Data daily XML dumps; mirrors `uspto_bulkdata` shape; BACKLOG Tier 1 Rank 3. Bulk-shaped (doesn't fit zero-infra) but legally clean.
- **EUIPO eSearch Case Law** — TM Board of Appeal decisions. No documented API; possible 2026-2027 per BACKLOG. Watch.

### Next steps

1. **Discovery research on TMview + DesignView APIs** — highest-leverage open question for trademark/design coverage.
2. **RCD → REUD cleanup** in `EM/EUIPO/Designs` manifest entry and connector code.
3. **Fee data integration** — REUD reform terms need to be in any cost-modeling layer.

## §6 Open questions

- **TMview API availability** — does EUIPO plan to expose TMview programmatically? See [`COVERAGE_STRATEGY.md`](../COVERAGE_STRATEGY.md) §8.
- **DesignView API availability** — symmetric question for designs.
- **Real quota numerics** — only the 429 error contract is published; real plan limits via sandbox or `apiteam@euipo.europa.eu`.
- **CZ/DK/HU/SK national TM search reports (opt-in 2024-01-01)** — does this expose national TM data through an EUIPO endpoint?

## §7 References

Primary sources only.

**APIs:**
- [EUIPO Developer Portal](https://www.euipo.europa.eu/en/about-us/services/developers)
- [TM Search API OpenAPI](../openapi/euipo_trademark_search.json)
- [Design Search API OpenAPI](../openapi/euipo_design_search.json)
- [Document Repository OpenAPI](../openapi/euipo_document_repository.json)

**Fees + legal basis:**
- [EUIPO TM fees](https://www.euipo.europa.eu/en/trade-marks/before-applying/fees-payable-direct-to-the-euipo)
- [EUIPO Design fees](https://www.euipo.europa.eu/en/designs/before-applying/fees-payable-direct-to-the-euipo)
- [Regulation (EU) 2024/2822 — design reform](https://eur-lex.europa.eu/eli/reg/2024/2822/oj) — Phase I effective 2025-05-01
- [EUTMR 2017/1001](https://eur-lex.europa.eu/eli/reg/2017/1001/oj) — EUTM regulation
- [Community Designs Regulation 6/2002](https://eur-lex.europa.eu/eli/reg/2002/6/oj) — design regulation (now amended by 2024/2822)

**Search frontends (no public API):**
- [TMview](https://www.tmdn.org/tmview/)
- [DesignView](https://www.tmdn.org/tmdsview-web/)

**Detail survey + fee research:**
- [`connectors/euipo.md`](../connectors/euipo.md)
- [`euipo_api_authoritative.md`](../euipo_api_authoritative.md)

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-16 | Initial synopsis. Reconciled RCD → REUD terminology (Reg. 2024/2822 Phase I). Noted REUD reform restructured the renewal curve (years 5/10/15/20 with a steep 4th renewal) and replaced separate registration + publication fees with a single application fee. Late-payment surcharges abolished. | — |
