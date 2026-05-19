# Taiwan Intellectual Property Office (TIPO / 智慧財產局)

**Layer:** national
**Jurisdiction:** TW (Republic of China / Taiwan)
**Issuing body:** Intellectual Property Office, Ministry of Economic Affairs (經濟部智慧財產局)
**Rights administered:** patent, utility_model, design (one Patent Act), trademark, copyright (registry only — not an examined right since 1985)
**Working languages:** Traditional Chinese (primary); partial English on policy pages and structured-field names; field *content* is Chinese-only
**Connector status:** partial — only the Trade Secrets Act statute (`TW/MOJ/TradeSecretsAct`) ships today; the TIPO REST API is verified green but not yet wrapped
**Last verified:** 2026-05-16
**Manifest entry:** [`coverage/sources.yaml` → `TW/MOJ/TradeSecretsAct`](../../coverage/sources.yaml) (the only TW row in the manifest today)

**Detail surveys:**
- [`connectors/tipo_taiwan.md`](../connectors/tipo_taiwan.md) — earlier 2026-05 scoping survey (some claims now stale, see §8 changelog)
- [`waves/2026-05-16-coverage-batch-2/tw-tipo.md`](../waves/2026-05-16-coverage-batch-2/tw-tipo.md) — current grounded discovery

