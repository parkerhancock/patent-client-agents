# Ufficio Italiano Brevetti e Marchi (IT/UIBM) — national

**Layer:** national
**Jurisdiction:** IT (WIPO ST.3: IT)
**Issuing body:** Ufficio Italiano Brevetti e Marchi (UIBM), part of the Direzione Generale per la Tutela della Proprietà Industriale (DGTPI) of the Ministero delle Imprese e del Made in Italy (MIMIT — the rebranded successor to the former MISE, Ministero dello Sviluppo Economico)
**Rights administered:** patent, utility model (*modello di utilità*), trademark, industrial design, supplementary protection certificate (*certificato complementare di protezione* — CCP), plant variety right (*privativa per nuova varietà vegetale*), semiconductor topography, geographic indication (artisanal and industrial)
**Working languages:** Italian (primary); English (institutional pages on MIMIT only); the *Bollettino Ufficiale dei Marchi* is Italian-only
**Connector status:** **skipped (red — no API)**
**Last verified:** 2026-05-18
**Manifest entry:** not yet listed (skipped)

**Detail surveys:**
- [`waves/2026-05-18-secondary-nationals-wave/it-uibm.md`](../waves/2026-05-18-secondary-nationals-wave/it-uibm.md) — 2026-05-18 grounded API discovery

