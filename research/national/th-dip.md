# Department of Intellectual Property, Thailand (TH/DIP) — national

**Layer:** national
**Jurisdiction:** TH (WIPO ST.3: TH)
**Issuing body:** Department of Intellectual Property (กรมทรัพย์สินทางปัญญา), Ministry of Commerce
**Rights administered:** patent (invention), patent (petty / utility model), design, trademark, copyright, geographical_indication
**Working languages:** Thai (primary), English (partial)
**Connector status:** **beta (BYOK)** — implemented from DIP's public catalogue field contract; synthetic-fixture tested; live account compatibility unverified
**Last verified:** 2026-08-03
**Manifest entries:** `TH/DIP/Patents`, `TH/DIP/Designs`, `TH/DIP/Trademarks`, `TH/DIP/Copyright`, `TH/DIP/GIs`

**Detail surveys:**
- [`waves/2026-05-18-secondary-nationals-wave/th-dip.md`](../waves/2026-05-18-secondary-nationals-wave/th-dip.md) — 2026-05-18 grounded API discovery

**Higher layers covering this office transitively:**
- **EPO INPADOC** (via [`regional/epo.md`](../regional/epo.md)) — TH patents with EP / PCT counterparts.
- **WIPO PATENTSCOPE** — TH national collection: 191,367 records, biblio + abstracts 1980-08-13 → 2025-12-08, last loaded 2026-01-22.
- **EUIPO TMview** — >960k Thai trademarks since the DIP-EUIPO integration.
- **ASEAN TMview / ASEAN DesignView** — TH aggregated with 8 other ASEAN states on EUIPO TMDN infrastructure (PH-operated as Country Lead, per [`research/national/ph-ipophl.md`](ph-ipophl.md) §3).
- **WIPO Madrid Monitor** — IRs designating TH since TH's accession 2017-11-07.
- **WIPO Hague** — NOT yet covering TH (Patent Act amendments approved by Parliament 2022-11-29; cabinet IP Work Plan 2025-08-26; not yet ratified).

---

## §1 Mission

DIP is Thailand's national IP office under the Ministry of Commerce. Unlike most SEA offices we've surveyed (ID/DGIP, PH/IPOPHL, SG/IPOS — all register-side red), DIP runs a real REST/JSON data-exchange platform with 21 documented APIs spanning all six rights families plus statistics. The contract gate is the constraint, not the technology.

## §2 What's unique here

- **TH petty patents** (อนุสิทธิบัตร) — a distinct simple-patent subtype not covered by EP / Hague / Madrid; DIP is the only register.
- **TH copyright recordal** (notification register; copyright itself is automatic under the Berne Convention but DIP runs a voluntary recordation index).
- **TH music-copyright service** as a separate API surface (A0002, `V_API_CPRSONG`).
- **TH geographical indications** (สิ่งบ่งชี้ทางภูมิศาสตร์ — including the 137-item GI register Thailand has aggressively promoted in regional trade negotiations).
- **TH-language full text** at register fidelity — neither PATENTSCOPE nor INPADOC carries DIP's Thai-language application text.

## §3 Programmatic surfaces

### DIP Data Exchange (the real REST surface)

