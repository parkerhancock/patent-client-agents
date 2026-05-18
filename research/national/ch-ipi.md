# Swiss Federal Institute of Intellectual Property (CH/IPI) — national

**Layer:** national
**Jurisdiction:** CH (WIPO ST.3: CH)
**Issuing body:** Eidgenössisches Institut für Geistiges Eigentum / Institut Fédéral de la Propriété Intellectuelle (IPI / IGE)
**Rights administered:** patent, trademark, design, SPC (supplementary protection certificate, including paediatric extension)
**Working languages:** German, French, Italian, English (API docs English-only)
**Connector status:** **planned (BYOK)** — IPI datadelivery API permits per-user self-hosted access via signed Terms of Use
**Last verified:** 2026-05-18
**Manifest entry:** not yet listed (planned)

**Detail surveys:**
- [`waves/2026-05-18-secondary-nationals-wave/ch-ipi.md`](../waves/2026-05-18-secondary-nationals-wave/ch-ipi.md) — 2026-05-18 grounded API discovery (437 lines)

**Higher layers covering this office transitively:**
- **EPO INPADOC** (via [`regional/epo.md`](../regional/epo.md)) — CH-validated EP patents at the biblio/family layer; CH is an EPC contracting state and London Agreement country (EP grants automatically effective in CH+LI as a unified patent territory).
- **WIPO Designview** — CH national designs since 2017-11-20 (the only programmatic path for CH designs; there is no `DesignSearch` action on IPI's own API).
- **WIPO Madrid** — Madrid IRs designating CH (also surfaced through IPI's `TrademarkSearch` action).

---

## §1 Mission

IPI is Switzerland's federal IP office. As a non-EU EPC contracting state with the unique CH+LI unified patent territory (1978 CH-LI Patent Treaty), CH register data is the only authoritative source for Swiss-national patents, SPCs (including paediatric extensions live since 2019-01-01), national-only Swiss trademarks, and Swiss designs. Agents working on European IP that touches Switzerland — pharmaceutical SPC strategy, Swiss-only TM portfolios, EP validation status in CH — need IPI as a primary register, not EPO INPADOC.

## §2 What's unique here

- **CH SPCs + paediatric SPCs** — EPO does not register national SPCs; IPI is the only path. Paediatric extension regime live since 2019-01-01.
- **CH+LI unified patent territory** — under the 1978 Treaty, the IPI register is canonical for both Switzerland and Liechtenstein on the patent side.
- **National-only Swiss trademarks** — those not filed via Madrid IR.
- **Swiss-language full text** — DE/FR/IT class headings and substantive text not surfaced in INPADOC.
- **CH designs** — available via WIPO Designview only on the programmatic side (no IPI `DesignSearch` action exists).

## §3 Programmatic surfaces

### IPI datadelivery API (the real live surface)

| Field | Value |
|---|---|
| Endpoint | `https://www.swissreg.ch/public/api/v1` (POST, XML body) |
| Auth | OpenID Connect / OAuth 2.0 ROPC grant at `idp.ipi.ch/auth/realms/egov` (Keycloak); username + password from a signed ToU account |
| Format | XML on WIPO ST.96 + Swiss-Interoperable-Superset extensions; ZIP-bundle option with `/response.xml` plus images/documents |
| Cost | Free of charge — "electronic delivery of IP data is available free of charge to anyone interested" |
| Rate limit | **2 GiB / 24-hour rolling window** per user; 12 concurrent requests; penalty model accumulates on 4xx/5xx (2048 cap → 15-min cooldown) |
| ToS posture | Wet-signed ToU posted to Bern; §2 forbids passing access details to third parties; §3 anti-redistribution clause runs with the data |
| Rating (BYOK) | 🟢 **Green for self-hosted per-user access** — same shape as JPO / KIPO / INPI France |
| Rating (zero-infra proxy) | 🔴 Red — §2 forbids credential sharing |
| Primary source | [IPI — Data delivery via API](https://www.ige.ch/en/services/digital-resources/ip-data/data-delivery-api) · [API docs](https://www.swissreg.ch/public/apidocs/) (last updated 2026-03-02) · [Terms of Use PDF](https://www.ige.ch/fileadmin/user_upload/schuetzen/marken/e/Terms_of_Use_for_the_Delivery_of_Data.pdf) |

Six action types: `TrademarkSearch`, `PatentSearch`, `PatentPublicationSearch`, `SPCSearch`, `SPCPublicationSearch`, plus the diagnostic `UserQuota` and `Echo`. **No `DesignSearch` action** — designs are explicitly out of scope on the API (IPI's own landing page confirms "Currently, trademark and patent data records can be obtained via API"). Query language is structured XML (`ApiRequest` documents with `Query` / `Require` / per-right namespace fields), not URL parameters. Pagination is cursor-style via `<Continuation>` elements. Session token capped at 600 minutes.

### Raw patent CSV bulk

| Field | Value |
|---|---|
| Endpoint | [Patent data page](https://www.ige.ch/en/services/digital-resources/ip-data/patent-data) |
| Auth | none |
| Format | CSV, filing dates from 1978-01-01, refreshed every six months |
| Rating | 🔴 Red — bulk-only; violates zero-infra constraint |

Companion to the API, not a replacement. Useful as a backfile snapshot but not for live register lookups.

### Swissreg web client (`database.ipi.ch` / `swissreg.ch` UI)

| Field | Value |
|---|---|
| Endpoint | [database-client/](https://www.swissreg.ch/database-client/) |
| Auth | none (public UI) |
| Format | HTML |
| Rating | 🔴 Red — UI scrape; supported path is the datadelivery API |

The classic Swissreg HTML UI is being retired in favor of `database.ipi.ch`; **the API host at `swissreg.ch/public/api/v1` is the long-term plan**, not the HTML side.

### opendata.swiss federal portal

| Field | Value |
|---|---|
| Endpoint | [opendata.swiss CKAN API](https://opendata.swiss/api/3/action/package_search?fq=organization:eidgenoessisches-institut-fuer-geistiges-eigentum) |
| Result | `count: 0` as of 2026-05-18 |
| Rating | 🔴 N/A — IPI does not publish to the federal open-data portal |

Notable structural choice — most other Swiss federal bodies (BFS, Swisstopo) do publish through opendata.swiss; IPI's only programmatic channels are the datadelivery API and the patent CSV bulk.

## §4 Fees

**Policy: link only.** Reproducing fee amounts is not our job.

IPI publishes a fee schedule (in CHF) covering filing, examination, grant, opposition, renewal, and recordation fees for patents, SPCs, trademarks, and designs. The datadelivery API itself is free of charge.

- **Official schedule:** [IPI — Fees](https://www.ige.ch/en/services/fees)
- **Statutory basis:** [Federal Act on Patents for Inventions (PatG / LBI)](https://www.fedlex.admin.ch/eli/cc/1955/871_893_899/en) · [Federal Act on the Protection of Trade Marks (MSchG / LPM)](https://www.fedlex.admin.ch/eli/cc/1993/274_274_274/en) · [Federal Act on the Protection of Designs (DesG / LDes)](https://www.fedlex.admin.ch/eli/cc/2002/289/en)

## §5 Connector strategy

### What we cover today

- CH-validated EP patents at biblio/family fidelity via [`patent_client_agents.epo_ops`](../regional/epo.md) (transitive).
- CH designs via WIPO Designview (no direct IPI surface).

### What we should add (planned — BYOK)

- **`patent_client_agents.ipi_swissreg`** — datadelivery API connector following the JPO / INPI France BYOK pattern. Env-gates MCP tools on `IPI_DATA_USERNAME` + `IPI_DATA_PASSWORD`; not exposed by the hosted demo. Covers `TrademarkSearch`, `PatentSearch`, `PatentPublicationSearch`, `SPCSearch`, `SPCPublicationSearch`. **Closes the SPC + CH-national TM + CH-language full-text gaps.** Estimated 4-6 days build given the XML query language + cursor pagination + penalty-model error handling (which is unusual — accumulates 4xx/5xx penalties that slow concurrency before hard cooldown; clients with sloppy error handling can dig themselves into a hole).

### What we should NOT add (and why)

- **IPI on the hosted demo at `mcp.patentclient.com`** — §2 of the ToU forbids passing access details to third parties; BYOK on self-hosted only.
- **CSV bulk ingestion** — six-monthly snapshot violates the zero-infra constraint; the API is the supported live path.
- **HTML scrape of the Swissreg / database.ipi.ch UI** — the classic UI is being retired; the API is the long-term plan.
- **`DesignSearch` action** — does not exist on IPI's API; CH designs route via WIPO Designview.

### Next steps

1. Sign and post the IPI Terms of Use to Stauffacherstrasse 65/59g, 3003 Bern — wet signature, no self-service portal. Foreign signup is permitted (no Swiss-residency requirement on the ToU's face), but the postal step adds real latency.
2. Write `specs/ch-ipi-connector-spec.md`. Pattern: JPO env-gating + OIDC ROPC token refresh + XML `ApiRequest` document builder + `<Continuation>` cursor pagination + penalty-aware retry/backoff.
3. Decide whether to record live cassettes (requires the credentials) or ship with synthesized fixtures (KIPO / INPI France precedent — live cassettes pending downstream-user credentials).

## §6 Open questions

- **Postal latency to credentials.** No primary source publishes a typical turnaround time from sending the signed ToU to receiving credentials. German Bundesbehörde analogues run 2-6 weeks.
- **Penalty model in practice.** The docs describe 4xx/5xx penalties as scaling concurrency down before lockout, but the exact thresholds for permit-release delay (`up to 15s`) and concurrency narrowing are undocumented.
- **CH+LI on the TM and design side.** The patent side is clearly unified by the 1978 Treaty; for TMs and designs LI runs through a separate Liechtenstein Office of Economic Affairs. Worth a separate LI/LO survey if Liechtenstein-only filings ever surface as a need.

## §7 References

Primary sources only.

**Service overviews:**
- [IPI — Data delivery via API](https://www.ige.ch/en/services/digital-resources/ip-data/data-delivery-api)
- [IPI — Patent data](https://www.ige.ch/en/services/digital-resources/ip-data/patent-data)
- [Swissreg trademark database help](https://www.ige.ch/en/services/digital-resources/databases-and-directories/swissreg/trade-mark-database)
- [Swissreg design database help](https://www.ige.ch/en/services/digital-resources/databases-and-directories/swissreg/design-database)

**Technical specs:**
- [API docs index](https://www.swissreg.ch/public/apidocs/) (last updated 2026-03-02)
- [Single-page LLM-friendly docs](https://www.swissreg.ch/public/apidocs/singlehtml/index.html)
- [Reference — Authentication](https://www.swissreg.ch/public/apidocs/reference/authentication.html)
- [Reference — Usage Limits](https://www.swissreg.ch/public/apidocs/reference/limits.html)
- [Schema catalog (XSDs)](https://schema.ige.ch/xml/)

**Legal terms:**
- [Terms of Use for the Delivery of Data PDF (2024-10-31)](https://www.ige.ch/fileadmin/user_upload/schuetzen/marken/e/Terms_of_Use_for_the_Delivery_of_Data.pdf)
- [IPI Legal notice](https://www.ige.ch/en/legal-notice)

**Substantive law:**
- [Federal Act on Patents (PatG / LBI)](https://www.fedlex.admin.ch/eli/cc/1955/871_893_899/en)
- [Federal Act on Trade Marks (MSchG / LPM)](https://www.fedlex.admin.ch/eli/cc/1993/274_274_274/en)
- [Federal Act on Designs (DesG / LDes)](https://www.fedlex.admin.ch/eli/cc/2002/289/en)

**Detail survey + wave:**
- [`waves/2026-05-18-secondary-nationals-wave/ch-ipi.md`](../waves/2026-05-18-secondary-nationals-wave/ch-ipi.md) — full 437-line API discovery

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-18 | Initial synopsis. Rating: yellow_byok. Datadelivery API is clean and free; blockers are contractual (wet-signed ToU posted to Bern + §2 prohibits credential sharing). Designs are an explicit gap on the API — only WIPO Designview covers them. | [waves/2026-05-18-secondary-nationals-wave/ch-ipi.md](../waves/2026-05-18-secondary-nationals-wave/ch-ipi.md) |
