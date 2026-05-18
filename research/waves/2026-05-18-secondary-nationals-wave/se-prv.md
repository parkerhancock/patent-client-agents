# PRV Sweden (SE) — Patents, Trademarks, Designs API Discovery

**Date:** 2026-05-18
**Scope:** Determine whether Patent- och registreringsverket (PRV,
the Swedish Patent and Registration Office) exposes a public,
queryable REST/JSON/XML API that we can proxy at runtime, zero
infrastructure on our side. Bulk dumps and HTML-only surfaces would
be a **red** verdict; per-user BYOK would be yellow.

**TL;DR:** **Green-ish — undocumented but live REST/JSON.** Behind
the new beta UI launched 2026-01-26 at
[`search.prv.se`](https://search.prv.se/) ("Sök i PRV:s databaser")
PRV runs **three unauthenticated JSON APIs**:
[`patents-search-api.prv.se`](https://patents-search-api.prv.se/),
[`dv-search-api.prv.se`](https://dv-search-api.prv.se/) (trademarks
+ designs + municipal arms), and [`api.prv.se`](https://api.prv.se/)
(per-record fetch, documents, drawings, SPC, replication log). All
three return application/json, all three accepted POST search calls
on probe 2026-05-18 with no auth, no API key, no CORS preflight
friction. A 4xx leaked the underlying stack —
`wildflyexternprod.prv.se:8080/prvpublicapi-web/api/public/...` —
i.e. a JAX-RS / RESTEasy service on WildFly with a `public` path
component, which strongly suggests these endpoints are *intended* to
be reachable. No developer portal, no documentation, no advertised
ToS for the API specifically; the only governance signal is PRV's
[`data.prv.se`](https://data.prv.se/) open-data catalog, whose
bulk distributions ship under **CC0 1.0** (patent docs, gazettes,
authority files) and **CC BY 4.0** (patent bibliographic data),
attribution to PRV.

Patents are also covered transitively via **EPO OPS / INPADOC** at
biblio/family fidelity; what PRV adds is **SE-national-only TMs and
designs**, **SE-national patent applications with fresh status**
(daily-updated register), **SE-language full text**, and Swedish
**Supplementary Protection Certificates**. PRV also runs the
SE-Federated Register Service for EPO Federated Register (deep
linking from FRS at [`https://was.prv.se/spd`](https://was.prv.se/spd)).

**Verdict: 🟢 Green (with caveats).** The endpoints are
unauthenticated, JSON, rate-limit-unobserved on a single-pager
probe, and the licenses on the parallel bulk feeds are
CC0 / CC BY 4.0 — strongest license posture in this wave (vs.
IPI's wet-signed §2 anti-redistribution and ÖPA's
personal-use-only Impressum). Caveats: the API is **undocumented**
(reverse-engineered from the SPA bundle), **versionless** (the SPA
ships a single `bundle.js` that can change schemas any deploy), and
the beta UI itself has acknowledged **older-material gaps** for
patents pre-2000 during the transition. Production posture would be
"watch for breakage" plus a contact-PRV-and-confirm step before the
hosted demo, not "wire it up and forget."

---

## 1. Endpoint

PRV's *consumer* search surface lives at four hosts:

### 1.1 search.prv.se beta UI (the new one — January 2026)

| | |
|---|---|
| Host | [`https://search.prv.se/`](https://search.prv.se/) |
| Shape | Single-page app — `bundle.js` (~1.4 MB, classic
React/Redux). Not Next.js, no Server Actions. |
| Auth | none |
| Status | beta, launched [2026-01-26](https://www.prv.se/en/knowledge-and-support/search-databases/) |
| Replaces | the legacy tc.prv.se SPD UI (frozen 2026-01-26, kept for pre-2000 material during transition) |

The SPA's network calls are plain `fetch()` POSTs to three
back-end hosts. They're enumerable directly from `bundle.js`:

### 1.2 patents-search-api.prv.se (the patent search API)

| Path | Method | Purpose |
|---|---|---|
| `/searchpatent/patentsimplesearch/` | POST | Free-text simple search |
| `/searchpatent/patentadvancedsearch/` | POST | Field-typed advanced search |
| `/searchpatentannouncement/patentsearchannouncements/` | POST | Search Svensk Patenttidning announcements |
| `/searchpatentspc/patentsearchspc/` | POST | Search SPCs |
| `/searchpatent/countPatent/` | GET | Total records count (probe 2026-05-18: `764224`) |
| `/patent/health/elasticsearchpatent` | GET | Backend Elasticsearch health (returns `true`) |

The `/searchpatent/...` endpoints accept a JSON body of shape:

```json
{
  "page": 0,
  "pageSize": 10,
  "sortColumn": "filingDate",
  "sortOrder": "DESC",
  "simpleSearchText": "Volvo"
}
```

Probe with `simpleSearchText: "Volvo"` returned 3,307 hits across
1,102 pages, with rich per-record data (see §5).

### 1.3 dv-search-api.prv.se (trademarks + designs + municipal arms)

| Path | Method | Purpose |
|---|---|---|
| `/searchtrademark/tmsimplesearch/` | POST | TM simple search |
| `/searchtrademark/tmadvancedsearch/` | POST | TM advanced search |
| `/searchtrademark/counttrademark` | GET | Total TM count |
| `/searchtrademark/municipalarmsimplesearch/` | POST | Municipal arms simple |
| `/searchtrademark/municipalArmAdvancedsearch/` | POST | Municipal arms advanced |
| `/searchtrademark/municipalarmssearchannouncements/` | POST | Municipal arms announcements |
| `/searchtrademark/countmunicipalarm` | GET | Municipal arms count |
| `/searchtrademarkpublication/tmpublicationsearch/` | POST | TM publication (Varumärkestidning) |
| `/searchdesign/dssimplesearch/` | POST | Design simple search |
| `/searchdesign/dsadvancedsearch/` | POST | Design advanced search |
| `/searchdesign/countdesign` | GET | Total design count |
| `/searchdesignpublication/dspublicationsearch/` | POST | Design publication (Designtidning) |
| `/dv/health/elasticsearchdv` | GET | Backend Elasticsearch health |

Same JSON payload shape. Probe with `simpleSearchText: "IKEA"`
returned 89 SE-national trademarks across 44 pages, including
classes, applicant address (with Swedish corporate identity number
`organisationsnummer`), filing/expiry/registration dates, and
status both EN + SV. Design probe with `"chair"` matched a 1971
expired design registration, confirming archive coverage.

### 1.4 api.prv.se (per-record fetch, documents, replication log)

| Path | Purpose |
|---|---|
| `/patents/applications/{id}?applicationType={enum}` | Get patent application — enum value unknown, returned 400 "Unknown applicationType" on probe with NAT / NATIONAL / N / EP / PCT |
| `/patents/documents/...` | Patent document fetch |
| `/patents/drawings/...` | Patent drawings |
| `/patents/spc/...` | SPC records (returns 404 without an id) |
| `/designs/applications/...` | Design application records |
| `/designs/base64DesignDocument/...` | Design documents (base64-encoded) |
| `/designs/diary/...` | Design diary entries |
| `/trademarks/applications/...` | TM application records |
| `/trademarks/base64Document/...` | TM documents (base64) |
| `/trademarks/diary/...` | TM diary entries |
| `/replicationLog/replicationDomain/{Design\|Trademark}` | Change log for replication clients |
| `/health/databasedv` | Backend DB health (returns `true` text/plain) |

The applicationType enum needs confirmation — best done by reading
the SPA's call to this endpoint, which the bundle does (but the
enum string didn't appear in the search probes). Behind the host
sits **WildFly + JAX-RS / RESTEasy** at internal address
`wildflyexternprod.prv.se:8080/prvpublicapi-web/api/public/`, leaked
by a 404 error message — the `prvpublicapi-web` Web Archive name
and the `/api/public/` path strongly suggest these endpoints are
*intended* to be reachable (vs. an accidentally-exposed internal).

### 1.5 Legacy surfaces (still up, but transitional)

| Host | State |
|---|---|
| [`tc.prv.se/spd`](https://tc.prv.se/spd/search?lang=en) | Frozen 2026-01-26; retained for pre-2000 material during transition |
| [`was.prv.se/spd`](https://was.prv.se/spd) | EPO Federated Register Service (FRS) deep-link target |
| [`tc.prv.se/spt-visa-web/servlet/pdf/`](https://tc.prv.se/spt-visa-web/servlet/pdf/) | Servlet still referenced from the new SPA for PDF document delivery |
| [`resources.prv.se/downloadAllDocuments.jsp`](https://resources.prv.se/) | JSP-era bulk document download (called from new SPA) |
| [`tc.prv.se/patentwebshop/servlet/showfees/`](https://tc.prv.se/) | Live fee calculator (servlet) |

### 1.6 data.prv.se — open data bulk

| | |
|---|---|
| Catalog | [`https://data.prv.se/`](https://data.prv.se/) (also at [`data.prv.se/index.rdf`](https://data.prv.se/index.rdf) as DCAT/RDF) |
| Distribution | FTP (`ftp://opendata.prv.se`, user `OpenDataSource`, password `opendata`, anonymous-style) |
| Datasets | 17 — patent docs / TM exports / design tidning / gazettes / kind codes / IPC↔DPK concordance / Aktinsyn case file index |
| License | CC0 1.0 (most patent + TM datasets) and CC BY 4.0 (bibliographic + DPK lists) |
| Contact | data@prv.se |
| Verdict | 🔴 Red against zero-infra proxy — bulk only, FTP-only — but **clean license posture** that informs how to treat the live API |

## 2. Auth

**None observed.** Every endpoint probed on 2026-05-18 served
HTTP 200 (search/count/health) or 4xx with structured error bodies
(missing/unknown parameters) without any `WWW-Authenticate`,
`Authorization` header, cookie, CSRF token, or API key requirement.
The SPA's `fetch()` calls in `bundle.js` send no `Authorization`
header — just `Content-Type: application/json`.

No developer portal, no signup form, no terms-of-use page, no
contract requirement, no rate-limit header observed. The catalog
contact email `data@prv.se` is the canonical channel; the
search-API hosts are not documented anywhere on `prv.se`.

## 3. Query language

Two flavors per right-type, mirroring the SPA's "simple" / "advanced" tabs.

**Simple search payload (confirmed shape):**

```json
{
  "page": 0,
  "pageSize": 10,
  "sortColumn": "filingDate",
  "sortOrder": "DESC",
  "simpleSearchText": "<free text>"
}
```

- `page` is 0-indexed.
- `sortColumn` accepts at least `"filingDate"` and `""`; the SPA
  passes `""` for the patent call and `"filingDate"` for TM /
  design / municipal arms.
- `sortOrder` is `"ASC"` or `"DESC"`.

**Advanced search** uses the same hostname/path-prefix but a
fielded payload. The exact field names are in the SPA bundle and
would need a one-pass extraction before connector implementation
(applicant, inventor, classification, filing-date range, status,
etc., per the UI). The 4xx error shape is consistent JSON
`{"message": "..."}` which makes field-validation
introspection-friendly.

## 4. Pagination

Offset/limit via `page` and `pageSize`. Response carries
`totalHits`, `totalPages`, `hits` (this-page count), and `page`
(echoed back) — typical Spring/Elasticsearch pagination shape:

```json
{"totalHits": 3307, "totalPages": 1102, "hits": 3, "page": 0, "searchPatentDTOS": [...]}
```

The page-size cap isn't documented; the SPA uses `10` / `20`
defaults. A probe with `pageSize: 3` succeeded; I did not test
the upper bound.

## 5. Response shape

The patent response wraps records in `searchPatentDTOS`, TMs in
`trademarks`, designs in `designs`. Each record is JSON with
nested arrays for applicants, inventors, representatives, and
classification.

**Patent record (Volvo example, abbreviated):**

```json
{
  "idPatent": 7064552,
  "applicants": [{"name": "VOLVO TRUCK CORPORATION", "address": "..., 405 08 Göteborg, Sverige"}],
  "applicationNumberFormatted": "SE2615555-6",
  "applicationType": "NAT",
  "cpcClasses": [], "dpkClasses": [], "ipcClasses": [],
  "filingDate": "2026-05-05",
  "grantDate": null,
  "inventors": [{"name": "David RAY", "address": "CHASSIEU, Frankrike"}],
  "publicationDate": "2026-05-05",
  "publicationNumber": "",
  "representatives": [{"name": "Zacco Sweden AB", "address": "..."}],
  "status": {
    "status": "116",
    "statusText": null,
    "statusDisplayTextEn": null,
    "statusDisplayTextSv": null,
    "statusSubText": null,
    "statusDisplaySubTextEn": null,
    "statusDisplaySubTextSv": null
  },
  "title": "CLIP ASSEMBLY FOR MOUNTING AN ACCESSORY TO A TRIM ELEMENT OF A VEHICLE, AND ASSOCIATED ARRANGEMENT AND VEHICLE"
}
```

Note `applicationType: "NAT"` appears in the response but is not
the right value for the `/patents/applications/{id}` GET path
(returned 400 "Unknown applicationType"). The enum on that GET
needs one more reverse-engineering pass against the SPA's detail
view, or a one-line ask to PRV.

**Trademark record (IKEA example, abbreviated):**

```json
{
  "idTrademark": 4907387,
  "applicants": [{"name": "IKEA Älmhult AB", "address": "...343 81 Älmhult, SE, 559070-5058"}],
  "applicationNumber": "2025-05038",
  "classes": ["35", "36", "41"],
  "dossierTypeEn": "National trademark",
  "dossierTypeSv": "Nationellt varumärke",
  "expiryDate": "2035-10-01",
  "filingDate": "2025-10-01",
  "markFeatureEn": "Figurative",
  "markFeatureSv": "Figur",
  "markSpecification": "form hult",
  "registrationNumber": "639377",
  "representatives": ["Advokatfirman Lindahl KB, ..., 916629-0834"],
  "statusEn": "Registered",
  "statusSv": "Registrerad"
}
```

Notable: the `address` strings carry Swedish corporate identity
numbers (`organisationsnummer` — `559070-5058`, `916629-0834`)
embedded as plain text. Useful for entity disambiguation, but
worth a normalization pass.

**Design record (1971 Television Chair example):**

```json
{
  "idDesign": 49866571,
  "applicants": [{"name": "Television Chair International", "address": "..., San Clemente, CA 92672, US"}],
  "applicationNumber": "1971-1323",
  "classes": ["06-01", "14-03"],
  "designId": "33772",
  "designNumber": 1,
  "designsTotal": 1,
  "expiryDate": null,
  "filingDate": "1971-09-03",
  "productTitle": "KOMBINERAD STOL OCH TELEVISIONSMOTTAGARE",
  "registrationNumber": "11182",
  "representatives": [{"name": "Valea AB", "address": "..., 417 56 Göteborg, SE, 556103-7838"}],
  "statusEn": "Expired",
  "statusSv": "Avförd"
}
```

Coverage back to **1971** for designs — earlier than the post-2018
bulk feeds suggest. The Locarno classification (`06-01`, `14-03`)
comes through as strings.

## 6. Coverage scope

### Patents — the SE-national slice

- **National patents and patent applications** filed at PRV, from
  1885 forward in the legacy SPD; the new beta limits older-material
  search but live data is daily-updated.
- **EP patents validated in Sweden** — the SE-Federated Register
  Service ([page](https://www.prv.se/en/patents/the-advanced-patent-guide/patent-databases/se-federated-register-service/))
  feeds biblio + status (in-force / not in force / not validated)
  + proprietor + last-paid renewal-fee date to the EPO's federated
  register at [`https://was.prv.se/spd`](https://was.prv.se/spd).
- **EP applications published under §88 of the Patents Act.**
- **Supplementary Protection Certificates (SPCs)** and **SPC
  extensions** — searchable via `/searchpatentspc/patentsearchspc/`
  (SPC GET on api.prv.se exists but returns 404 without specific id).
- Total `countPatent` on probe: **764,224 records.**

### Trademarks — the SE-national slice

- **National SE trademarks** filed directly with PRV (e.g. the
  IKEA Älmhult AB example, `dossierTypeEn: "National trademark"`).
- **Madrid IRs designating SE** — present in the same index based on
  the SPA's surfacing (TM count includes both; needs
  filter-confirmation).
- **Municipal arms** (`kommunvapen`) — a Swedish-specific separate
  register, with its own simple + advanced + count + announcements
  endpoints. Niche but real.
- **Svensk Varumärkestidning announcements** — daily kungörelser
  since 2026-01-26 (replacing the pre-2026 weekly PDF gazette).

### Designs — the SE-national slice

- **National SE design registrations** back to at least 1971 on
  probe. Locarno classes carried as `["06-01","14-03"]`.
- **Svensk Designtidning announcements** — daily kungörelser since
  2026-01-26.
- **Hague IRs designating SE** — not separately confirmed in this
  probe; needs a `dossierTypeEn`-filtered query.

### What PRV does *not* cover via the API

- **Pre-2000 patent material** in the new beta is explicitly limited
  per PRV's own beta notice — the legacy `tc.prv.se/spd` is the
  transitional fallback.
- **Patent classification (CPC/IPC/DPK)** is in the response model
  but the Volvo probe records returned empty arrays for all three;
  unclear whether this is a data-freshness issue (newly filed
  applications) or genuinely absent. Older records would test this.
- **Real file-history documents** as raw bytes come through
  `api.prv.se/patents/documents/` and the legacy
  `resources.prv.se/downloadAllDocuments.jsp` — both reachable; both
  need a follow-up probe to confirm the auth/path shape.
- **Aktinsyn** (case-file access) — the [open-data dataset of the
  same name](https://data.prv.se/dataset.jsp?uuid=888c893c424148159b41c080653dce973aa8d488e22d42c3aded43618c300f85)
  covers public patent applications from 2004 forward, with the
  raw originals delivered as PDFs.

## 7. Rate limits / quotas

**None observed on probe.** No rate-limit headers
(`X-RateLimit-*`, `RateLimit-*`), no 429 responses, no `Retry-After`,
no quota notice in the SPA bundle. The behavior is consistent with
"public-facing search API with no formal limits, scaled by
production capacity." For a hosted-demo with concurrent users this
is a real risk — PRV may throttle by IP if traffic spikes — but
not a contract-violating one. Operational discipline = polite
backoff + obvious user-agent identification + don't run bulk
scrapes.

## 8. Terms of service

There is **no published terms-of-service for the search APIs
specifically.** PRV's site footer doesn't carry a generic ToS, and
[`prv.se/en/about-us/contact/`](https://www.prv.se/en/about-us/contact/)
doesn't have a website-terms link. What's published is two
adjacent governance signals:

1. **Open-data licenses on [`data.prv.se`](https://data.prv.se/).** The
   parallel bulk distributions of essentially the same data are
   licensed **CC0 1.0** (patent kind-codes, patent documents,
   municipal arms, Svensk Patenttidning, Svensk Varumärkestidning,
   Svensk Designtidning, Aktinsyn, IPC classification helpers) and
   **CC BY 4.0** (bibliographic data 2019-, full-text 1973–2017, new
   patent documents 2022-). Both permit commercial reuse; CC BY 4.0
   requires attribution.

2. **The Swedish Open Data Act.** Sweden transposed [EU Open Data
   Directive 2019/1024](https://eur-lex.europa.eu/eli/dir/2019/1024)
   in April 2022 with [SFS 2022:818
   ("Lag om den offentliga sektorns tillgängliggörande av data")](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/lag-2022818-om-den-offentliga-sektorns_sfs-2022-818/),
   effective August 2022. The baseline is: public-sector data
   should be reusable for commercial or non-commercial purposes.

The strong inference is the search APIs ride on the same legal
substrate as the bulk feeds: register data is by statute
re-usable. The conservative interpretation for production is:
attribute PRV in any UI surface, identify the client by
User-Agent, and confirm-in-writing with `data@prv.se` before
deploying to a multi-tenant production environment.

Tracking note: [`tracking.prv.se`](https://tracking.prv.se/) (Google
Tag Manager) appears on the marketing pages but not on the search
APIs themselves.

## 9. Operational notes

**Versioning is the principal risk.** The endpoints are
undocumented and reverse-engineered. The `bundle.js` that defines
them is rebuilt on each SPA deploy. No `Api-Version` header, no
versioned path segment, no deprecation policy. A migration like
the [2026-01-26 launch](https://www.prv.se/en/knowledge-and-support/search-databases/)
(which froze tc.prv.se) could happen again at any deploy.
Mitigation = contact `data@prv.se`, register as a downstream
consumer, ask for changelog notice.

**Schema gaps.** `cpcClasses`, `ipcClasses`, `dpkClasses` came
back empty on a freshly-filed Volvo application. Either (a) data
is populated lazily as the application progresses through
classification, (b) the field is misnamed in the response, or (c)
classification data needs to be requested via the advanced search.
Worth probing against a granted patent before drawing conclusions.

**The applicationType enum mystery.** GET on
`/patents/applications/{id}?applicationType=X` requires the right
enum — `NAT`, `NATIONAL`, `EP`, `PCT`, and lowercase variants
all returned 400 `{"message":"Unknown applicationType."}` on
probe. The SPA's record-detail view sends the correct value; a
one-pass extraction against the bundle resolves it. Not a blocker;
the search responses already carry per-record data sufficient for
most agent uses.

**Stack signal.** A 404 leaked the internal host:
`http://wildflyexternprod.prv.se:8080/prvpublicapi-web/api/public/...`.
This is a **WildFly + RESTEasy** stack with a
`prvpublicapi-web` Web Application Archive deployed at
`/api/public/`. The `public` path component is a strong intent
signal — these endpoints are designed for outside callers, even
if no public documentation has been published.

**Encoding.** Responses are UTF-8 JSON. Swedish characters
(`å`, `ä`, `ö`) survive untouched. Address strings carry trailing
country names in Swedish (`Sverige`, `Frankrike`, `Indien`).
Status codes are numeric strings (`"116"`) with multilingual
display-text slots — that need fetching from somewhere (probably
`api.prv.se/health/databasedv` or a separate `/codes/` endpoint
we haven't yet found).

**WIPO IP API Catalog.** [`apicatalog.wipo.int`](https://apicatalog.wipo.int/)
returns **0 PRV entries** as of probe 2026-05-18 (179 total APIs
across DPMA, EPO, EUIPO, IP Australia, JPO, MOIP KOREA, QAZ, UPRP,
USPTO, WIPO). The WIPO Catalog is the canonical signal an office
has *announced* a public API; PRV's absence reflects the
undocumented status of the new search APIs, not their existence.

**SE-Federated Register Service.** PRV participates in the EPO
Federated Register, providing deep-link access to the SE national
patent register at [`https://was.prv.se/spd`](https://was.prv.se/spd).
This is a strong cross-office signal — Sweden runs structured
register data at scale; the same backing store likely feeds both
FRS and the new search APIs.

## 10. Verdict

**🟢 Green** — with the explicit caveat that this is a
*green-on-undocumented* rating, not a *green-on-contract* rating.

**What makes it green:**

- Three live JSON APIs returning rich, structured records on
  patents, TMs, designs, SPCs, municipal arms, and announcements.
- **No auth.** No registration, no API key, no signed ToU.
- Parallel bulk data is licensed **CC0 / CC BY 4.0** — the most
  permissive license posture in this wave (vs. IPI's
  wet-signed §2 anti-redistribution and ÖPA's
  personal-use-only).
- Sweden's Open Data Act (SFS 2022:818) provides statutory cover
  for re-using public-sector data.
- The stack-leak (`prvpublicapi-web/api/public/...`) is *intent
  signal* — these endpoints are named "public" by the agency.
- Coverage is the SE-national slice EPO OPS / INPADOC / EUIPO /
  WIPO don't reach.

**What flags the caveats:**

- **Undocumented.** No developer page, no spec, no contact.
  Reverse-engineered from `bundle.js`; the SPA can change schemas
  without notice.
- **Versionless.** No API version header or path segment.
- **No published API ToS.** Strong inference from CC0 / CC BY 4.0
  on parallel bulk feeds + Swedish Open Data Act, but **not** a
  signed agreement.
- **Beta status of the new UI** (since 2026-01-26) suggests
  schemas are still settling.
- **Older-material gap pre-2000** is acknowledged on the PRV side.

**Operational path:**

1. Build a thin connector against the three hosts: simple-search
   first; advanced-search second after another bundle extraction.
2. Send a registration / courtesy email to `data@prv.se` before
   any production deploy; ask for breakage notice.
3. Identify clients by `User-Agent: patent-client-agents/...` with
   contact link.
4. Treat `tc.prv.se/spd` (legacy) as a pre-2000 fallback during
   PRV's transition period.
5. Cache aggressively (5-min for status calls, 24h for record
   bodies) to limit load.

**Strategic memory:** PRV looks structurally similar to the
Nordic-cluster pattern — open, well-engineered, English-friendly
documentation around the bulk data even if the API itself is
undocumented. Worth checking whether NIPO (Norway), DKPTO
(Denmark), and PRH (Finland) follow the same pattern. PRH in
particular has been historically open about APIs.
