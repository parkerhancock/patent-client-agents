# IPOS Singapore (SG) — national

**Layer:** national
**Jurisdiction:** SG (WIPO ST.3: SG)
**Issuing body:** Intellectual Property Office of Singapore (IPOS), a statutory board under the Ministry of Law
**Rights administered:** patent, trademark, design, geographical_indication, plant_variety (and copyright is administered by IPOS for policy purposes; registration is not required under SG law)
**Working languages:** English (primary, authoritative for all statutes and manuals)
**Connector status:** **register-side: skipped** (no usable public REST + Oct-2020 patent freeze on the one open API); **fees-side: ready to build** (yellow → green; the prior wave's "SSO stochastic rate-limit + First Schedule URL unknown" finding is superseded — see §4); **statutes-side: planned** (revive the 2026-05 worktree under current `StaticLawCorpus` standards)
**Last verified:** 2026-05-19
**Manifest entry:** not yet listed in `coverage/sources.yaml`

**Detail surveys:**
- [`connectors/ipos_singapore.md`](../connectors/ipos_singapore.md) — 2026-05 detail survey (164 lines; full 14-surface inventory including IP2SG transactional, data.gov.sg, Digital Hub, SSO, IPOS manuals, eLitigation, LawNet, WIPO AMC Singapore, ASPEC)
- [`waves/2026-05-18-priority-2-synopses/sg-ipos.md`](../waves/2026-05-18-priority-2-synopses/sg-ipos.md) — 2026-05-18 grounded re-verification

**Higher layers covering this office transitively:**
- **EPO INPADOC** (via [`regional/epo.md`](../regional/epo.md)) — SG patent biblio + family + legal events for filings published in the INPADOC window. This is the operational substitute for SG patent register data.
- **WIPO PATENTSCOPE** — PCT applications filed at IPOS as a receiving office; PCT applications designating SG as national-phase target. **SG itself is NOT in ASEAN PATENTSCOPE** (no national collection mirrored to WIPO; the seven other ASEAN members are).
- **WIPO Madrid** — international TMs designating SG (SG is a Madrid member); national-only SG TMs remain IPOS-only.
- **WIPO Hague** — international designs designating SG (SG joined Hague 2005-04-17); national-only SG designs remain IPOS-only.

---

## §1 Mission

IPOS is Singapore's single national IP authority — patents, trademarks, registered designs, geographical indications, and plant variety protection, all from one English-language statutory board. It is materially smaller than KIPO or USPTO (SG is a population-5.9M city-state) but punches above weight on **policy infrastructure**: it operates a modern mobile-first filing platform (IPOS Digital Hub since 2 June 2022, plus the IPOS Go app), it administers the Singapore IP Strategy 2030, and it hosts the **WIPO Arbitration and Mediation Center Singapore office** at Maxwell Chambers — a regional ADR node since 2010. For agents, IPOS's authoritative value sits in the SG-national slice that escapes higher-layer coverage: SG-only trademarks, SG-only designs, and the SG substantive-law corpus. The register-side proxy story is materially weaker than the policy-infrastructure story — see [§3](#3-programmatic-surfaces).

## §2 What's unique here
- **SG-national-only trademarks** — Madrid IRs designating SG are visible via WIPO Madrid; pure SG-only TM filings live only in IPOS.
- **SG-national-only registered designs** — Hague IRs designating SG are visible via WIPO Hague; pure SG-only designs (and pre-2005 backfile) live only in IPOS.
- **Singapore-IP statutes corpus** — Patents Act 1994 ([`Act/PA1994`](https://sso.agc.gov.sg/Act/PA1994)), Trade Marks Act 1998 ([`act/tma1998`](https://sso.agc.gov.sg/act/tma1998)), Registered Designs Act 2000 ([`Act/RDA2000`](https://sso.agc.gov.sg/Act/RDA2000)), Copyright Act 2021, Geographical Indications Act 2014, Plant Varieties Protection Act 2004, Layout-Designs of Integrated Circuits Act 1999, and the IPOS Act 2001 ([`Act/IPOSA2001`](https://sso.agc.gov.sg/Act/IPOSA2001)). English-authoritative, version-controlled, free.
- **IPOS Director-General decisions** — TM oppositions and patent oppositions are first-instance administrative decisions issued by IPOS Hearings; not reproduced by any higher layer.
- **English-language Patent Examination Guidelines** (~4.3 MB PDF) and the parallel TM Work Manual / Designs Work Manual / Patents Formalities Manual at the IPOS [Guides](https://www.ipos.gov.sg/about-ip/patents/guides/) tree.
- **Singapore International Commercial Court (SICC)** sits inside the General Division of the High Court and hears cross-border IP disputes — relevant context, but case law is paywall-gated at [LawNet](https://www.lawnet.sg/) (subscription) with [eLitigation](https://www.elitigation.sg/) providing free docket browse.

## §3 Programmatic surfaces

### IP2SG transactional APIs (filings + renewals)

| Field | Value |
|---|---|
| Endpoint | `https://ip2sg.ipos.gov.sg/RPS/WC/API/APITokenRequest.aspx` |
| Auth | Singpass / CorpPass + IP2SG account + manual approval; CorpPass-gated to SG-resident entities |
| Format | JSON / REST (filing operations) |
| Rate limit | Not published |
| ToS posture | Designed for SG-resident filing agents; not contemplated for unaffiliated SaaS redistribution |
| Rating (zero-infra proxy) | 🔴 **Red** — filing-side, identity-gated, no read-side benefit |
| Primary source | [eServices entry](https://www.ipos.gov.sg/eservices/) · [Digital Hub launch circular (2 Jun 2022)](https://www.ipos.gov.sg/news/news-collection/circular--ipos-digital-hub-launch-on-2-june-2022/) |

Hard skip. SG-resident-only identity gating + filing-side scope. No bibliographic read REST is offered at this layer.

### data.gov.sg "IPOS applications API" — collection 281

| Field | Value |
|---|---|
| Endpoint | [`https://data.gov.sg/collections/281/view`](https://data.gov.sg/collections/281/view) — three datasets: [patents](https://data.gov.sg/datasets/d_c49410cc1e293b0a7213a433ab612067/view) / [trademarks](https://data.gov.sg/datasets/d_56058f817dc3708f8b97e0876335ac66/view) / [designs](https://data.gov.sg/datasets/d_63bfb01a27595bedef08da39a344402c/view) |
| Auth | None for read; API key (waitlist) recommended for production |
| Format | JSON envelope `{"items":[...]}` |
| Rate limit | 10-second buckets; 429 on overrun; enforcement live since 31 Dec 2025 |
| ToS posture | [Singapore Open Data Licence](https://data.gov.sg/open-data-licence) — permissive, attribution required |
| Rating (zero-infra proxy) | 🔴 **Red** — patents frozen Aug 2018→Oct 2020; query is lodgement-date-only (no search); biblio-only |
| Primary sources | [API overview](https://guide.data.gov.sg/developer-guide/api-overview) · [Rate limits](https://guide.data.gov.sg/developer-guide/api-overview/api-rate-limits) · [Privacy & terms](https://data.gov.sg/privacy-and-terms) |

The licence and the technical surface are both clean. What kills this as a register substrate is the patent coverage hole (~5 years stale, unchanged since 2026-05) and the query semantics — `?lodgement_date=YYYY-MM-DD` is a daily-walk, not a search. Useful as a *secondary* incremental feed once trademarks/designs freshness is empirically pinned; not a replacement for the authoritative register.

### IPOS Digital Hub — HTML front door (search, journals)

| Field | Value |
|---|---|
| Endpoint | [`https://digitalhub.ipos.gov.sg/FAMN/eservice/IP4SG/MN_BasicSearch`](https://digitalhub.ipos.gov.sg/FAMN/eservice/IP4SG/MN_BasicSearch) (and `MN_AdvancedSearch`, `MN_Journals`, `MN_TmSimilarMarkSearch`, `MN_TmIcgsSearch`) |
| Auth | None for read |
| Format | ASP.NET WebForms HTML (`__VIEWSTATE`) |
| Rate limit | Not published |
| ToS posture | Public read |
| Rating (zero-infra proxy) | 🔴 **Red** — brittle `__VIEWSTATE` scrape; not a proxy substrate |
| Primary source | [IPOS Digital Hub entry](https://www.ipos.gov.sg/eservices/ipos-digital-hub/) · [Digital Hub launch circular](https://www.ipos.gov.sg/news/news-collection/circular--ipos-digital-hub-launch-on-2-june-2022/) |

Replaced the legacy IP2SG UI 2 June 2022. The legacy [`ip2.sg`](https://www.ip2.sg/) host still serves the simple-search forms. Worth noting, not worth wrapping.

### Singapore Statutes Online (SSO)

| Field | Value |
|---|---|
| Endpoint | [`https://sso.agc.gov.sg/`](https://sso.agc.gov.sg/) — slug-addressable acts and subsidiary legislation |
| Auth | None |
| Format | HTML / PDF; no documented bulk export |
| Rate limit | Not published |
| ToS posture | Public read; government work |
| Rating (zero-infra proxy) | 🟢 **Green** — clean static corpus, same pattern as `ipo_in_statutes` / `dpma_statutes` / `legifrance_ip` / `tw_trade_secrets` |
| Primary source | [SSO portal](https://sso.agc.gov.sg/) · [Attorney-General's Chambers SSO page](https://www.agc.gov.sg/our-roles/drafter-of-laws/singapore-statutes-online/) |

Canonical, free, English-authoritative, version-controlled. This is the win.

### IPOS examination + work manuals

| Field | Value |
|---|---|
| Endpoint | [`https://www.ipos.gov.sg/about-ip/patents/guides/`](https://www.ipos.gov.sg/about-ip/patents/guides/) and the parallel TM and Designs trees |
| Auth | None |
| Format | PDF (chaptered); circulars at [Circulars and Practice Directions](https://www.ipos.gov.sg/about-ip/patents/circulars-and-practice-directions/) |
| Rating (zero-infra proxy) | 🟢 **Green** — static PDFs, predictable URLs |
| Primary source | [IPOS Guides](https://www.ipos.gov.sg/about-ip/patents/guides/) |

Same corpus shape as MoPP/MPEP/TMEP, single-fetch ingestion.

## §4 Fees

**Status (2026-05-19):** Ready to build. The earlier wave's
finding ("stochastic CloudFront rate-limit on SSO, First
Schedule lives at a separate sub-URL we haven't pinned") is
superseded — IPOS publishes the per-right schedule as native
HTML on six dedicated forms-and-fees pages plus an aggregate
landing, all reachable on first hit. SSO returns 200 OK with
full content (Patents Rules at 471 KB / 141 tables) — any
earlier CDN-throttle finding was transient. SSO is the
statutory primary source; the IPOS pages are the practical
extraction target.

**Publication chain:**

1. **Primary statutory source — Singapore Statutes Online
   ([sso.agc.gov.sg](https://sso.agc.gov.sg/)):**
   - **Patents Rules — First Schedule "Fees payable"** at
     [`SL/PA1994-R1`](https://sso.agc.gov.sg/SL/PA1994-R1).
     Subsidiary legislation under the Patents Act 1994.
     Current consolidated version reflects 01 Sep 2025
     amendment by [S 538/2025](https://sso.agc.gov.sg/SL/PA1994-R1?ProvIds=Sc1-).
   - **Trade Marks Rules — fee schedule** at
     [`SL/TMA1998-R1`](https://sso.agc.gov.sg/SL/TMA1998-R1).
     Subsidiary legislation under the Trade Marks Act 1998.
   - **Registered Designs Rules — fee schedule** at
     [`SL/RDA2000-R1`](https://sso.agc.gov.sg/SL/RDA2000-R1).
     Subsidiary legislation under the Registered Designs Act
     2000. (The earlier `/SL/266-R1` slug in this file's prior
     revision was outdated.)
   - **Plant Varieties Protection Act / Geographical
     Indications Act / Layout-Designs of Integrated Circuits
     Act** — each has its own subsidiary-legislation slug on
     SSO; v1 can pin Patent / TM / Design and follow up on the
     three sui generis rights later.

2. **IPOS forms-and-fees pages (practical extraction target,
   reachable as native HTML — verified 2026-05-19):**
   - **Patents:** [`ipos.gov.sg/about-ip/patents/forms-and-fees-singapore/`](https://www.ipos.gov.sg/about-ip/patents/forms-and-fees-singapore/) — **note the `-singapore` URL suffix**; the user-known `/about-ip/patents/forms-and-fees/` 404s. 9 tables on the page; the primary fee table is table 1 (102 rows) with shape `Form code | Description | Fee`. Form codes are `PFn` (e.g., PF1 = Request for Grant of a Patent at S$170) with `NA` for non-form items.
   - **Trade marks:** [`ipos.gov.sg/about-ip/trade-marks/forms-and-fees/`](https://www.ipos.gov.sg/about-ip/trade-marks/forms-and-fees/) — 4 tables. Explicit "From 1 April 2026" effective-date markers in the page body.
   - **Designs:** [`ipos.gov.sg/about-ip/designs/forms-and-fees/`](https://www.ipos.gov.sg/about-ip/designs/forms-and-fees/) — 3 tables. **Note the URL is `/designs/`, not `/registered-designs/`** (the user-known `/about-ip/registered-designs/forms-and-fees/` 404s).
   - **Geographical indications:** [`ipos.gov.sg/about-ip/geographical-indications/forms-and-fees/`](https://www.ipos.gov.sg/about-ip/geographical-indications/forms-and-fees/) — 3 tables.
   - **Plant variety rights:** [`ipos.gov.sg/about-ip/plant-variety-rights/forms-and-fees/`](https://www.ipos.gov.sg/about-ip/plant-variety-rights/forms-and-fees/) — 3 tables.
   - **Copyright:** [`ipos.gov.sg/about-ip/copyright/forms-and-fees/`](https://www.ipos.gov.sg/about-ip/copyright/forms-and-fees/) — 4 tables. Copyright is non-registrable in SG; this page covers tribunal / Copyright Tribunal fees.
   - **Aggregate landing:** [`ipos.gov.sg/about-ip/forms-fees/`](https://www.ipos.gov.sg/about-ip/forms-fees/) — note the hyphen-less slug. Links to all six right-type pages and to the 21 July 2025 circulars.

3. **Practice circulars (fee-change announcements)** —
   IPOS hosts these on the same forms-and-fees pages.
   Three were issued together on **21 July 2025** and contain
   side-by-side old/new fee tables in Annex A:
   - **Patents Circular No. 3 of 2025**
   - **Trade Marks Circular No. 3 of 2025**
   - **Designs Circular No. 1 of 2025**

   Circulars list, on a row-by-row basis, every changed fee
   with the old and new amounts side by side. They are the
   single best documentation source for *what changed* on
   1 Sep 2025 and 1 Apr 2026; the SSO Rules are the binding
   primary source for *what the current rate is*.

**Two-phase implementation — 2025-09-01 + 2026-04-01.** Most
of the announced changes took effect on **1 September 2025**;
a second tranche took effect on **1 April 2026**. The two
biggest April-2026 line items are:

- **Patents: examination review report fee → S$3,200.**
- **Trade marks: amendment fee → S$60 per class.**

If a connector serves fee data near either implementation
date, the IPOS HTML page is the source of truth (it shows
the *current effective* rate); the circulars contain both
old and new rates for back-dated fee estimates. The
connector should track both effective dates and surface
"in effect from" provenance on every FeeItem.

**Trademark filing — pre-approved database lever (S$240
vs S$410/class).** A real cost decision for US clients
filing broad specs:

- **S$240/class** if the applicant adopts the IPOS
  pre-approved goods and services classification database
  in full (no custom specification text).
- **S$410/class** (up from S$380 pre-1-Sep-2025) for
  custom specifications.

The connector should emit both as distinct FeeItems with
a `specification_type = "pre-approved"` / `"custom"`
provenance tag. This is a material cost lever — for a
broad US filing covering, say, 15 classes, the difference
is S$240×15 = S$3,600 vs S$410×15 = S$6,150.

**Patent excess claims — steeper as of 1 Sep 2025.**
Threshold dropped from 20 claims to **15**, and the
per-claim fee doubled from S$40 to **S$80** for
examination requests filed on or after 1 September 2025.
For portfolio-management workflows the implication is:
voluntary amendment before exam request can save real
money on claim-heavy applications. The connector should
emit excess-claims as a per-claim FeeItem with a clear
threshold note so cost-estimator tools can compute
correctly.

**Madrid Protocol designation fees are separate.** For
international registrations designating Singapore, the
relevant amounts as of **1 September 2025**:

- **Application / transformation:** S$380 → S$410 per class
- **Renewal:** S$440 → S$480 per class

These are paid to IPOS as the designated office (not to
WIPO) and are surfaced via the SG Individual Fee notification
on the WIPO Madrid system page. The connector should emit
these as separate `MadridDesignation` FeeItems with the
`route = "Madrid IR designating SG"` provenance tag.

**Scope of the schedule (SGD-denominated, per-form structure):**

- **Patents** — filing (PF1 = S$170), search, examination,
  excess claims fee (per claim over 15 = S$80 for exam
  requests on/after 2025-09-01), grant, annuities (years 4
  through 20), restoration, recordation, opposition,
  amendment, certification.
- **Trade marks** — filing per class (S$240 pre-approved DB
  / S$410 custom), opposition, registration of changes,
  renewal (10-year), goods-and-services amendment (S$60/class
  from 2026-04-01), recordation.
- **Registered designs** — filing per design, registration,
  extension (each 5-year extension up to maximum 15 years
  for newer registrations or 25 for older), recordation.
- **Geographical indications** — application, opposition,
  recordation.
- **Plant variety rights** — application, examination,
  grant, annuities.

**Discount tiers (mapped to `EntityTier`):**

- **No size-based small-entity rate.** The Singapore
  schedule does not encode a US-style large/small/micro
  tier.
- **The trademark pre-approved-DB rate** is not a tier in
  the legal sense — every applicant is eligible if they
  accept the canonical specifications. Treat it as a
  `specification_type` provenance, not as an
  `EntityTier`.
- **IPOS programme-level subsidies** (SG IP Fast / ASPEC /
  PPH) reduce *time*, not tariff amounts. Not represented
  as FeeItem discounts.

**Statutory basis:**

- [Patents Act 1994 — SSO PA1994](https://sso.agc.gov.sg/Act/PA1994)
- [Patents Rules (Cap. PA1994-R1) — First Schedule = Fees payable](https://sso.agc.gov.sg/SL/PA1994-R1)
- [Trade Marks Act 1998 — SSO TMA1998](https://sso.agc.gov.sg/Act/TMA1998)
- [Trade Marks Rules — SSO TMA1998-R1](https://sso.agc.gov.sg/SL/TMA1998-R1)
- [Registered Designs Act 2000 — SSO RDA2000](https://sso.agc.gov.sg/Act/RDA2000)
- [Registered Designs Rules — SSO RDA2000-R1](https://sso.agc.gov.sg/SL/RDA2000-R1)
- [IPOS Circulars and Practice Directions hub](https://www.ipos.gov.sg/about-ip/patents/circulars-and-practice-directions/) — index of all gazetted fee changes including the 21-Jul-2025 circulars

**v1 connector plan — `SG/IPOS/Fees/{Patent, Trademark, Design, GeographicalIndication, PlantVariety}`:**

- **Source:** the six IPOS HTML pages (the five right-type
  pages plus the aggregate landing for cross-reference).
- **Parser pattern:** `lxml` per-page table walk, similar
  to HK/IPD and CIPO Canada. The main fee table is
  consistently at table index 1 on each right-type page,
  with shape `Form | Description | Fee` (or just
  `Description | Fee` where forms don't apply).
- **Currency:** SGD.
- **Provenance metadata:** every FeeItem gets
  `in_effect_from` (mostly 2025-09-01 or 2026-04-01),
  `statutory_basis` (the relevant SSO slug), and
  `circular_announcement` (the 21-Jul-2025 circular for
  the current cycle).
- **Freshness probe:** quarterly hash check of the six
  IPOS pages + a SSO Rules-history poll for new
  S-numbered amendments since the recorded version.
- **Spec-type handling for TM:** emit
  `specification_type = "pre-approved"` (S$240/class) and
  `"custom"` (S$410/class) as separate FeeItems on the
  filing row.
- **Madrid SG-designation handling:** emit as separate
  FeeItems with `route = "Madrid IR designating SG"` to
  distinguish from direct-filing TM fees.
- **SSL note:** Both `ipos.gov.sg` (isomer-hosted on by.gov.sg
  CDN) and `sso.agc.gov.sg` present valid certs; no
  `verify=False` required.

**SSO "stochastic rate-limit" claim — superseded.** The
prior wave reported intermittent CloudFront 403s on SSO.
The 2026-05-19 probe returned 200 OK on first hit for all
three Rules slugs with full content (471 KB / 141 tables
on Patents Rules). If a rate-limit reappears under load,
respectful caching (TTL ≥ 7 days from one hit) and exponential
backoff should keep us within the envelope.

Notable IPOS acceleration programmes *(named only — these are
prosecution-time levers, not tariff discounts)*:

- **SG IP Fast (formerly SG Patent Fast Track)** — accelerated examination programme.
- **Patent Prosecution Highway (PPH)** — bilateral acceleration; fee posture per [IPOS PPH page](https://www.ipos.gov.sg/about-ip/patents/how-to-register-overview/acceleration-programmes/patent-prosecution-highway/).
- **ASPEC and ASPEC+** — ASEAN Patent Examination Cooperation. ASPEC has no public API; SG is not in ASEAN Patentscope national collections.

## §5 Connector strategy

### What we cover today

Nothing — SG is not in `coverage/sources.yaml` as of 2026-05-18. The earlier "IPOS Singapore statutes + manuals" worktree from the 2026-05 fan-out was never integrated and pre-dates the [connector-standards sweep](../../CONNECTOR_STANDARDS.md). SG patent biblio + family is currently accessed transitively via [`patent_client_agents.epo_ops`](../regional/epo.md).

### What we should add

**Revive the 2026-05 statutes worktree under current standards** — primary recommendation.

- **Module name candidate:** `sg_statutes` (mirroring `ipo_in_statutes`, `dpma_statutes`, `legifrance_ip`, `tw_trade_secrets`).
- **Scope:** Patents Act 1994, Patents Rules, Trade Marks Act 1998 and Rules, Registered Designs Act 2000 and Rules, Copyright Act 2021, Geographical Indications Act 2014, Plant Varieties Protection Act 2004, Layout-Designs of Integrated Circuits Act 1999, IPOS Act 2001, and the IP (Dispute Resolution) Act 2019. Each fetched once from its SSO slug URL.
- **Optional extension `sg_manuals`:** IPOS Patent Examination Guidelines, Patents Formalities Manual, TM Work Manual, Designs Work Manual, and the running Circulars and Practice Directions PDFs.
- **Why revive rather than close:** the substantive-law layer is the only **green** SG surface, the primary sources are stable since the worktree was first cut, and the static-corpus pattern is well-trodden (four sibling corpora already shipped). Closing it means we lose SG agent capability for filings, prosecution arguments, and SICC dispute work for no engineering saving.
- **Cross-reference:** queue in [`BACKLOG.md`](../BACKLOG.md) once the worktree revival lands; coverage/sources.yaml entry as `SG/AGC/IP` (or `SG/IPOS/Statutes` per the manifest naming convention used by `FR/Legifrance/IP`).

### What we should NOT add

- **Register-side hosted proxy at any layer.** No usable REST exists: IP2SG is SG-resident-identity-gated; data.gov.sg collection 281 is biblio-only with a 5-year-stale patent endpoint and lodgement-date-only query semantics; Digital Hub is ASP.NET `__VIEWSTATE` scrape. INPADOC, Madrid, and Hague cover the cross-border slice transitively; the SG-only slice is a real but narrow gap that does not justify a brittle scrape.
- **CorpPass-gated transactional APIs.** SG-resident identity gating; contract scope is filing agents, not unaffiliated proxies.
- **Digital Hub HTML scrape.** `__VIEWSTATE` WebForms; brittle and redundant.
- **LawNet** — paywall (subscription); not a viable substrate.
- **IPOS Go mobile** — filing front-end, not data.
- **WIPO AMC Singapore office** — operational ADR node; UDRP decisions are already in the global WIPO feed.
- **ASPEC / ASEAN PATENTSCOPE for SG** — ASPEC has no public API; SG is not in ASEAN PATENTSCOPE national collections.

### Next steps

1. **Cut a revival PR** for the 2026-05 statutes worktree under the current `StaticLawCorpus` shape — copy from `tw_trade_secrets` as the smallest sibling exemplar, then walk through `dpma_statutes` for the multi-act case.
2. **Empirically verify TM and design freshness** on data.gov.sg collection 281 before any future user-facing claim — the older survey's "TM current to May 2025" claim needs a 2026-05 re-pull.
3. **Monitor for an IPOS read REST.** No primary source suggests one is coming, but watch [news releases](https://www.ipos.gov.sg/news/) and the [Digital Hub eService catalogue](https://www.ipos.gov.sg/eservices/ipos-digital-hub/).
4. **Defer judgment on a thin data.gov.sg wrapper.** Quality is licence-clean but utility is low without a real search interface; revisit only if a downstream agent asks for SG TM daily-incremental.

## §6 Open questions

- **TM and design freshness on data.gov.sg collection 281** — primary-source confirmation that the [TM endpoint](https://data.gov.sg/datasets/d_56058f817dc3708f8b97e0876335ac66/view) and the [Design endpoint](https://data.gov.sg/datasets/d_63bfb01a27595bedef08da39a344402c/view) are current to ≥ 2026-04 has not been pinned in this wave. Action: pull a `lodgement_date=2026-04-01` sample.
- **Patent API freshness recovery** — is the Aug-2018→Oct-2020 freeze permanent or pending republish? No primary-source statement either way; email `data-feedback@tech.gov.sg`.
- **API-key tier numerics on data.gov.sg** — [Rate Limits page](https://guide.data.gov.sg/developer-guide/api-overview/api-rate-limits) describes the tiers but doesn't publish the per-tier numbers without registering.
- **Foreign-developer access to IP2SG transactional APIs** — Singpass/CorpPass appears mandatory; no documented foreign route. Confirm via [`ipos_enquiry@ipos.gov.sg`](https://www.ipos.gov.sg/) only if a paying customer asks.
- **SSO bulk export / Akoma Ntoso** — no documented path on [SSO](https://sso.agc.gov.sg/). Ask AGC Legislation Division for an XML dump of IP acts.
- **IPOS journals storage budget** — weekly PDFs since 2022. Per-PDF size estimate needed before deciding `extract-and-discard` vs. full mirror.

## §7 References

Primary sources only — IPOS, AGC SSO, data.gov.sg, WIPO.

**IPOS portals + service docs:**
- [Home — IPOS](https://www.ipos.gov.sg/)
- [eServices — IPOS](https://www.ipos.gov.sg/eservices/)
- [IPOS Digital Hub entry](https://www.ipos.gov.sg/eservices/ipos-digital-hub/)
- [Circular: IPOS Digital Hub Launch on 2 June 2022](https://www.ipos.gov.sg/news/news-collection/circular--ipos-digital-hub-launch-on-2-june-2022/)
- [For IP Professionals — IPOS](https://www.ipos.gov.sg/manage-ip/resources/for-ip-professionals/)
- [Patents Guides (Examination Guidelines, Formalities Manual, etc.)](https://www.ipos.gov.sg/about-ip/patents/guides/)
- [Circulars and Practice Directions — IPOS](https://www.ipos.gov.sg/about-ip/patents/circulars-and-practice-directions/)
- [IP Legislation — IPOS](https://www.ipos.gov.sg/global-ip-hub/statistics-and-legislation-developments/ip-legislation/)
- [IPOS Go Mobile App](https://www.ipos.gov.sg/eservices/ipos-go-mobile/)

**IPOS Digital Hub (HTML front-door):**
- [Basic Search](https://digitalhub.ipos.gov.sg/FAMN/eservice/IP4SG/MN_BasicSearch) · [Advanced Search](https://digitalhub.ipos.gov.sg/FAMN/eservice/IP4SG/MN_AdvancedSearch)
- [Journals](https://digitalhub.ipos.gov.sg/FAMN/eservice/IP4SG/MN_Journals) · [TM Similar Mark Search](https://digitalhub.ipos.gov.sg/FAMN/eservice/IP4SG/MN_TmSimilarMarkSearch) · [TM Goods & Services Search](https://digitalhub.ipos.gov.sg/FAMN/eservice/IP4SG/MN_TmIcgsSearch)
- [Legacy `ip2.sg` host](https://www.ip2.sg/)

**data.gov.sg (IPOS open-data):**
- [IPOS applications API — collection 281](https://data.gov.sg/collections/281/view)
- [Patent applications dataset](https://data.gov.sg/datasets/d_c49410cc1e293b0a7213a433ab612067/view) · [Trademark applications dataset](https://data.gov.sg/datasets/d_56058f817dc3708f8b97e0876335ac66/view) · [Design applications dataset](https://data.gov.sg/datasets/d_63bfb01a27595bedef08da39a344402c/view)
- [API overview](https://guide.data.gov.sg/developer-guide/api-overview) · [Rate limits](https://guide.data.gov.sg/developer-guide/api-overview/api-rate-limits)
- [Singapore Open Data Licence](https://data.gov.sg/open-data-licence) · [Privacy and terms](https://data.gov.sg/privacy-and-terms)

**Singapore Statutes Online (substantive law):**
- [SSO home](https://sso.agc.gov.sg/) · [AGC SSO page](https://www.agc.gov.sg/our-roles/drafter-of-laws/singapore-statutes-online/)
- [Patents Act 1994](https://sso.agc.gov.sg/Act/PA1994) · [Patents Rules](https://sso.agc.gov.sg/SL/PA1994-R1)
- [Trade Marks Act 1998](https://sso.agc.gov.sg/act/tma1998)
- [Registered Designs Act 2000](https://sso.agc.gov.sg/Act/RDA2000) · [Registered Designs Rules](https://sso.agc.gov.sg/SL/266-R1)
- [IPOS Act 2001](https://sso.agc.gov.sg/Act/IPOSA2001)
- [IP (Dispute Resolution) Act 2019](https://sso.agc.gov.sg/Acts-Supp/23-2019)

**Detail survey + wave:**
- [`connectors/ipos_singapore.md`](../connectors/ipos_singapore.md) — 2026-05 detail survey
- [`waves/2026-05-18-priority-2-synopses/sg-ipos.md`](../waves/2026-05-18-priority-2-synopses/sg-ipos.md) — 2026-05-18 grounded re-verification

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-19 | **Fees re-rated yellow → ready to build.** Prior wave's "SSO stochastic CloudFront rate-limit + First Schedule URL unpinned" finding is superseded — the 2026-05-19 probe returned 200 OK on first hit for all three Rules slugs ([Patents Rules](https://sso.agc.gov.sg/SL/PA1994-R1) 471 KB / 141 tables; [Trade Marks Rules](https://sso.agc.gov.sg/SL/TMA1998-R1) 134 tables; [Registered Designs Rules](https://sso.agc.gov.sg/SL/RDA2000-R1) 116 tables; First Schedule "Fees payable" confirmed on the Patents Rules page). The IPOS forms-and-fees pages are reachable on six dedicated URLs — **but with URL-pattern surprises:** patents is at `/about-ip/patents/forms-and-fees-singapore/` (the user-known `/about-ip/patents/forms-and-fees/` 404s) and designs is at `/about-ip/designs/forms-and-fees/` (the user-known `/about-ip/registered-designs/forms-and-fees/` 404s). Two-phase fee implementation: most changes 1 Sep 2025 (S 538/2025), second tranche 1 Apr 2026 (patent examination review report fee → S$3,200, TM amendment fee → S$60/class). Trademark filing has a per-applicant cost lever: S$240/class if the IPOS pre-approved goods-and-services database is adopted in full vs S$410/class for custom specs. Patent excess-claims threshold dropped from 20 to 15 with per-claim fee doubling from S$40 to S$80 for exam requests on/after 2025-09-01. Madrid SG-designation fees are separate (S$380→S$410 application, S$440→S$480 renewal). Three [IPOS circulars](https://www.ipos.gov.sg/about-ip/patents/circulars-and-practice-directions/) dated 21 July 2025 (Patents #3, TM #3, Designs #1) have Annex A side-by-side fee tables for back-dated estimate work. Connector plan: `SG/IPOS/Fees/{Patent,Trademark,Design,GeographicalIndication,PlantVariety}` — five routes from six HTML pages, `lxml` multi-table pattern (table index 1 per page, 3-col `Form | Description | Fee` shape; 102 rows on the patent table). Register-side rating unchanged (🔴 red). | This session; live probes 2026-05-19; user-sourced 2025-2026 implementation timeline. |
| 2026-05-18 | Initial synopsis. Register-side **🔴 red** — no usable read REST: IP2SG transactional is Singpass/CorpPass-gated to SG residents; data.gov.sg collection 281 is biblio-only with patents frozen Aug 2018 → Oct 2020 and lodgement-date-only query semantics; Digital Hub is ASP.NET `__VIEWSTATE` HTML. Statutes-side **🟢 green** — SSO + IPOS PDF tree are clean static-corpus material; recommend reviving the 2026-05 `sg_statutes`/`sg_manuals` worktree under current `StaticLawCorpus` standards (same shape as `ipo_in_statutes`, `dpma_statutes`, `legifrance_ip`, `tw_trade_secrets`). Drift from older detail survey: the data.gov.sg **design endpoint `d_63bfb01a27595bedef08da39a344402c` is in fact published** (older survey marked it as placeholder). | [waves/2026-05-18-priority-2-synopses/sg-ipos.md](../waves/2026-05-18-priority-2-synopses/sg-ipos.md) · [data.gov.sg collection 281](https://data.gov.sg/collections/281/view) · [SSO](https://sso.agc.gov.sg/) |
