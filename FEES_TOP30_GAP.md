# Fees connector — top-30 coverage gap

Honest accounting of where `patent_client_agents.fees` stands against the
WIPO World IP Indicators 2024 ranking of patent offices by filing volume
(2023 data). Updated 2026-05-19 (afternoon, rolling) — user-pointed research
sessions cleared seven offices from the "blocked" pile to
actionable status without writing connector code yet. **Five are
green (httpx + pypdf/lxml will ship cleanly)**, **one is yellow
(needs dev-browser for v1)**, and **one is architectural-different
(ship as service-catalog reference document, not a FeeItem
connector — TCP-layer block on every primary source + dynamic
filing-time fee calculation, no consolidated PDF analogue)**:

- **MX**: the May 2023 *Acuerdo* PDF at `gob.mx/cms/uploads/attachment/file/824879/Acuerdo.Tarifa.12.05.23.pdf` is reachable from US egress (the geo-block applies to register hosts, not the CMS attachment endpoint); DOF's "block" turned out to be an SSL chain issue resolved with `verify=False`. Consolidated 2023 + a March 2024 amendment (indigenous/Afro-Mexican fee waiver) are the binding state; no post-April-2026-reform tariff has been republished yet. See [`research/national/mx-impi.md`](research/national/mx-impi.md) §4.
- **TR**: the 2026 schedule was gazetted in Resmî Gazete 5. mükerrer 31-12-2025 (BİK/TÜRKPATENT 2026/1 → `20251231M5-37.pdf`) and re-hosted as native HTML tables (6-column shape) on three TÜRKPATENT site pages; earlier "SPA" finding was wrong. See [`research/national/tr-turkpatent.md`](research/national/tr-turkpatent.md) §4.
- **HK**: all three IPD forms-and-fees pages (patents / trade-marks / designs) are reachable as server-rendered HTML. Earlier 404 in the gap doc was a wrong URL guess — the designs section is at `/en/designs/`, not `/en/registered-designs/`. The two standard-patent routes (OGP since Dec 2019 vs re-registration of designated CN/GB/EP(UK) patents) are encoded inline as `(O)` / `(R)` tags in the description column with substantially different grant fees (HK$4,413 vs HK$686). Statutory citation is Cap. 514C Sched. 4, Cap. 559A Sched. 1, Cap. 522A on e-Legislation (JS SPA — citation only). See [`research/national/hk-ipd.md`](research/national/hk-ipd.md) §4.
- **SG**: SSO returned 200 OK on first hit (141 tables on Patents Rules) with First Schedule "Fees payable" confirmed — prior wave's "stochastic CloudFront rate-limit" finding superseded. IPOS publishes the per-right schedule on 6 dedicated HTML pages, but with two non-obvious slugs: patents is at `/about-ip/patents/forms-and-fees-singapore/` (with `-singapore` suffix; the user-known `/forms-and-fees/` 404s) and designs is at `/about-ip/designs/forms-and-fees/` (not `/registered-designs/`). Two-phase 2025-09-01 + 2026-04-01 implementation; three structural levers (TM pre-approved-DB S$240 vs custom S$410/class; patent excess-claims threshold 20→15 with S$80/claim doubling; Madrid SG-designation as separate route). See [`research/national/sg-ipos.md`](research/national/sg-ipos.md) §4.
- **ES** *(green)*: prior wave's "URL retired" finding for the procedural-fees page is real (the signos / diseños sub-pages return 410 Gone today) but OEPM publishes a **single consolidated PDF** at [`oepm.es/.../TASAS_y_PRECIOS_PUBLICOS.pdf`](https://www.oepm.es/export/sites/portal/comun/documentos_relacionados/PDF/TASAS_y_PRECIOS_PUBLICOS.pdf) covering every fee surface (patents / UM / SPCs / designs / TMs / trade names / semiconductor topographies / PCT national-phase / precios públicos). 670 KB / 17 pages, "Actualizado a fecha: 1 de abril de 2026" stamp, parses cleanly with `pypdf`. Dual-channel pricing (paper vs electronic ~15% reduced); SME / individual-entrepreneur / public-university 50% reduction flagged with `(*)` asterisk on rows eligible under Ley 24/2015 art. 186. Statutory basis: Ley 24/2015 Annex + Ley 17/2001 Annex + Ley 20/2003 on BOE; year-over-year amounts adjusted by the annual *Ley de Presupuestos Generales del Estado*. See [`research/national/es-oepm.md`](research/national/es-oepm.md) §4.
- **IL** *(yellow)*: prior wave's "Cloudflare 403 on gov.il" is correct for `gov.il/*` (every sub-path is wall-walled from US residential egress), but the **canonical current-effective schedule lives on `ecom.gov.il/counterspa/home/14/2/{patents,trademarks,designs}`** — a separate subdomain gated by Akamai Bot Manager instead of Cloudflare, returning 200 OK with valid SSL. The pages are Angular SPA shells (~3 KB) requiring hydration + CSRF + Akamai PoW to load data — plain httpx gets the shell only. v1 path: dev-browser-rendered DOM extraction (EPO BFF analogue), ~1-2 hr SPA reverse-engineering planned to promote to clean httpx. Statutory structure from [WIPO Lex 19117](https://www.wipo.int/wipolex/en/legislation/details/19117) (Patents Regulations 5728-1968 Schedule), but its consolidated text is as-amended-up-to-2019 → stale by 7 years for amounts because Israeli fees CPI-adjust every 1 January (2025: +3.5%). Three structural levers: (a) small-entity 40% with turnover-under-NIS-10M-AND-first-ever-application criteria (narrower than US small-entity), (b) excess-claims per claim >50, (c) excess-pages per 50 pages >100 (sequence listings excluded). See [`research/national/il-ilpo.md`](research/national/il-ilpo.md) §4.
- **SA** *(architectural-different — ship as reference doc)*: every SAIP primary source (eServices unified portal `eservices.saip.gov.sa`, legacy TM portal `tm.saip.gov.sa`, SAIP main site `saip.gov.sa`, Umm al-Qura gazette `uqn.gov.sa`) **ConnectTimeout at the TCP layer from US residential egress** — packet-level filtering, not a WAF challenge. No sister-subdomain bypass available (unlike Israel's gov.il-vs-ecom.gov.il split). WIPO Lex reachable for [Implementing Regulations 19743](https://www.wipo.int/wipolex/en/legislation/details/19743) but consolidated only through SAIP Board Decision 5/8/2019 of 9 May 2019 — does not reflect post-2019 Board resolutions (notably the June 2022 TM publication-fee cuts) or the 2024 designs protection-duration amendment. **More importantly, the architectural model differs from every other office in this wave**: SAIP doesn't publish a standalone gazette annex or downloadable consolidated PDF — fees are calculated *dynamically* at the point of filing in the eServices portal, with statutory authority fragmented across principal laws + Implementing Regulations + periodic SAIP Board resolutions. Recommended v1 deliverable: **Option A — service-catalog reference document** with explicit "fee calculated at filing time" caveat, anchored from user-sourced notes (TM filing SAR 1,000/class, TM publication SAR 500, post-June-2022 renewal publication ~USD 310). SAR pegged to USD at ~3.75 (no volatility caveat needed); **Hijri-year TM term** docketing trap (10 Hijri ≈ 9y 8m Gregorian); SA is **not** a Madrid party (TMs filed nationally). See [`research/national/sa-saip.md`](research/national/sa-saip.md) §4.

The earlier afternoon ship batch — TIPO Taiwan (`db91c5d`), INPI Brazil,
INPI France — remains in place. The Brazil unblock came from the user
finding the English-PDF mirror at
`gov.br/inpi/en/costs-and-payment/schedule-of-fees-*.pdf`, which is
anonymously accessible while the pt-BR Plone tabela page is auth-gated.

This doc exists so the next session doesn't have to re-discover what's
blocking each remaining office.

---

## §1 Coverage today: 13 of 30 offices

Routes already shipped on the fees connector
(`src/patent_client_agents/fees/registry.py`):

| Rank | Office | Routes | Patterns demonstrated |
|------|--------|--------|------------------------|
| 1    | CNIPA China        | P              | Hierarchical HTML state-machine walker |
| 2    | USPTO              | P / TM / D     | HTML × many sections; entity tiers (large/small/micro) |
| 3    | JPO Japan          | P              | Full Sec-Fetch fingerprint required; multi-cohort tagging |
| 4    | KIPO Korea         | P              | Per-claim row pairing; "N to M years" expansion |
| 5    | EPO                | P              | Hidden JSON BFF discovered via dev-browser |
| 6    | IPO India          | P              | Schedule_1.pdf via pypdf with column-alignment sanity check |
| 7    | DPMA Germany       | P              | PDF (pypdf) with 6-digit code prefix categorization |
| 9    | CIPO Canada        | P              | Multi-table HTML; English-word ordinal year-band expansion |
| 10   | IP Australia       | P              | Multi-table HTML, heading-walks-up-DOM |
| 11   | UKIPO              | P / TM         | gov.uk per-form fan-out (bounded concurrency = 5) |
| 12   | INPI Brazil        | P / TM         | PDF (pypdf) with backward code lookup; large/small tiers via "discounted" column |
| 23   | INPI France        | P / TM / D     | PDF (curated catalog + annuity walker); large/small tiers via "TARIFS RÉDUITS" column; SPC at y=21 |
| 13   | TIPO Taiwan        | P / TM         | HTML table + bilingual PDF curated catalog |
| 25   | OEPM Spain         | P / TM / D     | Single consolidated PDF (pypdf) with curated catalog + Y/U-to-I catalog-key normalization; dual-channel via FeeCondition(paper_filing); PYMES + universities tier=small; SPC annuities via year+recargo decoder |

Plus 3 non-national routes:
* **EUIPO** (regional TM/D — Next.js SSR stream decoding for TM, HTML for D)
* **WIPO** PCT / Madrid / Hague (international systems)

**Total** = 18 offices on 28 routes; 14/30 of the WIPO national ranking,
or 14/27 if we exclude the offices below that are blocked on factors
outside our control (Russia + Iran sanctions, plus offices we have not
yet found a public route for).

### Documented but not yet built (ready to ship — research done 2026-05-19)

These have a confirmed primary-source URL, a parsing pattern
already proven on another office, and a research synopsis on
file. The block is "we haven't written the code yet," not
infrastructure:

| Rank | Office | Source identified | Pattern to copy | Synopsis |
|---|---|---|---|---|
| 14 | **HKIPD Hong Kong** | IPD 3 HTML pages (patents / trade-marks / designs) + Cap. 514C / 559A / 522A on e-Legislation as citation | CIPO Canada / IP Australia — `lxml` multi-table HTML with inline route tag and e-filing/paper sub-tables | [`research/national/hk-ipd.md`](research/national/hk-ipd.md) §4 |
| 15 | **IMPI Mexico** | gob.mx CMS PDF `824879/Acuerdo.Tarifa.12.05.23.pdf` + DOF amendment codigo=5720420 | IPIN India / DPMA / INPI BR — `pypdf` 3-column extraction | [`research/national/mx-impi.md`](research/national/mx-impi.md) §4 |
| 17 | **TÜRKPATENT** | TÜRKPATENT 3 HTML pages + Resmî Gazete `20251231M5-37.pdf` | IP Australia / UKIPO — `lxml` multi-table HTML | [`research/national/tr-turkpatent.md`](research/national/tr-turkpatent.md) §4 |
| 22 | **IPOS Singapore** | IPOS 5 HTML pages (P/TM/D + GI + PVR; `forms-and-fees-singapore` on patents, `/designs/` not `/registered-designs/`) + SSO Patents Rules `PA1994-R1` First Schedule + TMA1998-R1 + RDA2000-R1 | CIPO Canada / IP Australia — `lxml` multi-table HTML; primary fee table at idx 1 per page (3-col `Form code \| Description \| Fee`) | [`research/national/sg-ipos.md`](research/national/sg-ipos.md) §4 |
| 25 | ~~**OEPM Spain**~~ | ✅ SHIPPED 2026-05-19 via the consolidated `TASAS_y_PRECIOS_PUBLICOS.pdf` (670 KB / 17 pages, "Actualizado a fecha: 1 de abril de 2026"). Curated catalog + Y/U-to-I catalog-key normalization handles the three tier tables (full-rate IT/IE; PYMES YT/YE; universities UT/UE — both mapped to `EntityTier.small`). Dual-channel via `FeeCondition(trigger=paper_filing)` on T-suffix codes. SPC annuities (CP01..CP55) decoded into year × recargo band. Notable correction: the `(*)` row markers on the PDF are credit-card-payable flags per the page-2 footnote — NOT SME-eligibility flags as the original research note suggested. v1 GAPS: patent annuities (page 6 IP/2P/5P × IR/2R/5R × YP/Y2/Y5 × UP/U2/U5), design renewal table (page 13 DT41/D241/D541), PCT international fees (pages 8-9), and precios públicos (pages 16-17) ship as separate column structures and are documented as known v1 gaps. | n/a | n/a |
| 26 | **ILPO Israel** *(yellow)* | ecom.gov.il counterspa SPAs for `/patents` + `/trademarks` + `/designs` (current amounts, Akamai-gated Angular); WIPO Lex 19117 Patents Regulations 5728-1968 Schedule (structure, 2019-consolidated → stale amounts) | EPO BFF — dev-browser-rendered DOM extraction; 1-2 hr SPA reverse-engineer planned to promote to clean httpx | [`research/national/il-ilpo.md`](research/national/il-ilpo.md) §4 |
| 29 | **SAIP Saudi Arabia** *(architectural-different)* | WIPO Lex Implementing Regulations 19743 (statutory structure, 2019-consolidated → stale amounts) + user-sourced fee anchors from June 2022 SAIP Board resolution (TM filing/publication/renewal); eServices + Umm al-Qura unreachable from US egress | None — ships as a service-catalog reference document, not a FeeItem connector. Closest sibling: `StaticLawCorpus` with explicit "fee calculated at filing time" caveat | [`research/national/sa-saip.md`](research/national/sa-saip.md) §4 |

---

## §2 Remaining offices (ranked 8-30) — blocker + unblock path

Probes were run with realistic browser UA + http2 between 2026-05-19
~13:00-14:00 UTC. Each "blocker" entry is what a plain `httpx` fetch
returned, not what the page would look like in a real browser.

| # | Office | Last-known fee URL | Probe result | Blocker class | Unblock path |
|---|--------|--------------------|--------------|---------------|--------------|
| 8 | **Rospatent** RU | rospatent.gov.ru | n/a (not probed) | Sanctions (OFAC/EU) | Defer pending compliance review. Schedule itself is informational only; the question is whether we can host it on the public demo. |
| 12 | ~~**INPI Brazil**~~ | ✅ SHIPPED 2026-05-19 via `gov.br/inpi/en/costs-and-payment/schedule-of-fees-*.pdf` (the EN-language PDFs are anonymously accessible while the pt-BR Plone landing is auth-gated) | n/a | n/a | n/a |
| 14 | **HKIPD** Hong Kong | **✅ READY** — [`ipd.gov.hk/en/patents/forms-and-fees/`](https://www.ipd.gov.hk/en/patents/forms-and-fees/index.html) (32 tables), [`/en/trade-marks/forms-and-fees/`](https://www.ipd.gov.hk/en/trade-marks/forms-and-fees/index.html) (17 tables), [`/en/designs/forms-and-fees/`](https://www.ipd.gov.hk/en/designs/forms-and-fees/index.html) (12 tables — note `/designs/` not `/registered-designs/`) | All 200 OK, server-rendered HTML, `Descriptions | Fee (HKD)` shape with `(O)` / `(R)` route tags inline and e-filing/paper-filing sub-tables where applicable. Valid SSL. | Mis-diagnosed: prior URL guesses just hit the wrong path; the IPD designs section is at `/en/designs/`, not `/en/registered-designs/`. | **Ready to ship.** Connector: `HK/IPD/Fees/{Patent,ShortTermPatent,Trademark,Design}`. Currency HKD. Patent route is a first-class dimension (OGP vs re-registration, very different grant fees: HK$4,413 vs HK$686). Statutory citation: Cap. 514C Sched. 4, Cap. 559A Sched. 1, Cap. 522A on [e-Legislation](https://www.elegislation.gov.hk/) (JS-rendered SPA — citation only). |
| 15 | **IMPI Mexico** | **✅ READY** — [`gob.mx/cms/uploads/attachment/file/824879/Acuerdo.Tarifa.12.05.23.pdf`](https://www.gob.mx/cms/uploads/attachment/file/824879/Acuerdo.Tarifa.12.05.23.pdf) | 200 OK, 644 KB PDF, clean 3-column extraction with `pypdf` (22 pages, 200+ Artículos). DOF accessible too (SSL chain needs `verify=False`). | Mis-diagnosed: the geo-block applies to the register hosts on Telmex `187.130.250.0/24`, **not** the gob.mx CMS attachment endpoint (Akamai-fronted). | **Ready to ship.** v1 schedule = May 2023 PDF + March 2024 *Acuerdo* (indigenous/Afro-Mexican fee waiver, [codigo=5720420](https://www.dof.gob.mx/nota_detalle.php?codigo=5720420&fecha=15/03/2024)). Watch DOF for post-April-2026-reform tariff republication. Connector: `MX/IMPI/Fees/{Patent,UtilityModel,Design,IntegratedCircuit,Trademark}`. |
| 16 | **Iran IPI** | n/a | n/a (not probed) | Sanctions + connectivity | Defer pending compliance + sanctions review. |
| 17 | **TÜRKPATENT** | **✅ READY** — [`turkpatent.gov.tr/patent-islem-ucretleri`](https://www.turkpatent.gov.tr/patent-islem-ucretleri) (P/UM) + [`marka-islem-ucretleri`](https://www.turkpatent.gov.tr/marka-islem-ucretleri) (TM) + [`tasarim-islem-ucretleri`](https://www.turkpatent.gov.tr/tasarim-islem-ucretleri) (D); Resmî Gazete [`20251231M5-37.pdf`](https://www.resmigazete.gov.tr/eskiler/2025/12/20251231M5-37.pdf) as primary source | 200 OK, 1 real `<table>` per page, 6 cols (KOD/AÇIKLAMA/ÜCRET/KDV/HARÇ/TOPLAM TUTAR), 57 patent rows. Resmî Gazete reachable, valid SSL. | Earlier "21 scripts SPA" assessment was wrong — pages have server-rendered tables. | **Ready to ship.** v1 connector: `TR/TURKPATENT/Fees/{Patent,UtilityModel,Design,Trademark,Appeal}`. Currency TRY. Annual republication on/about 31 Dec, large YoY jumps (2024→2025 +44%, 2025→2026 +20–25% from TRY inflation) — flag freshness aggressively. Statutory basis Law 6769 SMK Art. 188. |
| 18 | **DIP Thailand** | ipthailand.go.th | Not probed | PDF (Thai + EN) per research | Probe needed; likely DPMA/IPIN-shape PDF scraper. |
| 19 | **DGIP Indonesia** | dgip.go.id | Not probed | PP 28/2019 PDF + HTML | Probe needed. |
| 20 | **IP Viet Nam** | noip.gov.vn | Not probed | Circular 263/2016 PDF | Probe needed. |
| 21 | **EAPO** | eapo.org | Not probed | Multilateral; potential RU exposure | EAPO billing is in USD which is unusual. Compliance check first. |
| 22 | **IPOS Singapore** | **✅ READY** — IPOS 5 HTML pages: [`patents/forms-and-fees-singapore`](https://www.ipos.gov.sg/about-ip/patents/forms-and-fees-singapore/) (9 tables, 102-row patent table at idx 1), [`trade-marks/forms-and-fees`](https://www.ipos.gov.sg/about-ip/trade-marks/forms-and-fees/), [`designs/forms-and-fees`](https://www.ipos.gov.sg/about-ip/designs/forms-and-fees/), [`geographical-indications/forms-and-fees`](https://www.ipos.gov.sg/about-ip/geographical-indications/forms-and-fees/), [`plant-variety-rights/forms-and-fees`](https://www.ipos.gov.sg/about-ip/plant-variety-rights/forms-and-fees/) + SSO Rules ([PA1994-R1](https://sso.agc.gov.sg/SL/PA1994-R1) / [TMA1998-R1](https://sso.agc.gov.sg/SL/TMA1998-R1) / [RDA2000-R1](https://sso.agc.gov.sg/SL/RDA2000-R1)) | All 200 OK on first hit; SSO returns full content (141/134/116 tables on the three Rules; First Schedule "Fees payable" confirmed). Patent URL has `-singapore` suffix; designs URL is `/designs/` not `/registered-designs/`. Valid SSL. | Mis-diagnosed: prior "stochastic CDN rate-limit" finding either transient or load-induced — first-hit probes today returned full 471 KB. URL guesses failed on patents + designs because IPOS uses non-obvious slugs. | **Ready to ship.** Connector: `SG/IPOS/Fees/{Patent,Trademark,Design,GeographicalIndication,PlantVariety}`. Currency SGD. Two-phase implementation: 2025-09-01 + 2026-04-01 effective dates as FeeItem provenance. Three structural levers: (a) TM spec-type S$240 pre-approved vs S$410 custom, (b) patent excess-claims threshold 20→15 with per-claim S$40→S$80, (c) Madrid SG-designation as separate route. Statutory cite: Patents Rules SSO `PA1994-R1` First Schedule, TM Rules `TMA1998-R1`, Designs Rules `RDA2000-R1`. |
| 23 | ~~**INPI France**~~ | ✅ SHIPPED 2026-05-19 via inpi.fr/inpi-block/download-document?id=20516 (the procedures PDF, anonymously accessible — discovered as an anchor on the INPI Tarifs landing page). The Cloudflare-blocked legifrance route turned out to be unnecessary. | n/a | n/a | n/a |
| 24 | **UIBM Italy** | uibm.mise.gov.it/index.php/it/tasse-e-tariffe | Not yet probed in this session | TBD | Probe needed. uibm.mise.gov.it has historically been straightforward HTML. |
| 25 | ~~**OEPM Spain**~~ | ✅ SHIPPED 2026-05-19 — `ES/OEPM/Fees/{Patent, Trademark, Design}` from the consolidated [`TASAS_y_PRECIOS_PUBLICOS.pdf`](https://www.oepm.es/export/sites/portal/comun/documentos_relacionados/PDF/TASAS_y_PRECIOS_PUBLICOS.pdf). Patent route covers IT/IE (full rate) + YT/YE (PYMES, 50%) + UT/UE (public universities, 50%) + ET (EP-validation) + PT/PE + CP (SPC annuities, year × recargo decoder) + I3/I5/I7/I8 procedural. Trademark covers MT/ME + CM/CI common procedural with per-class structure. Design covers DT/DE + max-payment caps. The earlier "(*) = SME-eligible" claim was corrected: the asterisk is a credit-card-payment marker per the PDF's page-2 footnote — not a tariff dimension. UM track is structurally identical to patent (same IT/IE codes apply per §3 section header) and can ship later as a thin wrapper over the patent builder. | n/a | n/a |
| 26 | **ILPO Israel** | **🟡 YELLOW** — current amounts at [`ecom.gov.il/counterspa/home/14/2/patents`](https://ecom.gov.il/counterspa/home/14/2/patents) + `/trademarks` + `/designs` (Angular SPA, Akamai bot manager, no Cloudflare); statutory structure at [WIPO Lex 19117](https://www.wipo.int/wipolex/en/legislation/details/19117) (Patents Regulations 5728-1968 Schedule, **stale by 7 years for amounts**) | gov.il proper is Cloudflare-403-wide from US egress, but ecom.gov.il subdomain bypasses Cloudflare; SPA shells return 200 OK / valid SSL / 3 KB. Content requires Angular hydration + CSRF + Akamai PoW to load — plain httpx returns the shell only. | Half-superseded: prior "Cloudflare 403" is correct for gov.il proper, but the real fee data was always on the separate ecom.gov.il subdomain (which is Akamai-gated, not Cloudflare-gated). | **Needs dev-browser for v1.** First office in this wave that doesn't ship cleanly with `httpx` + `pypdf` / `lxml`. Plan: dev-browser-rendered DOM extraction (EPO BFF analogue), ~1-2 hr SPA reverse-engineering planned to promote to clean httpx. Currency NIS. Structural levers: small-entity 40% (turnover-under-NIS-10M + first-application criteria, narrower than US small-entity), excess-claims (per claim >50), excess-pages (per 50 pages >100). CPI-adjusted annually 1 January (2025: +3.5%). |
| 27 | **MyIPO Malaysia** | myipo.gov.my/en/patent/ (200, 3 tables on Act page) | URL discovery needed for actual fees page | URL unknown | 15-min dev-browser navigation from myipo.gov.my homepage. Probably reachable. |
| 28 | **IPOPHL Philippines** | ipophl.gov.ph | Not probed | Memorandum Circular PDF + HTML schedule | Probe needed. |
| 29 | **SAIP Saudi Arabia** | **🟠 ARCHITECTURAL** — primary sources (eServices `eservices.saip.gov.sa`, legacy TM portal `tm.saip.gov.sa`, SAIP main site `saip.gov.sa`, Umm al-Qura gazette `uqn.gov.sa`) all ConnectTimeout from US egress (packet-level block, not WAF); reachable fallback: [WIPO Lex Implementing Regulations 19743](https://www.wipo.int/wipolex/en/legislation/details/19743) — but consolidated only through 2019-05-09, doesn't reflect post-2019 SAIP Board resolutions (notably the June 2022 TM publication-fee cuts) | All 4 SAIP-related subdomains ConnectTimeout; not even a sister-subdomain bypass available. WIPO Lex reachable for statutory **structure** but stale by 7 years for amounts. | **Structurally different.** Unlike every other office in this wave, SAIP doesn't publish a standalone gazette annex or downloadable consolidated PDF — fees are calculated dynamically at the point of filing in the eServices portal. There is **no clean FeeItem extraction path** from US egress. | **Ship as reference document, not connector.** v1 plan: curated markdown / JSON mirroring the SAIP service catalog with explicit caveats ("fee calculated at filing time", "for litigation/opinion use local KSA counsel + Umm al-Qura"). Key anchors from user notes: TM filing SAR 1,000/class, publication SAR 500, post-June-2022 renewal publication ~USD 310. SAR pegged to USD at ~3.75 (no volatility). **Hijri-year TM term** (10 Hijri yrs ≈ 9y 8m Gregorian — docketing trap). SA is **not** a Madrid party — TMs filed nationally. |
| 30 | **UPRP Poland** | uprp.gov.pl | Not probed | Regulation annex PDF | Probe needed. |

Boundary cases just outside top-30 (any could displace #28-30 in any
given year): South Africa CIPC, Argentina INPI, Egypt EAIP, Switzerland
IGE/IPI (most CH activity flows through EPO anyway), New Zealand IPONZ
(has research note + research suggests clean HTML at iponz.govt.nz/get-ip).

---

## §3 Aggregated unblock paths

Looking across the gap table, the same handful of infra needs unblock
many offices at once. Picking ONE of these gets us further than any
single-office push:

### 3.1 Stealth HTTP service (highest leverage)

A residential-IP stealth proxy (ScrapingBee, Zyte, ScraperAPI, Bright
Data — $30-300/mo) would unblock:

* INPI Brazil (Plone auth-gate may persist, but Portaria PDFs on
  `in.gov.br` would be reachable)
* Legifrance for INPI France
* Wayback Machine (currently rate-limiting us)
* Brazilian DOU search
* Cloudflare-challenged pages (Israel ILPO, possibly more)
* IMPI Mexico geo-block
* SAIP Saudi Arabia ConnectTimeout from US

**Estimated impact: +5-7 offices unblocked from infrastructure alone**,
without writing any office-specific code. Each unblocked office still
needs its 2-3 hr scraper write + verification.

**Cost:** ~$30/mo on the entry tier; one-time integration ~2-3 hr
(BYOK env-var, route critical clients through the proxy).

**Tradeoff:** Adds an external dependency and a recurring spend. Worth
it for hosted-demo coverage; not worth it if the goal is local-only.

### 3.2 Paid official APIs (free but require registration)

* **Legifrance PISTE** — `piste.gouv.fr` — French statutory database
  with structured Code de la propriété intellectuelle access. Free
  with registration. Unblocks France only.
* **Gazette PISTE** — same provider — covers DOU equivalents for
  Portugal/Spain in some cases.
* **gov.br federated auth** — Brazilian CPF or consular nat-reg
  required. Bureaucratic for foreign developers; not recommended
  unless we have a Brazilian collaborator.

### 3.3 Dev-browser stealth profile

The `dev-browser` skill at `~/.claude/skills/dev-browser/` ships a
stealth-mode chromium. In this session it was in a flaky state (CDP
WebSocket connection timing out after a restart) — about 30 min of
investment to get it healthy. Once working, unblocks:

* All Cloudflare-challenged pages (FR, IL)
* All JS-rendered SPAs (TR, BR — though BR auth-gate persists)
* Wayback Machine (browser doesn't trigger API rate limit)

**Estimated impact: similar to §3.1 but no recurring spend.** Tradeoff:
slower per-fetch (~5-10s vs <1s) and requires the dev-browser server
running.

### 3.4 Class lessons learned (from MX + TR triage on 2026-05-19)

Each of the next "blocked" offices should be re-probed against these
patterns before any tool spend or proxy spend is considered:

- **HTML landing page blocked ≠ canonical document blocked.** gob.mx
  serves a PoW Challenge Validation on the HTML landing for IMPI
  (`/impi/acciones-y-programas/...`) but the **CMS attachment endpoint**
  (`/cms/uploads/attachment/file/.../*.pdf`) is anonymously fetchable
  from US egress. Many other governments split static-asset CDN edges
  from session-stateful HTML — always probe the attachment URL pattern
  separately before declaring an office blocked.
- **SSL cert chain errors look like geo-blocks but aren't.** `dof.gob.mx`
  was listed as "DOF gating" in the earlier table — actually it ships
  an incomplete cert chain that fails plain `httpx` with
  `CERTIFICATE_VERIFY_FAILED`. Reachable cleanly with `verify=False` or
  with a current Mozilla CA bundle. **Always try `verify=False` once
  before declaring an SSL failure as a block.**
- **"X scripts, 0 tables, looks like a SPA" can be wrong.** TÜRKPATENT
  was flagged as a JS-rendered SPA based on a script count; the page
  actually has 1 server-rendered `<table>` per right type. Always
  inspect for `<table>` markup directly before deferring to
  dev-browser.
- **Annual-republication offices have an inflation tell.** TÜRKPATENT
  jumps +44% / +20–25% YoY due to TRY inflation. Any office where
  the rate-of-change between published versions exceeds ~10% YoY needs
  an aggressive freshness window (≤90d) and a TRY-equivalent currency
  note in client cost estimates.
- **A 404 on a guessed URL is not evidence the office is blocked.** The
  HKIPD entry sat at "URL drift / unknown" because earlier guesses
  hit `/en/registered-designs/forms-and-fees/index.html` (404) and
  `/eng/fees.htm` (404). The actual designs URL is `/en/designs/...` —
  IPD's designs section is the singleton exception to its long-form
  section naming. Always walk down from the office homepage's
  navigation rather than guessing per-right URL patterns based on the
  ordinance title.
- **Right-type-specific structural features matter for the data model.**
  Hong Kong's two patent routes (OGP vs re-registration) and its
  e-filing/paper-filing splits are first-class FeeItem dimensions, not
  flatten-able into a single per-row amount. Probe each office for
  these structural features before committing the column model:
  filing-channel discounts, dual prosecution routes, per-class TM
  fees, multi-design discounts, etc.
- **Staged effective dates inside a single schedule.** Singapore's
  current schedule mixes amounts in force from 2025-09-01 with
  amounts in force from 2026-04-01 on the same page; the IPOS HTML
  shows the *current effective* rate but the back-dated rates live on
  the 21-Jul-2025 circulars' Annex A tables. The connector must emit
  an `in_effect_from` provenance per FeeItem so that fee-as-of-date
  queries work correctly — flattening to a "current rate" alone loses
  the ability to estimate costs for filings made just before or after
  an implementation date.
- **Per-applicant choice levers** (not size-based tiers). Singapore's
  trademark filing fee is S$240/class if the applicant adopts the IPOS
  pre-approved goods-and-services classification database, or
  S$410/class for custom specs — both rates available to every
  applicant, with the choice driven by drafting strategy not by entity
  status. This is structurally distinct from a `large/small/micro`
  `EntityTier`; it's a `specification_type` provenance field. Watch
  for similar patterns elsewhere (e-filing vs paper at HK, language
  preference at certain offices, etc.).
- **Dual-channel pricing on every row + stackable size-based discount.**
  Spain's consolidated PDF gives each fee a *pair* of codes — one for
  the non-electronic channel (`MT17`/`IT01`) and one for the
  electronic channel at ~15% reduction (`ME17`/`IE01`). On top of
  that, a `(*)` asterisk on the electronic-channel key flags rows
  where the Ley 24/2015 art. 186 SME / individual-entrepreneur /
  public-university 50% reduction *also* applies. The two discounts
  *stack* multiplicatively (electronic ~15% × SME 50% on filing,
  search, and substantive examination fees). The data model has to
  carry `filing_channel` and `eligible_for_sme_reduction` as
  independent dimensions — flattening to one column loses the
  legal arithmetic. Watch for similar patterns elsewhere (most
  European offices with both e-filing discounts and statutory SME
  schemes).
- **EP-validation rows belong in the national fees schedule but tagged
  as a separate track.** ES Annex of Ley 24/2015 covers both
  direct ES-national patent annuities and EP-validation-in-Spain
  post-grant annuities, often sharing code numbers. The EPO grant
  fee itself is paid to EPO, not to OEPM, so EP-validation fees
  should carry a `validation_track = "EP-XX"` provenance tag to
  avoid being double-counted against EPO Rfees. Same principle
  for any office that validates EP patents (DE, FR, NL, IT, etc.).
- **Bot-protection perimeters differ by subdomain.** Israel's
  `gov.il/*` returns Cloudflare 403 from US egress on every
  sub-path (EN, HE, ilpo, departments, dynamiccollectors —
  everything), but `ecom.gov.il/counterspa/*` is on the e-payment
  subdomain, gated by Akamai Bot Manager instead — and Akamai
  doesn't block at the perimeter, it just requires the SPA's
  CSRF + PoW handshake to load data. Same pattern at gob.mx
  (HTML pages gated, CMS attachments not). When an office's
  main domain returns 403, **always probe sister subdomains**
  (e-payment portals, e-filing portals, CMS attachment paths,
  open-data portals) before concluding the office is blocked
  — they often run on different infrastructure with different
  perimeters.
- **JS-rendered SPAs aren't always bot-blocked.** Israel's
  ecom.gov.il counterspa pages reach 200 OK from US egress
  with valid SSL; they just don't render content without
  Angular initialization. Don't conflate "SPA shell" with
  "blocked" — the dev-browser path is always available, and
  often the underlying JSON API is reverse-engineerable for a
  clean httpx promotion. Plan the SPA-reverse-engineering hour
  alongside the dev-browser-v1 ship, not after.
- **Architectural-different offices need a different deliverable
  shape.** Saudi Arabia is the first office in this wave that
  fundamentally doesn't publish a standalone fee schedule —
  SAIP calculates fees dynamically at point of filing in the
  eServices portal, with statutory authority fragmented across
  the principal laws, their Implementing Regulations, and
  periodic SAIP Board resolutions gazetted in *Umm al-Qura*.
  Combined with packet-level TCP blocking of every primary
  source from US egress, there is no clean FeeItem extraction
  path. The right deliverable is a **service-catalog reference
  document** (curated markdown / JSON with explicit "fee
  calculated at filing time" caveats), not a connector. Watch
  for similar architectures elsewhere — any office where the
  applicant has to log in to a portal to see the fee, with no
  parallel PDF schedule, falls into this class. Cost-estimator
  tools should fall back to the reference document with a
  clear "needs local counsel for defensible cite" caveat.
- **Calendar-system traps in term-of-protection metadata.**
  Saudi trademark registration is **10 *Hijri* years** from
  filing date (~9 years 8 months Gregorian), renewable in 10-
  Hijri-year periods. A Gregorian-based docketing reminder
  runs ~4 months late. The data model must carry a
  `term_calendar = "Hijri"` (or "Buddhist", or "Iranian
  Solar" — see Thailand / Iran) provenance on all
  term-of-protection FeeItems for offices outside the
  Gregorian-default zone. Don't bake "10 years" as a Gregorian
  duration — the underlying statute often specifies a
  different calendar system, and the difference compounds
  across renewal cycles.

### 3.5 Sanctions clearance for RU/IR

Russia (Rospatent) and Iran (IPI) are blocked on OFAC / EU sanctions
considerations, not technical infrastructure. The fee schedule itself
is publicly informational, but hosting it on `mcp.patentclient.com`
without compliance review is a different question. Recommended:

* Defer Rospatent + Iran until a sanctions advisor signs off.
* If the answer is "informational publication is fine," both offices
  are reachable from the US with regular `httpx`.
* If the answer is "no public hosting," we can still ship the
  scrapers locally and gate them off the hosted demo.

---

## §4 Realistic ceiling without paid infra

* **Today**: 13 of 30 = 43%.
* **With the EN-PDF-anchor pattern applied to the unprobed offices**:
  estimate 18-22 / 30 = 60-73%. The Brazil + France wins this session
  came from finding a parallel public PDF anchor that bypassed the
  obvious Cloudflare/auth wall on the canonical URL. The same pattern
  likely works for IL, ES, IT, SG, MY, HK, TR, ID, VN, TH, PH.
* **With a stealth HTTP service + ~2 weeks**: 22-25 / 30 = 73-83%.
* **30 / 30**: requires sanctions waivers for RU/IR. The other
  remaining offices should all be reachable via the EN-PDF pattern
  or a paid official API; pure 30/30 is feasible without exotic infra
  if we can get a clean probe sweep first.

The honest target is **22-25 of 30 ≈ 80% coverage** of top-30 by
patent filing volume on a one-developer push. Beyond that, RU and
Iran need sanctions clearance; the rest is "keep probing until we
find the anonymous EN-PDF route."

---

## §5 Recommended next steps (in order of leverage)

**Discovery first, ship second.** The session re-anchored this
priority after Brazil and France both turned out to be unblockable
once we found the right URL. The next session should:

1. **Do a 30-min "EN-PDF anchor sweep"** across the remaining
   unprobed offices: IT, ID, VN, TH, PH, NZ, UPRP, HK, MY, IL, ES,
   SG, TR. For each: fetch the main fees URL → look for `<a href>`
   to a downloadable PDF (`.pdf`, `/download-document`, `/block/`,
   `/wSite/public/Attachment/`, etc.) AND try the `/en/`-prefix
   equivalent. Even if the canonical URL 403s, a parallel anonymous
   PDF route is the more-common-than-not outcome.
2. **Order ship work by ranking × accessibility**:
   - Singapore (#22) — landing hub works; SSO has the statutory
     route under stochastic rate-limit. Try the EN-PDF pattern
     on ipos.gov.sg first.
   - Italy (#24) — uibm.mise.gov.it not yet probed; statutory
     ministerial decree route via Normattiva is documented.
   - Spain (#25) — research note has BOE links; both the
     procedural fees pages 410'd but BOE is anonymously fetchable.
   - Israel (#26) — Cloudflare on gov.il; check WIPO Lex copy at
     `wipo.int/wipolex/en/legislation/details/19117` first.
   - Mexico (#15) — geo-blocked subdomain; needs non-US IP. Lower
     priority without stealth service.
3. **Defer until policy review**: Rospatent + Iran IPI (sanctions);
   Brazil 2025 Portaria 10 update (waiting on INPI to republish the
   EN PDF — the scraper currently reflects the 2019 schedule).

Until step 1 is decided, further office-by-office grinding is likely
to keep producing 0 commits per hour.

### §5.1 Next-session pickup: EN-PDF-anchor probe script

Drop this into the next session as a starting point. It hits the
landing pages for the 13 unshipped non-sanctioned offices in
parallel, reports HTTP status + PDF-link count + currency hints,
and flags any office whose page has a fetchable PDF anchor.

```python
import asyncio, httpx, re
from lxml import html as L

OFFICES = {
    "SG/IPOS-patent":   "https://www.ipos.gov.sg/manage-ip/",
    "IT/UIBM":          "https://uibm.mise.gov.it/index.php/it/tasse-e-tariffe",
    "ES/OEPM-patent":   "https://www.oepm.es/es/invenciones/Presentar-una-solicitud/tasas-pagos-y-reintegros/",
    "IL/ILPO":          "https://www.gov.il/en/departments/ilpo",
    "MY/MyIPO":         "https://www.myipo.gov.my/en/patent/",
    "SA/SAIP":          "https://saip.gov.sa/en/",
    "HK/HKIPD":         "https://www.ipd.gov.hk/en/",
    "TR/TurkPatent":    "https://www.turkpatent.gov.tr/en/",
    "ID/DGIP":          "https://www.dgip.go.id/",
    "VN/IPVN":          "https://ipvietnam.gov.vn/",
    "TH/DIP":           "https://www.ipthailand.go.th/",
    "PH/IPOPHL":        "https://www.ipophl.gov.ph/",
    "NZ/IPONZ":         "https://www.iponz.govt.nz/get-ip/patents/fees/",
    "PL/UPRP":          "https://uprp.gov.pl/en",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
    "Accept-Language": "en;q=0.9",
}

async def probe(client, name, url):
    try:
        r = await client.get(url, follow_redirects=True)
        d = L.fromstring(r.text) if r.text else None
        pdfs = []
        if d is not None:
            for a in d.cssselect("a[href]"):
                href = (a.get("href") or "").lower()
                text = (a.text_content() or "").strip().lower()
                if ".pdf" in href or "download-document" in href or "/block/" in href:
                    if any(t in text for t in ["fee", "tarif", "redevance", "tasa", "ücret", "費", "fees"]) or ".pdf" in href:
                        pdfs.append((a.text_content().strip()[:50], a.get("href")))
        # Currency hints
        currencies = sum(c in r.text for c in ["€", "£", "$", "¥", "₺", "₹", "₪", "₱", "₫", "฿", "₩", "Rp", "RM"])
        return f"{name:18s} {r.status_code} bytes={len(r.text):>7} pdf-anchors={len(pdfs):>2} curr-hints={currencies:>3}  →  first PDF: {pdfs[0] if pdfs else '-'}"
    except Exception as e:
        return f"{name:18s} ERROR {type(e).__name__}: {str(e)[:50]}"

async def main():
    async with httpx.AsyncClient(timeout=30.0, headers=HEADERS, http2=True) as c:
        results = await asyncio.gather(*[probe(c, n, u) for n, u in OFFICES.items()])
        for r in results:
            print(r)

asyncio.run(main())
```

Then, for offices with PDF anchors: download, run `pypdf` for a
sample page, and decide between the IPIN/DPMA/INPI-BR PDF pattern
(numeric codes + columns) vs the INPI-FR curated-catalog pattern
(prose with embedded amounts). Most office PDFs are clean column
tables — favour the IPIN pattern when possible.

---

## §6 Session log

* **2026-05-19 (post-research-wave)** — Shipped OEPM Spain
  (`ES/OEPM/Fees/{Patent, Trademark, Design}`) from the consolidated
  TASAS PDF. 156 patent FeeItems / 75 trademark / 67 design covering
  filing, search, examination, EP-validation, SPC annuities (year 1-5
  × no-surcharge/25%/50% recargo bands), procedural common (CM/CI,
  I3/I5), with PYMES + universities tiers folded into
  `EntityTier.small` via a `_catalog_key` Y/U→I normalizer. 64 new
  tests; 86% module coverage (uncovered = HTTP fetch path
  intentionally exercised only via the cached PDF fixture). One
  research-note correction during the build: the per-row `(*)` flag
  is a credit-card-payment marker (page-2 footnote), not an
  SME-eligibility marker — so we don't lift it into provenance.
  Documented v1 GAPS: patent annuities (page 6 multi-column
  IP/2P/5P × IR/2R/5R × YP/Y2/Y5 × UP/U2/U5 table), design renewal
  table (page 13 DT41/D241/D541), PCT international fees (pages 8-9),
  *precios públicos* (pages 16-17). UM route deferred — same codes
  as patent so it's a thin wrapper, not a separate scrape.
* **2026-05-19 (after Brazil ship)** — User pointed at the INPI France
  Tarifs landing page. A deeper inspection (looking past the 11 inline
  ``<li>`` €-items I'd captured earlier) revealed three downloadable
  PDF anchors on the page, one of which — "Tarifs des procédures
  applicables au 27 avril 2026.pdf" at
  `inpi.fr/inpi-block/download-document?id=20516` — is the full
  cross-right schedule. Anonymously accessible, no Cloudflare on the
  download endpoint. Shipped `FR/INPI/Fees/{Patent,Trademark,Design}`
  via a curated-catalog + annuity-walker. Patent annuities years 2-20
  extracted (reduced rates reliably for 2-7 only — pypdf drops second
  column for years 8-20).
* **2026-05-19 (after the gap doc)** — User found the English-language
  INPI Brazil fee PDFs at `gov.br/inpi/en/costs-and-payment/schedule-of-fees-*.pdf`
  (anonymously accessible, no auth). Shipped `BR/INPI/Fees/Patent`
  (272 FeeItems from 60 codes × tier × year-band expansion) and
  `BR/INPI/Fees/Trademark` (34 FeeItems). Worth noting: the official
  research note had been pointing to the auth-gated pt-BR landing
  page; the EN-PDF path on `/inpi/en/costs-and-payment/` is the
  practical working route. v1 GAPS documented for the multi-tier
  per-claim surcharges (prose-formatted in the PDF) and PCT-section
  variable-amount rows.
* **2026-05-19 (post-TIPO)** — Probed 9 offices for the "easy HTML
  batch" plan (BR, SG, FR, ES, IL, MY, SA, HK, TR). Found that the
  subagent's "low complexity" estimate was wrong: only 1 returned a
  plausibly-scrapeable response on first probe (MyIPO patent ACT
  page; not actually the fees page). Spent 30 min on Brazil
  (auth-gated), 20 min on France (Cloudflare), 10 min on Singapore
  (CDN rate-limit). Wrote this doc instead of forcing another
  attempt. Doc superseded by the EN-PDF discovery for Brazil.
