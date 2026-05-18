# Patent- och registreringsverket (SE/PRV) — national

**Layer:** national
**Jurisdiction:** SE (WIPO ST.3: SE)
**Issuing body:** Patent- och registreringsverket (Swedish Patent and Registration Office, PRV)
**Rights administered:** patent, trademark, design, supplementary protection certificate (including paediatric extension), municipal arms (kommunvapen); copyright collective-management oversight
**Working languages:** Swedish (primary); English (institutional pages + most response fields carry parallel `*Sv` / `*En` slots)
**Connector status:** **planned (green — undocumented but live)**
**Last verified:** 2026-05-18
**Manifest entry:** not yet listed (planned)

**Detail surveys:**
- [`waves/2026-05-18-secondary-nationals-wave/se-prv.md`](../waves/2026-05-18-secondary-nationals-wave/se-prv.md) — 2026-05-18 grounded API discovery

**Higher layers covering this office transitively:**
- **EPO INPADOC** (via [`regional/epo.md`](../regional/epo.md)) — SE-validated EP patents at biblio/family/legal-events fidelity. Sweden is an EPC contracting state and a [UPC contracting state](https://www.unified-patent-court.org/) (since 2023-06-01); EP-route patents are well-covered.
- **EUIPO** (via planned `regional/euipo.md`) — EUTMs designating SE and Community designs (RCDs / REUDs).
- **WIPO Madrid / Hague** — Madrid IRs designating SE / Hague IRs designating SE.
- **UPC** (via shipped `upc_decisions` connector) — UPC-routed disputes touching SE.

---

## §1 Mission

PRV is Sweden's national IP office — sole registrar for SE-national
patents, SE-national trademarks, SE-national designs, Swedish
supplementary protection certificates, and the niche Swedish
register of municipal arms (`kommunvapen`). Because Sweden is an
EPC contracting state, a UPC member, and an EU member, most "Swedish
patents" of commercial scale are EP-routed (covered by EPO OPS) and
most "Swedish trademarks" of any reach are EUTMs (covered by EUIPO).
PRV's genuine value-add for agents is the SE-national-only slice
— national-only trademarks, national-only designs back to 1971
(probed), national-route SE patents, Swedish SPCs, and live
register status updated daily.

What sets PRV apart in this wave: it ships its register data on
the open-data side as **CC0 1.0** and **CC BY 4.0** (the most
permissive license posture among the secondary-nationals surveyed
2026-05-18), and runs three live JSON APIs behind the new
[`search.prv.se`](https://search.prv.se/) beta UI — undocumented
but unauthenticated and well-structured.

## §2 What's unique here

- **SE-national-only patents and patent applications** — filed at PRV, not via EP.
- **SE-national-only trademarks** — filed directly with PRV, not via Madrid or EUTM. National-vs-Madrid is surfaced as `dossierTypeEn` on response records.
- **SE-national-only designs** — back to at least 1971 on probe.
- **Swedish SPCs and SPC extensions** — searchable via `/searchpatentspc/`.
- **Municipal arms (`kommunvapen`)** — separate Swedish register with its own simple + advanced + count + announcements endpoints.
- **SE-language full text** for patents (the 2019- bibliographic feed + 1973–2017 backfile have both been OCR-corrected).
- **Live status with daily updates** — both the new beta UI and the SE-Federated Register Service confirm daily refresh.
- **Aktinsyn** — file inspection for public patent applications from 2004 onward (raw originals as PDF).
- **Daily online announcements** since 2026-01-26 replacing the pre-2026 weekly PDF gazettes (Svensk Patenttidning, Svensk Varumärkestidning, Svensk Designtidning).

## §3 Programmatic surfaces

### search.prv.se backing APIs (the live REST/JSON surface)

| Field | Value |
|---|---|
| Endpoint | `https://patents-search-api.prv.se/` (patents + SPC), `https://dv-search-api.prv.se/` (TM + design + municipal arms), `https://api.prv.se/` (per-record fetch, documents, replication log) |
| Auth | **none** — no API key, no signed ToU, no developer portal |
| Format | JSON (UTF-8); offset/limit pagination with `totalHits` / `totalPages` |
| Rate limit | not published, no rate-limit headers observed on probe |
| ToS posture | no published API ToS; parallel bulk feeds are CC0 1.0 / CC BY 4.0 under Sweden's [Open Data Act SFS 2022:818](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/lag-2022818-om-den-offentliga-sektorns_sfs-2022-818/) |
| Rating (zero-infra proxy) | 🟢 **Green (undocumented)** |
| Primary source | reverse-engineered from [`search.prv.se`](https://search.prv.se/) `bundle.js` 2026-05-18; backend identified as WildFly + RESTEasy at internal `prvpublicapi-web/api/public/` |

Simple-search payload (probed and confirmed on patents, TMs, designs):

```json
{"page": 0, "pageSize": 10, "sortColumn": "filingDate", "sortOrder": "DESC", "simpleSearchText": "Volvo"}
```

Probes returned 764,224 total patent records, 3,307 hits for
"Volvo", 89 hits for "IKEA" TMs, and a 1971 design registration for
"chair". The endpoints are unauthenticated and the backend Web
Archive is named `prvpublicapi-web` deployed at `/api/public/` —
strong intent signal these are designed for outside callers.

Caveats: undocumented, versionless, schema can change on any SPA
deploy. Production deployment should send a courtesy registration
to `data@prv.se` and identify the client by User-Agent.

### was.prv.se SPD — SE-Federated Register Service

| Field | Value |
|---|---|
| Endpoint | [`https://was.prv.se/spd`](https://was.prv.se/spd) |
| Auth | none |
| Format | deep-link HTML record pages from the EPO Federated Register |
| Rating | 🟡 Yellow — HTML deep-link target, but the underlying register data is already on the search APIs |
| Primary source | [SE-Federated Register Service page](https://www.prv.se/en/patents/the-advanced-patent-guide/patent-databases/se-federated-register-service/) |

PRV publishes biblio + status + proprietor + last-paid renewal-fee
date to the EPO's federated register. Useful as a cross-link, not
as a primary surface.

### data.prv.se — open data bulk

| Field | Value |
|---|---|
| Catalog | [`https://data.prv.se/`](https://data.prv.se/) (DCAT/RDF at [`/index.rdf`](https://data.prv.se/index.rdf)) |
| Distribution | FTP — `ftp://opendata.prv.se`, user `OpenDataSource`, password `opendata` |
| Format | XML (bibliographic + full-text), CSV (1973–2017 backfile), PDF (gazettes, kind codes, DPK lists) |
| License | **CC0 1.0** (most patent + TM datasets) and **CC BY 4.0** (bibliographic + DPK) |
| Rating | 🔴 Red against zero-infra proxy — bulk only, FTP-only — but **clean license posture** informs the live API |
| Primary source | [Open public data (EN)](https://www.prv.se/en/about-us/open-public-data/) |

17 datasets covering Swedish patent documents from 1885 forward,
trademark exports, design tidning, kind codes, and the IPC↔DPK
concordance. Useful as a backfile snapshot and as the license
governance signal for the live APIs.

### tc.prv.se SPD — legacy UI (frozen)

| Field | Value |
|---|---|
| Endpoint | [`https://tc.prv.se/spd/search`](https://tc.prv.se/spd/search?lang=en) |
| Auth | none |
| Format | HTML |
| Rating | 🔴 Red — HTML scrape; frozen 2026-01-26 |
| Primary source | [About Swedish Patent Database](https://tc.prv.se/spd/about?lang=en) |

Retained during the transition period for pre-2000 material the
new beta does not yet surface. Not a connector target.

### Sveriges dataportal — federal open data

| Field | Value |
|---|---|
| Endpoint | [`https://www.dataportal.se/`](https://www.dataportal.se/) (CKAN-flavoured) |
| Rating | 🔴 N/A — PRV's data lives on `data.prv.se`, indexed via DCAT into the federal portal but not separately exposed |

### WIPO IP API Catalog

| Field | Value |
|---|---|
| Endpoint | [`https://apicatalog.wipo.int/`](https://apicatalog.wipo.int/) |
| Result | **0 PRV entries** as of 2026-05-18 (179 total across DPMA, EPO, EUIPO, IP Australia, JPO, MOIP KOREA, QAZ, UPRP, USPTO, WIPO) |
| Rating | informational — confirms the search APIs are undocumented from the canonical-inventory standpoint |

## §4 Fees

**Policy: link only.**

PRV publishes fee schedules (in SEK) covering patent filing,
search, examination, grant, opposition, renewal, and SPC fees;
trademark filing per class + renewals; design filing + renewals;
plus miscellaneous services (file inspection, certified copies,
priority documents). Statutory basis is the Patent Act
(`patentlagen` 1967:837), the Trademark Act (`varumärkeslagen`
2010:1877), and the Design Protection Act (`mönsterskyddslagen`
1970:485), each with implementing fee ordinances set by government
regulation.

- **Official patent fee schedule:** [Fees and payment (patents) EN](https://www.prv.se/en/patents/the-advanced-patent-guide/fees-and-payment/)
- **Official trademark fee schedule:** [Fees and payment (trademarks) EN](https://www.prv.se/en/trademarks/prepare-for-the-trademark-application/fees-and-payment/)
- **Consolidated PRV fees PDF:** [globalassets/dokument/avgifter/fees.pdf](https://www.prv.se/globalassets/dokument/avgifter/fees.pdf)
- **Statutory basis (patents):** [Patentlag (1967:837)](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/patentlag-1967837_sfs-1967-837/)
- **Statutory basis (trademarks):** [Varumärkeslag (2010:1877)](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/varumarkeslag-20101877_sfs-2010-1877/)
- **Statutory basis (designs):** [Mönsterskyddslag (1970:485)](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/monsterskyddslag-1970485_sfs-1970-485/)
- **Live fee calculator:** [tc.prv.se/patentwebshop/servlet/showfees/](https://tc.prv.se/patentwebshop/servlet/showfees/?lang=EN) (servlet referenced from the new SPA)

Notable discount programmes *(name only)*:

- **Patent application without examination fee** — small-applicant pathways under `patentlagen` ch. 2.
- **SME fund (EUIPO Ideas Powered for Business)** — partial reimbursement of national trademark and design fees, [administered jointly with EUIPO for SE applicants](https://euipo.europa.eu/tunnel-web/secure/webdav/guest/document_library/contentPdfs/SME-FUND/2025/SME-funds-2025-Fees-file-Sweden.pdf).

## §5 Connector strategy

### What we cover today

- **SE-validated EP patents at biblio / family / legal-events fidelity** — transitively via [`patent_client_agents.epo_ops`](../regional/epo.md) (country code `SE`).
- **EUTMs designating SE and Community designs (RCD / REUD)** — transitively via the planned EUIPO connector.
- **Madrid IRs / Hague IRs designating SE** — via planned WIPO Madrid / Hague connectors.
- **UPC-routed disputes touching SE** — via shipped `upc_decisions` connector.

### What we should add (planned — green, undocumented)

- **`patent_client_agents.prv`** — thin connector against the three
  search-API hosts. Pattern: zero-auth REST/JSON like
  Google Patents, with the wrinkle that the schema is reverse-
  engineered and versionless. Initial scope:
  - `patents-search-api.prv.se/searchpatent/patentsimplesearch/` and `…/patentadvancedsearch/`
  - `dv-search-api.prv.se/searchtrademark/tmsimplesearch/` and `…/tmadvancedsearch/`
  - `dv-search-api.prv.se/searchdesign/dssimplesearch/` and `…/dsadvancedsearch/`
  - `patents-search-api.prv.se/searchpatentspc/patentsearchspc/`
  - `dv-search-api.prv.se/searchtrademark/municipalArmAdvancedsearch/`
  - Count endpoints (`countPatent`, `counttrademark`, `countdesign`, `countmunicipalarm`) as cheap probes.
  - Per-record GET on `api.prv.se/patents/applications/{id}` after one more bundle-extraction pass to resolve the `applicationType` enum.

**Closes the SE-national-only TM + design + SPC + national-patent gaps.**
Estimated 3-5 days build — most of the time is structured
field-name extraction from the SPA bundle (the advanced-search
payload), then writing the response models. The simple-search path
is already proved-end-to-end.

### What we should NOT add (and why)

- **HTML scrape of the new `search.prv.se` UI.** The backing APIs
  are the better target — the SPA only adds rendering on top.
- **HTML scrape of legacy `tc.prv.se/spd`.** Frozen 2026-01-26.
  Treat as a pre-2000 fallback only if/when it matters.
- **FTP bulk ingestion of `opendata.prv.se`.** Violates the
  zero-infra constraint. The license posture (CC0 / CC BY 4.0) is
  informationally useful but bulk ingestion is out of scope.
- **EPO Federated Register Service (`was.prv.se/spd`) deep links.**
  Same data is already on the JSON APIs.

### Next steps

1. **Send a courtesy registration to `data@prv.se`** before the
   hosted demo turns on. Identify ourselves, ask for breakage
   notice, confirm we're identifying the client by User-Agent.
   Sweden's Open Data Act (SFS 2022:818) provides statutory cover,
   but proactive contact is cheap insurance against schema-change
   surprises.
2. **One more bundle-extraction pass** to resolve: (a) the
   `applicationType` enum string for `/patents/applications/{id}`
   GET, (b) the advanced-search field names per right-type, (c)
   the patent status-code lookup (response carries numeric codes
   like `"116"` with multilingual display-text slots that need
   resolution).
3. **Write `specs/se-prv-connector-spec.md`** — patterns:
   - Three hosts, one connector class.
   - Versionless schema: validate response shape on every call,
     surface clean errors when fields disappear.
   - Polite caching: 5 min for status, 24 h for record bodies.
   - User-Agent identifying the project + contact link.
4. **Probe a granted patent** to confirm whether `cpcClasses` /
   `ipcClasses` / `dpkClasses` populate post-classification, vs.
   the empty arrays observed on freshly-filed Volvo applications.

## §6 Open questions

- **Status code lookup.** Patent records carry numeric `status`
  codes (`"116"`) with multilingual display-text slots returning
  `null` on probe — needs a separate `/codes/` or `/status/`
  endpoint we haven't yet discovered, or the display text comes
  from the SPA's i18n bundle.
- **applicationType enum.** GET `/patents/applications/{id}?applicationType=…`
  rejects `NAT`, `NATIONAL`, `EP`, `PCT`, and lowercase variants.
  The SPA's record-detail view sends the correct value.
- **Madrid IR coverage in the TM index.** Both national and Madrid
  IRs likely live in the same index (`dossierTypeEn` slot suggests
  a discriminator); needs filter-confirmation.
- **Hague IR coverage in the design index.** Same question.
- **Page-size upper bound.** SPA defaults to 10–20; the cap is
  undocumented.
- **Rate-limit behavior under load.** No headers observed on
  single-pager probes — production patterns unknown.
- **Pre-2000 material gap.** PRV's own beta notice acknowledges
  limitations; the magnitude isn't quantified.
- **Nordic cluster — NIPO / DKPTO / PRH.** Worth checking
  whether the Norwegian, Danish, and Finnish offices follow the
  same pattern (open, English-friendly, undocumented JSON behind
  a modern SPA). PRH (Finland) is historically the most API-open.

## §7 References

Primary sources only — `prv.se`, `search.prv.se`, `data.prv.se`,
`apicatalog.wipo.int`, `riksdagen.se` for statutes.

**Service overviews:**
- [PRV (EN home)](https://www.prv.se/en/)
- [Sök i PRV:s databaser — beta search](https://search.prv.se/)
- [About Svensk Patentdatabas (EN)](https://tc.prv.se/spd/about?lang=en)
- [Search PRV's databases — beta launch announcement (EN)](https://www.prv.se/en/knowledge-and-support/search-databases/)
- [Patent databases (EN)](https://www.prv.se/en/patents/patent-databases/)
- [Trademark databases (EN)](https://www.prv.se/en/trademarks/trademark-databases/)
- [SE-Federated Register Service (EN)](https://www.prv.se/en/patents/the-advanced-patent-guide/patent-databases/se-federated-register-service/) — deep-links at [`https://was.prv.se/spd`](https://was.prv.se/spd)

**Open data and licenses:**
- [Open public data (EN)](https://www.prv.se/en/about-us/open-public-data/)
- [Öppna data — Swedish catalog index](https://www.prv.se/sv/om-oss/oppna-data/)
- [data.prv.se catalog](https://data.prv.se/)
- [data.prv.se DCAT/RDF manifest](https://data.prv.se/index.rdf)
- [FTP server](ftp://opendata.prv.se/) (`OpenDataSource` / `opendata`)
- [Sveriges dataportal (federal)](https://www.dataportal.se/)
- [Aktinsyn — public patent applications from 2004 dataset](https://data.prv.se/dataset.jsp?uuid=888c893c424148159b41c080653dce973aa8d488e22d42c3aded43618c300f85)

**Fees:**
- [Fees and payment (patents) EN](https://www.prv.se/en/patents/the-advanced-patent-guide/fees-and-payment/)
- [Fees and payment (trademarks) EN](https://www.prv.se/en/trademarks/prepare-for-the-trademark-application/fees-and-payment/)
- [Consolidated PRV fees PDF](https://www.prv.se/globalassets/dokument/avgifter/fees.pdf)
- [Live fee calculator (servlet)](https://tc.prv.se/patentwebshop/servlet/showfees/?lang=EN)

**Substantive law (Swedish statutes via Riksdagen):**
- [Patentlag (1967:837)](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/patentlag-1967837_sfs-1967-837/)
- [Varumärkeslag (2010:1877)](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/varumarkeslag-20101877_sfs-2010-1877/)
- [Mönsterskyddslag (1970:485)](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/monsterskyddslag-1970485_sfs-1970-485/)
- [Lag (2022:818) om den offentliga sektorns tillgängliggörande av data](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/lag-2022818-om-den-offentliga-sektorns_sfs-2022-818/) — Sweden's Open Data Act transposing [EU Directive 2019/1024](https://eur-lex.europa.eu/eli/dir/2019/1024)
- [Lag (1986:1009) om Patent- och registreringsverket](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/forordning-19861009-med-instruktion-for_sfs-1986-1009/) — PRV's instructional ordinance

**Cross-office context:**
- [WIPO IP API Catalog](https://apicatalog.wipo.int/) — probed 2026-05-18; 0 PRV entries
- [PCT Applicant's Guide — Sweden](https://pctlegal.wipo.int/eGuide/view-doc.xhtml?doc-code=SE&doc-lang=en)
- [The Swedish Patent and Registration Office (Government.se)](https://www.government.se/government-agencies/the-swedish-patent-and-registration-office/)

**Detail surveys + waves:**
- [`waves/2026-05-18-secondary-nationals-wave/se-prv.md`](../waves/2026-05-18-secondary-nationals-wave/se-prv.md) — 2026-05-18 grounded API discovery

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-18 | Initial synopsis; rating **`green_undocumented`**. Findings: (a) PRV runs three unauthenticated JSON APIs behind the new [`search.prv.se`](https://search.prv.se/) beta (launched 2026-01-26) — `patents-search-api.prv.se`, `dv-search-api.prv.se`, and `api.prv.se` — covering patents, SPCs, trademarks, designs, and municipal arms, all probed end-to-end with structured rich responses; (b) backend leak reveals a JAX-RS/RESTEasy WildFly stack with Web Archive named **`prvpublicapi-web`** deployed at **`/api/public/`** — strong "designed for outside callers" intent signal; (c) parallel bulk distributions on [`data.prv.se`](https://data.prv.se/) are licensed **CC0 1.0** and **CC BY 4.0**, the most permissive license posture among the secondary-nationals surveyed 2026-05-18; (d) Sweden's [Open Data Act SFS 2022:818](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/lag-2022818-om-den-offentliga-sektorns_sfs-2022-818/) provides statutory cover for register-data reuse; (e) [WIPO IP API Catalog](https://apicatalog.wipo.int/) returns 0 PRV entries — the APIs are undocumented from the canonical-inventory standpoint. Caveats: undocumented + versionless + no published API ToS — production posture is "courtesy-register with `data@prv.se` + watch for breakage." | [waves/2026-05-18-secondary-nationals-wave/se-prv.md](../waves/2026-05-18-secondary-nationals-wave/se-prv.md) |
