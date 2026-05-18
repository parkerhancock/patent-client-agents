# IL/ILPO — wave file (2026-05-18 priority-2 synopses)

Grounded API discovery for the **Israel Patent Office** (ILPO; רשם
הפטנטים, המדגמים וסימני המסחר), the registration unit inside the
Ministry of Justice that runs all three Israeli registered IP rights
(patents, trademarks, designs) plus appellations of origin / GIs. The
existing 2026-05 detail survey at
[`connectors/israel_pto.md`](../../connectors/israel_pto.md) is the
working baseline; this wave re-verifies primary sources against today's
ILPO domains and resolves the open question about whether anything has
shifted on the register-API front since the survey was written.

Rights covered: patent, trademark, design, geographical indication
(appellations of origin under the 5725-1965 law administered by ILPO).
Plant breeders' rights sit with the Plant Variety Council under the
Ministry of Agriculture, not ILPO.

---

## 1. Endpoint

ILPO publishes **three asset-typed register portals plus a separate
gazette**, none of which expose a public REST/JSON contract. The full
inventory observed today:

- **`israelpatents.justice.gov.il`** — flagship Patents Search +
  file-inspection portal. Modern **Angular SPA** served with hashed JS
  chunks (`main-OYASZJHU.js`, `chunk-…`) that hydrate a runtime
  `webApiAddress` from a server-side config endpoint. Verified live
  2026-05-18 at the [English landing page](https://israelpatents.justice.gov.il/en/home)
  and the canonical search URL pattern
  `israelpatents.justice.gov.il/<lang>/search?AP_0_option=Any&AP_0_0=<appno>`
  ([example](https://israelpatents.justice.gov.il/en/search?AP_0_option=Any&AP_0_0=234599),
  [per-record landing](https://israelpatents.justice.gov.il/en/patent-file/details/135507)).
  No published OpenAPI; the SPA backend uses **CSRF tokens, reCAPTCHA,
  and Glassbox session capture** (`isGlassboxOn` flag visible in
  client config) — explicit anti-automation telemetry. No documented
  JSON contract.
- **`trademarks.justice.gov.il`** — Trademarks Search portal, **ASP.NET
  MVC + Kendo UI** stack. Verified at
  [`trademarks.justice.gov.il/TradeMarkSearch/TradeMarkSearch?lang=en`](https://trademarks.justice.gov.il/TradeMarkSearch/TradeMarkSearch?lang=en).
  No documented API; the supported machine-readable substrate is the
  bulk CKAN feed on data.gov.il (below), not this UI.
- **`designsearch.justice.gov.il`** — Designs Search portal, same
  ASP.NET MVC + Kendo UI stack. Verified live at
  [the search root](https://designsearch.justice.gov.il/). Approximate
  total record count ~25,000 per the 2026-05 detail survey; not
  re-verified against a current count from the portal because the SPA
  does not surface a total in the response envelope.
- **`israelpatents.justice.gov.il/<lang>/patents-journal`** — official
  **Patents Journal / Gazette** section, browsed inside the same SPA.
  Per-issue PDF downloads of "Full Publications" plus per-event
  sections (publications, oppositions, grants, lapsed, restored, PCT
  events). Monthly cadence. Inherits the anti-automation surface of the
  parent SPA.
- **`data.gov.il`** — Israel's national CKAN-based open-data portal,
  operated by the Government ICT Authority. The Ministry of Justice
  publishes the **trademark register dataset** here on a weekly basis —
  the only confirmed structured ILPO-source feed. Landing page at
  [`gov.il/en/departments/data_gov_il/govil-landing-page`](https://www.gov.il/en/departments/data_gov_il/govil-landing-page);
  CKAN backend documented in the open-source
  [`datagovil-ckanext`](https://github.com/gov-il/datagovil-ckanext)
  extensions. No primary-source page enumerates a parallel patents or
  designs dataset alongside the TM feed.
- **`gov.il/en/departments/ilpo`** — the unified ILPO department page
  on the consolidated `gov.il` portal, used as the entry point for
  examination guidelines, work-procedure circulars, fees, and the
  ILPO's own service pages. The Hebrew-side
  [`gov.il/he/Departments/DynamicCollectors/work-procedure-db`](https://www.gov.il/he/Departments/DynamicCollectors/work-procedure-db?skip=0)
  hosts the per-procedure work-procedure database (HE primary, EN for
  selected high-impact procedures).
- **`justice.gov.il/En/Units/ILPO/...`** — legacy English-side Ministry
  of Justice unit page; [Search Databases hub](https://www.justice.gov.il/En/Units/ILPO/Departments/Patents/Guides/Pages/SearchDatabases.aspx)
  links onward to the three search portals above.

There is **no separate REST surface**, no documented OpenAPI/Swagger,
no Atom feed, no SOAP, no documented bulk SFTP, and no documented
GraphQL or SPARQL endpoint anywhere across the ILPO estate. The Angular
SPA has an internal JSON contract behind reCAPTCHA + CSRF + Glassbox;
that contract is **not published** and is not stable across builds.

## 2. Auth

- **`israelpatents.justice.gov.il` (SPA + JSON backend)**: anonymous
  browse on the surface, but the JSON backend is bound to a CSRF token
  issued at session start, **reCAPTCHA challenges** (visible
  client-side `recaptcha` script reference in the SPA bundle), and
  **Glassbox session-capture instrumentation**
  (`isGlassboxOn`/`glassboxApplicationId` flags). The combination is a
  textbook anti-automation perimeter.
- **`trademarks.justice.gov.il`**: anonymous browse; no published API
  contract; ASP.NET WebForms session cookies on the supporting forms.
- **`designsearch.justice.gov.il`**: same posture as TMs — anonymous
  browse, no API.
- **`data.gov.il` CKAN**: free public reads; an API key is available
  for higher-volume / production access via the portal account flow.
  No documented foreign-developer signup restriction. CKAN's standard
  `package_show` / `resource_show` / `datastore_search` endpoints
  apply.
- **Examination guidelines / `gov.il`**: anonymous read; PDFs served
  as static assets.

Foreign-developer accessibility: data.gov.il is the only ILPO-source
substrate that is unambiguously open to non-Israeli signups (the rest
require no signup but enforce anti-automation at the network /
reCAPTCHA layer). The three register portals were built for human use
inside the Israeli legal-services market; nothing in their visible
configuration suggests programmatic-third-party use is contemplated.

## 3. Query language

- **Patents SPA**: query-string-driven search on the URL surface
  (`AP_0_option=<field>&AP_0_<idx>=<value>`), with stacked filter
  groups behind the visible URL. The backend JSON contract is not
  published, so any field grammar must be reverse-engineered per
  build, against the CAPTCHA gate.
- **TMs / Designs portals**: HTML form fields per asset (number,
  proprietor, classification, filing date). ASP.NET `__VIEWSTATE` POST
  shape; no documented URL grammar.
- **Patents Journal**: browse-only inside the SPA; no documented query
  parameters.
- **data.gov.il CKAN**: standard CKAN
  [`/api/3/action/datastore_search?resource_id=…`](https://docs.ckan.org/en/latest/api/#ckan.logic.action.get.datastore_search)
  with `q=`, `filters=`, `limit=`, `offset=`. Field-level filters are
  defined by the underlying dataset schema, which Israel's CKAN
  exposes per resource.

No CQL, no Lucene/SolR documented on the public surface.

## 4. Pagination

- **Patents SPA**: client-side pagination inside the SPA shell; the
  HTTP JSON contract is not published.
- **TMs / Designs**: HTML hit lists paginated via ASP.NET postbacks.
- **data.gov.il CKAN**: standard CKAN `limit` / `offset` semantics
  ([CKAN datastore docs](https://docs.ckan.org/en/latest/maintaining/datastore.html)).

## 5. Response shape

- **Patents SPA**: HTML envelope; per-record landing pages render
  bibliographic data, IPC, classification, dispatch / event timeline,
  and PDF-download links. The undocumented JSON contract carries the
  same fields but is not stable across SPA rebuilds.
- **TMs / Designs**: HTML result tables and per-record detail pages.
- **Patents Journal**: per-issue HTML index + per-event PDFs.
- **data.gov.il TM dataset**: CKAN JSON envelope `{"result": {"records": [...]}}`,
  bilingual Hebrew + English fields per the CKAN dataset schema. The
  exact field set was not re-walked in this wave; the 2026-05 detail
  survey reports parallel HE/EN fields. Re-verify against the live
  dataset page before any user-facing commitment about field coverage.

No primary source found for a sample JSON of a single ILPO **register**
hit because **there is no public register JSON surface to sample**.

## 6. Coverage scope

- **Patents SPA** — all Israeli national patent applications plus PCT
  national-phase entries to IL. WIPO INSPIRE reports **2011-present
  for legal events**; biblio backfile extends earlier via legacy data.
  [INSPIRE IL profile](https://inspire.wipo.int/system/files/juri/il.pdf).
- **TM portal** — all Israeli national TMs + Madrid IRs designating
  IL (IL has been a Madrid Protocol member since 2010 per the
  [Madrid member list](https://www.wipo.int/madrid/en/members/)).
- **Designs portal** — registered designs under the Israeli Designs
  Law 5777-2017 (in force 2018-08-07) and legacy filings under the
  former Patents and Designs Ordinance; covered by Hague IRs as of
  Israel's accession (2020).
- **Patents Journal** — monthly issues from 2011-present per the SPA
  archive (verified by the same INSPIRE profile above).
- **data.gov.il TM dataset** — weekly refresh per the 2026-05 detail
  survey. Live dataset accessible via the data.gov.il portal index.
  Patent and design parallel datasets on data.gov.il are **not
  evidenced by primary source** as of 2026-05-18 — the survey flagged
  this as an open question and that question is still open.

PCT side: Israel is **ISA / IPEA from 2012-06-01** per the
[USPTO notice](https://www.uspto.gov/sites/default/files/patents/law/notices/ilpo_isa-ipea.pdf)
+ [PCT eGuide IL](https://pctlegal.wipo.int/eGuide/view-doc.xhtml?doc-code=IL&doc-lang=en).
ILPO-issued ISRs and written opinions appear inside WIPO PATENTSCOPE
under the standard PCT event flow; they are not a separate IL feed.

## 7. Rate limits / quotas

- **Patents SPA**: undocumented; the reCAPTCHA + Glassbox stack is the
  enforcement mechanism. No primary source publishes throttle
  thresholds.
- **TMs / Designs portals**: no published rate limits.
- **data.gov.il CKAN**: no per-IP rate limit pinned on the public
  documentation surface (the CKAN extension repo
  [`datagovil-ckanext`](https://github.com/gov-il/datagovil-ckanext)
  is the operational substrate but does not publish a throttle table).
  API keys lift any soft caps.

## 8. Terms of service

- **`data.gov.il` open-data**: Israel's national open-data programme.
  No primary source pins a single line of redistribution licence text
  in the wave's evidence trail; the portal operates under the
  government's open-data policy administered through `gov.il`. Walk
  the dataset page before any redistribution claim.
- **`israelpatents.justice.gov.il`**: terms displayed inside the SPA
  + reCAPTCHA enforcement implicitly prohibit automated scraping. No
  primary source found for a standalone "Terms of Use" page on the
  patents-search domain beyond the SPA-rendered text.
- **`trademarks.justice.gov.il` / `designsearch.justice.gov.il`**: no
  primary-source ToS page found in this wave; same implicit prohibition
  via session cookies + WebForms enforcement.
- **Substantive law**: WIPO Lex authorised translations carry an "EN
  translation by ILPO / Ministry of Justice, reproduced with
  permission" notice — public read; the controlling text is the
  Hebrew, reachable through
  [Knesset](https://main.knesset.gov.il/en/), Nevo (paywalled), or
  Takdin (paywalled). [WIPO Lex IL profile](https://www.wipo.int/wipolex/en/profile.jsp?code=IL)
  is the canonical hub.

## 9. Operational notes

- **Languages**: Hebrew is the controlling language across statute and
  the register. ILPO's three search portals all expose an EN locale
  (`?lang=en` on TMs / Designs; `/en/...` on Patents); EN coverage of
  examination guidelines and the work-procedures database is
  partial — selected high-impact procedures translated, the bulk
  Hebrew-primary.
- **Geofencing**: none observed on the SPA, TM/design portals, or
  data.gov.il; CAPTCHA + Glassbox replace any explicit geo-block.
- **Anti-automation perimeter**: the Patents SPA's combination of
  CSRF + reCAPTCHA + Glassbox is unusually aggressive for a national
  IP-office register. It is *not* a coincidence; it's an explicit
  product decision by the Ministry of Justice's IT directorate that
  forecloses any reasonable hosted-proxy posture from our side.
- **Case-law side (outside ILPO)**: IP first-instance jurisdiction is
  **District Court**, with the **Tel Aviv District Court Economic
  Department** hearing the bulk of patent / TM litigation; final
  appeal at the **Supreme Court** (no specialised IP court of
  appeals). [supreme.court.gov.il](https://supreme.court.gov.il/sites/en/Pages/home.aspx)
  publishes selected decisions; English translations are scarce and
  curated. The **Versa project at Cardozo Law School**
  ([versa.cardozo.yu.edu](https://versa.cardozo.yu.edu/topics/intellectual-property))
  is the only practical English entry point to Israeli Supreme Court
  IP case law, with ~700 curated translations across all subject
  areas; the IP slice (trademarks topic, IP topic) is the surfaceable
  subset.
- **Commercial legal-research databases**: [Nevo](https://www.nevo.co.il/)
  (publishes all court decisions since 1997) and Takdin (~600k cases
  + statutes). Both subscription, both scrape-hostile, both how Israeli
  attorneys actually access case law. Pricing is per-seat law-firm
  pricing — out of budget for v1.
- **PCT ISA / IPEA status (2012-06-01)** affects how IL prosecution
  data is **surfaced** in WIPO PATENTSCOPE but does not give ILPO a
  separate developer-facing API. ISA / IPEA agreements track at
  [WIPO PCT agreements](https://www.wipo.int/en/web/pct-system/access/isa_ipea_agreements).

## 10. Rating

**Register-side rating: 🔴 red_no_api.**

ILPO exposes **no public REST/JSON register API** for patents,
trademarks, or designs. The patents-side portal is an Angular SPA
fronted by reCAPTCHA + Glassbox + CSRF, with no documented JSON
contract and a perimeter that is **explicitly anti-automation**. The
TM and design portals are ASP.NET WebForms with no API. The data.gov.il
weekly trademark dataset is a **bulk feed**, not a query endpoint —
useful as a daily-incremental walk into an external index, but
explicitly off-spec under our hard constraint ("proxy live APIs at
runtime; do NOT host bulk dumps, build search indexes, or maintain
offline corpora"). Under that constraint, the register-side surface is
indistinguishable in outcome from "no API at all."

This **confirms** the existing STATE.yaml rating of `red_no_api`;
the older 2026-05 detail survey's "scrape-only" framing maps cleanly
onto the current rating taxonomy.

**Substantive-law side rating** (the orthogonal question this wave is
asked to answer): **🟢 green** for the static-law layer. Israel's
statute landscape is one of the easiest in our coverage map — eight
core IP statutes with authoritative ILPO/Ministry-of-Justice English
translations on WIPO Lex, mirrorable once into our `StaticLawCorpus`
shape exactly the way DPMA, Légifrance, IPO India, and Taiwan are
already done. **The two ratings are independent**: the register
verdict is "no API, skip"; the statutes verdict is "clean static
corpus, ship."

---

## Drift vs. the 2026-05 detail survey

- **Register surface**: no material change. The Angular SPA at
  `israelpatents.justice.gov.il` is still live with the same
  anti-automation perimeter; the TMs and Designs portals are still
  ASP.NET WebForms. The 2026-05 survey's "Hard — modern SPA … no
  documented contract" / "Medium — legacy ASP.NET, no API" framings
  remain accurate. No new public API has been announced by ILPO.
- **`pibd`-style FR case-law migration analogue**: no equivalent
  observed for IL — there is **no announced replacement** for the
  Patents SPA's data layer with a documented developer API.
- **data.gov.il**: the trademark dataset endpoint is still the only
  confirmed structured ILPO-source feed; the survey's open question
  about parallel patents/designs datasets is **still open** (no
  primary source as of 2026-05-18 enumerating a patents or designs
  dataset alongside the TMs feed).
- **Stale worktree at IL/ILPO**: STATE.yaml shows
  `connector_status: in_progress` because a 2026-05 worktree built an
  "ILPO statutes + TM bulk catalog." The substrates that worktree
  targeted — WIPO Lex statute mirroring + data.gov.il CKAN TM feed —
  are both **still live and addressable** today. The bulk-catalog
  half of that worktree is the same shape question we've already
  resolved for BR/INPI (sibling wave file
  [`br-inpi.md`](./br-inpi.md)): hosting an offline TM index is
  off-spec under current standards even if the data substrate is
  clean.

## Connector-strategy implications

Two independent questions, two independent decisions:

1. **Register layer (patents / TMs / designs).** Skip. There is no
   usable REST surface, the SPA is explicitly anti-automation, and
   coverage of the bibliographic essentials is already provided
   transitively by EPO INPADOC (IL biblio + family + legal events from
   2011), WIPO Madrid (Madrid IRs designating IL), and WIPO Hague
   (Hague IRs designating IL). File-wrapper PDFs and Israeli national-
   only TMs are real coverage gaps, but the demand is too thin and the
   perimeter too hostile to justify the build. Rating stays
   **🔴 red_no_api**.

2. **Substantive-law layer (the stale `israel_statutes` worktree).**
   **Revive, do not close.** The eight statutes
   ([Patents Law 5727-1967](https://www.wipo.int/wipolex/en/legislation/details/15167),
   [Patents Regulations 5728-1968](https://www.wipo.int/wipolex/en/legislation/details/19117),
   [Trade Marks Ordinance 5732-1972](https://www.wipo.int/wipolex/en/legislation/details/8200),
   [Designs Law 5777-2017](https://www.wipo.int/wipolex/en/legislation/details/19434),
   [Commercial Torts Law 5759-1999](https://www.wipo.int/wipolex/en/legislation/details/2375)
   — the standalone trade-secrets statute,
   [Plant Breeders' Rights Law 5733-1973](https://www.wipo.int/wipolex/en/legislation/details/9524),
   [Copyright Act 5768-2007](https://www.wipo.int/wipolex/en/legislation/details/11509),
   [Appellations of Origin 5725-1965](https://www.wipo.int/wipolex/en/legislation/details/2373))
   are all addressable today via WIPO Lex with authoritative EN
   translations published by ILPO / Ministry of Justice. This is the
   same shape as `ipo_in_statutes`, `dpma_statutes`, `legifrance_ip`,
   `tw_trade_secrets`. Half-day-per-statute work; high agent-value
   payoff for Israeli prosecution, opposition, and trade-secret
   matters. The unique-feature row is the **Commercial Torts Law
   5759-1999** — a statute that combines trade secrets with
   unregistered marks and procedural remedies (Anton Piller-style
   seizures, asset freezes) in one instrument, distinct from the
   common-law breach-of-confidence baseline and from the EU Directive
   2016/943 transpositions.

The bulk-TM-catalog half of the stale worktree should **not** be
revived under current standards — it would require hosting an offline
index, which is exactly the constraint we deliberately violated
ourselves into on IL+BR+SG and have since explicitly reversed in
CONNECTOR_STANDARDS.md.

## Recommended STATE.yaml resolution (read-only here; orchestrator owns the write)

- `rating: red_no_api` — confirmed, unchanged.
- `rating_basis:` register portals are Angular SPA + reCAPTCHA + Glassbox
  (patents) and ASP.NET WebForms (TMs, designs); data.gov.il TMs feed is
  bulk, not query — off-spec under current standards.
- `connector_status:` move from `in_progress` to **`planned`** for the
  **statutes** half (revive `israel_statutes` as `StaticLawCorpus`) and
  **`none`** / **`closed_bulk_only`** for the **register / TM bulk** half.
  Two manifest IDs not one: `IL/ILPO/Statute` (planned) +
  `IL/ILPO/Register` (none).
- `next_action: spec_writing` for the statutes half; `monitor` for
  the register half (watch for a documented ILPO REST surface or
  a PIBD-style migration announcement — neither has been signalled).
- `last_verified: 2026-05-18`.

## Sources (primary)

- ILPO unit (Ministry of Justice EN): [`justice.gov.il/En/Units/ILPO`](https://www.justice.gov.il/En/Units/ILPO/Pages/default.aspx)
- ILPO consolidated `gov.il` page: [`gov.il/en/departments/ilpo`](https://www.gov.il/en/departments/ilpo)
- Search Databases hub (EN): [`justice.gov.il/En/Units/ILPO/Departments/Patents/Guides/Pages/SearchDatabases.aspx`](https://www.justice.gov.il/En/Units/ILPO/Departments/Patents/Guides/Pages/SearchDatabases.aspx)
- Patents Search SPA (EN home): [`israelpatents.justice.gov.il/en/home`](https://israelpatents.justice.gov.il/en/home)
- Patents Search query example: [`israelpatents.justice.gov.il/en/search?AP_0_option=Any&AP_0_0=234599`](https://israelpatents.justice.gov.il/en/search?AP_0_option=Any&AP_0_0=234599)
- Patents Search per-record example: [`israelpatents.justice.gov.il/en/patent-file/details/135507`](https://israelpatents.justice.gov.il/en/patent-file/details/135507)
- Trademarks Search (EN): [`trademarks.justice.gov.il/TradeMarkSearch/TradeMarkSearch?lang=en`](https://trademarks.justice.gov.il/TradeMarkSearch/TradeMarkSearch?lang=en)
- Designs Search: [`designsearch.justice.gov.il`](https://designsearch.justice.gov.il/)
- data.gov.il landing: [`gov.il/en/departments/data_gov_il/govil-landing-page`](https://www.gov.il/en/departments/data_gov_il/govil-landing-page)
- data.gov.il CKAN extension (open-source repo): [`github.com/gov-il/datagovil-ckanext`](https://github.com/gov-il/datagovil-ckanext)
- ILPO work-procedures DB (HE): [`gov.il/he/Departments/DynamicCollectors/work-procedure-db`](https://www.gov.il/he/Departments/DynamicCollectors/work-procedure-db?skip=0)
- WIPO INSPIRE IL profile: [`inspire.wipo.int/system/files/juri/il.pdf`](https://inspire.wipo.int/system/files/juri/il.pdf)
- WIPO Lex IL hub: [`wipo.int/wipolex/en/profile.jsp?code=IL`](https://www.wipo.int/wipolex/en/profile.jsp?code=IL)
- Patents Law 5727-1967: [WIPO Lex 15167](https://www.wipo.int/wipolex/en/legislation/details/15167)
- Patents Regulations 5728-1968: [WIPO Lex 19117](https://www.wipo.int/wipolex/en/legislation/details/19117)
- Trade Marks Ordinance 5732-1972: [WIPO Lex 8200](https://www.wipo.int/wipolex/en/legislation/details/8200)
- Designs Law 5777-2017: [WIPO Lex 19434](https://www.wipo.int/wipolex/en/legislation/details/19434)
- Commercial Torts Law 5759-1999: [WIPO Lex 2375](https://www.wipo.int/wipolex/en/legislation/details/2375)
- Plant Breeders' Rights Law 5733-1973: [WIPO Lex 9524](https://www.wipo.int/wipolex/en/legislation/details/9524)
- Copyright Act 5768-2007: [WIPO Lex 11509](https://www.wipo.int/wipolex/en/legislation/details/11509)
- Appellations of Origin Law 5725-1965: [WIPO Lex 2373](https://www.wipo.int/wipolex/en/legislation/details/2373)
- Madrid Protocol member list: [`wipo.int/madrid/en/members`](https://www.wipo.int/madrid/en/members/)
- Knesset: [`main.knesset.gov.il/en`](https://main.knesset.gov.il/en/)
- Supreme Court of Israel (EN): [`supreme.court.gov.il/sites/en`](https://supreme.court.gov.il/sites/en/Pages/home.aspx)
- Versa (Cardozo) Israeli Supreme Court Project — IP topic: [`versa.cardozo.yu.edu/topics/intellectual-property`](https://versa.cardozo.yu.edu/topics/intellectual-property)
- Versa — Trademarks topic: [`versa.cardozo.yu.edu/topics/trademarks`](https://versa.cardozo.yu.edu/topics/trademarks)
- PCT ISA / IPEA — USPTO notice on ILPO: [`uspto.gov/.../ilpo_isa-ipea.pdf`](https://www.uspto.gov/sites/default/files/patents/law/notices/ilpo_isa-ipea.pdf)
- PCT eGuide IL: [`pctlegal.wipo.int/eGuide/view-doc.xhtml?doc-code=IL`](https://pctlegal.wipo.int/eGuide/view-doc.xhtml?doc-code=IL&doc-lang=en)
- Earlier detail survey: [`connectors/israel_pto.md`](../../connectors/israel_pto.md)