**Higher layers covering this office transitively:**
- **None.** Taiwan is not a WIPO member (PRC blocks ROC membership); therefore TW is **not in PCT, Madrid, Hague, UPOV, or INPADOC**. TIPO is the **only** route to TW IP data. The EPO INPADOC family bridge that covers CN/JP/KR does not extend to TW patents.
- WIPO Lex carries TW statutes under the politically-charged "Taiwan Province of China" profile ([wipo.int/wipolex/en/members/profile/TW](https://www.wipo.int/wipolex/en/members/profile/TW)) — that's the *only* WIPO-administered TW resource.

---

## §1 Mission

TIPO is the unitary IP office for Taiwan, administering invention patents, utility models, designs (all under one Patent Act), trademarks, the integrated-circuit-layout registry, the copyright office (administrative only — no exam since 1985), and the Trade Secrets Act regulatory function. It is the sole authoritative source for TW IP data: because Taiwan is excluded from every WIPO treaty system, there is no PCT national-phase, no Madrid IR designating TW, no Hague Geneva-Act design designating TW, and no INPADOC family bridge that reaches the TW register. For agents covering Asia, the TIPO surface is a load-bearing piece that cannot be substituted by any higher-layer source.

## §2 What's unique here

Data points reachable **only** through TIPO (no upstream substitute):

- **TW invention/UM/design biblio + IPC/LOC + applicant nationality** (`/PatentAppl`). Filing data back to 1972 (oldest in the API is `appl-no=06202104`, `appl-date=1972/07/26`, verified live).
- **TW trademark register** (3,386,403 applications back to 1951; `appl-no=000000001`, `appl-date=1951/02/27`, applicant "盛香堂　許鉗", Taichung).
- **Patent-rights status events** including the Taiwan-specific `twins-flag` field — Article 32 of the Patent Act allows an applicant to file an invention application and a utility-model application on the same day for the same invention ("一案兩請"), with the UM granted first and revoked when/if the invention grants. `/PatentTwins` exposes these dual-track pairs.
- **TW Trade Secrets Act** — Taiwan was the **second jurisdiction in the world** (after Sweden) to enact a stand-alone trade-secrets statute (1996), with criminal penalties added 2013 and foreign-protection + secrecy-order reforms 2019. The only TW connector shipped today wraps this statute.
- **Traditional-Chinese applicant/inventor name strings**. Latin-name fields exist but are routinely null for domestic applicants — TIPO is the only place to get the Chinese name.
- **Patent linkage register pointers** (Article 60-1 of the Patent Act, 2019 amendments — the linkage *register* itself is at TFDA, but the patent-side metadata lives here).

## §3 Programmatic surfaces

### TIPO OpenData REST API (the headline asset)

| Field | Value |
|---|---|
| Endpoint | `https://cloud.tipo.gov.tw/S220/opdataapi/api/` — 15 GET operations |
| OAS spec | [`/S220/opdata/api/file/oas`](https://cloud.tipo.gov.tw/S220/opdata/api/file/oas) — Swagger 2.0, 179 KB |
| Auth | `tk` query-string token, issued by emailing a Word-form application to **ipoid@tipo.gov.tw** ([form](https://cloud.tipo.gov.tw/S220/opdata/api/information/file/api-register-form-docx)) |
| Format | JSON or XML (negotiated via `format=` param) |
| Pagination | `top` + `skip`; hard cap **6,000 rows per request** (empirically verified) |
| Rate limit | Not documented; no observed 429 on 10 rapid requests with the public demo `tk` |
| ToS | [Taiwan Open Government Data License v1.0](https://data.gov.tw/license) — perpetual / worldwide / sublicensable / **CC-BY-4.0-compatible** |
| Verdict (zero-infra proxy) | 🟢 **green** — for biblio + status. Red for full-text/claims/figures. |
| Primary source | [TIPO OpenData portal](https://cloud.tipo.gov.tw/S220/opdata) |

Real REST, real Swagger, clean license. The endpoints (`/PatentAppl`, `/PatentPub`, `/PatentRights`, `/PatentPriority`, `/PatentAnnuity`, `/PatentAlteration`, `/PatentDivide`, `/PatentTwins`, `/PatentChange`, `/TmarkAppl`, `/TmarkRights`, `/TmarkPriority`, `/TmarkPics`, `/TmarkDivide`, `/TmarkChange`) deliver bibliographic and status data only — there's no `abstract`, `claims`, `description`, or `figures` field anywhere in the OAS, and per-record full XMLs are pointed to via `ftps://ftp.tipo.gov.tw/` URLs (not the HTTPS host). Backfile: patents to 1972, TMs to 1951.

### TIPO bulk portal (cloud.tipo.gov.tw/S220/opdata)

| Field | Value |
|---|---|
| Endpoint | [`https://cloud.tipo.gov.tw/S220/opdata`](https://cloud.tipo.gov.tw/S220/opdata) — Next.js SPA |
| Auth | None for downloads |
| Format | ZIP-packed XML / CSV; weekly gazette + classification + applicant tables; XML detail per record on FTPS |
| ToS | Same Taiwan OGDL v1.0 |
| Verdict | 🟡 **yellow** — works but violates our zero-corpus constraint; skip unless API quota becomes a blocker |
| Primary source | [Portal landing](https://cloud.tipo.gov.tw/S220/opdata) |

Mentioned for completeness — the REST API supersedes it for the live-proxy use case.

### iPKM patent/trademark search UI (the user-facing portal)

| Field | Value |
|---|---|
| Endpoint | [`https://cloud.tipo.gov.tw/S400`](https://cloud.tipo.gov.tw/S400) — Next.js SPA launched 2024-12-18 |
| Auth | None (UI) |
| Format | HTML / PDF |
| ToS | UI license; scraping not addressed |
| Verdict | 🔴 **red** — no documented API; do not scrape |
| Primary source | [TIPO News 2025-05-15](https://www.tipo.gov.tw/en/tipo2/363-22677.html) |

**Replaces the TWPAT family**, which TIPO scheduled offline 2025-04-25. The older `connectors/tipo_taiwan.md` survey's discussion of TWPAT / TWPAT-simple / TWPAT6 / GPSS is largely moot now — iPKM is the unified UI. Full-text / claims / figures live here behind a JS interface; not a proxy target.

### Intellectual Property and Commercial Court (IPCC) decisions

| Field | Value |
|---|---|
| Endpoint | [`judgment.judicial.gov.tw`](https://judgment.judicial.gov.tw) + [`ipc.judicial.gov.tw`](https://ipc.judicial.gov.tw) |
| Auth | None (UI) |
| Format | HTML / PDF in Chinese only |
| Verdict | 🔴 **red** — no API; CN-only; no English equivalent of CanLII |
| Primary source | [IPCC EN site](https://ipc.judicial.gov.tw/en/mp-092.html) |

Out of scope for any TIPO-style connector — different agency (Judicial Yuan, not MOEA). Tracked but not proxied.

## §4 Fees

TIPO publishes patent and trade mark fee schedules in TWD.

- **Patent fees (EN):** [TIPO — Patent fees](https://www.tipo.gov.tw/en/cp-289-855395-15881-2.html)
- **Trademark fees (EN):** [TIPO — Trademark fees](https://www.tipo.gov.tw/en/lp-282-2.html)


## §5 Connector strategy

### What we cover today

- [`patent_client_agents.tw_trade_secrets_corpus`](../../src/patent_client_agents/) — `TW/MOJ/TradeSecretsAct`, the standalone Trade Secrets Act statute (1996, current 2024 form), shipping as a bundled SQLite/FTS5 corpus mirroring the IPO-India and DPMA shape currently being built on the `feature/tw-trade-secrets-corpus` branch.
- **Nothing else.** No TIPO patent, UM, design, or trademark coverage in production.

### What we should add

**`tipo_opdata` — wrap the REST API.** Verdict in §3 is green for biblio + status, which is exactly the surface our agent flows need for cite-checking, family-resolution backstop, applicant lookup, and TM watch. Specifics:

- Auth: `TIPO_API_KEY` env var carrying the `tk` token; provisioned via the docx form mailed to `ipoid@tipo.gov.tw`.
- Scope: all 15 OAS endpoints. The right-by-right mapping is:
  - **Patent (invention)** — `/PatentAppl?applclass=1` + `/PatentPub` + `/PatentRights?applclass=1` + `/PatentPriority` + `/PatentAnnuity` + `/PatentAlteration`.
  - **Utility model** — same endpoints with `applclass=2`. Plus `/PatentTwins` for one-application-two-rights cross-references.
  - **Design** — same endpoints with `applclass=3` (Taiwan treats design as a Patent Act category).
  - **Trademark** — `/TmarkAppl` + `/TmarkRights` + `/TmarkPriority` + `/TmarkPics` + `/TmarkDivide` + `/TmarkChange`.
- Pagination: standard top/skip helper with 6,000-row hard cap.
- Provenance / attribution: surface a TIPO/MOEA attribution string in the response envelope per OGDL §3.2.
- Caveats: biblio-only; no claim text. Document this clearly in the connector README so agents don't expect file-history depth.

The `tw_statutes` follow-on (Patent Act / Trademark Act / Copyright Act / IC Layout Act / Plant Variety) remains queued in [`BACKLOG.md`](../BACKLOG.md) — the Trade Secrets Act is row 1 and is shipping now; the other six belong in a shared `tw_statutes` corpus modeled on `ipo_in_statutes` and `dpma_statutes`.

### What we should NOT add

- **TWPAT / TWPAT-simple / TWPAT6 / iPKM scraping.** TWPAT is scheduled offline 2025-04-25 per [TIPO News 2025-05-15](https://www.tipo.gov.tw/en/tipo2/363-22677.html); iPKM is a Next.js SPA with no documented JSON API. Even if we could scrape it, the bibliographic surface is fully covered by the OpenData REST API. Skip.
- **GPSS (gpss.tipo.gov.tw).** Account-gated; aggregates IP5 + foreign offices, but the TW portion overlaps the REST API. Foreign coverage already lives in EPO OPS / Google Patents / USPTO ODP.
- **cloud.tipo.gov.tw/S282 trademark image search.** UI-only; back-end not exposed; the TM image URLs are already in `/TmarkAppl` response payloads.
- **judgment.judicial.gov.tw IPCC decisions.** Different agency (Judicial Yuan), no API, CN-only, no English access. Defer until a Judicial-Yuan open-data initiative ships.
- **TFDA Patent Linkage register.** Different agency; pharma-niche; out of scope.
- **PCT / Madrid / Hague / UPOV bridges.** Taiwan is in none of them; document the gap, don't wrap.

### Next steps

1. Register a `tk` with TIPO (email the docx form to `ipoid@tipo.gov.tw`) — owner: maintainer. ETA unknown (no published SLA).
2. Once `tk` arrives, write `tipo_opdata` connector spec under [`research/specs/`](../specs/) following the IP Australia template.
3. Build `tipo_opdata` per [`CONNECTOR_STANDARDS.md`](../../CONNECTOR_STANDARDS.md). Add `TW/TIPO/Patents`, `TW/TIPO/Trademarks`, `TW/TIPO/Designs`, `TW/TIPO/UtilityModels` rows to `coverage/sources.yaml` at ship time. (Shipped 2026-05-18 — see `src/patent_client_agents/tipo_opdata/`.)
4. Queue `tw_statutes` corpus (the remaining six IP statutes) for after `tipo_opdata`.

## §6 Open questions

- **What does the `tk` issuance SLA look like for a foreign developer?** The application form is Traditional-Chinese-only and asks for industry classification with no obvious "overseas" option. Pre-registration with a TW collaborator may be faster than trying solo. No primary source on foreign-applicant success rate found.
- **Daily / per-key quotas.** The 6,000-rows-per-request cap is confirmed; no daily ceiling is published. TIPO presumably enforces something at the back-end — discover empirically once we hold a real `tk`.
- **FTPS detail handoff.** Response payloads point at `ftps://ftp.tipo.gov.tw/ftp/TmarkRights/000/TmarkRights_1_00083309.xml`–style URLs for per-record detail. Does our CoWork allowlist + zero-infra constraint accommodate FTPS, or do we ship a biblio-only v1 and skip detail records? No primary source on whether FTPS will be replaced by HTTPS.
- **Token renewal / rotation cadence.** Not documented anywhere. Plan for "as long as it works"; alert on `status: "error"` with a token-related message.
- **Chinese-only field content.** Agent EN-only flows need a graceful-degradation policy when `appl-name-e` is null. Decide at connector-design time whether to upstream translate or leave to the agent.
- **WIPO Lex jurisdiction string.** WIPO Lex labels Taiwan as "Taiwan Province of China"; our manifest should decide whether to remap to "Taiwan" for user-facing output. Consistency with `TW/MOJ/TradeSecretsAct` matters — that one uses "Taiwan."

## §7 References

Primary sources only.

- [TIPO OpenData portal landing](https://cloud.tipo.gov.tw/S220/opdata)
- [TIPO OAS / Swagger 2.0 spec download](https://cloud.tipo.gov.tw/S220/opdata/api/file/oas) — `OpenData_API.json`, 179 KB
- [TIPO API registration form (docx)](https://cloud.tipo.gov.tw/S220/opdata/api/information/file/api-register-form-docx)
- [Sample TIPO API endpoint — TmarkPriority with demo tk](https://cloud.tipo.gov.tw/S220/opdataapi/api/TmarkPriority?format=json&tk=43b47d07-4795-45d9-819a-9c71c72e4105&top=2)
- [data.gov.tw — TIPO TM priority dataset (35466) citing the demo tk](https://data.gov.tw/en/datasets/35466)
- [Taiwan Open Government Data License v1.0](https://data.gov.tw/license)
- [TIPO News — iPKM launch announcement (2025-05-15)](https://www.tipo.gov.tw/en/tipo2/363-22677.html)
- [iPKM new search platform](https://cloud.tipo.gov.tw/S400)
- [TIPO Patent fees (EN)](https://www.tipo.gov.tw/en/cp-289-855395-15881-2.html)
- [TIPO Trademark fees (EN landing)](https://www.tipo.gov.tw/en/lp-282-2.html)
- [Patent Act (MOJ EN)](https://law.moj.gov.tw/ENG/LawClass/LawAll.aspx?pcode=J0070007)
- [Trademark Act (MOJ EN)](https://law.moj.gov.tw/ENG/LawClass/LawAll.aspx?pcode=J0070001)
- [Trade Secrets Act (MOJ EN)](https://law.moj.gov.tw/ENG/LawClass/LawAll.aspx?pcode=J0080028)
- [Intellectual Property and Commercial Court (EN)](https://ipc.judicial.gov.tw/en/mp-092.html)
- [WIPO Lex — Taiwan profile](https://www.wipo.int/wipolex/en/members/profile/TW)

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-16 | Initial synopsis. **Drift corrections vs. older [`connectors/tipo_taiwan.md`](../connectors/tipo_taiwan.md)**: (a) API host moved from `tiponet.tipo.gov.tw` to `cloud.tipo.gov.tw` (old host 301-redirects); (b) auth is `tk` *query parameter*, not an `apiKey` *header* as the publicapi.dev listing claims; (c) **TWPAT scheduled offline 2025-04-25** and replaced by iPKM at `cloud.tipo.gov.tw/S400` (launched 2024-12-18); (d) ToS resolved — Taiwan OGDL v1.0, CC-BY-4.0-compatible, sublicensing permitted; (e) 6,000-row-per-request page cap discovered empirically; (f) older "no rate limits" claim is misleading. The biblio-only scope finding from the older survey is confirmed — no full text/claims/figures in the API. | Live OAS pull + sample-mode probe + authenticated probe with demo `tk` from data.gov.tw + TIPO English news pages; full detail in [`waves/2026-05-16-coverage-batch-2/tw-tipo.md`](../waves/2026-05-16-coverage-batch-2/tw-tipo.md) |