**Higher layers covering this office transitively:**
- **EPO INPADOC / OPS** (via [`regional/epo.md`](../regional/epo.md)) — IT-validated EP patents at biblio / family / legal-events fidelity. Italy is an EPC contracting state, an EU member, and a UP-participating state.
- **UPC** (via shipped `upc_decisions` connector) — UPC-routed disputes touching IT, **including the Milan section of the UPC Central Division** which opened 2024-06-27 as the third central-division seat per [the UPC announcement](https://www.unified-patent-court.org/en/news/opening-milan-it-section-central-division) and [Kluwer Patent Blog 2024-01-30](https://patentblog.kluweriplaw.com/2024/01/30/italy-and-unified-patent-court-sign-agreement-on-milan-central-division/). Milan handles IPC class A "Human Necessities" excluding SPCs — pharma, medical devices, agriculture, food, tobacco, household, sports/gaming. The Milan section replaced the originally planned London seat after Brexit.
- **EUIPO** (via planned `regional/euipo.md`) — EUTMs designating IT, Community designs (RCDs / REUDs). IT national TMs and designs flow into [TMview / DesignView via the EUIPN Common Tools Integration (CTI)](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI) back-office bridge.
- **WIPO Madrid Monitor / Hague Express** — Madrid IRs designating IT / Hague IRs designating IT.

---

## §1 Mission

UIBM is Italy's national IP office and the sole authoritative registrar
for IT national patents, IT utility models (*modello di utilità*), IT
trademarks, IT industrial designs, Italian supplementary protection
certificates (CCPs), Italian plant variety rights, semiconductor
topographies, and Italian geographic indications. It sits inside the
Direzione Generale per la Tutela della Proprietà Industriale (DGTPI)
of MIMIT (Ministero delle Imprese e del Made in Italy), the rebranded
successor of MISE.

Because Italy is an EPC contracting state, an EU member, **a
UP-participating state, and the host of the UPC Central Division's
Milan section** (opened 2024-06-27, jurisdiction over IPC class A
"Human Necessities" excluding SPCs), most "Italian patents" of
commercial scale are EP-route (covered by EPO OPS) and most IT patent
disputes route through the UPC connector. Most "Italian trademarks"
of scale are EUTMs (covered by EUIPO). UIBM's genuine value-add for
agents is the **IT-national-only slice** — IT national-route patents,
IT utility models (large filing-volume share for Italian SMEs), IT
SPCs (note: not within Milan UPC Central Division's jurisdiction —
UIBM is the only register of record for IT SPC status), IT
national-only TMs and designs, plant variety rights, trascrizioni
(assignment / license recordals), and Italian geographic indications.

The 2024 opening of the **Milan section of the UPC Central Division**
is the structurally most consequential recent development — IT
hosts a third central-division seat alongside Paris and Munich, after
the originally planned London seat lapsed post-Brexit.

## §2 What's unique here

- **IT utility models (*modello di utilità*)** — distinct national right, 10-year term, **examined for formal requirements only** at filing per [SIB filing summary](https://www.sib.it/en/patents/inventions-insights/utility-model/) and [Jacobacci utility-model overview](https://www.jacobacci.com/en/patents/filing-of-utility-models-in-italy-and-abroad); per [UIBM 2022 statistics](https://uibm.mise.gov.it/index.php/en/documents/202-news-english/2036279-patents), ~11,000 inventions + UMs filed per year, >95% via the online deposit portal.
- **IT national-route patents** — filed directly at UIBM, not via EP. Italian-language full text. Sometimes in INPADOC at bibliographic fidelity; not at register fidelity.
- **IT SPCs (*certificati complementari di protezione*)** — IT SPC register status. The **Milan UPC Central Division explicitly excludes SPCs** from its jurisdiction, so UIBM remains the only register of record for IT SPC status.
- **IT plant variety rights (*privative per nuove varietà vegetali*)** — IT PVR register; sui generis vs. CPVO (which covers EU PVRs).
- **IT national-only trademarks** — filed at UIBM, not via Madrid IR or EUTM. Bibliographic data surfaces in TMview via [CTI](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI) but full register events (oppositions, renewals, transcrizioni, nullity decisions) live at UIBM.
- **IT national-only designs** — filed at UIBM, not via Hague or RCD. Same CTI / DesignView story.
- **TM nullity / lapse / opposition decisions** — UIBM publishes the canonical decision corpus at [`bancadati/Decisioni/index`](https://www.uibm.gov.it/bancadati/Decisioni/index).
- **Italian geographic indications (artisanal + industrial IGPs)** — UIBM publishes the [Bollettini IGP](https://www.uibm.gov.it/bancadati/igp/Bollettini_igp/index).
- **Trascrizioni** (assignment / license recordals) — IT-side register events; not consistently in INPADOC.
- **Hosts the UPC Milan Central Division** — 2024-06-27 opening; out of scope for UIBM as a register, but the geographic / jurisdictional fact that Milan is now a UPC seat is structurally consequential and worth recording on this office page.

## §3 Programmatic surfaces

### `uibm.gov.it/bancadati/` — search front-end

| Field | Value |
|---|---|
| Endpoint | [`uibm.gov.it/bancadati/`](https://www.uibm.gov.it/bancadati/) |
| Engine | CodeIgniter PHP + jQuery + Bootstrap 3 + DataTables (URL pattern `/bancadati/index.php/{controller}/{action}`) |
| Auth | none (CodeIgniter `ci_session` cookie set on landing); a hidden `g-recaptcha-response` field is present in every form but **the server does not validate a captcha token** (empirically confirmed — `applicant_search/result` returns 1,298 real records for "FERRARI S.P.A." with the field omitted) |
| Format | **HTML chunks** (`text/html; charset=UTF-8`); never JSON. AJAX endpoints respond unauthenticated but emit rendered HTML for injection into a result `<div>` |
| Rate limit | not published |
| ToS posture | [Note Legali (PDF)](https://brevettidb.uibm.gov.it/static/images/UIBM-BrevettiDB_noteLegali.pdf) **expressly prohibits "deep linking"** (verbatim: *"E' vietato il cd. 'deep linking' ossia l'utilizzo non trasparente, su siti di soggetti terzi, di parti del sito"*) — i.e., the operational pattern of a hosted runtime proxy that fetches parts of UIBM pages on behalf of third parties; reproduction and distribution of data and analyses is permitted with attribution and integrity, but the runtime-fetch mode is the prohibited form |
| Rating (zero-infra proxy) | 🔴 **Red — HTML-only output + anti-deep-linking ToS + decorative recaptcha tripwire** |
| Primary source | reverse-engineered from [`uibm.gov.it/bancadati/`](https://www.uibm.gov.it/bancadati/) 2026-05-18 |

The AJAX endpoints respond, but the combination of HTML-only output,
anti-deep-linking ToS, and a recaptcha tripwire that could be enabled
at any time make this a poor connector target. The closest functional
sibling is **NL/RVO** (Struts2 server-rendered with no API); the
closest legal-posture sibling is **AT/ÖPA** (Impressum forbids
commercial reuse without consent).

### `brevettidb.uibm.gov.it` — granted-patent PDF archive

| Field | Value |
|---|---|
| Endpoint | [`brevettidb.uibm.gov.it`](https://brevettidb.uibm.gov.it/) |
| Engine | Django (CSRF token on the search form) |
| Coverage | ~25,000 patents granted from applications deposited **July 2008 — June 2015**. Archive only. |
| Format | HTML form → PDF downloads of granted-patent fascicoli |
| Auth | none |
| Programmatic API | none — `/api/`, `/openapi.json`, `/swagger/`, `/robots.txt` all return HTTP 404 |
| Rating | 🔴 Red — frozen Django archive, no API, no current coverage |

### `servizionline.uibm.gov.it` — e-filing portal

| Field | Value |
|---|---|
| Endpoint | [`servizionline.uibm.gov.it`](https://servizionline.uibm.gov.it/) — redirects to `/static/serviceClosed.html` outside business hours |
| Hours | Mon-Fri 08:00-19:00 only |
| Purpose | Filing new applications, paying fees, submitting actions |
| Rating | 🔴 Red — deposit channel, not a read API |

### `statistiche.uibm.gov.it` — statistics portal

| Field | Value |
|---|---|
| Endpoint | [`statistiche.uibm.gov.it`](https://statistiche.uibm.gov.it/) |
| Engine | Joomla + jQuery DataTables; server-rendered tables |
| Coverage | Monthly aggregated statistics (filings, grants, by modality) |
| Rating | 🔴 Red — HTML tables, no JSON layer |

### `uibm.gov.it/biotech/` — biotechnology dataset

| Field | Value |
|---|---|
| Endpoint | [`uibm.gov.it/biotech/dataset.html`](https://www.uibm.gov.it/biotech/dataset.html) |
| Format | Static JSON at `/biotech/assets/datjson/dati_bibliograficiXsito.json` (~3,000 biotechnology patent records with `{Anno_Deposito, Application, Filing_Date, Invention-Title, Classifica}` keys) |
| Auth | none |
| Rating | 🔴 Red — static dump, narrow scope (biotech only), not a programmatic surface |

### `uibm.gov.it/iperico/` — counterfeiting seizure statistics

| Field | Value |
|---|---|
| Endpoint | [`uibm.gov.it/iperico/`](https://www.uibm.gov.it/iperico/) |
| Coverage | Customs (ADM) + Guardia di Finanza counterfeiting seizure aggregates; excludes food, drink, tobacco, medicines |
| Format | CSV + PDF download for aggregate tables |
| Rating | informational — enforcement statistics, not IP register data |

### `dati.gov.it` (Italy's national open-data CKAN)

| Field | Value |
|---|---|
| Endpoint | [`dati.gov.it`](https://www.dati.gov.it/) — CKAN 2.x at `/opendata/api/3/action/` |
| Probe (2026-05-18) | `?q=uibm` → **0 hits**; `?q=brevetti` → 15 hits (all third-party — ENEA, UNIBA, Regione Puglia, Università Piemonte Orientale, Regione Toscana, CCIAA Lecce); `?q=proprietà industriale` → 6 hits (none from UIBM); `package_list` full sweep (69,942 packages) → **0 UIBM-published IP datasets** |
| MIMIT presence | MIMIT publishes **state-aid registry data only (RNA Aiuti, monthly)**; no IP register data |
| Rating | 🔴 N/A — UIBM does not publish to dati.gov.it |
| Primary source | [`dati.gov.it/api`](https://www.dati.gov.it/api) — CKAN API documentation |

### Bulk semestrale extracts

| Field | Value |
|---|---|
| Channel | request-only extraction of bibliographic database for six-month periods |
| Authority | [DM 02.04.2007](https://uibm.mise.gov.it/index.php/it/i-servizi/prediagnosi-in-materia-di-pi-pi-uibm) tariff schedule |
| Auth | per-request (paid) |
| Rating | 🔴 Red — paid bulk, no zero-infra path |

### WIPO IP API Catalog

| Field | Value |
|---|---|
| Endpoint | [`apicatalog.wipo.int`](https://apicatalog.wipo.int/) (open `GET /api/apis?size=300` read endpoint) |
| Probe (2026-05-18) | `totalCount: 179`; organisations: `[DPMA, EPO, EUIPO, IP Australia, JPO, MOIP KOREA, QAZ, UPRP, USPTO, WIPO]`. **UIBM is not among them.** Zero Italy-related entries. |
| Rating | informational — confirms UIBM is absent from the canonical-inventory layer |

## §4 Fees

**Policy: link only.**

UIBM publishes fee schedules (in EUR) covering patent and utility
model filing, search, examination, grant, renewal, and annual fees;
SPC filing and renewal; trademark filing per class and renewals
(multi-class schedule); industrial design filing per design and
renewals; plant variety filing and maintenance; miscellaneous services
(file inspection, certified copies, priority documents, *trascrizioni*
recordal fees, BOPI publication of acts); and the **paid bulk
semestrale extract** of the register under DM 02.04.2007. Statutory
basis is the **Codice della Proprietà Industriale (CPI), Decreto
Legislativo 10 febbraio 2005, n. 30**, with implementing fee schedules
updated by ministerial decree.

- **Official fee schedule:** [UIBM tariffe (IT)](https://uibm.mise.gov.it/index.php/it/tasse-e-tariffe)
- **Statutory basis (Codice della Proprietà Industriale):** [D.Lgs. 30/2005 on Normattiva](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2005-02-10;30)
- **Original publication:** [D.Lgs. 30/2005 — Gazzetta Ufficiale](https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2005-03-04&atto.codiceRedazionale=005G0055)
- **Codice della Proprietà Industriale — UIBM landing:** [CPI page (IT)](https://uibm.mise.gov.it/index.php/it/normativa-pi/il-codice-della-proprieta-industriale)
- **Filing-cost overview (designs):** [Costi di un deposito in Italia (designs)](https://uibm.mise.gov.it/index.php/it/disegni-e-modelli/costi-di-un-deposito-in-italia)
- **Estratti semestrali Banca Dati (paid bulk):** [DM 02.04.2007 tariff link](https://uibm.mise.gov.it/index.php/it/i-servizi/prediagnosi-in-materia-di-pi-pi-uibm)

Notable discount programmes *(name + eligibility — no specific amounts or dates)*:

- **SME Fund (EUIPO Ideas Powered for Business)** — partial reimbursement of national TM and design fees, administered jointly with EUIPO for IT applicants.
- **PCT national-phase entry into IT** — separate fee profile; IT is a PCT contracting state.

## §5 Connector strategy

### What we cover today

- **IT-validated EP patents at biblio / family / legal-events fidelity** — transitively via [`patent_client_agents.epo_ops`](../regional/epo.md) (country code `IT`).
- **Unitary patents effective in IT** — transitively via [`patent_client_agents.epo_ops`](../regional/epo.md) over the EPO Unitary Patent Register.
- **UPC-routed disputes touching IT, including the Milan Central Division** — via shipped `upc_decisions` connector.
- **EUTMs designating IT and Community designs (RCD / REUD)** — transitively via the planned EUIPO connector.
- **IT national TMs and designs (TMview / DesignView)** — transitively via [CTI](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI) through the planned EUIPO connector. **Bibliographic data only** — full register events live at UIBM.
- **Madrid IRs / Hague IRs designating IT** — via planned WIPO Madrid / Hague connectors.

### What we should NOT add — and why

**No UIBM-specific connector.** Documented blockers:

- **No documented programmatic surface.** No REST, no SOAP, no JSON, no XML feed, no API key programme, no developer portal, no acceso-a-servicios-web equivalent.
- **No WIPO IP API Catalog entry.** UIBM is absent from the 179-entry inventory of 10 contributing offices.
- **No `dati.gov.it` presence.** Italy's national open-data CKAN portal has zero UIBM IP datasets. The office has not adopted the open-data posture that OEPM, INPI-FR, PRH, or DPMA have.
- **Anti-deep-linking ToS.** The [Note Legali](https://brevettidb.uibm.gov.it/static/images/UIBM-BrevettiDB_noteLegali.pdf) expressly prohibits the specific operational pattern of a hosted runtime proxy. Permissive for attributed redistribution of "data and analyses" with integrity, restrictive for the runtime-fetch mode.
- **HTML-only AJAX output.** The bancadati AJAX endpoints respond unauthenticated but emit HTML chunks, not JSON — a high-maintenance reverse-engineering surface.
- **Decorative recaptcha tripwire.** The hidden `g-recaptcha-response` field is present but not currently validated server-side; it could be activated at any time, breaking any unauthenticated proxy without notice.
- **Bollettino marchi went HTML-only 2021-05-03.** The previous PDF bollettino was the closest thing to a stable programmatic ingestion path; that's gone.
- **Bulk extracts are paid.** The estratti semestrali under DM 02.04.2007 fall outside the zero-infra constraint.

### Next steps

1. **Watch for change.** UPC Milan Central Division opened 2024-06-27; the Italian MIMIT may eventually align IP register publication with the broader EU Open Data Directive ([2019/1024](https://eur-lex.europa.eu/eli/dir/2019/1024)) push that produced OEPM's permissive Aviso legal and PRH's CC-BY 4.0 sister portal. Re-probe in 12 months.
2. **Address coverage transitively.** EPO OPS for EP-route patents; UPC connector for Milan-routed disputes; EUIPO + CTI for IT TMs and designs at bibliographic fidelity; WIPO Madrid / Hague for international IRs designating IT.
3. **If a specific case demands IT national-only data:** treat as a manual research task; do not engineer a proxy.
4. **Direct enquiry to MIMIT.** Send a courtesy enquiry to [`dgtpi.uibm@mise.gov.it`](mailto:dgtpi.uibm@mise.gov.it) and / or [`assistenza.informatica@mise.gov.it`](mailto:assistenza.informatica@mise.gov.it) asking whether (a) any open-data roadmap is contemplated for the IP register, (b) the WIPO IP API Catalog absence reflects an internal decision or a not-yet-done registration, (c) whether the bollettino marchi has any partner-only XML / PDF export path post-2021.

## §6 Open questions

- **Recaptcha enforcement timeline.** Is the `g-recaptcha-response` field decorative because it was never wired up, or because it was disabled? A note in the page source or a UIBM news announcement would help calibrate the risk of future re-enablement.
- **MIMIT's open-data roadmap.** MIMIT publishes the RNA Aiuti state-aid registry on `dati.gov.it` (monthly cadence). Whether there is any internal plan to extend that posture to UIBM's IP register is unknown.
- **Note Legali scope.** The Note Legali PDF lives at the `brevettidb` sub-site. Whether the same text governs the main bancadati endpoints, or whether bancadati has its own (possibly less restrictive) terms, is unclear.
- **CTI fidelity for IT national TMs and designs.** Italy implements EUIPN CTI; empirical probe needed on whether IT-only register events (oppositions, renewals, *trascrizioni*) surface in TMview / DesignView at full fidelity or just bibliographic-data.
- **UPC Milan Central Division decision routing.** Milan is the third UPC seat (after Paris and Munich). Whether the shipped `upc_decisions` connector treats Milan-routed cases as a separate divisional shard, or commingled with Paris / Munich, is a follow-up validation for the `upc_decisions` connector itself.
- **Estratti semestrali licensing.** The paid bulk extracts under [DM 02.04.2007](https://uibm.mise.gov.it/index.php/it/i-servizi/prediagnosi-in-materia-di-pi-pi-uibm) — whether the resulting data carries a license compatible with redistribution is the gating question for any paid-tier shape (out of scope for the zero-infra constraint regardless).
- **Bollettino marchi post-2021 ingestion path.** UIBM switched from PDF bollettini to web-only HTML on 2021-05-03; whether a PDF / XML export path was preserved for cooperating partners (e.g., EUIPN for TMview ingestion) is unknown.

## §7 References

Primary sources only — `uibm.gov.it`, `uibm.mise.gov.it`,
`mimit.gov.it`, `mimit.gov.it`, `dati.gov.it`, `normattiva.it` /
`gazzettaufficiale.it` for substantive law, `apicatalog.wipo.int`,
`unified-patent-court.org`.

**Service overviews:**
- [UIBM home (MIMIT, IT)](https://uibm.mise.gov.it/index.php/it/)
- [UIBM home (EN)](https://uibm.mise.gov.it/index.php/en/)
- [UIBM database landing page (Banche Dati)](https://uibm.mise.gov.it/index.php/it/banche-dati)
- [Banca dati bibliografica e documentale delle domande e dei titoli italiani di Proprietà Industriale (P.I.)](https://uibm.mise.gov.it/index.php/it/banche-dati/banca-dati-bibliografica-e-documentale-delle-domande-e-dei-titoli-italiani-di-proprieta-industriale-p-i)
- [DGPI-UIBM Ricerca — bancadati search front-end](https://www.uibm.gov.it/bancadati/)
- [brevettidb — granted-patent PDF archive (2008-2015)](https://brevettidb.uibm.gov.it/)
- [Servizi OnLine — e-filing portal (business hours)](https://servizionline.uibm.gov.it/)
- [UIBM Reportistica — statistics portal](https://statistiche.uibm.gov.it/)
- [IPERICO — counterfeiting seizure statistics](https://www.uibm.gov.it/iperico/)
- [Biotech dataset](https://www.uibm.gov.it/biotech/dataset.html)
- [Bollettino marchi — TMs gazette (HTML-only since 2021-05-03)](https://uibm.mise.gov.it/index.php/it/banche-dati/bollettino-marchi)
- [Decisioni — TM nullity / lapse / opposition decisions](https://www.uibm.gov.it/bancadati/Decisioni/index)
- [IGP bulletins — Geographic Indications](https://www.uibm.gov.it/bancadati/igp/Bollettini_igp/index)

**ToS / Note Legali:**
- [Note Legali (PDF, brevettidb)](https://brevettidb.uibm.gov.it/static/images/UIBM-BrevettiDB_noteLegali.pdf) — the dispositive anti-deep-linking clause

**Substantive law (Italian statutes via Normattiva / Gazzetta Ufficiale):**
- [Codice della Proprietà Industriale — Decreto Legislativo 10 febbraio 2005, n. 30 (Normattiva)](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2005-02-10;30)
- [Decreto Legislativo 10 febbraio 2005, n. 30 (Gazzetta Ufficiale)](https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2005-03-04&atto.codiceRedazionale=005G0055)
- [Codice della Proprietà Industriale — UIBM/MIMIT landing](https://uibm.mise.gov.it/index.php/it/normativa-pi/il-codice-della-proprieta-industriale)

**Fees:**
- [UIBM tariffe (IT)](https://uibm.mise.gov.it/index.php/it/tasse-e-tariffe)
- [Estratti semestrali Banca Dati — paid bulk under DM 02.04.2007](https://uibm.mise.gov.it/index.php/it/i-servizi/prediagnosi-in-materia-di-pi-pi-uibm)
- [Costi di un deposito in Italia (designs)](https://uibm.mise.gov.it/index.php/it/disegni-e-modelli/costi-di-un-deposito-in-italia)

**Open data (Italy's national CKAN):**
- [`dati.gov.it`](https://www.dati.gov.it/) — Italy's open-data portal (CKAN 2.x)
- [`dati.gov.it/api`](https://www.dati.gov.it/api) — CKAN API documentation
- [Open Data MIMIT — RNA Aiuti (state-aid registry, no IP)](https://www.dati.gov.it/opendata/api/3/action/package_search?q=ministero+delle+imprese)

**MIMIT parent:**
- [Direzione generale per la proprietà industriale — UIBM organisation on MIMIT](https://www.mimit.gov.it/it/component/organigram/?view=structure&id=11)
- [MIMIT EN organisation page](https://www.mimit.gov.it/en/component/organigram/?view=structure&id=11)

**UPC Milan Central Division:**
- [Opening of the Milan section of the central division (UPC, 2024-06-27)](https://www.unified-patent-court.org/en/news/opening-milan-it-section-central-division)
- [Inauguration ceremony of the Milan section of the central division](https://www.unified-patent-court.org/en/news/inauguration-ceremony-milan-it-section-central-division-unified-patent-court)
- [Italy and UPC sign agreement on Milan central division (Kluwer Patent Blog, 2024-01-30)](https://patentblog.kluweriplaw.com/2024/01/30/italy-and-unified-patent-court-sign-agreement-on-milan-central-division/)

**Cross-office context:**
- [WIPO IP API Catalog](https://apicatalog.wipo.int/) — probed 2026-05-18; 0 UIBM entries across 179 office APIs from DPMA, EPO, EUIPO, IP Australia, JPO, MOIP Korea, QAZ, UPRP, USPTO, WIPO
- [EUIPN Common Tools Integration (CTI)](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI) — bibliographic flow to TMview / DesignView
- [PCT Applicant's Guide — Italy](https://pctlegal.wipo.int/eGuide/view-doc.xhtml?doc-code=IT&doc-lang=en)

**Detail surveys + waves:**
- [`waves/2026-05-18-secondary-nationals-wave/it-uibm.md`](../waves/2026-05-18-secondary-nationals-wave/it-uibm.md) — 2026-05-18 grounded API discovery

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-18 | Initial synopsis; rating **`red_no_api`**. Findings: (a) UIBM publishes **no** documented REST/JSON/XML developer API; (b) [WIPO IP API Catalog](https://apicatalog.wipo.int/) returns **0 UIBM entries** across 179 office APIs from 10 contributing offices; (c) [`dati.gov.it`](https://www.dati.gov.it/) CKAN portal contains **0 UIBM-published IP datasets** — UIBM is absent from Italy's national open-data portal across all probes (`?q=uibm` → 0 hits; `?q=brevetti` → 15 hits all third-party; `?q=proprietà industriale` → 6 hits none from UIBM; full `package_list` sweep of 69,942 packages → 0 UIBM matches); (d) the bancadati search front-end at [`uibm.gov.it/bancadati/`](https://www.uibm.gov.it/bancadati/) is a CodeIgniter / jQuery / Bootstrap 3 server-rendered application whose AJAX endpoints **do respond unauthenticated** (verified empirically — 1,298 records for "FERRARI S.P.A." via `POST /bancadati/index.php/single_search/general/applicant_search/result` with only a `ci_session` cookie and zero recaptcha token) but return **HTML chunks, not JSON**, with a hidden `g-recaptcha-response` decorative tripwire that could be activated at any time; (e) the [Note Legali (PDF)](https://brevettidb.uibm.gov.it/static/images/UIBM-BrevettiDB_noteLegali.pdf) **expressly prohibits "deep linking"** (verbatim: *"E' vietato il cd. 'deep linking' ossia l'utilizzo non trasparente, su siti di soggetti terzi, di parti del sito"*) — the operational pattern of a hosted runtime proxy falls within the prohibited envelope; (f) the [Bollettino marchi switched from PDF to web-only HTML on 2021-05-03](https://uibm.mise.gov.it/index.php/it/banche-dati/bollettino-marchi), removing the previously stable programmatic ingestion path; (g) bulk semestrale extracts are **paid** under [DM 02.04.2007](https://uibm.mise.gov.it/index.php/it/i-servizi/prediagnosi-in-materia-di-pi-pi-uibm); (h) the [`servizionline.uibm.gov.it`](https://servizionline.uibm.gov.it/) e-filing portal is restricted to business hours (Mon-Fri 08:00-19:00); (i) coverage closes transitively via EPO OPS (EP-route), shipped `upc_decisions` connector (incl. **Milan Central Division** opened [2024-06-27](https://www.unified-patent-court.org/en/news/opening-milan-it-section-central-division)), EUIPO (EUTMs + RCDs), EUIPN [CTI](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI) (IT national TMs + designs into TMview / DesignView at bibliographic fidelity), and WIPO Madrid / Hague (IRs designating IT). Connector status: **skipped**. Largest residual gap: IT *modello di utilità* and IT SPCs (the latter explicitly outside Milan UPC Central Division's IPC class A jurisdiction). | [waves/2026-05-18-secondary-nationals-wave/it-uibm.md](../waves/2026-05-18-secondary-nationals-wave/it-uibm.md) |