| Field | Value |
|---|---|
| Catalogue endpoint | `api.ipthailand.go.th/data-exchange/view/home.aspx` (200 OK, 84,715-byte HTML cataloguing 21 APIs) |
| Per-API endpoints | Operational base URL resolved per-API via the catalogue's `getformbody` / `GetField` views; portal-then-host indirection (DPMA-shaped) |
| Auth | Bearer token, issued after (a) self-service registration + (b) paper request letter posted to DIP's ICT Center within 30 days |
| Format | JSON (POST request bodies; one GET) |
| Cost | Free (no published fee on the registration page; postal-only contract route) |
| Rate limit | Not published; per-token quota enforced by DIP |
| ToS posture | Per-org Bearer token; the registration agreement is bilateral DIP↔contracting-party |
| Rating (BYOK) | 🟡 **Yellow** — DPMA / KIPO shape; real REST surface with paper-contract gate |
| Rating (zero-infra proxy) | 🔴 Red — credential is per-org and not transferable |
| Primary sources | [Data Exchange home](https://api.ipthailand.go.th/data-exchange/view/home.aspx) · [Register portal](https://api.ipthailand.go.th/data-exchange/Register.aspx) |

The 21 catalogued APIs cover: 6 register-data APIs (invention patents, design patents, petty patents, TMs, copyright, music copyright, GI, unified patent chatbot), 1 TM-application search, and 13 statistics views (filings/grants by province / nationality across all rights). All published with `API_NAME_ENG`, `API_URL`, `API_METHOD`, version, and last-updated date in the catalogue DOM.

### Consumer search hosts

| Surface | Stack | Probe result |
|---|---|---|
| `patentsearch.ipthailand.go.th` | Cloudflare Turnstile + ASP.NET WebForms | 🔴 403 / Turnstile challenge |
| `tmsearch.ipthailand.go.th` | Cloudflare Turnstile + ASP.NET WebForms | 🔴 403 / Turnstile challenge |
| `search-tm.ipthailand.go.th/portal` | Cloudflare-walled | 🔴 403 / challenge |
| `search.ipthailand.go.th` | Incapsula | 🔴 HTML iframe shell only |

Consumer UIs are anti-bot-walled. The Data Exchange APIs are the only programmatic path.

### Statutes via Office of the Council of State

| Field | Value |
|---|---|
| Endpoint | `www.ocs.go.th` (formerly krisdika.go.th; OCS rebrand) |
| Auth | none |
| Format | clean HTML (Apache 2.4 / PHP 7.3, no WAF) |
| Coverage | Patent Act B.E. 2522 (1979); Trademark Act B.E. 2534 (1991); Copyright Act B.E. 2537 (1994); Industrial Design Act provisions in Patent Act; GI Act B.E. 2546 (2003); Trade Secrets Act B.E. 2545 (2002) |
| Rating | 🟢 Green — clean static-corpus surface alongside WIPO Lex |

## §4 Fees

**Policy: link only.** Reproducing fee amounts is not our job.

DIP publishes fee schedules (in THB) for filing, examination, grant, opposition, renewal, and recordation across all rights families.

- **Official schedules:** [DIP Patent fees (TH)](https://www.ipthailand.go.th/) · [DIP Trademark fees (TH)](https://www.ipthailand.go.th/)
- **Statutory basis:** [Patent Act B.E. 2522 (Office of the Council of State)](https://www.ocs.go.th/) · [Trademark Act B.E. 2534](https://www.ocs.go.th/) · [Copyright Act B.E. 2537](https://www.ocs.go.th/)

## §5 Connector strategy

### What we cover today

- TH patents with EP/PCT counterparts via [`patent_client_agents.epo_ops`](../regional/epo.md) (transitive).
- TH TMs via ASEAN TMview / WIPO Madrid Monitor (transitive).

### What we added (beta — BYOK)

- **`patent_client_agents.thai_dip`** — DIP Data Exchange connector following the DPMA / KIPO BYOK pattern. It env-gates nine MCP tools on `DIP_DATA_EXCHANGE_TOKEN` and is not exposed by the hosted demo. It covers invention patents, petty patents, design patents, trademarks, copyright notifications, music copyright, and geographical indications. The implementation uses the exact request examples and response fields published in DIP's catalogue. It is synthetic-fixture tested and live unverified. See [`specs/th-dip-connector-spec.md`](../specs/th-dip-connector-spec.md).
- **`th_statutes`** — static-law SQLite/FTS5 corpus over `www.ocs.go.th` + WIPO Lex covering the six core TH IP statutes. Same pattern as `ipo_in_statutes` / `dpma_statutes` / `legifrance_ip` / `tw_trade_secrets`.

### What we should NOT add (and why)

- **DIP on the hosted demo at `mcp.patentclient.com`** — per-org Bearer token is not transferable; BYOK on self-hosted only.
- **Consumer-UI scrape** (`patentsearch.ipthailand.go.th`, `tmsearch.ipthailand.go.th`) — Cloudflare Turnstile / Incapsula walls; brittle and against the spirit of anti-bot enforcement.

### Next steps

1. Register on Data Exchange and send the paper request letter to the DIP ICT Center. No documented foreign-developer eligibility constraint, but bilingual TH/EN paperwork.
2. Run a private smoke test for all seven datasets with an approved token.
3. Report sanitized response-shape differences without sharing tokens, personal data, protected works, or confidential records.

## §6 Open questions

- **Hague accession timeline.** Patent Act amendments approved 2022-11-29 but not ratified as of 2026-05-18. Once TH acceeds, TH designs become reachable transitively via WIPO Hague.
- **Token issuance latency.** No primary source publishes typical paper-request turnaround.
- **API stability.** Two of the 21 statistics APIs share view IDs across rights — `V_PT_REGISTER_PROVINCE` and `V_PT_REGISTER_NATION` appear in both A0024/A0026 (grants/filings) and A0025/A0027 — worth verifying whether this is a catalogue-rendering quirk or actual endpoint reuse.

## §7 References

Primary sources only.

**Service overviews:**
- [DIP Data Exchange catalogue](https://api.ipthailand.go.th/data-exchange/view/home.aspx)
- [DIP Data Exchange registration](https://api.ipthailand.go.th/data-exchange/Register.aspx)
- [DIP institutional landing](https://www.ipthailand.go.th/)

**Substantive law:**
- [Office of the Council of State (OCS) — formerly krisdika.go.th](https://www.ocs.go.th/)
- [WIPO Lex — Thailand](https://www.wipo.int/wipolex/en/legislation/profile/TH)

**Transitive coverage:**
- [PATENTSCOPE — TH Data Coverage row 76](https://patentscope.wipo.int/search/en/help/data_coverage.jsf)
- [EUIPO TMview](https://www.tmdn.org/tmview/welcome) (TH integrated)
- [ASEAN IP Portal](https://aseanip.org/) (regional aggregator, IPOPHL-operated)
- [WIPO Madrid Monitor](https://www3.wipo.int/madrid/monitor/en/) (TH accession 2017-11-07)

**Detail survey + wave:**
- [`waves/2026-05-18-secondary-nationals-wave/th-dip.md`](../waves/2026-05-18-secondary-nationals-wave/th-dip.md) — full API discovery

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-08-03 | Implemented the BYOK connector with nine MCP tools over seven register datasets. The build uses DIP's public request examples and response field tables. It remains live unverified. | [DIP catalogue](https://api.ipthailand.go.th/data-exchange/view/home.aspx) · [`specs/th-dip-connector-spec.md`](../specs/th-dip-connector-spec.md) |
| 2026-05-18 | Initial synopsis. Rating: yellow_byok. DIP runs a documented Bearer-token REST surface with 21 APIs across all six rights families; gate is paper-contract registration (DPMA / KIPO shape). Statutes-side is separately 🟢 green via `www.ocs.go.th` + WIPO Lex. | [waves/2026-05-18-secondary-nationals-wave/th-dip.md](../waves/2026-05-18-secondary-nationals-wave/th-dip.md) |
