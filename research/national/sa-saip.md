# Saudi Authority for Intellectual Property (SA/SAIP) — national

**Layer:** national
**Jurisdiction:** SA (WIPO ST.3: SA)
**Issuing body:** Saudi Authority for Intellectual Property (الهيئة السعودية للملكية الفكرية), established by Council of Ministers Decision No. 496 (2018)
**Rights administered:** patent, utility model (*model of utility*), industrial design, integrated-circuit layout-design, plant variety, trademark, copyright (administrative registration), geographical indication
**Working languages:** Arabic (primary, authoritative for all gazetted texts); English (institutional pages on `saip.gov.sa/en/`, EN translations of some Implementing Regulations on WIPO Lex)
**Connector status:** **register: skipped until SAIP publishes a supported API or bulk feed**; **fees: manual reference from official service pages**; **statutes: WIPO Lex reference only**
**Last verified:** 2026-08-02
**Manifest entry:** not yet listed in `coverage/sources.yaml`

> **August 2026 correction.** SAIP now publishes an indexed service
> directory, service-specific fee pages, an IP Search landing page,
> gazettes, and open-data links on its main site. The direct IP Search
> application still timed out from US egress during this survey, and
> no documented API or bulk feed was found. The May 2026 reachability
> and fee-source conclusions below are historical probe notes, not the
> current connector decision.

