# Patentti- ja rekisterihallitus (FI/PRH) — national

**Layer:** national
**Jurisdiction:** FI (WIPO ST.3: FI)
**Issuing body:** Patentti- ja rekisterihallitus (Finnish Patent and Registration Office, PRH); Patent- och registerstyrelsen in Swedish
**Rights administered:** patent, utility model (hyödyllisyysmalli), supplementary protection certificate, trademark, well-known trademarks register (toiminimirekisteri / TMR), design; plus trade register (kaupparekisteri), associations, foundations, business names
**Working languages:** Finnish (primary), Swedish (co-official), English (institutional pages + most response fields carry FI/SV/EN slots)
**Connector status:** **planned (green — undocumented but live)**
**Last verified:** 2026-05-18
**Manifest entry:** not yet listed (planned)

**Detail surveys:**
- [`waves/2026-05-18-secondary-nationals-wave/fi-prh.md`](../waves/2026-05-18-secondary-nationals-wave/fi-prh.md) — 2026-05-18 grounded API discovery

**Higher layers covering this office transitively:**
- **EPO INPADOC / EP Register** (via [`regional/epo.md`](../regional/epo.md)) — FI-validated EP patents at biblio/family/legal-events fidelity. Finland is an EPC contracting state and a UPC contracting state ([UP system started 2023-06-01](https://www.unified-patent-court.org/)).
- **EUIPO** (via planned `regional/euipo.md`) — EUTMs designating FI and Community designs (RCDs / REUDs).
- **WIPO Madrid / Hague** — Madrid IRs designating FI / Hague IRs designating FI.
- **UPC** (via shipped `upc_decisions` connector) — UPC-routed disputes touching FI.

---

## §1 Mission

PRH is Finland's national IP office and trade-register operator —
sole registrar for FI-national patents, FI utility models
(hyödyllisyysmalli), Finnish SPCs, FI-national trademarks, the
Finnish well-known trademarks register (TMR), and FI-national
designs. Because Finland is an EPC and UPC contracting state,
most "Finnish patents" of commercial scale are EP-routed and
covered by EPO OPS; most "Finnish trademarks" of any reach are
EUTMs and covered by EUIPO. PRH's genuine value-add for agents
is the FI-national-only slice — utility models (huge in Finland,
where the SME pathway favors UMs over patents), national-only
TMs and designs, FI SPCs, and live FI prosecution data with
register fidelity (named examiner, named representative,
annual-fee payment timeline, T-prefixed EP-translation kind
codes).

What sets PRH apart in this wave: it runs three independent
unauthenticated JSON APIs behind modern React SPAs at
[`patenttitietopalvelu.prh.fi`](https://patenttitietopalvelu.prh.fi/),
[`tavaramerkkitietopalvelu.prh.fi`](https://tavaramerkkitietopalvelu.prh.fi/),
and [`mallioikeustietopalvelu.prh.fi`](https://mallioikeustietopalvelu.prh.fi/)
— covering ~394k patent dossiers, ~283k trademarks (back to 1891),
and ~34k designs (back to 1971). Same Nordic-office pattern as
Sweden's PRV (see [`se-prv.md`](./se-prv.md)) — undocumented but
stable enough that the React SPAs ship them to every visitor.

## §2 What's unique here

- **FI utility models (hyödyllisyysmalli)** — `PatentDossierUtilityModel`
  in the patent index. UM is a first-class FI right with its own
  statute (Utility Models Act, 800/1991) and its own publication
  kind codes (`UM_Granted_Y1`, `UM_Corrected_Y8`, `UM_Revoked`,
  `UM_AnnulledPartial_Z1`). Not in EPO OPS at register fidelity.
- **FI SPCs and SPC continuations** — `Spc` patentType; SPC
  publication kind codes (`PT_SPCGranted_Certificate`, `PT_SPCFiled`,
  `PT_SPCContinuationGranted`, `PT_SPCLapsed`).
- **FI-national-only patents** — filed at PRH, not via EP.
- **EP-FI validation events at PRH register fidelity** — T1/T2/T3/T4/T5/T6/T7/T9
  publication kind codes capturing claim translations, opposition
  amendments, limitation publications. EPO OPS does not expose
  these T-prefixed FI-specific kind codes.
- **Examiner name, named representative, annual-fee payment
  timeline** on the per-application file wrapper — visible in
  `GET /nis-api-gateway-pat/patent/{n}`.
- **FI-national-only trademarks** — filed directly with PRH, not
  via Madrid or EUTM. ~283k records back to 1891.
- **Well-known trademarks register (TMR)** — separate national-only
  register of marks recognized as well-known in Finland. ~111
  records as of probe; includes free-text `targetGroup`
  (target-audience description, e.g. "15-44-vuotiaat suomalaiset"
  for the TAFFEL snack mark).
- **FI-national-only designs** — back to 1971. ~34k records with
  Locarno classifications and per-application design embodiments.
- **Trademark images and thumbnails** at `/opendata/trademark/image/...`
  and `/opendata/trademark/thumbnail/.../large/...`.
- **Trilingual titles** for patents (FI/SV/EN slots on every
  record — though EN slot frequently empty for older filings).

## §3 Programmatic surfaces

### patenttitietopalvelu.prh.fi — patent + UM + SPC + EP-FI API

| Field | Value |
|---|---|
| Endpoint | `https://patenttitietopalvelu.prh.fi/nis-api-gateway-pat/` |
| Auth | **none** — no API key, no signed ToU, no developer portal |
| Format | JSON (UTF-8); single response envelope `{totalResults, results: [...]}` for search; rich nested doc for GET-by-applicationNumber |
| Rate limit | not published, no rate-limit headers observed on single-pager probes |
| ToS posture | no published API ToS; sister business-register service `avoindata.prh.fi` is CC-BY 4.0; internal path prefix uses `/opendata/...` for image surfaces |
| Rating (zero-infra proxy) | 🟢 **Green (undocumented)** |
| Primary source | reverse-engineered from [`patenttitietopalvelu.prh.fi`](https://patenttitietopalvelu.prh.fi/) React bundle 2026-05-18 |

Two confirmed endpoints:

```
POST /nis-api-gateway-pat/patent       — corpus search, body = full Bn shape (32 fields)
GET  /nis-api-gateway-pat/patent/{n}   — file wrapper for application number
```

Probed totals: **393,750** patent + UM + SPC + EP-FI records in
the full corpus; 7,471 Nokia hits; 87 "Kone" utility-model hits;
41 Pfizer SPCs. Server caps the `results` array at 3,000 entries
per query — narrow queries needed for high-population applicants.

### tavaramerkkitietopalvelu.prh.fi — trademark + TMR API

| Field | Value |
|---|---|
| Endpoint | `https://tavaramerkkitietopalvelu.prh.fi/nis-api-gateway/` |
| Auth | **none** |
| Format | JSON; image surfaces are GIF + JPEG |
| Rating | 🟢 **Green (undocumented)** |
| Primary source | reverse-engineered from [`tavaramerkkitietopalvelu.prh.fi`](https://tavaramerkkitietopalvelu.prh.fi/) React bundle 2026-05-18 |

Confirmed endpoints:

```
POST /nis-api-gateway/trademark          — TM corpus search (282,824 records back to 1891)
POST /nis-api-gateway/tmr                — well-known marks (111 records)
GET  /opendata/trademark/image/{n}/{r}   — full image (GIF on probe)
GET  /opendata/trademark/thumbnail/{n}/{r}            — small thumbnail (JPEG)
GET  /opendata/trademark/thumbnail/large/{n}/{r}      — large thumbnail (JPEG)
```

Bundle also references `recordal`, `opposition`, `international`,
`tmrResults` as additional endpoint names in the router pool — not yet probed.

### mallioikeustietopalvelu.prh.fi — design API

| Field | Value |
|---|---|
| Endpoint | `https://mallioikeustietopalvelu.prh.fi/nis-api-gateway/` |
| Auth | **none** |
| Format | JSON |
| Rating | 🟢 **Green (undocumented)** |
| Primary source | reverse-engineered from [`mallioikeustietopalvelu.prh.fi`](https://mallioikeustietopalvelu.prh.fi/) React bundle 2026-05-18 |

Confirmed endpoint:

```
POST /nis-api-gateway/design             — design corpus search (33,682 records back to 1971)
```

Each design record carries Locarno classifications and a
`designs: [{...}]` array of per-application design embodiments.

### avoindata.prh.fi — business-register open-data (sister service, IP-irrelevant)

| Field | Value |
|---|---|
| Endpoint | `https://avoindata.prh.fi/opendata-ytj-api/v3/`, `/opendata-krek-api/v3/`, `/opendata-xbrl-api/v3/` |
| Auth | none |
| Format | JSON |
| License | **CC-BY 4.0** ([Creative Commons Attribution 4.0 International (EN)](https://creativecommons.org/licenses/by/4.0/deed.en)) |
| Rating | 🟢 green — **but covers business register + financial statements only, not patents/TMs/designs** |
| Primary source | [Tietoa palvelusta / About the service](https://avoindata.prh.fi/fi/info/swagger-ui) |

YTJ business identifiers, registered notifications (krek) from
2014-11-07 onward, iXBRL digital financial statements. **Not in
scope for IP coverage** — listed here because it is the strongest
license-posture signal for the IP search APIs (same office, same
"avoindata" governance umbrella, explicit CC-BY 4.0).

### avoindata.fi — Finland's national open-data portal

| Field | Value |
|---|---|
| Endpoint | [`https://www.avoindata.fi/`](https://www.avoindata.fi/) (CKAN) |
| Result | PRH organization page returns **3 datasets, all business-register**: SBR taxonomy, YTJ JSON, YTJ API metadata. **No IP datasets.** |
| Rating | 🔴 N/A — no IP coverage; informational only |

### WIPO IP API Catalog

| Field | Value |
|---|---|
| Endpoint | [`https://apicatalog.wipo.int/`](https://apicatalog.wipo.int/) |
| Result | **0 PRH entries** as of 2026-05-18 (179 office APIs across DPMA, EPO, EUIPO, IP Australia, JPO, MOIP KOREA, QAZ, UPRP, USPTO, WIPO) |
| Rating | informational — confirms the search APIs are undocumented from the canonical-inventory standpoint |

## §4 Fees

**Policy: link only.**

PRH publishes fee schedules (in EUR) covering patent filing,
search, examination, grant, publication, opposition, appeal, and
annual fees; utility-model registration and renewal; SPC filing
and renewal; trademark filing per class + renewals (Nice
classes); design filing + renewals (Locarno classes); plus
miscellaneous services. Statutory basis is the
[Patents Act 550/1967](https://www.finlex.fi/fi/laki/ajantasa/1967/19670550),
the [Utility Models Act 800/1991](https://www.finlex.fi/fi/laki/ajantasa/1991/19910800),
the [Trade Marks Act 544/2019](https://www.finlex.fi/fi/laki/ajantasa/2019/20190544),
and the [Design Act 221/1971](https://www.finlex.fi/fi/laki/ajantasa/1971/19710221),
each with implementing fee decrees set by the Ministry of
Economic Affairs and Employment (TEM). Government patent fees
are 0 % VAT; commercial trademark and design services attract
25.5 % VAT from 2026-01-01.

- **Official patent fee schedule (EN):** [Patent fees and payment instructions](https://www.prh.fi/patent_fees)
- **Official trademark fee schedule (EN):** [Trademark fees and payment instructions](https://www.prh.fi/en/price-lists/trademark_fees.html)
- **2026 commercial TM + design fee notice (EN):** [Changes to fees for commercial trademark and design right services from 1 January 2026](https://www.prh.fi/en/presentation_and_duties/uutislistaus/announcements/2025/changestofeesforcommercialtrademarkanddesignrightservicesfrom1january2026.html)
- **Live fee calculator:** integrated into the e-filing service at [`https://asiointi.prh.fi/maksupalvelu`](https://asiointi.prh.fi/maksupalvelu) (linked from the patent SPA)

Notable discount programmes *(name only)*:

- **SME fund (EUIPO Ideas Powered for Business)** — partial
  reimbursement of national trademark and design fees, administered
  jointly with EUIPO for FI applicants.
- **PCT national-phase entry into FI** — separate fee profile
  (FI is a PCT contracting state; PRH acts as receiving office,
  ISA, and IPEA under bilateral arrangements).

## §5 Connector strategy

### What we cover today

- **FI-validated EP patents at biblio / family / legal-events fidelity** — transitively via [`patent_client_agents.epo_ops`](../regional/epo.md) (country code `FI`).
- **EUTMs designating FI and Community designs (RCD / REUD)** — transitively via the planned EUIPO connector.
- **Madrid IRs / Hague IRs designating FI** — via planned WIPO Madrid / Hague connectors.
- **UPC-routed disputes touching FI** — via shipped `upc_decisions` connector.

### What we should add (planned — green, undocumented)

- **`patent_client_agents.prh`** — async client over three hosts.
  Same architectural shape as the planned `prv` (Sweden) connector.
  Initial scope:
  - `patents.search(...)` → `POST /nis-api-gateway-pat/patent`
  - `patents.get(application_number)` → `GET /nis-api-gateway-pat/patent/{n}`
  - `trademarks.search(...)` → `POST /nis-api-gateway/trademark`
  - `trademarks.search_tmr(...)` → `POST /nis-api-gateway/tmr` (well-known marks)
  - `designs.search(...)` → `POST /nis-api-gateway/design`
  - `trademarks.image(...)` and `.thumbnail(...)` → `/opendata/trademark/...`
  - Response models for the full `In` (117-element status enum) and `Ln` (42-element publication-type enum) vocabularies extracted from the React bundle
  - Pagination wrapper that warns when totalResults > 3,000 (server-side cap, no client paging exposed)

**Closes the FI-national-only patent + UM + SPC + TM + TMR + design gaps.**
Estimated 3-5 days build alongside the parallel SE/PRV connector —
the architectural pattern is identical and can be templated.

### What we should NOT add (and why)

- **HTML scrape of the React SPAs.** The backing APIs are the
  better target — the SPAs only add rendering on top.
- **`avoindata.prh.fi` ingestion as an IP source.** The
  business-register and iXBRL APIs there do not cover patents,
  utility models, trademarks, or designs.
- **Bulk dataset mirroring.** No bulk IP datasets exist on
  `avoindata.fi` (probed 2026-05-18; only 3 PRH datasets, all
  business-register, all CC-BY 4.0).

### Next steps

1. **Send a courtesy registration to `avoindata@prh.fi`** before
   the hosted demo turns on. Identify the project, ask for
   breakage notice, confirm we identify the client by User-Agent.
   No statutory cover for register-data reuse is as explicit as
   Sweden's [SFS 2022:818](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/lag-2022818-om-den-offentliga-sektorns_sfs-2022-818/),
   but Finland implements the same EU Open Data Directive
   (2019/1024) and the sister business-register service is
   already CC-BY 4.0 — proactive contact is cheap insurance.
2. **Bundle re-extraction pass** to enumerate the remaining
   router targets in the TM SPA: `recordal`, `opposition`,
   `international`, `tmrResults`. Best guesses: TM recordal
   register, opposition register, Madrid IR designations to FI,
   TMR pagination.
3. **Probe `/patent/bulletins` and `/patent/surveys` payload
   shape.** Both currently return HTTP 400 — endpoints exist but
   the query body is unknown. Bulletins likely corresponds to
   the weekly patent gazette; surveys is probably user-survey
   metadata (non-essential).
4. **Write `specs/fi-prh-connector-spec.md`** — patterns:
   - Three hosts, one connector class
   - Versionless schema: validate response shape on every call,
     surface clean errors when fields disappear
   - Polite caching: 5 min for status views, 24 h for record bodies
   - User-Agent identifying the project + contact link

## §6 Open questions

- **License clarity on the IP search APIs.** Sister business-register
  service is explicit CC-BY 4.0; the IP APIs share the
  `/opendata/...` path prefix on image surfaces but the published
  ToS only covers business-register data. Email enquiry to
  `avoindata@prh.fi` recommended before production deployment.
- **Server-side cap on `results`.** Probes confirm a hard 3,000-row
  ceiling regardless of `pageSize` / `page` / `limit` / `offset`
  inputs. Whether a documented pagination cursor exists, and what
  parameter name unlocks it, is unknown.
- **`PatentDossier` vs. `PatentEurope` discrimination.** The
  `patentTypes` enum splits FI-national patents and EP-FI
  validations cleanly — needs confirmation that PCT national-phase
  entries (NATO route) land in `PatentDossier` and not a separate
  bucket.
- **TM Madrid IR coverage.** The TM index returned 282,824 records;
  the proportion of those that are Madrid IRs (vs. FI-national
  filings) is not yet derived. The `dossierStatus` enum may carry
  a discriminator that we haven't extracted.
- **Design Hague IR coverage.** Same question for the design index.
- **TMR refresh cadence.** 111 well-known marks is a small set
  — is this curated by PRH manually, and how often?
- **Rate-limit behavior under load.** No headers observed on
  single-pager probes — production patterns unknown.
- **Bulletins + surveys payload shape.** Both endpoints return
  HTTP 400 (not 404) — body parameters need bundle re-extraction.
- **Norwegian / Danish parallel.** Norway (NIPO/Patentstyret) and
  Denmark (DKPTO) are the remaining Nordic offices. With Sweden
  and Finland both green on the same modern-SPA pattern, the
  Nordic-office cluster hypothesis is worth re-testing —
  Norway and Denmark are next.

## §7 References

Primary sources only — `prh.fi`, `patenttitietopalvelu.prh.fi`,
`tavaramerkkitietopalvelu.prh.fi`, `mallioikeustietopalvelu.prh.fi`,
`avoindata.prh.fi`, `avoindata.fi`, `finlex.fi` for substantive
law, `apicatalog.wipo.int`.

**Service overviews:**
- [PRH EN home](https://www.prh.fi/en/)
- [PRH Patent Information Service accessibility statement (EN)](https://www.prh.fi/en/presentation_and_duties/accessibility_in_our_online_services/patent_information_service.html)
- [PRH Patentinformationstjänst — Swedish landing](https://patenttitietopalvelu.prh.fi/sv)
- [PRH open data overview — business register (EN)](https://www.prh.fi/en/companiesandorganisations/tietopalvelut/prhopendata.html)
- [PRH organisation card on Suomi.fi (EN)](https://www.suomi.fi/organization/finnish-patent-and-registration-office/9425cf74-0ca7-4cd1-b804-3a51131962fa)
- [PRH news (Current issues) listing (EN)](https://www.prh.fi/en/presentation_and_duties/uutislistaus/announcements.html)

**Live IP search APIs (probed 2026-05-18 — undocumented but unauthenticated):**
- [`patenttitietopalvelu.prh.fi`](https://patenttitietopalvelu.prh.fi/) — patents + UM + SPC + EP-FI (`/nis-api-gateway-pat/`)
- [`tavaramerkkitietopalvelu.prh.fi`](https://tavaramerkkitietopalvelu.prh.fi/) — trademarks + TMR (`/nis-api-gateway/`)
- [`mallioikeustietopalvelu.prh.fi`](https://mallioikeustietopalvelu.prh.fi/) — designs (`/nis-api-gateway/`)

**Business-register open data (CC-BY 4.0):**
- [`avoindata.prh.fi`](https://avoindata.prh.fi/) — service home with swagger UI for YTJ, krek, XBRL
- [Tietoa palvelusta / About the service (EN)](https://avoindata.prh.fi/en/info/swagger-ui)
- [Creative Commons Attribution 4.0 International (EN deed)](https://creativecommons.org/licenses/by/4.0/deed.en) — license posture confirmed on the avoindata service

**Substantive law (Finlex — Finland's official statute database):**
- [Patenttilaki 550/1967 — Patents Act (ajantasa)](https://www.finlex.fi/fi/laki/ajantasa/1967/19670550)
- [Patents Act 550/1967 — English translation](https://www.finlex.fi/en/legislation/translations/1967/eng/550)
- [Hyödyllisyysmallioikeuslaki 800/1991 — Utility Models Act (ajantasa)](https://www.finlex.fi/fi/laki/ajantasa/1991/19910800)
- [Tavaramerkkilaki 544/2019 — Trade Marks Act (ajantasa)](https://www.finlex.fi/fi/laki/ajantasa/2019/20190544)
- [Trade Marks Act 544/2019 — English translation](https://finlex.fi/en/legislation/translations/2019/eng/544)
- [Mallioikeuslaki 221/1971 — Design Act (ajantasa)](https://www.finlex.fi/fi/laki/ajantasa/1971/19710221)

**Fees:**
- [Patent fees (EN)](https://www.prh.fi/patent_fees)
- [Trademark fees (EN)](https://www.prh.fi/en/price-lists/trademark_fees.html)
- [Changes to commercial TM + design fees from 2026-01-01 (EN)](https://www.prh.fi/en/presentation_and_duties/uutislistaus/announcements/2025/changestofeesforcommercialtrademarkanddesignrightservicesfrom1january2026.html)

**Cross-office context:**
- [WIPO IP API Catalog](https://apicatalog.wipo.int/) — probed 2026-05-18; 0 PRH entries across 179 office APIs
- [PRV / Sweden — sister Nordic-office synopsis](./se-prv.md) — same green-undocumented pattern
- [Suomi.fi — Apply for a trademark (FI patent and registration office)](https://www.suomi.fi/services/applying-for-a-trademark-finnish-patent-and-registration-office/9d580c6f-ba1e-41b3-b053-a5109bf3ff46)

**Detail surveys + waves:**
- [`waves/2026-05-18-secondary-nationals-wave/fi-prh.md`](../waves/2026-05-18-secondary-nationals-wave/fi-prh.md) — 2026-05-18 grounded API discovery

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-18 | Initial synopsis; rating **`green_undocumented`**. Findings: (a) PRH runs **three** unauthenticated JSON APIs behind modern React SPAs at [`patenttitietopalvelu.prh.fi`](https://patenttitietopalvelu.prh.fi/), [`tavaramerkkitietopalvelu.prh.fi`](https://tavaramerkkitietopalvelu.prh.fi/), and [`mallioikeustietopalvelu.prh.fi`](https://mallioikeustietopalvelu.prh.fi/), proxied through internal gateways `/nis-api-gateway-pat` (patents) and `/nis-api-gateway` (TM + design); (b) corpus sizes probed end-to-end: **393,750 patent + UM + SPC + EP-FI records**, **282,824 trademarks** back to 1891, **111 well-known marks (TMR)**, **33,682 designs** back to 1971 — all in fully-structured JSON with FI/SV/EN trilingual title slots; (c) per-application GET `/nis-api-gateway-pat/patent/{n}` returns register-fidelity prosecution data (named examiner, named representative, annual-fee payment timeline with creditor reference, T-prefixed EP-translation kind codes, SPC authorizations); (d) trademark image surface at `/opendata/trademark/image/.../.../` and thumbnail variants serves GIF/JPEG directly; (e) sister business-register service [`avoindata.prh.fi`](https://avoindata.prh.fi/) is explicit **CC-BY 4.0** — the strongest available license-posture signal for the IP search APIs (which share the `/opendata/...` path prefix on image surfaces); (f) [WIPO IP API Catalog](https://apicatalog.wipo.int/) returns 0 PRH entries — the APIs are undocumented from the canonical-inventory standpoint; (g) server-side cap of **3,000 results** per query with no client-paging exposed — narrow queries required for high-population applicants. Same Nordic-office green-undocumented pattern as Sweden's [PRV](./se-prv.md). Production posture: courtesy-register with `avoindata@prh.fi` + watch for breakage. Recommended `connector_status: planned`. | [waves/2026-05-18-secondary-nationals-wave/fi-prh.md](../waves/2026-05-18-secondary-nationals-wave/fi-prh.md) |
