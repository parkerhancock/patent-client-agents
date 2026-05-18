# UIBM Italy (IT) — Patents, Trademarks, Designs API Discovery

**Date:** 2026-05-18
**Scope:** Determine whether the **Ufficio Italiano Brevetti e Marchi**
(UIBM — the Italian Patent and Trademark Office, sitting inside the
**Direzione Generale per la Tutela della Proprietà Industriale (DGTPI)**
of the **Ministero delle Imprese e del Made in Italy / MIMIT**, the
re-branded successor to the former MISE) exposes a public, queryable
REST/JSON/XML API we can proxy at runtime with zero infrastructure on
our side. Bulk dumps and HTML-only surfaces would be **red**; per-user
BYOK is **yellow**; undocumented-but-unauthenticated stable JSON is
**green**. Italy is an EPC contracting state, an EU member, and a UPC
contracting state — and as of [2024-06-27](https://www.unified-patent-court.org/en/news/opening-milan-it-section-central-division)
also hosts the **Milan section of the UPC Central Division** (third
seat, jurisdiction over IPC class A "Human Necessities" excluding
SPCs), replacing the originally planned London seat after Brexit. So
most "Italian patents" of commercial scale are EP-route (covered by
EPO OPS), most "Italian trademarks" of scale are EUTMs (covered by
EUIPO), and Italian patent disputes can route through the UPC
connector (already shipped). UIBM's value-add for agents is the
**IT-national-only slice**.

**TL;DR — Verdict: 🔴 red_no_api.** UIBM does **not** publish any
REST/JSON/XML developer API, has **no entry** in the [WIPO IP API
Catalog](https://apicatalog.wipo.int/) (probed 2026-05-18; 0 UIBM
results across 179 office APIs from DPMA / EPO / EUIPO / IP Australia /
JPO / MOIP Korea / QAZ / UPRP / USPTO / WIPO), and has **no UIBM /
MIMIT-IP dataset** on Italy's national open-data portal
[`dati.gov.it`](https://www.dati.gov.it/) (probed via CKAN
`package_search?q=uibm` → 0 hits; `?q=brevetti` → 15 hits all
third-party / regional / university; `?q=proprietà industriale` →
6 hits none from UIBM; `package_list` full sweep → 0 matches with
"uibm" or "marchi" / "brevetti" attributable to UIBM). The principal
search front-end is [`uibm.gov.it/bancadati/`](https://www.uibm.gov.it/bancadati/)
— a CodeIgniter / jQuery / Bootstrap 3 server-rendered application
whose AJAX endpoints **do respond unauthenticated** (verified probe
returns **1,298 records for "FERRARI S.P.A."** as `applicant` via
[`POST /bancadati/index.php/single_search/general/applicant_search/result`](https://www.uibm.gov.it/bancadati/)
with only a `ci_session` cookie and zero recaptcha token) but **return
HTML chunks, not JSON**, and the site's [Note Legali (binding legal
notice)](https://brevettidb.uibm.gov.it/static/images/UIBM-BrevettiDB_noteLegali.pdf)
**expressly prohibits "deep linking"** (verbatim: *"E' vietato il cd.
'deep linking' ossia l'utilizzo non trasparente, su siti di soggetti
terzi, di parti del sito"*). The e-filing portal at
[`servizionline.uibm.gov.it`](https://servizionline.uibm.gov.it/) is
restricted to business hours and redirects unauthenticated visitors
to a "serviceClosed" page. Bulk semestrale extracts of the database
are available but **paid** under [DM 02.04.2007](https://uibm.mise.gov.it/index.php/it/i-servizi/prediagnosi-in-materia-di-pi-pi-uibm)
and the [Bollettino Ufficiale dei Marchi switched from
PDF to web-only HTML on 2021-05-03](https://uibm.mise.gov.it/index.php/it/banche-dati/bollettino-marchi)
— erasing the previously stable programmatic ingestion path. UIBM is
the **AT/ÖPA-shape sibling in southern Europe**: a major office with
substantial filing volume but no developer / open-data path.

**Material distinguishers vs. the wave so far:**
- **vs. ES/OEPM (yellow_byok):** OEPM has a documented catalogue of five free SOAP/XML services with WSDLs gated behind a free per-applicant credentials form, plus permissive [Aviso legal](https://sede.oepm.gob.es/eSede/datos/es/aviso-legal/) under Ley 37/2007. UIBM has **no equivalent catalogue** — no acceso-a-servicios-web form, no SOAP WSDLs, no published programmatic interface of any kind.
- **vs. FI/PRH (green_undocumented):** PRH ships three unauthenticated JSON APIs proxied through `/nis-api-gateway-pat/` and `/nis-api-gateway/` from React SPAs. UIBM's bancadati is a classical CodeIgniter HTML application — the AJAX endpoints return rendered HTML, not JSON, and the legal notice forbids the SE/PRV-style "deep linking" pattern that Finland's tacit posture tolerates.
- **vs. SE/PRV (green_undocumented):** PRV's `search.prv.se` SPA fetches JSON from an undocumented `/api/v1/search` and `/api/v1/document/{n}` shape. UIBM's `bancadati` is server-rendered HTML with no JSON layer.
- **vs. AT/ÖPA (red, personal-use Impressum):** **Closest sibling.** Both run substantial offices with no documented API, both have Impressum / Note Legali clauses with anti-redistribution / anti-deep-linking language, both publish bulk semestrale data only on request and at cost. The differences are minor: UIBM hosts the Milan UPC Central Division (huge consequence — IT patent disputes can route through `upc_decisions`), AT does not.
- **vs. NL/RVO (red_no_api):** Twin reds. RVO's eRegister is Struts2 server-rendered; UIBM's bancadati is CodeIgniter server-rendered. Both have anti-scraping legal posture. Both close transitively via EPO Federated Register.

---

## 1. Endpoint inventory

### 1.1 `uibm.gov.it/bancadati/` — the public search front-end

Server-rendered web application (CodeIgniter PHP + jQuery + Bootstrap
3 + DataTables). The URL pattern is the classic CI shape:

```
GET  /bancadati/                                                 — landing
GET  /bancadati/home/index/                                      — home (33.6 KB HTML)
GET  /bancadati/Number_search/type_url?type={wpn|sn|srn}         — number search form
GET  /bancadati/Advanced_search/type_url?type={tm|pt|pct|ut|ds|fa|ccp|pp|tr}&cl={0|1}  — advanced search form
GET  /bancadati/single_search/general/applicant_search/index/    — applicant single-search form
GET  /bancadati/single_search/general/applicant_vat/index/       — VAT-number search form
GET  /bancadati/single_search/general/attorney_search/index/     — attorney search form
GET  /bancadati/single_search/general/representative_search/index/ — representative search
GET  /bancadati/single_search/patent/inventor_search/index/      — inventor search
GET  /bancadati/single_search/geographic_search/index/           — geographic search
GET  /bancadati/single_search/patent/doc_search/index/           — full-text search across patents+UMs
GET  /bancadati/single_search/text_search/index/                 — title/denomination/description search
GET  /bancadati/bollettini/index/                                — TM bulletin list (510 KB HTML)
GET  /bancadati/bollettini_CCP/index/                            — SPC bulletin
GET  /bancadati/bollettini_CCPF/index/                           — plant-protection SPC bulletin
GET  /bancadati/bollettini_storici/index/                        — historical TMs register
GET  /bancadati/c_trademark/index/                               — collective TMs list (frozen 2019-06-05)
GET  /bancadati/v_trademark/index/                               — IP rights auction bulletins
GET  /bancadati/Decisioni/index                                  — TM nullity/lapse/opposition decisions
GET  /bancadati/igp/Bollettini_igp/index                         — Geographic Indication bulletins
GET  /bancadati/old_new_number/index/                            — old/new application-number map
GET  /bancadati/old_new_number_opp/index/                        — old/new opposition-number map
GET  /bancadati/c_eplist/index/                                  — EP validation correspondence list

POST /bancadati/index.php/single_search/general/applicant_search/result  — applicant search
POST /bancadati/index.php/single_search/general/applicant_list/get_applicant_list  — applicant autocomplete (returns HTML <li>s)
POST /bancadati/index.php/advanced_search/result                 — advanced (combined criteria) search
POST /bancadati/index.php/Single_search_result/result            — number search
POST /bancadati/index.php/class_list/index                       — Nice class list autocomplete
POST /bancadati/index.php/subclass_list/index                    — sub-class autocomplete
POST /bancadati/index.php/L_subclass_list/index                  — Locarno sub-class autocomplete
POST /bancadati/index.php/provincia_list/index                   — Italian province autocomplete
```

The right-modality enum:

| URL `type=` | Modality | EN |
|---|---|---|
| `tm` | Marchi | trademarks |
| `pt` | Invenzioni | patent inventions |
| `pct` | PCT national phase | PCT national-phase entry |
| `ut` | Modelli di utilità | utility models |
| `ds` | Disegni e modelli | industrial designs |
| `fa` | Convalide rivendicazioni domanda di brevetto europeo e brevetto europeo | EP validations |
| `ccp` | Certificati complementari di protezione | SPCs |
| `pp` | Privative per nuove varietà vegetali | plant variety rights |
| `tr` | Trascrizioni | transcriptions (assignments / licenses) |

Confirmed-working POST probe (`ci_session` cookie + zero recaptcha):

```
POST /bancadati/index.php/single_search/general/applicant_search/result
Content-Type: application/x-www-form-urlencoded
applicant=FERRARI%20S.P.A.&oper_opt=AND

→ HTTP 200, 141,747 bytes HTML, "Totale record prodotti dalla ricerca 1298"
```

The autocomplete endpoint is even cleaner:

```
POST /bancadati/index.php/single_search/general/applicant_list/get_applicant_list
applicant=Ferrari

→ HTTP 200, 3,014 bytes HTML, list of <li><a id="FERRARI S.P.A."...></a></li> entries
```

Form payload pattern: every form ships a hidden `g-recaptcha-response`
input but **no Google reCAPTCHA `api.js` is included on any probed
page** — i.e., the field is decorative; the server does not actually
validate a captcha token (verified empirically — 1,298 records
returned with `g-recaptcha-response` omitted entirely from the POST
body). This is unusual and **could be tightened in the future without
notice**. Treat as a brittle anti-pattern, not a license.

**Format:** every result endpoint returns `text/html; charset=UTF-8`
(rendered HTML chunks injected into `<div id="result">`). No JSON
content-type encountered on any probe. Pagination uses `page` +
`start_from` hidden inputs on a `form-next` form; default page size
is 10.

### 1.2 `brevettidb.uibm.gov.it` — granted-patent PDF archive

| Field | Value |
|---|---|
| Endpoint | [`brevettidb.uibm.gov.it`](https://brevettidb.uibm.gov.it/) |
| Engine | Django (CSRF token `csrfmiddlewaretoken` in form) |
| Format | HTML form → PDF downloads |
| Coverage | **Frozen.** ~25,000 patents granted from applications deposited **July 2008 — June 2015**. Static archive only. |
| Auth | none |
| Programmatic API | none — `/api/`, `/openapi.json`, `/swagger/`, `/robots.txt` all return HTTP 404 |
| Note Legali | [PDF](https://brevettidb.uibm.gov.it/static/images/UIBM-BrevettiDB_noteLegali.pdf) — see §5 |

### 1.3 `servizionline.uibm.gov.it` — e-filing portal

| Field | Value |
|---|---|
| Endpoint | [`servizionline.uibm.gov.it`](https://servizionline.uibm.gov.it/) → 302 → `/static/serviceClosed.html` |
| Purpose | Filing of new applications, paying fees, submitting actions; **not** a search API |
| Hours | Mon-Fri 08:00-19:00 only; outside hours returns serviceClosed redirect |
| Contact | hd1.deposito@mise.gov.it (help desk), contactcenteruibm@mise.gov.it (info) |
| Note | Per [UIBM filing stats](https://uibm.mise.gov.it/index.php/en/documents/202-news-english/2036279-patents), >95% of the ~11,000 IT patent + UM applications filed in 2022 went through this portal — i.e., it is the deposit channel, not a public read path |

### 1.4 `statistiche.uibm.gov.it` — statistics portal

| Field | Value |
|---|---|
| Endpoint | [`statistiche.uibm.gov.it`](https://statistiche.uibm.gov.it/) |
| Engine | Joomla + jQuery DataTables; HTML pages with aggregated tables |
| Format | HTML; pure-jQuery + DataTables UI; no JSON discovered |
| Auth | none |
| Programmatic API | none — page does not load a JSON layer; tables are server-rendered |
| Coverage | Monthly aggregated statistics (filings, grants, by modality) |

### 1.5 `uibm.gov.it/biotech/` — biotechnology dataset

| Field | Value |
|---|---|
| Endpoint | [`uibm.gov.it/biotech/dataset.html`](https://www.uibm.gov.it/biotech/dataset.html) |
| Format | **Static JSON file** at `/biotech/assets/datjson/dati_bibliograficiXsito.json` |
| Probe | HTTP 200, 388 KB, ~3000 records with `{Anno_Deposito, Application, Filing_Date, Invention-Title, Classifica}` keys |
| Coverage | Biotechnology-only patent applications, narrow scope |
| Auth | none |
| License | inherited from main UIBM Note Legali (anti-deep-linking) |

**Interesting but narrow** — a static JSON file (not an API endpoint
with parameters; just a flat dump that the page's DataTable loads at
init). Not a programmatic surface; not coverage for general patents,
TMs, or designs.

### 1.6 `uibm.gov.it/iperico/` — counterfeiting seizure statistics

| Field | Value |
|---|---|
| Endpoint | [`uibm.gov.it/iperico/`](https://www.uibm.gov.it/iperico/) |
| Engine | Joomla + RSS/Atom feeds advertised, but content is enforcement seizure tables only |
| Coverage | Customs (ADM) + Guardia di Finanza counterfeiting seizure aggregates; excludes food, drink, tobacco, medicines |
| Format | CSV + PDF download for the produced tables; no parameterised API |
| Relevance | enforcement statistics, not IP register data |

### 1.7 MIMIT parent / `mimit.gov.it`

| Field | Value |
|---|---|
| Endpoint | [`mimit.gov.it`](https://www.mimit.gov.it/) (Ministero delle Imprese e del Made in Italy) |
| Open data | MIMIT publishes ~30 datasets on [`dati.gov.it`](https://www.dati.gov.it/) (probed `?q=ministero+delle+imprese` → 6,470 hits; first page = "RNA Aiuti" state-aid registry datasets) — **none** are UIBM/IP-register data |
| Direct dataset list | [Open Data RNA Aiuti](https://www.dati.gov.it/opendata/api/3/action/package_search?q=ministero+delle+imprese) — state-aid monitoring datasets only |

### 1.8 `dati.gov.it` (Italy's national open-data CKAN)

| Field | Value |
|---|---|
| Endpoint | [`dati.gov.it`](https://www.dati.gov.it/) — CKAN 2.x at `/opendata/api/3/action/` |
| Auth | none for read endpoints |
| Probes (2026-05-18) | `?q=uibm` → **0 hits**; `?q=brevetti` → 15 hits (all third-party — ENEA, UNIBA, Regione Puglia, Università Piemonte Orientale, Regione Toscana, CCIAA Lecce); `?q=proprietà industriale` → 6 hits (none from UIBM); `package_list` full sweep (69,942 packages) → 13 matches on "uibm/brevetti/marchi" of which **0** are UIBM-published |
| Conclusion | UIBM / MIMIT-IP does **not** publish to dati.gov.it. The IP register is not represented on the national open-data portal. |

### 1.9 WIPO IP API Catalog

| Field | Value |
|---|---|
| Endpoint | [`apicatalog.wipo.int`](https://apicatalog.wipo.int/) (Angular SPA + `https://apicatalog.wipo.int/api/apis` unauthenticated read endpoint) |
| Probe (2026-05-18) | `GET /api/apis?size=300` → `totalCount: 179`; organisations: `[DPMA, EPO, EUIPO, IP Australia, JPO, MOIP KOREA, QAZ, UPRP, USPTO, WIPO]`. **UIBM is not among the 10 organisations contributing APIs.** Italy-related entries: **0**. |
| Conclusion | UIBM has not registered any API in WIPO's canonical inventory. |

## 2. Auth model

- **bancadati AJAX endpoints:** none (only a CodeIgniter `ci_session` cookie, set on the first GET; this is a session token, not credentials). Hidden `g-recaptcha-response` form field is decorative — **the server does not validate a captcha token** (empirically confirmed by `applicant_search/result` returning real result data with the field omitted). Treat as a brittle anti-pattern that could be tightened without notice.
- **brevettidb:** Django `csrfmiddlewaretoken` on the search form. Static archive; no API.
- **servizionline:** SPID / CNS / e-filing login for filers; not relevant to read use.
- **statistiche / iperico / biotech:** no auth; static HTML / static JSON.
- **There is no documented developer programme** — no acceso-a-servicios-web equivalent, no api-gateway, no OAuth2, no API key, no email-issued shared key.

## 3. Format

- **bancadati AJAX:** HTML chunks (`text/html; charset=UTF-8`) injected into a result `<div>`. Never JSON. Pagination via hidden `page` + `start_from` form inputs (default 10 records per page).
- **bollettini marchi:** **HTML web pages only since 2021-05-03** (the previous PDF publication path was discontinued — per [UIBM news on the bollettino](https://uibm.mise.gov.it/index.php/it/banche-dati/bollettino-marchi)).
- **brevettidb:** PDF downloads of granted-patent fascicoli; archive only.
- **biotech:** static JSON file (one-shot dump, no query parameters).
- **iperico:** CSV / PDF tables of aggregate seizures.
- **bulk semestrale extracts:** XML / proprietary tabular formats, **paid** per [DM 02.04.2007 tariff schedule](https://uibm.mise.gov.it/index.php/it/i-servizi/prediagnosi-in-materia-di-pi-pi-uibm).

There is **no WIPO ST.36 / ST.66 / ST.86** standardised bulk
distribution (contrast: OEPM, DPMA, INPI all publish in these
standards). UIBM does feed the EPO Federated Register Service and
EUIPO TMview / DesignView via the [EUIPN Common Tools Integration
(CTI)](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI),
but those are office-to-office data flows, not public bulk feeds.

## 4. Rate limit

None published. No rate-limit headers observed on the bancadati
endpoints during single-pager probes. The legal posture (Note Legali)
suggests UIBM does not expect or licence sustained automated traffic;
production-scale scraping would be very visible and at risk of
unilateral blocking.

## 5. ToS — the Note Legali

The [Note Legali for `brevettidb.uibm.gov.it`](https://brevettidb.uibm.gov.it/static/images/UIBM-BrevettiDB_noteLegali.pdf)
is the most explicit governing document UIBM publishes on the public
web. Key clauses (verbatim, 2026-05-18):

- **Statutory basis:** *"sulla base di quanto previsto dall'art. 53, comma 3, del Codice della Proprietà Industriale e dall'art. 5, comma 2, del Decreto Ministeriale 27.6.2008"* — i.e., the Italian Industrial Property Code ([Decreto Legislativo 10 febbraio 2005, n. 30 — Codice della proprietà industriale](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2005-02-10;30)) art. 53 §3 and DM 27.06.2008 art. 5 §2.
- **Authoritative source clause:** *"In caso di divergenze rispetto ai testi originali, questi ultimi fanno fede e prevalgono su quelli presenti nel sito"* — site content is informational; originals prevail.
- **No-decision clause:** *"Essi non possono in alcun caso costituire la base per decisioni giuridiche o economiche fondamentali"* — site data cannot be the basis of legal or economic decisions.
- **Disclaimer:** *"L'Ufficio non assume alcuna responsabilità per eventuali errori od omissioni…"*
- **Copyright (the redistribution clause):** *"È possibile riprodurre, distribuire, trasmettere liberamente dati e analisi presenti nel sito, a condizione che venga citata la fonte e che ne venga garantita l'integrità."* — **permissive for data and analyses**, with attribution and integrity required.
- **Anti-deep-linking clause (the dispositive clause for our purposes):** *"E' vietato il cd. 'deep linking' ossia l'utilizzo non trasparente, su siti di soggetti terzi, di parti del sito."* — **deep linking (non-transparent reuse of parts of the site from third-party sites) is forbidden.** Plain hyperlinks to UIBM pages do not require authorisation, but proxying / iframing / non-transparent reuse of UIBM's content **is** prohibited.

The anti-deep-linking clause is the **stop-sign** for a hosted-proxy
posture. It does not categorically prohibit reuse — "freely reproduce
and distribute data and analyses with attribution and integrity" is
arguably broader than NL/RVO's posture — but the specific operational
mode of a runtime proxy (fetching parts of bancadati pages on demand
on behalf of third-party users) falls within the prohibited "deep
linking" envelope as defined. This is structurally similar to AT/ÖPA's
Impressum.

The biotech, IPERICO, and statistiche sub-sites do not republish the
Note Legali at their own URLs, but the parent UIBM hosting context
applies.

## 6. Verdict and shape

🔴 **red_no_api.** UIBM exposes:

- a **server-rendered HTML application** (`bancadati`) whose AJAX endpoints respond to unauthenticated POSTs but return HTML chunks (not JSON), with a decorative `g-recaptcha-response` field that the server doesn't currently enforce — a brittle reverse-engineering surface that could be locked down at any time;
- a **frozen Django archive** (`brevettidb`) of granted-patent PDFs from 2008-2015;
- a **business-hours-only e-filing portal** (`servizionline`);
- a **static-tables statistics site** (`statistiche`);
- a **niche static JSON dump** (biotech, ~3,000 records);
- **paid bulk semestrale extracts** at DM 02.04.2007 rates.

And, critically:

- **zero presence on `dati.gov.it`** (the national open-data CKAN);
- **zero presence in the WIPO IP API Catalog** (179 entries across 10 offices, none Italian);
- **a Note Legali that expressly prohibits "deep linking"** — i.e., the specific operational pattern of a hosted runtime proxy that fetches parts of UIBM pages on behalf of third parties.

Closest siblings in this wave: **AT/ÖPA** (red, Impressum forbids
commercial reuse without consent — UIBM allows reuse with attribution
but forbids deep linking, which is a different stop-sign with the same
practical effect) and **NL/RVO** (red, Struts2 server-rendered with
no API — UIBM's CodeIgniter is structurally identical from a connector
posture standpoint).

What pushes UIBM further into red than AT/ÖPA: **the bollettino-marchi
PDF distribution was discontinued in 2021-05-03** in favor of web-only
HTML pages, removing the one stable programmatic ingestion path that
had previously existed.

What would push UIBM out of red: (a) UIBM publishes any of its
existing bulk products under a CC-BY equivalent license at no cost on
`dati.gov.it`; (b) UIBM registers an API in the WIPO IP API Catalog;
(c) MIMIT launches a developer programme. None of (a)-(c) appear on
the public roadmap as of 2026-05-18.

## 7. Coverage already in place

Italy coverage transitively, **before any UIBM-specific connector:**

| Right | Higher layer | Notes |
|---|---|---|
| **Patents (EP-validated in IT)** | [EPO OPS / INPADOC](https://www.epo.org/searching-for-patents/data/web-services/ops.html) | Italy is an EPC contracting state; EP-route patents validated in IT are well-covered at biblio / family / legal-events fidelity. |
| **Patents (Italian national route)** | EPO INPADOC (partial) | IT bibliographic data flows to EPO Federated Register Service per the federated-register cooperation. National-only IT patents that never went EP are the gap — but per [UIBM filing statistics](https://uibm.mise.gov.it/index.php/en/documents/202-news-english/2036279-patents), Italy's national filings (~11,000/year for inventions + UMs) are heavily dominated by *modello di utilità* (no novelty examination at filing — IT-specific). |
| **Unitary patents (UP) effective in IT** | [EPO Unitary Patent Register](https://www.epo.org/searching-for-patents/legal/register.html) via EPO OPS | Italy is a UP-participating EU member state. |
| **UPC decisions affecting IT** | shipped `upc_decisions` connector + **Milan Central Division** (third seat, opened 2024-06-27 per [UPC opening announcement](https://www.unified-patent-court.org/en/news/opening-milan-it-section-central-division), [Kluwer Patent Blog 2024-01-30](https://patentblog.kluweriplaw.com/2024/01/30/italy-and-unified-patent-court-sign-agreement-on-milan-central-division/)) | Milan handles IPC class A "Human Necessities" excluding SPCs — pharma, medical devices, agriculture, food, tobacco, household, sports/gaming. |
| **EUTMs designating IT** | [EUIPO](https://www.euipo.europa.eu/) (planned regional connector) | EU trademarks; standard EUIPO coverage. |
| **Community designs (RCDs / REUDs) designating IT** | EUIPO | Same. |
| **IT national TMs (via TMview)** | [EUIPN TMview](https://www.tmdn.org/tmview/) via CTI | IT participates in EUIPN's Common Tools Integration; national TMs flow into TMview / DesignView. |
| **IT national designs (via DesignView)** | EUIPO DesignView | Same CTI route. |
| **Madrid IRs designating IT** | WIPO Madrid Monitor (planned multilateral connector) | International registrations designating Italy. |
| **Hague IRs designating IT** | WIPO Hague Express | International design registrations. |

## 8. Genuine UIBM-only gaps (what an IT connector would fill, if there were a path)

| Gap | Right | Notes |
|---|---|---|
| **IT national-only patents** (direct UIBM, not EP) | patent | Italian-language full text. Lower commercial volume than the EP route; some bibliographic coverage in INPADOC. |
| **IT *modello di utilità* (utility models)** | utility model | Per [SIB / Jacobacci utility-model summaries](https://www.sib.it/en/patents/inventions-insights/utility-model/), UM is examined for **formal requirements only** at filing — distinct from the IT patent register. 10-year term, mid-period maintenance fee. Sometimes in INPADOC but often not at register fidelity. |
| **IT *certificati complementari di protezione* (SPCs)** | patent | IT SPC register; UPC Milan Central does NOT cover SPCs, so UIBM is the only register of record for IT SPC status. |
| **IT *privative per nuove varietà vegetali* (plant variety rights)** | plant variety | IT PVR — distinct register. CPVO covers EU PVRs but national IT PVRs are separately registered at UIBM. |
| **IT national TMs at register fidelity (events, oppositions, renewals)** | trademark | TMview via CTI surfaces bibliographic data; full register events live at UIBM. |
| **IT national designs at register fidelity** | design | Same. |
| **TM nullity / lapse / opposition decisions** | trademark | UIBM's [Decisioni page](https://www.uibm.gov.it/bancadati/Decisioni/index) is the canonical source. |
| **Italian geographic indications (artisanal + industrial IGPs)** | GI | UIBM publishes the IGP bulletins; sui generis IT IGP register. |
| **Pre-EP IT patent backfile** | patent | UIBM data feeds INPADOC; IT national-only filings from before EP route adoption may have lower fidelity. |
| **Trascrizioni** (assignment / license recordals) | all modalities | UIBM-side register events; not consistently in INPADOC. |

The **modello di utilità** gap is the largest by volume — UMs are the
default for Italian SMEs filing national-only IP, and they don't
surface in the EP route at all. The **SPCs** gap is the largest by
commercial weight (pharma).

## 9. WIPO API Catalog probe — empirical

[`https://apicatalog.wipo.int/api/apis?size=300`](https://apicatalog.wipo.int/api/apis?size=300) —
probed 2026-05-18 (the catalog ships an unauthenticated read endpoint
once you know the URL from `env.js`; the SPA's `/api/apis/all` and
`/api/ipo/all` endpoints require OAuth2 via login.microsoftonline.com,
but `/api/apis` with a `size` query parameter is open).

```json
{
  "start": 0,
  "size": 300,
  "totalCount": 179,
  "results": [ ... 179 entries ... ]
}
```

Organisations contributing APIs (alphabetical): **DPMA, EPO, EUIPO,
IP Australia, JPO, MOIP KOREA, QAZ, UPRP, USPTO, WIPO**.

**UIBM is not among them.** Zero entries with "italian" or "uibm" or
"IT" in any field. This confirms the SOAP / REST / JSON catalogue
absence at the canonical-inventory layer.

## 10. Recommendation

**Connector status: skipped (red_no_api).** Document the UPC Milan
Central Division and the Federated EP Register / EUIPN CTI transitive
coverage in the synopsis; do not queue a UIBM-specific connector. The
key blockers, in priority order:

1. **No documented programmatic surface.** No REST, no SOAP, no JSON, no XML feed, no API key programme, no developer portal.
2. **Anti-deep-linking ToS.** The Note Legali expressly prohibits the specific operational pattern of a hosted runtime proxy. Permissive for attributed redistribution of "data and analyses"; restrictive for the runtime-fetch mode.
3. **HTML-only output.** The bancadati AJAX endpoints respond unauthenticated but emit HTML chunks, not JSON — a high-maintenance reverse-engineering surface even before the legal posture.
4. **Decorative recaptcha tripwire.** The hidden `g-recaptcha-response` field could be activated at any time, breaking any unauthenticated proxy without notice.
5. **No `dati.gov.it` presence.** Italy's national open-data CKAN portal has zero UIBM datasets — the office has not adopted the open-data posture taken by OEPM, INPI-FR, PRH, or DPMA.
6. **Bollettino marchi went HTML-only in 2021-05-03.** The previous PDF bollettino was the closest thing to a stable programmatic ingestion path; that's gone.

### What we should do instead

- **Watch for change.** UPC Milan Central Division opened 2024-06-27; the Italian MIMIT may eventually align IP register publication with the broader EU Open Data Directive ([2019/1024](https://eur-lex.europa.eu/eli/dir/2019/1024)) push that produced OEPM's permissive Aviso legal and PRH's CC-BY 4.0 sister portal. Re-probe in 12 months.
- **Address coverage transitively.** EPO OPS for EP-route patents; UPC connector for Milan-routed disputes; EUIPO + CTI for IT TMs and designs at bibliographic fidelity; WIPO Madrid / Hague for international IRs designating IT.
- **If a specific case demands IT national-only data:** treat as a manual research task; pull the bancadati pages via browser, do not engineer a proxy.

### What we should NOT do

- **Do not build an HTML scraper of `bancadati`.** Anti-deep-linking ToS plus brittle recaptcha tripwire plus HTML-not-JSON output = bad return on engineering investment.
- **Do not ingest the biotech static JSON as if it were a general patent feed.** It is biotech-only, ~3000 records, narrow domain.
- **Do not wrap a third-party commercial IT-register proxy.** Adds a paid intermediary without changing the upstream posture.

## 11. Open questions

- **Recaptcha enforcement timeline.** Is the `g-recaptcha-response` field decorative because it was never wired up, or because it was wired up and disabled? Empirical probe shows zero validation today. A note in the page source or a UIBM news announcement would help calibrate the risk of future re-enablement.
- **MIMIT's open-data roadmap.** MIMIT publishes the RNA Aiuti state-aid registry on `dati.gov.it` (monthly cadence). Whether there is any internal plan to extend that posture to UIBM's IP register is unknown — direct enquiry to [`dgtpi.uibm@mise.gov.it`](mailto:dgtpi.uibm@mise.gov.it) or [`assistenza.informatica@mise.gov.it`](mailto:assistenza.informatica@mise.gov.it) would be the next probe.
- **Note Legali on `uibm.gov.it/bancadati/` directly.** The Note Legali PDF lives at the `brevettidb` sub-site. Whether the same text governs the main bancadati endpoints, or whether bancadati has its own (less restrictive?) terms, is unclear. The MIMIT parent portal at [`mimit.gov.it`](https://www.mimit.gov.it/) has a separate footer that may or may not control.
- **CTI fidelity for IT national TMs and designs.** Italy implements EUIPN CTI ([EUIPN page](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI)); empirical probe needed on whether IT-only register events (oppositions, renewals, transcrizioni) surface in TMview / DesignView at full fidelity or just bibliographic-data.
- **UPC Milan Central Division decision routing.** Milan is the third UPC seat (after Paris and Munich) per the [Inauguration ceremony page](https://www.unified-patent-court.org/en/news/inauguration-ceremony-milan-it-section-central-division-unified-patent-court). Whether the shipped `upc_decisions` connector treats Milan-routed cases as a separate divisional shard, or commingled with Paris / Munich, is a follow-up validation for the `upc_decisions` connector itself.
- **Estratti semestrali licensing.** The bulk semestrale extracts under [DM 02.04.2007](https://uibm.mise.gov.it/index.php/it/i-servizi/prediagnosi-in-materia-di-pi-pi-uibm) are paid; whether the resulting data carries a license compatible with redistribution (i.e., whether buying the extract and proxying its content would be defensible) is the gating question for any paid-tier shape — out of scope for the zero-infra constraint regardless.
- **Bollettino marchi post-2021 ingestion.** UIBM switched from PDF bollettini to web-only HTML on 2021-05-03; whether a PDF / XML export path was preserved for cooperating partners (e.g., EUIPN for TMview ingestion) is unknown.

## 12. References — primary sources only

**UIBM service surfaces:**
- [UIBM home (MIMIT)](https://uibm.mise.gov.it/index.php/it/) — institutional landing
- [UIBM home (EN)](https://uibm.mise.gov.it/index.php/en/)
- [UIBM database landing page (Banche Dati)](https://uibm.mise.gov.it/index.php/it/banche-dati)
- [Banca dati bibliografica e documentale delle domande e dei titoli italiani di Proprietà Industriale (P.I.)](https://uibm.mise.gov.it/index.php/it/banche-dati/banca-dati-bibliografica-e-documentale-delle-domande-e-dei-titoli-italiani-di-proprieta-industriale-p-i)
- [DGPI-UIBM Ricerca — bancadati search front-end](https://www.uibm.gov.it/bancadati/)
- [Database dei brevetti italiani — page describing the bancadati system](https://uibm.mise.gov.it/index.php/it/deposito-titoli/modulistica-per-il-deposito-cartaceo/226-dglc-uibm/2035905-database-dei-brevetti-italiani)
- [brevettidb — granted-patent PDF archive (2008-2015)](https://brevettidb.uibm.gov.it/)
- [Servizi OnLine — e-filing portal (business hours)](https://servizionline.uibm.gov.it/)
- [UIBM Reportistica — statistics portal](https://statistiche.uibm.gov.it/)
- [IPERICO — counterfeiting seizure statistics](https://www.uibm.gov.it/iperico/)
- [Biotech dataset](https://www.uibm.gov.it/biotech/dataset.html)
- [Bollettino marchi — TMs gazette (now HTML-only)](https://uibm.mise.gov.it/index.php/it/banche-dati/bollettino-marchi)
- [Bollettino marchi — EN landing](https://uibm.mise.gov.it/index.php/en/marchi/bollettino-marchi)
- [Estratti semestrali Banca Dati — paid bulk under DM 02.04.2007](https://uibm.mise.gov.it/index.php/it/i-servizi/prediagnosi-in-materia-di-pi-pi-uibm)
- [Modello di utilità — UM filing page](https://uibm.mise.gov.it/index.php/it/?option=com_content&view=article&id=2036790&catid=236)
- [DesignView (UIBM page)](https://uibm.mise.gov.it/index.php/it/banche-dati/designview)
- [TMview (UIBM page)](https://uibm.mise.gov.it/index.php/it/banche-dati/tmview)
- [Decisioni — TM nullity / lapse / opposition decisions](https://www.uibm.gov.it/bancadati/Decisioni/index)
- [IGP bulletins — Geographic Indications](https://www.uibm.gov.it/bancadati/igp/Bollettini_igp/index)

**ToS / Note Legali:**
- [Note Legali (brevettidb, PDF)](https://brevettidb.uibm.gov.it/static/images/UIBM-BrevettiDB_noteLegali.pdf) — the dispositive anti-deep-linking clause

**Substantive law (Italian statutes via Normattiva / Gazzetta Ufficiale):**
- [Codice della Proprietà Industriale — Decreto Legislativo 10 febbraio 2005, n. 30 (Normattiva)](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2005-02-10;30)
- [Decreto Legislativo 10 febbraio 2005, n. 30 (Gazzetta Ufficiale)](https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2005-03-04&atto.codiceRedazionale=005G0055)
- [Codice della Proprietà Industriale — UIBM/MIMIT landing](https://uibm.mise.gov.it/index.php/it/normativa-pi/il-codice-della-proprieta-industriale)

**Open data (Italy's national CKAN):**
- [`dati.gov.it`](https://www.dati.gov.it/) — Italy's open-data portal (CKAN 2.x)
- [`dati.gov.it/api`](https://www.dati.gov.it/api) — CKAN API documentation
- [Open Data MIMIT — RNA Aiuti](https://www.dati.gov.it/opendata/api/3/action/package_search?q=ministero+delle+imprese) — MIMIT's open-data presence (state-aid registry; no IP)

**MIMIT parent:**
- [Direzione generale per la proprietà industriale — UIBM organisation structure on MIMIT](https://www.mimit.gov.it/it/component/organigram/?view=structure&id=11)
- [MIMIT EN organisation page](https://www.mimit.gov.it/en/component/organigram/?view=structure&id=11)

**UPC Milan Central Division:**
- [Opening of the Milan section of the central division (UPC, 2024-06-27)](https://www.unified-patent-court.org/en/news/opening-milan-it-section-central-division)
- [Inauguration ceremony of the Milan section of the central division](https://www.unified-patent-court.org/en/news/inauguration-ceremony-milan-it-section-central-division-unified-patent-court)
- [Italy and UPC sign agreement on Milan central division (Kluwer Patent Blog, 2024-01-30)](https://patentblog.kluweriplaw.com/2024/01/30/italy-and-unified-patent-court-sign-agreement-on-milan-central-division/)

**Cross-office context:**
- [WIPO IP API Catalog](https://apicatalog.wipo.int/) — probed 2026-05-18; 0 UIBM entries
- [WIPO IP API Catalog — apis read endpoint](https://apicatalog.wipo.int/api/apis?size=300) — empirical inventory
- [EUIPN Common Tools Integration (CTI)](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI) — bibliographic flow to TMview / DesignView
- [EU Open Data Directive (EU) 2019/1024](https://eur-lex.europa.eu/eli/dir/2019/1024) — comparative legal baseline

---

**Verdict line:** 🔴 red_no_api. No documented programmatic API, no
WIPO IP API Catalog entry, no `dati.gov.it` IP datasets, anti-deep-
linking Note Legali, HTML-only AJAX surfaces with decorative recaptcha
tripwire, bollettino marchi went HTML-only 2021-05-03, paid bulk
extracts only. Coverage closes transitively via EPO OPS (EP-route),
UPC connector (incl. **Milan Central Division** opened 2024-06-27),
EUIPO (EUTMs + RCDs), EUIPN CTI (IT national TMs + designs into
TMview / DesignView at bibliographic fidelity), and WIPO Madrid /
Hague (IRs designating IT). Connector status: **skipped**.