**Higher layers covering this office transitively:**
- **EPO INPADOC / OPS** — Saudi Arabia is recognized in INPADOC; SA patents flow through OPS biblio + family + legal events for filings published in the INPADOC window.
- **WIPO Patentscope** — Saudi Arabia is a [PCT contracting state since 2013-08-03](https://www.wipo.int/pct/en/pct_contracting_states.html); PCT national-phase entries into SA flow through Patentscope and INPADOC.
- **WIPO Hague Express** — Saudi Arabia is a [Hague contracting party since 2020-12-29](https://www.wipo.int/hague/en/members/); Hague IRs designating SA flow through Hague Express.
- **WIPO Madrid Monitor — NOT applicable.** Saudi Arabia is **not yet a Madrid Protocol contracting party** as of 2026-05-19. Trademarks must be filed nationally with SAIP. No higher-layer coverage of SA TMs at the Madrid layer.
- **GCC Patent Office (legacy)** — operated through the GCC Patent Office in Riyadh until [closure of new filings effective 6 January 2021](https://www.wipo.int/wipolex/en/legislation/details/21680). Pre-closure GCC grants extending to SA remain enforceable but no new GCC patent applications are accepted; national filings at SAIP are the only route.

---

## §1 Mission

SAIP is Saudi Arabia's sole national IP office, established
under [Council of Ministers Decision No. 496 (2018)](https://www.saip.gov.sa/en/about-saip/establishment/),
consolidating responsibilities previously distributed across
the General Directorate of Industrial Property at KACST
(patents / IC / PV / designs), the Ministry of Commerce
(trademarks), and the Ministry of Information (copyright).

The Kingdom is a member of WIPO (since 1982), Paris Convention
(2004), TRIPS (2005), PCT (2013), Hague Agreement (2020), and
Nice Agreement (2021), but is **not yet a Madrid Protocol
contracting party** — a structurally important fact for
trademark cost work, because SA TMs must be filed nationally,
not through Madrid.

SAIP's transition to the unified eServices portal at
[`eservices.saip.gov.sa`](https://eservices.saip.gov.sa/) on
**19 December 2023** replaced the legacy per-right portals
(of which `tm.saip.gov.sa` is the only one still operating,
for trademarks filed before that date).

## §2 What's unique here

Data types that live ONLY at SAIP and are not covered by any
higher layer at full fidelity:

- **SA national patents and utility models** — direct
  national filings (not via PCT national-phase or GCC).
- **SA industrial designs** — Locarno-classed national
  designs (some Hague-IR-designating-SA designs flow through
  Hague Express).
- **SA national-only trademarks** — direct national filings;
  Madrid is not available.
- **SA plant variety rights** — sui generis under the same
  Royal Decree M/27 (2004) framework as patents / IC /
  designs.
- **SA copyright administrative registrations** —
  registration is administrative and discretionary, not a
  pre-requisite to protection under Saudi copyright law.

## §3 Programmatic surfaces

### eServices portal — packet-level inaccessible from US egress

| Field | Value |
|---|---|
| Endpoint | [`eservices.saip.gov.sa`](https://eservices.saip.gov.sa/) (unified, since 19 December 2023); [`tm.saip.gov.sa`](https://tm.saip.gov.sa/) (legacy TM, pre-19-Dec-2023 marks only) |
| Auth | SAIP account + Nafath digital identity (Saudi national / iqama-resident gating expected, analogous to Singapore CorpPass / Mexico FIEL) |
| Format | Unknown — pages likely SPA-rendered behind Saudi government CDN |
| Reachable from US? | ❌ — **ConnectTimeout** at the TCP layer from US residential egress (probes 2026-05-19; same result as earlier 2026-05 wave). This is **not** a Cloudflare WAF 403 or a content-blocked page; it is packet-level connection refusal, consistent with whole-AS-or-CIDR filtering of cloud-egress and US-egress IP ranges. |
| Rate limit | unknown |
| ToS posture | no public API ToS; eServices is the operative source for current fee amounts per SAIP's own direction to applicants |
| Rating (zero-infra proxy) | 🔴 **Red** — packet-level geo-block, not a WAF challenge. Same posture as IMPI Mexico register subdomains; mitigations would require Saudi-egress or paid stealth-proxy infrastructure. |

### SAIP main site — saip.gov.sa

| Field | Value |
|---|---|
| Endpoint | [`saip.gov.sa/en/`](https://www.saip.gov.sa/en/) (English) · [`saip.gov.sa/ar/`](https://www.saip.gov.sa/ar/) (Arabic) |
| Reachable from US? | ❌ — same packet-level ConnectTimeout as eServices |
| Rating | 🔴 Red — same block class |

### Umm al-Qura official gazette — uqn.gov.sa

| Field | Value |
|---|---|
| Endpoint | [`uqn.gov.sa/`](https://uqn.gov.sa/) — the Kingdom's official gazette, where Royal Decrees and ministerial decisions implementing IP fee changes are formally published. |
| Reachable from US? | ❌ — ConnectTimeout. The most-citable primary source for a specific fee figure (litigation / opinion work) is therefore unreachable without a Saudi-egress or stealth-proxy detour. |
| Rating | 🔴 Red — same block class |

### WIPO Lex — substantive law + Implementing Regulations (reachable, but stale)

| Field | Value |
|---|---|
| Endpoints | [WIPO Lex SA legislation listing](https://www.wipo.int/wipolex/en/main/profile/SA) and per-document details pages |
| Reachable from US? | ✅ — WIPO Lex is anonymously reachable with valid SSL; signed-URL PDFs on `wipolex-res.wipo.int` have an expiry window |
| Format | HTML detail pages + EN/AR PDF documents |
| Rating | 🟡 Yellow — useful for **statutory structure** but not for current **fee amounts**, because the consolidated text is "as amended up to 2019-05-09" and SAIP Board resolutions after that date (notably the June 2022 publication-fee reductions) are not reflected. |

Key WIPO Lex IDs:
- [Law on Patents, Layout-Designs of Integrated Circuits, Plant Varieties, and Industrial Designs (Royal Decree M/27, 2004) — WIPO Lex 23123](https://www.wipo.int/wipolex/en/legislation/details/23123)
- [Implementing Regulations of the Law (as amended up to Decision of the Board of Directors of SAIP No. 5/8/2019 of 4 Ramadan 1440H — 9 May 2019) — WIPO Lex 19743](https://www.wipo.int/wipolex/en/legislation/details/19743) — **the document the user's notes identify as containing the fee schedule for patents / UM / IC / PV / designs**, but consolidated text stops at the 2019-05-09 Board decision.
- [Executive Regulations of the GCC Patent Law — WIPO Lex 21680](https://www.wipo.int/wipolex/en/legislation/details/21680) — covers the legacy GCC track (closed for new filings 2021-01-06).
- [Regulations on Compulsory Licensing of Patents — WIPO Lex 19762](https://www.wipo.int/wipolex/en/legislation/details/19762)

### Archive.org Wayback — historical SAIP snapshots (limited utility)

| Field | Value |
|---|---|
| Endpoint | [`web.archive.org/web/2026/https://www.saip.gov.sa/en/`](https://web.archive.org/web/2026/https://www.saip.gov.sa/en/) |
| Reachable from US? | ✅ — Wayback is reachable but rate-limits cloud egress |
| Rating | 🟡 Yellow — useful for capturing the SAIP services-catalog page structure at a known point in time, but Wayback is not a primary source and won't carry the live-calculated fee amounts from eServices |

## §4 Fees

**Status (2026-05-19):** **Red for clean FeeItem extraction;
yellow for a service-catalog reference document.** Saudi
Arabia is structurally different from every other office
documented in this wave: SAIP does **not** publish a
standalone gazette annex or downloadable consolidated PDF
analogous to OEPM `TASAS_y_PRECIOS_PUBLICOS.pdf`, INPI France
`download-document?id=20516`, or IMPI Mexico
`Acuerdo.Tarifa.12.05.23.pdf`. Instead:

- **The eServices portal is the operative source.** SAIP
  directs applicants to log in, select the service, and have
  the fee calculated at the point of filing. Each
  combination of (right type, service, applicant entity
  type, claim count, etc.) is computed dynamically against
  the SAIP Board's current resolution.
- **The statutory basis is fragmented** across (a) the
  principal laws, (b) their Implementing Regulations, and
  (c) periodic SAIP Board resolutions adjusting specific
  fees.
- **The official gazette of record is Umm al-Qura**
  ([uqn.gov.sa](https://uqn.gov.sa/)), where Royal Decrees
  and ministerial decisions implementing fee changes are
  formally published.

All three primary-source paths (eServices, SAIP main site,
Umm al-Qura) **ConnectTimeout from US egress** at the TCP
layer. This is not a WAF block or auth gate — packet-level
filtering, consistent with whole-AS / whole-CIDR geo-
filtering of cloud-egress and US-egress IP ranges.

**Publication chain (theoretical — none of the primary
sources are reachable from US egress today):**

1. **Operative live amounts — SAIP eServices portal:**
   - Unified portal (post-19 December 2023): [`eservices.saip.gov.sa/`](https://eservices.saip.gov.sa/) ❌ ConnectTimeout
   - Legacy trademark portal (pre-19-Dec-2023 marks only): [`tm.saip.gov.sa/`](https://tm.saip.gov.sa/) ❌ ConnectTimeout
   - SAIP main site (English navigation, services catalog): [`saip.gov.sa/en/`](https://www.saip.gov.sa/en/) ❌ ConnectTimeout

2. **Statutory and regulatory primary sources:**
   - **Law of Patents, Layout-Designs of Integrated Circuits, Plant Varieties, and Industrial Designs** — Royal Decree No. M/27 dated 29/5/1425H (17 July 2004). Substantive law; fees are set by the Implementing Regulations and SAIP Board resolutions.
   - **Implementing Regulations** — issued by Administrative Decision No. 118828/M/10 dated 14/11/1425H (26 December 2004), as amended up to SAIP Board Decision No. 5/8/2019 of 4 Ramadan 1440H (9 May 2019). The Schedule contains fee structure for patents / UM / IC / PV / designs. [WIPO Lex 19743](https://www.wipo.int/wipolex/en/legislation/details/19743) is reachable but consolidated only through 2019.
   - **GCC Trademark Law** — adopted by Saudi Arabia via Royal Decree No. M/51 dated 26/7/1435H (2014). Implementing Regulations issued by Ministerial Decision. Sets the trademark fee structure.
   - **SAIP Board resolutions** — periodically adjust specific fees. Recent notable example: **June 2022 reduction in trademark publication fees** — filing publication dropped from ~USD 920 to ~USD 155; renewal publication from ~USD 920 to ~USD 310; with similar cuts for assignments / mergers / recordals.

3. **Official gazette of record — Umm al-Qura:**
   - [`uqn.gov.sa/`](https://uqn.gov.sa/) ❌ ConnectTimeout
   - The most citable primary source for a specific fee figure (litigation / opinion work) but unreachable without Saudi egress or paid stealth proxy.

**Scope of the schedule (SAR-denominated, USD-pegged at
~3.75 SAR/USD, so unlike NIS and TRY, currency volatility is
not a concern for cost estimates):**

- **Patents / utility models / integrated-circuit layouts.** Filing, search, examination, grant, annuities, recordation. Implementing Regulations Schedule (consolidated to 2019-05-09 on WIPO Lex) carries the structural list; current amounts on eServices.
- **Industrial designs.** Filing per design, examination, registration, renewal. **2024 amendments extended the protection duration** for industrial designs — worth verifying the current term and renewal cadence at the time of any client work.
- **Plant varieties.** Filing, examination, grant, annuities. Sui generis under the same M/27 framework.
- **Trademarks.** Per-class filing at **SAR 1,000 (~USD 270)**, publication for opposition at **SAR 500**, registration, renewal (10 *Hijri* years from filing — see Hijri vs Gregorian below), recordation. Per-class structure standardized to Nice classification since [Saudi Arabia's accession to the Nice Agreement effective 22 July 2021](https://www.wipo.int/treaties/en/notifications/nice/treaty_nice_226.html).

**Hijri-vs-Gregorian docketing trap.** Trademark registration
is **10 Hijri years** (~9 years 8 months Gregorian) from
filing date, renewable in 10-Hijri-year periods. A standard
Gregorian-based renewal reminder runs ~4 months late. The
connector should emit a `term_calendar = "Hijri"` provenance
on all SA term-of-protection FeeItems so cost-estimator tools
can flag the conversion correctly.

**Discount tiers (no clean primary-source confirmation from
US egress today):**

- Practitioner mirrors suggest individual / SME tracks may
  exist, but the SAIP Implementing Regulations text on WIPO
  Lex (2019-consolidated) does not establish a uniform
  small-entity reduction analogous to USPTO §41(h) or
  Ley 24/2015 art. 186. v1 connector should treat SA fees
  as **single-tier** unless / until primary sources confirm
  otherwise from a reachable channel.

**2024 examination practice amendment — affects total
prosecution cost timeline, not tariff amounts.** SAIP
amended its trademark examination practice in 2024:

- The prior 10-day amendment window on refused applications was eliminated.
- Refused applications now go directly to rejection, followed by a **60-day non-extendable appeal period**.

Not a tariff change, but a docketing impact — cost-estimator
tools should flag the 60-day appeal window in any quoted
TM cost estimate.

**Statutory basis (summary):**

- [Law on Patents, Layout-Designs of Integrated Circuits, Plant Varieties, and Industrial Designs (Royal Decree M/27, 2004) — WIPO Lex 23123](https://www.wipo.int/wipolex/en/legislation/details/23123)
- [Implementing Regulations of the Law (as amended up to 2019-05-09) — WIPO Lex 19743](https://www.wipo.int/wipolex/en/legislation/details/19743) — Schedule = fees for patents / UM / IC / PV / designs
- **GCC Trademark Law** + Implementing Regulations — adopted by SA via Royal Decree M/51 dated 26/7/1435H (2014); ministerial decision for Implementing Regulations; **English text not currently surfaced on WIPO Lex SA listing**; Arabic text in *Umm al-Qura* gazette
- **SAIP Board resolutions** — periodically published in *Umm al-Qura* and indexed on `saip.gov.sa`; most relevant recent: June 2022 reduction of TM publication / recordation fees

**v1 connector plan — three options, ranked by realism:**

### Option A — Service-catalog reference document (recommended)

Ship a **reference document** for SA, not a `FeeItem`-shaped
schedule. The deliverable is a curated markdown / JSON file
mirroring the SAIP service catalog (right type → service →
known fee anchor + source citation), with explicit caveats:

- "Fee calculated at point of filing in eServices portal — confirm against live amount."
- "For litigation / opinion work, pull the current SAIP Board resolution from Umm al-Qura via local KSA counsel."
- "Last anchored from user-provided notes 2026-05-19; trademark filing SAR 1,000/class (~USD 270), TM publication SAR 500, TM renewal publication ~USD 310 (June 2022 Board resolution)."

Manifest entry: `SA/SAIP/Fees` rated **yellow** with the
explicit caveat that it is reference-grade, not connector-
grade. Closest sibling pattern: the substantive-law `StaticLawCorpus` connectors (`dpma_statutes`,
`legifrance_ip`, etc.) but with a custom shape acknowledging
the dynamic nature of the eServices source.

### Option B — Paid stealth proxy + eServices scrape

If a downstream user (e.g., a paying client filing in KSA)
requires connector-grade FeeItems, the path is:

1. Provision a Saudi-egress or paid stealth proxy (Bright
   Data residential, Smartproxy, or equivalent), ~$30-300/mo
   entry tier.
2. Reverse-engineer the eServices SPA's fee-calculation
   endpoint (similar work to the Israel ILPO ecom.gov.il
   case, but with an additional layer of Nafath digital-
   identity gating that may block foreign-developer access
   entirely).
3. Ship a yellow-rated connector with explicit dependence
   on the paid infrastructure.

Tradeoff: adds recurring spend and an external dependency
for a country whose IP filings — while not trivial — are
modest relative to the top 8 offices we already cover.

### Option C — Defer until SAIP publishes a downloadable schedule

SAIP has discussed publishing a consolidated service catalog
in PDF form on the Open Saudi Data initiative; if and when
that lands, the connector becomes a one-PDF `pypdf`
extraction analogous to OEPM Spain. No published primary
source confirms a timeline as of 2026-05-19.

**Recommendation: Option A.** Ship the reference document
as part of the next wave so downstream tools have *something*
for SA cost questions, with clear provenance that it is
reference-grade and that defensible citations require local
KSA counsel and the Umm al-Qura gazette.

## §5 Connector strategy

### What we cover today
Nothing on the SA register side; coverage for SA flows
transitively through:
- **EPO INPADOC** — granted SA patents (biblio + family + legal events).
- **WIPO Patentscope** — PCT national-phase entries (SA acceded 2013-08-03).
- **Hague Express** — Hague IRs designating SA (SA acceded 2020-12-29).
- **Google Patents** — web-crawl coverage of SA patents.

### What we should add (in order of leverage)

1. **`SA/SAIP/Fees` as Option A** — service-catalog reference document; ship in next wave to fill the gap with explicit caveats.
2. **`SA/SAIP/Statute` as a `StaticLawCorpus`** — copy of WIPO Lex Implementing Regulations PDF (sa065en) + Compulsory Licensing Regs (sa066en) + Patents Law (sa115en). Statute-side rating yellow because the WIPO Lex consolidation stops at 2019-05-09 but the statutory text is reasonably stable for substantive-law lookups; the *fee* amounts are the moving part, not the substantive provisions.
3. **Monitor SAIP for an open-data API.** No primary source suggests one is coming, but quarterly check of [`saip.gov.sa/en/news/`](https://www.saip.gov.sa/en/news/) (unreachable) — proxy via Wayback or user reports.

### What we should NOT add

- **eServices SPA scrape from US egress.** Unbuildable without paid stealth infrastructure; reverse-engineering Nafath digital-identity gating may be impossible for foreign-developer accounts regardless.
- **Wrapping a commercial proxy** (e.g., Saba IP, Abu-Ghazaleh, JAH IP fee mirrors) — same anti-pattern as the IMPI / TIPO / OEPM cases: adds a paid intermediary without upstream guarantees.

## §6 Open questions

- **Cloud-egress vs US-residential block scope.** Our probes were from a US residential IP. Whether the SAIP / Umm al-Qura block applies uniformly to all non-Saudi egress, or specifically to US-egress CIDRs, would change the proxy-infrastructure conversation. Confirm from Cloud Run / EU-egress / Asia-egress before committing to paid infrastructure.
- **Nafath digital-identity gating depth.** If Nafath gates the entire eServices portal (not just transactional endpoints), foreign-developer access is structurally infeasible regardless of geo-routing. Confirm by sourcing a Saudi-resident collaborator or local counsel.
- **GCC Trademark Law English text.** Not surfaced on the WIPO Lex SA listing as of 2026-05-19; check WIPO Lex multi-jurisdiction listings and AGCC site (`agcc.com`) for an EN-language copy.
- **SAIP Board resolutions index.** Whether SAIP publishes a stable index of Board resolutions affecting fees, or whether they only land in *Umm al-Qura*. The June 2022 publication-fee reduction is the most-cited example; any official index would dramatically improve the freshness story for Option A.
- **Industrial designs term-of-protection 2024 amendment.** What specifically changed (term length, renewal periods, fees)? WIPO Lex 19743 is pre-2024 and won't reflect it. Cross-reference with PCT eGuide SA (which valid-as-of 2026-02-01 has been refreshed since the 2024 amendment).
- **2025-2026 SAIP Board resolutions affecting fees.** Whether there's been a post-2022 round adjusting other fees beyond TM publication. Defaults to "unknown" without Umm al-Qura access.

## §7 References

Primary sources first; mirrors and analyses only where they cite primary sources.

**SAIP portals (all unreachable from US egress 2026-05-19):**
- [SAIP institutional (English)](https://www.saip.gov.sa/en/) — ConnectTimeout
- [SAIP institutional (Arabic)](https://www.saip.gov.sa/ar/) — ConnectTimeout
- [SAIP eServices portal — unified post-19-Dec-2023](https://eservices.saip.gov.sa/) — ConnectTimeout
- [Legacy SAIP trademark portal — pre-19-Dec-2023 marks](https://tm.saip.gov.sa/) — ConnectTimeout

**Official gazette (unreachable from US egress 2026-05-19):**
- [Umm al-Qura — uqn.gov.sa](https://uqn.gov.sa/) — ConnectTimeout. The most citable primary source for SAIP Board resolutions and Royal Decrees affecting fees.

**WIPO Lex — reachable, primary-source-grade statutes (stale to 2019-05-09):**
- [WIPO Lex SA legislation listing](https://www.wipo.int/wipolex/en/main/profile/SA)
- [Law on Patents, Layout-Designs, Plant Varieties, and Industrial Designs (Royal Decree M/27, 2004) — WIPO Lex 23123](https://www.wipo.int/wipolex/en/legislation/details/23123)
- [Implementing Regulations of the Law (as amended up to 2019-05-09) — WIPO Lex 19743](https://www.wipo.int/wipolex/en/legislation/details/19743)
- [Executive Regulations of the GCC Patent Law — WIPO Lex 21680](https://www.wipo.int/wipolex/en/legislation/details/21680)
- [Regulations on Compulsory Licensing of Patents — WIPO Lex 19762](https://www.wipo.int/wipolex/en/legislation/details/19762)

**WIPO / international framework:**
- [PCT Applicant's Guide SA (valid as of 2026-02-01)](https://pctlegal.wipo.int/eGuide/view-doc.xhtml?doc-code=SA&doc-lang=en)
- [WIPO PCT contracting states](https://www.wipo.int/pct/en/pct_contracting_states.html) (SA since 2013-08-03)
- [WIPO Hague members](https://www.wipo.int/hague/en/members/) (SA since 2020-12-29)
- [WIPO Nice notifications](https://www.wipo.int/treaties/en/notifications/nice/treaty_nice_226.html) (SA accession effective 2021-07-22)

**Background articles (cited for context, not primary):**
- [Saudi Arabia gears up on IP — WIPO Magazine](https://www.wipo.int/web/wipo-magazine/articles/saudi-arabia-gears-up-on-ip-41634)

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-08-02 | Corrected the main-site reachability conclusion. SAIP now exposes public service and fee pages, but its IP Search application remained unreachable from US egress and no supported API or bulk feed was found. Register work is skipped until that changes. | [SAIP IP Search](https://www.saip.gov.sa/en/resources/tools-and-research/ip-search-engine); [SAIP service directory](https://www.saip.gov.sa/en/services/service-directory) |
| 2026-05-19 | Initial synopsis. **Fees rated red for clean FeeItem extraction; yellow for service-catalog reference document.** Architectural difference: unlike OEPM Spain, INPI France, IMPI Mexico, or IPOS Singapore, SAIP does not publish a standalone gazette annex or downloadable consolidated PDF — fees are calculated at the point of filing in the eServices portal, with statutory authority fragmented across the principal laws, their Implementing Regulations, and periodic SAIP Board resolutions formally published in *Umm al-Qura*. Every primary-source path (eServices unified portal `eservices.saip.gov.sa`, legacy TM portal `tm.saip.gov.sa`, SAIP main site `saip.gov.sa`, Umm al-Qura gazette `uqn.gov.sa`) **ConnectTimeout at the TCP layer from US residential egress** — packet-level filtering, not a WAF challenge. WIPO Lex reachable and carries the [Implementing Regulations PDF — WIPO Lex 19743](https://www.wipo.int/wipolex/en/legislation/details/19743) with the fee-schedule Schedule for patents/UM/IC/PV/designs, but consolidated only through SAIP Board Decision No. 5/8/2019 of 9 May 2019 — does not reflect the [June 2022 TM publication-fee reduction](https://www.saip.gov.sa/en/news/) or the 2024 amendments to industrial-designs protection duration. Key facts from user-sourced notes: TM filing SAR 1,000/class (~USD 270), TM publication SAR 500, TM renewal publication ~USD 310 (post-June-2022); SAR pegged to USD at ~3.75 (no currency volatility); TM registration 10 **Hijri** years from filing (~9y 8m Gregorian — docketing trap); 2024 examination amendment eliminated the 10-day refusal-amendment window in favor of outright rejection + 60-day non-extendable appeal. Saudi Arabia is **not yet a Madrid Protocol contracting party** — TMs filed nationally. Recommended v1 deliverable: Option A — service-catalog reference document with explicit "fee calculated at filing time" caveat. Option B (paid stealth proxy + eServices scrape) requires recurring spend and may be blocked by Nafath digital-identity gating regardless. Coverage for SA register flows transitively through EPO INPADOC + Patentscope + Hague Express; no Madrid coverage. | This session; live probes 2026-05-19; user-sourced notes; [WIPO Lex SA](https://www.wipo.int/wipolex/en/main/profile/SA). |
