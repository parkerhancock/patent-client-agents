# FI/PRH (Patentti- ja rekisterihallitus) — Wave 2026-05-18

**Question:** Does PRH expose a public REST/JSON/XML API we can call
per user query at runtime? Currently `rating: tbd` in
`STATE.yaml`. Bulk dumps and HTML-only surfaces = red. BYOK with
per-user creds = yellow. Undocumented-but-unauthenticated APIs
that are stable = green.

**Verdict:** 🟢 **Green — three undocumented, unauthenticated JSON
APIs cover patents (incl. utility models, SPCs, EP validations),
trademarks (incl. well-known "TMR" register), and designs.** Same
Nordic-office pattern that PRV (Sweden) exhibits — modern Next.js /
React SPA fronts call a versionless internal gateway (`/nis-api-
gateway-pat` for patents, `/nis-api-gateway` for TM + design),
fully addressable from outside the SPA without any authentication.
Open data licensing on the sister business-register service is
explicit CC BY 4.0 (no parallel statement for the IP search APIs
yet observed, but the same office). **Recommended
`connector_status: planned (green — undocumented)`.**

---

## 1. PRH at a glance

PRH (Patentti- ja rekisterihallitus, lit. "Patent and Registration
Office") is Finland's national IP office and trade-register
operator. It is an agency of the Ministry of Economic Affairs and
Employment ([Suomi.fi org card](https://www.suomi.fi/organization/finnish-patent-and-registration-office/9425cf74-0ca7-4cd1-b804-3a51131962fa)).
It grants patents, registers utility models
(hyödyllisyysmalli), trademarks, designs, business names, and runs
the YTJ business information system jointly with the Finnish Tax
Administration ([PRH EN home](https://www.prh.fi/en/)).

Finland is an EPC contracting state, a UPC contracting state (UP
system live since 2023-06-01), and an EU member, so most "Finnish
patents" of commercial scale are EP-routed (covered by EPO OPS),
most "Finnish trademarks" of any reach are EUTMs (covered by
EUIPO), and Madrid IRs / Hague IRs designating FI flow through
WIPO. PRH's national-only slice — Finnish utility models, FI
national patents that never went EP, FI SPCs, FI national-only TMs
(not Madrid / not EUTM), FI national-only designs (not Hague /
not RCD), Finnish well-known marks register (TMR) — is the
genuine value-add.

## 2. Surface inventory

Six service surfaces probed 2026-05-18:

| # | Surface | Right(s) | Format | Verdict |
|---|---|---|---|---|
| 1 | `patenttitietopalvelu.prh.fi` SPA + `/nis-api-gateway-pat` | patent, utility model, SPC, EP-FI | JSON | 🟢 green (undocumented) |
| 2 | `tavaramerkkitietopalvelu.prh.fi` SPA + `/nis-api-gateway` | trademark, well-known marks (TMR) | JSON | 🟢 green (undocumented) |
| 3 | `mallioikeustietopalvelu.prh.fi` SPA + `/nis-api-gateway` | design | JSON | 🟢 green (undocumented) |
| 4 | `avoindata.prh.fi` open-data APIs (YTJ + krek + XBRL) | business register, financial statements | JSON | 🟢 green — but business-register only, no patents/TMs/designs |
| 5 | `avoindata.fi` (national open-data portal) | meta-catalog | DCAT/CKAN | 🔴 red — only 3 PRH datasets, all business-register |
| 6 | WIPO IP API Catalog | meta-catalog | JSON | informational — 0 PRH entries |

## 3. Surface 1 — `patenttitietopalvelu.prh.fi` (patents + UM + SPC + EP-FI)

### How the SPA was reverse-engineered

The SPA at [`https://patenttitietopalvelu.prh.fi/en/search/`](https://patenttitietopalvelu.prh.fi/en/search/)
is a React app (Create-React-App, not Next.js, judging by the
`/static/js/main.05f306a4.js` bundle path). Bundle 926 KB. Two
critical leaks from minified config dotenv block:

```
REACT_APP_API_URL:"/nis-api-gateway-pat"
REACT_APP_PATENTS_COMMUNICATION_ID:"dbbce2df-4748-40fb-b32c-ac2a85821a54"
REACT_APP_PAYMENT_SERVICE_URL:"https://asiointi.prh.fi/maksupalvelu"
```

The search hook is minified to:

```js
const Iu = "/nis-api-gateway-pat";
function Fu() { return Fl((e => ({url: `${Iu}/${e}`, method: "GET"}))); }
const [y, v] = Fl((e => ({url: `${Iu}/patent`, method: "POST", data: e})));
```

The initial form state `Bn` is fully exposed:

```js
Bn = {
  patentTitle:"", applicationNumber:"", registrationNumber:"", priorityNumber:"",
  dossierStatus: In,  // a 117-element default array of status codes
  applicant:"", assignee:"", inventor:"", representative:"",
  applicationStartDate:"", applicationEndDate:"",
  filingStartDate:"", filingEndDate:"",
  oppositionPeriodStartStartDate:"", oppositionPeriodStartEndDate:"",
  grantStartDate:"", grantEndDate:"",
  openStartDate:"", openEndDate:"",
  publicationStartDate:"", publicationEndDate:"",
  priorityStartDate:"", priorityEndDate:"",
  ipcClassification:"", cpcClassification:"",
  basicSearch:"",
  patentTypes: ["PatentDossier","PatentDossierUtilityModel","PatentEurope","Spc"],  // Mn default
  noAuthoAppm:"", spcBasePatentNumber:"",
  publicationTypes: Ln  // 42-element default publication-type array
}
```

The status enum (`In`) holds the entire vocabulary in mixed
case styling — `"Valid"`, `"Renounced"`, `"Annulled"`,
`"Application_filed"`, `"EP_620_grant_B1"`, `"valid"`,
`"renounced"`, `"basic_patent_has_lapsed"`, plus PCT phase codes
(`"ro_filed"`, `"ipea_finished"`, etc.). The publication-type
enum (`Ln`) carries UM/PT prefixed codes like `"UM_Granted_Y1"`,
`"PT_SPCGranted_Certificate"`, `"PT_EPTranslationValidation_T3"`.

### Endpoints confirmed by live probe

**`POST /nis-api-gateway-pat/patent`** — corpus search. Body
requires the full `Bn` shape; empty body → HTTP 400. Filled with
the default `In` and `Ln` arrays → HTTP 200 JSON `{totalResults,
results: [...]}`. Server-side cap: `results` array maxes out at
3,000 entries regardless of any `pageSize` / `page` / `limit` /
`offset` field in the body. Verified with five different
parameter shapes.

Probed totals (filter-only, no text):

| Query | totalResults |
|---|---|
| All types (`PatentDossier`+`PatentDossierUtilityModel`+`PatentEurope`+`Spc`) | **393,750** |
| `applicant:"Nokia"`, all types | 7,471 |
| `basicSearch:"Kone"`, UM only | 87 (including one `Telaketjuilla liikkuva kone` — UM granted 2017) |
| `applicant:"Pfizer"`, `Spc` only | 41 SPCs |
| `basicSearch:"Nokia"`, `PatentEurope` only | 521 EP-FI validations |

Sample result row:

```json
{
  "applicationNumber": "982825",
  "registrationNumber": "106323",
  "dossierStatus": "Renounced",
  "dossierType": "PatentDossier",
  "applicationDate": "1998-12-30",
  "statusDate": "2005-03-14",
  "applicants": [{"name": null, "companyName": "Nokia Mobile Phones Ltd", "ordinal": 1}],
  "classifications": [{"classification": "G02F 1/1335"}, ...],
  "titles": [
    {"title": "Taustavalaistuksen valonjohdin litteälle näytölle", "language": "FI", "ordinal": 1},
    {"title": "Bakgrundsbelysningens ljusledare för en flat bildskärm", "language": "SV", "ordinal": 2},
    {"title": "", "language": "EN", "ordinal": 3}
  ],
  "owners": [{"name": null, "companyName": "Nokia Mobile Phones Ltd", "ordinal": 1}],
  "appms": [], "publications": [], "ordinal": 1
}
```

**`GET /nis-api-gateway-pat/patent/{applicationNumber}`** — full
file wrapper. Probed `/patent/982825`:

```json
{
  "applicationType": "PATENT_FOR_INVENTION",
  "applicationNumber": "982825",
  "registrationNumber": "106323",
  "applicationDate": "1998-12-30",
  "filingDate": "1998-12-30",
  "grantDate": "2001-01-15",
  "publicationDate": "2000-07-01",
  "patentTitle": [ ... FI/SV/EN trilingual ],
  "events": [
    {"eventDate": "2005-03-14", "current": true,  "event": "ACTIONS_ON_RECORD.renouncement", "ordinal": "1"},
    {"eventDate": null,         "current": false, "event": "COURT_DECISION.filed",           "ordinal": "2"}
  ],
  "abstracts": [], "priorityClaims": [], "imageUrl": null, "documents": [],
  "dossierStatus": "Renounced", "dossierStatusDate": "2005-03-14",
  "applicants":      [{"companyName": "Nokia Mobile Phones Ltd", "country": "FI", "ordinal": 1}],
  "representatives": [{"companyName": "Page White & Farrer Ltd", "country": "GB", "ordinal": 1}],
  "inventors":       [{"fullName": "Parikka Marko", "firstName": "Marko", "lastName": "Parikka", "country": "FI", "ordinal": 1}],
  "owners":          [{"companyName": "Nokia Mobile Phones Ltd", "country": "FI", "ordinal": 1}],
  "examiner": {"fullName": "Ann-Charlotte Kahlson-Sjöblom"},
  "ipcClassifications": ["G09F 9/35","G02F 1/1335","F21V 8/00","G02F 1/13"],
  "cpcClassifications": [],
  "basePatentNumber": null,
  "paymentDetails": {
    "payable": [],
    "paid": [{
      "identifier": "M007", "dueDate": "2004-12-31", "limitDate": "2005-06-30",
      "paymentDate": "2004-12-14", "lateFeePaymentDueDate": "2005-06-30",
      "ref": "2004121460-166", "feePaidAmount": 200,
      "comment": null, "creditorReference": "RF319828250198", "ordinal": 1
    }]
  },
  "relatedDossiers": [],
  "spcAuthorizations": [],
  "t3PublicationDate": null,
  "filingLanguage": "EN"
}
```

This is **register-fidelity prosecution data**: examiner name,
named representative, country-coded applicant, annual-fee payment
details with creditor reference, T3 (EP claim translation)
publication date slot, SPC authorizations, related dossiers.
Better than INPADOC for the FI-national slice and arguably
matching the EP Register for EP-validation events.

### Other patent-API probes

| Path | Method | Status | Note |
|---|---|---|---|
| `/nis-api-gateway-pat` | GET | 404 | Gateway root not exposed |
| `/nis-api-gateway-pat/swagger-ui` | GET | 404 | No swagger advertised |
| `/nis-api-gateway-pat/openapi.json` | GET | 404 | No OpenAPI spec |
| `/nis-api-gateway-pat/v3/api-docs` | GET | 404 | No springdoc |
| `/nis-api-gateway-pat/patent/bulletins` | GET | 400 | Needs query param |
| `/nis-api-gateway-pat/patent/surveys`   | GET | 400 | Needs query param |
| `/nis-api-gateway-pat/patent/{appNum}`  | GET | 200 | **Confirmed** |
| `/nis-api-gateway-pat/patent`           | POST | 200 | **Confirmed** |

Bulletins + surveys exist (status 400, not 404) — they need
parameters we haven't yet derived. Bundle hints at "bulletin"
(weekly patent gazette) and "survey" (user surveys) — non-essential.

## 4. Surface 2 — `tavaramerkkitietopalvelu.prh.fi` (TM + TMR)

The TM SPA bundle (1.1 MB) leaks `REACT_APP_API_URL:"/nis-api-
gateway"` (no `-pat` suffix). The search hook calls a flexible
endpoint name:

```js
const Kc = "/nis-api-gateway";
const [k, v] = Uc(((e, t) => ({url: Kc + "/" + t, method: "POST", data: e})));
// Routes pool: A = ["search","results","trademark","recordal","opposition","international","tmr","tmrResults"]
```

Two endpoints probed end-to-end:

**`POST /nis-api-gateway/trademark`** (empty body)

```
HTTP 200 size=2,010,757 bytes
{"totalResults": 282824, "results": [...]}
```

282,824 TMs back to 1891 (first result: `T189100011` "J. & P.
COATS"). Each result includes `applicationNumber`,
`registrationNumber`, `dossierStatus`, `dossierSubType`
(Figurative-word, Word, etc.), `applicationDate`,
`registrationDate`, `expirationDate`, `applicants`, `priorities`,
`trademarkWord`, `trademarkHasImage`, `goodsAndServices: [{classNumber, ordinal}]`
(Nice classes), `imageUrl`, `thumbnailUrl`, `largeThumbnailUrl`.

**`POST /nis-api-gateway/tmr`** (empty body)

```
HTTP 200 size=72,698 bytes
{"totalResults": 111, "results": [...]}
```

The Finnish **well-known trademarks register (TMR =
toiminimirekisteri / "Tunnetut tavaramerkit")**. 111 records.
Includes `targetGroup` (free text) — e.g. "15-44-vuotiaat
suomalaiset" for TAFFEL chips. This is **national-only PRH
data with no transitive coverage from EUIPO / WIPO Madrid**.

**Image surface:** `GET /opendata/trademark/image/{appNum}/{regNum}`
returns `image/gif` (354×336 for the historic mark probed);
`GET /opendata/trademark/thumbnail/{appNum}/{regNum}` returns
`image/jpeg`; `…/thumbnail/large/…` is the large thumbnail variant.
This is served on the same SPA host (not on `/nis-api-gateway`)
— probed live, 200 OK.

The path prefix `/opendata/trademark/...` is a deliberate marker —
PRH's own internal naming declares these images "open data".

## 5. Surface 3 — `mallioikeustietopalvelu.prh.fi` (designs)

Same Create-React-App pattern. Bundle 969 KB.

```js
const Wd = "/nis-api-gateway";
// Routes = ["search","results","design"]
```

**`POST /nis-api-gateway/design`** (empty body)

```
HTTP 200 size=3,200,262 bytes
{"totalResults": 33682, "results": [...]}
```

33,682 design records back to **1971** (first result:
`M19710001` for Oy Fiskars Ab, dismissed). Each record carries
`dossierStatus` (`DS_Application_dismissed`, `DS_Expired`, etc.),
`dossierSubType`, `applicants`, `representatives`, `priorities`,
`goodsAndServices`, `locarnos: [{classNumber, ordinal}]` (Locarno
classes), `designs: [{...}]` (individual design embodiments per
application), `imageUrl`. Coverage from 1971 forward — same start
year as PRV Sweden's design register.

## 6. Surface 4 — `avoindata.prh.fi` (business register only)

Separate from the IP search surface. Lives at
[`https://avoindata.prh.fi/`](https://avoindata.prh.fi/) and
publishes a Next.js portal documenting **three** swagger-described
APIs:

- **`/opendata-ytj-api/v3/`** — YTJ business identifiers, company
  details (excludes private traders, no email/phone)
- **`/opendata-krek-api/v3/`** — registered notifications to the
  trade register, from 2014-11-07 onward
- **`/opendata-xbrl-api/v3/`** — iXBRL digital financial
  statements (only ~5 % of all filings — other 95 % must be bought
  via [Virre](https://virre.prh.fi/novus/home))

**License (explicit, EN page):**
[`creativecommons.org/licenses/by/4.0/deed.en`](https://creativecommons.org/licenses/by/4.0/deed.en)
— "Mention the original source. … Services based on the data
must not use the PRH or YTJ logo or otherwise confuse the user
that this is a PRH service."

These APIs do **not** cover patents, utility models, trademarks,
or designs. PRH explicitly separates the corporate-register open
data (here) from the IP search services (Surfaces 1-3).

The avoindata.prh.fi swagger is for the YTJ stack only; it is the
strongest **license-posture signal** for the IP search APIs —
they sit on the same office's open-data umbrella, and the
internal path prefixes `/opendata/trademark/...` reinforce that
PRH considers the IP search responses to be open data too. But
that is inference, not the stated terms of service.

## 7. Surface 5 — `avoindata.fi` (national open-data portal)

CKAN-based federal catalog at
[`https://www.avoindata.fi/`](https://www.avoindata.fi/). PRH
organization page (`organization_show?id=patentti-ja-rekisterihallitus`)
returns **3 datasets, all CC-BY 4.0, all business-register**:

1. `sbr-taksonomia-osakeyhtioiden-ja-saatioiden-paivitykset` — SBR taxonomy
2. `yritykset` — YTJ JSON snapshot
3. `prh-avoin-data` — YTJ API metadata pointer

A free-text package search for `patent` returns 208 hits but
none from PRH — all are Ministry of Finance dictionary entries
(WSDL, RDF, etc.). **There is no patent / UM / TM / design
bulk dataset on avoindata.fi.**

## 8. Surface 6 — WIPO IP API Catalog

Probed [`https://apicatalog.wipo.int/api/apis?size=200`](https://apicatalog.wipo.int/api/apis?size=200)
2026-05-18. 179 office APIs across 10 organisations:

```
['DPMA', 'EPO', 'EUIPO', 'IP Australia', 'JPO',
 'MOIP KOREA', 'QAZ', 'UPRP', 'USPTO', 'WIPO']
```

**Zero PRH entries.** Same status as Sweden, Netherlands, Austria
in the secondary-nationals sweep — the canonical API inventory
hasn't registered PRH's IP services. The APIs are real and live,
but operationally invisible from the canonical catalog.

## 9. Compliance / ToS posture

- **No published API ToS** on any of the three IP SPAs.
- **No `robots.txt`** on `tavaramerkkitietopalvelu.prh.fi` (404).
- **No developer page or signup portal** for IP-side APIs.
- **No rate-limit headers** observed on probe runs (single
  back-to-back requests, no `x-ratelimit-*` or `retry-after`).
- **Parallel sister service** (`avoindata.prh.fi`) is **CC-BY 4.0**
  with named attribution requirements.
- **Statutory cover:** Finland is subject to the EU Open Data
  Directive (2019/1024), transposed via Finland's Act on the
  Openness of Public Sector Activities and other measures. PRH's
  status as a public agency under the Ministry of Economic
  Affairs and Employment is administrative cover, not contract
  cover — but it tracks the same governance shape that produced
  CC-BY 4.0 on the business-register side.

Production posture: courtesy-register with `avoindata@prh.fi`
(the contact listed in the avoindata.prh.fi footer), identify the
client by User-Agent, document the breakage-monitoring plan, and
flag the IP search APIs as undocumented + versionless in the
connector code.

## 10. Verdict + connector strategy

**Verdict: 🟢 green (undocumented but live).** Three unauthenticated,
structured-JSON APIs that cover the entire FI-national-only slice
that EPO OPS / EUIPO / WIPO Madrid don't reach:

- FI national patents that never went EP (Surface 1)
- FI utility models (`PatentDossierUtilityModel` — Surface 1)
- FI SPCs (`Spc` — Surface 1)
- EP-FI validations with FI-specific events (T1/T3/T4/T6/T7
  publication kinds — Surface 1)
- FI national trademarks (national-only, not Madrid, not EUTM — Surface 2)
- FI well-known marks register / TMR (Surface 2)
- FI national designs (national-only, not Hague, not RCD — Surface 3)
- Trademark image and thumbnail downloads (Surface 2)

**Recommended `connector_status: planned (green — undocumented)`.**
Pattern matches PRV / Sweden almost exactly — same Nordic-office
modern-SPA-over-versionless-JSON-gateway shape. Estimated
build: 3-5 days. Initial scope:

- `patent_client_agents.prh` — async client wrapping three hosts
- `POST /nis-api-gateway-pat/patent` → `patents.search(...)` (returns up to 3,000 results)
- `GET  /nis-api-gateway-pat/patent/{n}` → `patents.get(application_number)`
- `POST /nis-api-gateway/trademark` → `trademarks.search(...)` (returns up to ? — full corpus probed delivers full result set)
- `POST /nis-api-gateway/tmr` → `trademarks.search_tmr(...)`
- `POST /nis-api-gateway/design` → `designs.search(...)`
- `GET  /opendata/trademark/image/{appNum}/{regNum}` → `trademarks.image(...)`
- `GET  /opendata/trademark/thumbnail/{appNum}/{regNum}` → `trademarks.thumbnail(...)`
- Versionless-schema validation per call; surface clean errors
  when fields disappear
- Courtesy User-Agent identifying `patent-client-agents`
- Polite cache: 5 min for status views, 24 h for record bodies

**Risks / caveats:**

- Schema is reverse-engineered; the `In` (status) and `Ln`
  (publication-type) enums in the patent service are 117 and
  42 elements respectively and may shift on any deploy.
- Server caps `results` at 3,000 per query with no client-side
  paging exposed — narrow queries needed for high-population
  applicants (e.g. Nokia patents 7,471 > 3,000 cap).
- The bulletins / surveys endpoints exist (HTTP 400, not 404) but
  payload shape unknown — non-essential.
- License posture on the IP search APIs is implicit (parallel
  CC-BY 4.0 on the sister business-register service, internal
  `/opendata/...` path prefixes on image endpoints) but not
  contractually stated. Courtesy registration with
  `avoindata@prh.fi` is the cheap mitigation.

**Next steps:** write the synopsis at
`research/national/fi-prh.md`; queue a connector spec
(`specs/fi-prh-connector-spec.md`) referencing this wave file;
add `FI/PRH` to `BACKLOG.md` at green priority alongside SE/PRV.

## 11. Primary sources

**Live services (probed 2026-05-18):**
- [`https://patenttitietopalvelu.prh.fi/`](https://patenttitietopalvelu.prh.fi/) — patent + UM + SPC + EP-FI SPA
- [`https://tavaramerkkitietopalvelu.prh.fi/`](https://tavaramerkkitietopalvelu.prh.fi/) — TM + TMR SPA
- [`https://mallioikeustietopalvelu.prh.fi/`](https://mallioikeustietopalvelu.prh.fi/) — design SPA
- [`https://avoindata.prh.fi/`](https://avoindata.prh.fi/) — business-register open-data portal (CC-BY 4.0)

**Office overview:**
- [PRH EN home](https://www.prh.fi/en/)
- [PRH Suomi.fi org card](https://www.suomi.fi/organization/finnish-patent-and-registration-office/9425cf74-0ca7-4cd1-b804-3a51131962fa)
- [PRH Patent Information Service accessibility statement](https://www.prh.fi/en/presentation_and_duties/accessibility_in_our_online_services/patent_information_service.html)
- [PRH open data overview (business register)](https://www.prh.fi/en/companiesandorganisations/tietopalvelut/prhopendata.html)

**Substantive law (Finlex):**
- [Patenttilaki 550/1967 (ajantasa)](https://www.finlex.fi/fi/laki/ajantasa/1967/19670550) — Patents Act
- [Hyödyllisyysmallioikeuslaki 800/1991 (ajantasa)](https://www.finlex.fi/fi/laki/ajantasa/1991/19910800) — Utility Models Act
- [Tavaramerkkilaki 544/2019 (ajantasa)](https://www.finlex.fi/fi/laki/ajantasa/2019/20190544) — Trade Marks Act
- [Mallioikeuslaki 221/1971 (ajantasa)](https://www.finlex.fi/fi/laki/ajantasa/1971/19710221) — Design Act
- [Patents Act 550/1967 — English translation](https://www.finlex.fi/en/legislation/translations/1967/eng/550)
- [Trade Marks Act 544/2019 — English translation](https://finlex.fi/en/legislation/translations/2019/eng/544)

**Fees (link only — no amounts):**
- [Patent fees and payment instructions (EN)](https://www.prh.fi/patent_fees)
- [Trademark fees and payment instructions (EN)](https://www.prh.fi/en/price-lists/trademark_fees.html)
- [Changes to commercial TM + design fees from 2026-01-01 (EN)](https://www.prh.fi/en/presentation_and_duties/uutislistaus/announcements/2025/changestofeesforcommercialtrademarkanddesignrightservicesfrom1january2026.html)

**Cross-office context:**
- [WIPO IP API Catalog (probed 2026-05-18 — 0 PRH entries across 179 office APIs)](https://apicatalog.wipo.int/)
- [PRV (Sweden) sister wave](./se-prv.md) — same Nordic-office green pattern (also undocumented JSON behind a modern SPA)
- [EPO OPS](https://www.epo.org/searching-for-patents/data/web-services.html) — covers EP-FI patents transitively
- [Suomi.fi service for "Tavaramerkin hakeminen"](https://www.suomi.fi/services/applying-for-a-trademark-finnish-patent-and-registration-office/9d580c6f-ba1e-41b3-b053-a5109bf3ff46)
