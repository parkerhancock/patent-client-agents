# Intellectual Property Department (HK/IPD) — national

**Layer:** national
**Jurisdiction:** HK (WIPO ST.3: HK) — Hong Kong Special Administrative Region of the People's Republic of China
**Issuing body:** Intellectual Property Department (IPD), Government of the Hong Kong Special Administrative Region
**Rights administered:** standard patent (original-grant route, "OGP"), standard patent (re-registration route from a designated patent in CN / GB / EP(UK)), short-term patent (8-year), trademark, registered design, copyright (administrative registration limited; no register), plant variety (separate agency), geographical indication (TM-based protection)
**Working languages:** English and Traditional Chinese (both official under the Basic Law); IPD pages are bilingual mirrors
**Connector status:** **fees: ready to build (green — IPD pages reachable, full schedule rendered as native HTML tables); register: not yet surveyed**
**Last verified:** 2026-05-19
**Manifest entry:** not yet listed (fees scheduled for next build wave)

**Higher layers covering this office transitively:**
- **EPO INPADOC / OPS** — HK is a [recognized patent office in INPADOC](https://www.epo.org/en/searching-for-patents/data/coverage); HK patents (granted via either route) flow through OPS biblio + family + legal events.
- **WIPO Patentscope** — Hong Kong is not a PCT contracting state; coverage for PCT entries into HK flows through the re-registration route via CN (PCT designations into China that are extended to HK) or GB / EP(UK) (PCT entries into those offices that are then re-registered in HK). Direct PCT-HK national-phase is not available.
- **WIPO Madrid Monitor** — HK is part of the Madrid Protocol via [PRC's territorial extension](https://www.wipo.int/treaties/en/notifications/madridp-gp/treaty_madridp_gp_180.html); Madrid IRs designating "CN-HK" flow through Madrid Monitor as a CN-territory designation, not as a standalone HK designation.
- **WIPO Hague Express** — HK is part of the Hague System via [PRC's accession effective 2022-05-05](https://www.wipo.int/hague/en/members/) extended to HK; Hague IRs designating CN cover HK by territorial application.

---

## §1 Mission

The Intellectual Property Department is the sole authority for
registration and administration of industrial property rights in
the Hong Kong SAR. It operates under the Commerce and Economic
Development Bureau and is the registrar for **standard patents**
(via two distinct routes), **short-term patents**, **trade marks**,
and **registered designs**. Substantive law is contained in
**three principal ordinances** with their respective subsidiary
rules:

- **Patents Ordinance (Cap. 514)** + **Patents (General) Rules (Cap. 514C)**
- **Trade Marks Ordinance (Cap. 559)** + **Trade Marks Rules (Cap. 559A)**
- **Registered Designs Ordinance (Cap. 522)** + **Registered Designs Rules (Cap. 522A)**

All four are accessible via [Hong Kong e-Legislation](https://www.elegislation.gov.hk/),
the bilingual statutory database maintained by the Department of
Justice.

The dual-route patent system is the structural feature most
relevant to fee work: since **December 2019** the OGP (original-
grant route) has run in parallel with the older re-registration
route. Foreign filers who already hold a designated patent in
CN, GB, or EP(UK) typically choose re-registration; HK-only
filers and those without a foreign anchor patent use the OGP
route. The two routes have **substantially different fee
schedules** — see §4 for the structural details.

## §2 What's unique here

Data types that live ONLY at IPD and are not covered transitively
through CN at full fidelity:

- **HK standard patents (original-grant route, OGP)** — direct
  HK national filings, available since December 2019 under the
  Patents (Amendment) Ordinance 2016. INPADOC has these but
  legal-events fidelity is thinner than for CN/EPO-anchored
  patents.
- **HK short-term patents** — sui generis 8-year term, granted
  on formality examination only, without substantive examination.
  Useful for fast-moving or short-lived inventions; statutorily
  separate from standard patents.
- **HK standard patents (re-registration route)** — derived
  from designated CN / GB / EP(UK) patents but maintained under
  HK law; the post-registration prosecution events (annuity
  payments, surrender, restoration) are HK-only.
- **HK national-only trade marks** — direct filings (not via
  Madrid). Madrid designations targeting HK are encoded as
  CN-territory designations through PRC's Madrid extension,
  not as standalone HK marks.
- **HK national-only registered designs** — Locarno-classed
  national designs under Cap. 522, separate from Hague IRs
  designating CN-extended-to-HK.

## §3 Programmatic surfaces — to be surveyed

Status: deferred. Fees connector takes priority. A follow-up
survey should cover:

- IPD's "**Online Search System**" — public register search for
  patents, TMs, and designs; surface (HTML, JSON BFF, or both)
  to be characterized.
- "**Patent (Amendment) Ordinance 2016 Implementation**"
  bibliographic data feed if any.
- e-Legislation as a substantive-law citation source
  (XML/JSON not exposed; HTML is fully JS-rendered).
- Bulk gazette feeds (Hong Kong Government Gazette) for IP
  matters.

## §4 Fees

**Status (2026-05-19):** Ready to build. The fee schedules are
published on three IPD pages as **native HTML tables** with
clean column structure, fully rendered server-side. The
statutory primary source (Cap. 514C Schedule 4, Cap. 559A
Schedule 1, Cap. 522A schedule) is on e-Legislation but is JS-
rendered and not directly extractable without dev-browser — it
serves as the formal citation target, not the extraction
target.

**Publication chain:**

1. **Primary statutory source — Hong Kong e-Legislation
   (https://www.elegislation.gov.hk):**
   - **Patents (General) Rules (Cap. 514C), Schedule 4** —
     [`elegislation.gov.hk/hk/cap514C`](https://www.elegislation.gov.hk/hk/cap514C). Promulgated under Patents Ordinance Cap. 514.
   - **Trade Marks Rules (Cap. 559A), Schedule 1** —
     [`elegislation.gov.hk/hk/cap559A`](https://www.elegislation.gov.hk/hk/cap559A). Promulgated under Trade Marks Ordinance Cap. 559.
   - **Registered Designs Rules (Cap. 522A)** —
     [`elegislation.gov.hk/hk/cap522A`](https://www.elegislation.gov.hk/hk/cap522A). Promulgated under Registered Designs Ordinance Cap. 522.

   Each is the legally binding text; amendments are made by
   subsidiary-legislation orders gazetted in the Hong Kong
   Government Gazette. e-Legislation pages are SPA-rendered
   (server returns a 7.5 KB JS shell that resolves the
   ordinance text via authenticated JSP backends) — not
   directly fetchable as HTML without a JS-capable client.

2. **IPD forms-and-fees pages (practical extraction target,
   reachable as native HTML):**
   - **Patents:** [`ipd.gov.hk/en/patents/forms-and-fees/index.html`](https://www.ipd.gov.hk/en/patents/forms-and-fees/index.html) — 32 tables observed 2026-05-19. Two-column shape (`Descriptions | Fee (HKD)`) with sub-row e-filing / paper-filing splits where applicable; route is encoded inline in the description (e.g., `"Request for grant of a standard patent (O)"` for OGP route, `(R)` for re-registration). Short-term-patent rows are tagged inline.
   - **Trade Marks:** [`ipd.gov.hk/en/trade-marks/forms-and-fees/index.html`](https://www.ipd.gov.hk/en/trade-marks/forms-and-fees/index.html) — 17 tables observed.
   - **Registered Designs:** [`ipd.gov.hk/en/designs/forms-and-fees/index.html`](https://www.ipd.gov.hk/en/designs/forms-and-fees/index.html) — 12 tables observed. **URL note:** the IPD designs section lives at `/en/designs/`, not `/en/registered-designs/` (the latter 404s). All other IPD sections use the long form; designs is the singleton exception.

3. **Bilingual mirrors:** the Chinese-language versions live
   at `/tc/...` (Traditional Chinese) on the same paths.
   English is the most stable parser target.

**Earlier "URL drift / unknown" finding superseded.** The
2026-05-19 probe found all three pages reachable from US
egress with no auth, no CDN challenge, and clean table
markup. The URL for designs was simply different from the
guess.

**Scope of the schedule (HKD-denominated):**

- **Standard patents — OGP route (`(O)` rows).** Filing
  request for grant, advertisement, late-payment surcharge,
  request for substantive examination (~HK$4,000), grant fee
  (~HK$4,413), annuity (3rd through 20th year), recordation,
  amendment, divisional, restoration.
- **Standard patents — re-registration route (`(R)` rows).**
  Request to record (designated patent application from CN /
  GB / EP(UK)), advertisement, request for registration and
  grant (~HK$686 — substantially lower than the OGP grant
  fee because most prosecution has already been done by the
  designated office), annuity, recordation.
- **Short-term patents.** Filing, search report by designated
  searching authority, grant, renewal (4th year and 8th
  year — short-term patents have a maximum 8-year term),
  recordation. Separate fee track from standard patents.
- **Trade marks.** Application per class (Form T2,
  HK$2,000 for the first class with reduced additional-class
  fees), divisional application, opposition, observation,
  cancellation / revocation / invalidation, registrar's
  decision review, renewal (10-year term, renewable
  indefinitely), recordation.
- **Registered designs.** Application by design / by set /
  multiple-design applications (1, 2, or more designs for
  articles in the same class), with e-filing vs paper-filing
  splits. Renewal (5-year terms, renewable up to 25 years).
  Recordation.

**Column model:**

The IPD fee tables use a `Descriptions | Fee (HKD)` shape,
with **inline route tagging** in the description column:
- `(O)` → original-grant route for standard patents
- `(R)` → re-registration route for standard patents
- *(no tag)* on patent rows → short-term patent or general

Where electronic filing is discounted relative to paper, a
sub-table breaks the fee column into `E-filing | Paper-filing`
(e.g., the request-for-grant row: HK$345 e-filing vs HK$480
paper). The connector should preserve both columns as
separate FeeItems with `filing_channel = "electronic"` /
`"paper"` provenance.

**Patent-route fee divergence — practical impact for client work.**
The same legal step has very different fees on the two
patent routes. From the IPD patent page (current):
- Grant of a standard patent (OGP, `(O)`): **HK$4,413**
- Registration and grant of a standard patent (`(R)`): **HK$686**

The connector must emit both as distinct FeeItems with route
tags; client-facing summary tools should ask which route is
in scope before quoting.

**Discount tiers (mapped to `EntityTier`):**

- No US-style small-entity reduction. HK schedules do not
  encode size-based tiers.
- The OGP route's substantive-examination fee (~HK$4,000)
  is itself effectively the size-neutral examination cost.
- Reduced rates appear at the form level via the e-filing /
  paper-filing split — encoded as `filing_channel`
  provenance, not as a `tier`.

**Annual revision cadence.** Amendments are made by
gazetted subsidiary-legislation orders. There is no fixed
annual republication cadence; updates are sporadic and
typically tied to legislative reform packages (the most
recent being the 2019 Patents (Amendment) Ordinance
implementation). Freshness window can be quarterly.

**Statutory basis:**

- [Patents Ordinance (Cap. 514) — e-Legislation](https://www.elegislation.gov.hk/hk/cap514)
- [Patents (General) Rules (Cap. 514C) — e-Legislation](https://www.elegislation.gov.hk/hk/cap514C) (Schedule 4 contains the fee table)
- [Trade Marks Ordinance (Cap. 559) — e-Legislation](https://www.elegislation.gov.hk/hk/cap559)
- [Trade Marks Rules (Cap. 559A) — e-Legislation](https://www.elegislation.gov.hk/hk/cap559A) (Schedule 1 contains the fee table)
- [Registered Designs Ordinance (Cap. 522) — e-Legislation](https://www.elegislation.gov.hk/hk/cap522)
- [Registered Designs Rules (Cap. 522A) — e-Legislation](https://www.elegislation.gov.hk/hk/cap522A)

**v1 connector plan — `HK/IPD/Fees/{Patent, ShortTermPatent, Trademark, Design}`:**

- **Source:** the three IPD HTML pages.
- **Parser pattern:** `lxml` multi-table HTML — same shape as
  CIPO Canada and IP Australia. Per-page table walk, with
  inline `(O)` / `(R)` regex tagging on description, and
  e-filing / paper-filing sub-table flattening.
- **Currency:** HKD.
- **Provenance metadata:** `version_as_of = "live"` (no
  fixed publication date on the IPD pages; cite Cap. 514C /
  Cap. 559A / Cap. 522A as the statutory authority and
  record the fetch date as the version pin).
- **Freshness probe:** quarterly hash check of the three
  IPD pages; on detected change, diff the fee values and
  surface in the change log.
- **Route handling:** emit `route = "OGP"` /
  `"re-registration"` / `"short-term"` as a FeeItem tag for
  patent rows; emit `filing_channel = "electronic"` /
  `"paper"` where the sub-table split applies.
- **SSL note:** Both `ipd.gov.hk` and `elegislation.gov.hk`
  present valid certs; no `verify=False` required.

## §5 Connector strategy

### Fees connector (this wave)

Ship `HK/IPD/Fees/{Patent, ShortTermPatent, Trademark, Design}`
per §4 — four routes from three HTML pages. The IPD HTML
route is the practical scraping target; the e-Legislation
Cap. links are the citation source. Patent route tags
(`(O)` / `(R)`) and filing-channel splits (e-filing /
paper) are first-class FeeItem dimensions.

### Register connector (deferred)

Survey pending. Open questions for the survey:

- Does IPD publish a documented REST/JSON API for patent /
  TM / design search?
- Is the Online Search System guest-accessible or
  account-gated?
- Is there a bulk gazette feed for IP matters?
- How does the re-registration route surface bibliographic
  data — under HK patent numbers, or as cross-references to
  the designated CN / GB / EP(UK) patents?

Until surveyed, HK register coverage flows transitively
through EPO INPADOC (granted HK patents on either route),
Madrid Monitor (Madrid IRs designating CN-HK), Hague
Express (Hague IRs designating CN-extended-to-HK), and
Google Patents (web-crawl basis).

## §6 Open questions

- **e-Legislation extractable variant.** The HTML pages
  resolve to a JS-rendered SPA; is there a publicly
  documented XML / JSON / PDF export route for an
  individual ordinance? Worth a quick reverse-engineer on
  the Cap. 514C page to find the data endpoint before
  committing to dev-browser as the only route.
- **Bilingual table parity.** Whether the Traditional
  Chinese `/tc/` mirror of the IPD fee pages stays
  byte-for-byte synchronized with the English `/en/`
  version, or drifts. v1 parses EN only.
- **Route encoding completeness.** Verified `(O)` and
  `(R)` patent route tags appear in the description column.
  Need to confirm whether every patent row is tagged or
  whether some are route-agnostic (e.g., common
  recordation fees).
- **Hague-CN-HK territorial scope.** Whether IPD treats
  Hague IRs designating CN as automatically protected in
  HK, or whether a separate HK extension request is
  required. Doesn't affect fee work directly but matters
  for register-side coverage.
- **Short-term patent search-authority designation.** The
  designated searching authority option list (CN, EP, JP,
  etc.) affects the search-report fee — verify whether
  the IPD table encodes per-authority pricing or a single
  rate.

## §7 References

**IPD institutional + fee pages (reachable):**
- [IPD landing](https://www.ipd.gov.hk/en/)
- [Patent fee schedule — forms-and-fees](https://www.ipd.gov.hk/en/patents/forms-and-fees/index.html)
- [Trade Mark fee schedule — forms-and-fees](https://www.ipd.gov.hk/en/trade-marks/forms-and-fees/index.html)
- [Design fee schedule — forms-and-fees](https://www.ipd.gov.hk/en/designs/forms-and-fees/index.html)

**Substantive law (Hong Kong e-Legislation — JS-rendered):**
- [Patents Ordinance Cap. 514](https://www.elegislation.gov.hk/hk/cap514)
- [Patents (General) Rules Cap. 514C (Schedule 4 = fees)](https://www.elegislation.gov.hk/hk/cap514C)
- [Trade Marks Ordinance Cap. 559](https://www.elegislation.gov.hk/hk/cap559)
- [Trade Marks Rules Cap. 559A (Schedule 1 = fees)](https://www.elegislation.gov.hk/hk/cap559A)
- [Registered Designs Ordinance Cap. 522](https://www.elegislation.gov.hk/hk/cap522)
- [Registered Designs Rules Cap. 522A](https://www.elegislation.gov.hk/hk/cap522A)

**International framework:**
- [WIPO Madrid contracting parties — PRC territorial extension to HK](https://www.wipo.int/treaties/en/notifications/madridp-gp/treaty_madridp_gp_180.html)
- [WIPO Hague members — PRC accession 2022-05-05](https://www.wipo.int/hague/en/members/)

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-19 | Initial synopsis, **fee-focused**. Fees rated **green (ready to build)** — the prior gap-doc finding ("URL drift / unknown — 404 on guessed paths") is superseded. All three IPD fee pages reachable from US egress: [patents](https://www.ipd.gov.hk/en/patents/forms-and-fees/index.html) (32 tables), [trade marks](https://www.ipd.gov.hk/en/trade-marks/forms-and-fees/index.html) (17 tables), [designs](https://www.ipd.gov.hk/en/designs/forms-and-fees/index.html) (12 tables — URL is `/en/designs/`, not `/en/registered-designs/` which 404s). Two patent routes (OGP / re-registration) are tagged inline in the description column as `(O)` / `(R)`, with the substantive grant fee diverging substantially (~HK$4,413 OGP vs ~HK$686 re-registration). E-filing vs paper-filing splits encoded as a sub-table on relevant rows. Statutory basis: Cap. 514C Schedule 4 (patents), Cap. 559A Schedule 1 (TMs), Cap. 522A (designs) on [Hong Kong e-Legislation](https://www.elegislation.gov.hk/) — these are JS-rendered SPAs and serve as citation source, not extraction target. Annual revision is sporadic (tied to gazette-published amendments to subsidiary legislation, not a fixed calendar). Register-side connector survey deferred. Coverage of HK at biblio fidelity flows transitively through EPO INPADOC and Google Patents; Madrid / Hague designations are encoded as CN-territory-extension to HK, not standalone HK designations. | This session; live probes 2026-05-19 |
