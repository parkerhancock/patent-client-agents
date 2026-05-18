# Rospatent Russia (RU) — national

**Layer:** national
**Jurisdiction:** RU (WIPO ST.3: RU)
**Issuing body:** Federal Service for Intellectual Property — Rospatent (Федеральная служба по интеллектуальной собственности), operationally executed by FIPS (Federal Institute of Industrial Property)
**Rights administered:** patent, utility_model, design, trademark, geographical_indication, appellation_of_origin
**Working languages:** Russian (primary, near-exclusive on register records). English (thin EN landing pages on rospatent.gov.ru/en and fips.ru/en; abstracts EN where present)
**Connector status:** **register-side: skipped (red_blocked)** — politics + economics closure, locked permanent absent a material change in the sanctions environment; **statutes-side: queued** as a separate `RU/CivilCode/Part4` static-law corpus workstream
**Last verified:** 2026-05-18
**Manifest entry:** *not listed in `coverage/sources.yaml`* — register-side closure; statutes-side corpus is queued, not shipped

**Detail surveys:**
- [`connectors/rospatent.md`](../connectors/rospatent.md) — 2026-05 detail survey (238 lines; feasibility matrix, sanctions analysis, EAPO + IP Court inventory)
- [`waves/2026-05-18-priority-2-synopses/ru-rospatent.md`](../waves/2026-05-18-priority-2-synopses/ru-rospatent.md) — 2026-05-18 grounded re-evaluation; locks the red rating with refreshed primary sources

**Higher layers covering this office transitively:**
- **EPO INPADOC** (via [`regional/epo.md`](../regional/epo.md)) — RU patent biblio + family continues post-2022. RU legal-status events were **partial pre-2022** per the [INPADOC country-coverage notes](https://cas-stnext.zendesk.com/hc/en-us/articles/30921938483085-INPADOCDB-and-INPAFAMDB-Country-Coverage); the gap has not closed.
- **WIPO Patentscope** — PCT applications filed by RU applicants and PCT national-phase entries designating RU. Russia remains a PCT Contracting State per [WIPO directory — RU](https://www.wipo.int/directory/en/details.jsp?country_code=RU).
- **WIPO Madrid Monitor / Global Brand Database** — Madrid IRs designating RU; RU is a Madrid member and **WIPO has not suspended Russia from Madrid as of 2026-05**.
- **WIPO Hague** — Hague IRs designating RU; RU acceded 2018-02-28.
- **WIPO Lex** — Civil Code Part IV (statutes); queued under the planned `RU/CivilCode/Part4` corpus.

---

## §1 Mission

Rospatent is the **federal executive body** responsible for legal
protection of intellectual property in Russia, with FIPS as its
operational research and examination institute
([rospatent.gov.ru/en](https://rospatent.gov.ru/en/),
[fips.ru/en](https://www.fips.ru/en/)). It administers RU national
patents, utility models, industrial designs, trademarks (incl. service
marks, well-known marks, and Madrid extensions to RU), appellations
of origin, geographical indications, and computer-program /
database / IC-topography registrations. Russia was a top-10
filing jurisdiction by raw volume pre-2022. Operationally, post-2022
RU sits inside an **adverse compliance, infrastructure, and
reciprocity environment** that makes it materially different from
every other jurisdiction we cover — the closure rationale here is
*not* "no API," it is "the politics and economics don't justify
the engineering investment, even where OFAC GL 31 permits the
reading." See [§5](#5-connector-strategy) for the locked rationale
and [§3](#3-programmatic-surfaces) for the per-surface analysis.

## §2 What's unique here

Materially nothing not covered by INPADOC + Patentscope + Madrid +
Hague post-2022 at the fidelity our agents need. The genuine
RU-only slices are real but narrow and largely de-prioritized by
the broader market post-2022:

- **Russian-language full text** of RU inventions, utility models,
  and designs — present on FIPS; rendered EN in INPADOC only at
  bibliographic-abstract fidelity.
- **RU national trademarks outside Madrid** — a real slice; small
  agent demand post-2022.
- **Decree 299 designation orders** — fragmentary primary record on
  pravo.gov.ru and the official gazette; **no canonical
  Decree-299-affected-patent register exists**; building product
  around a "Decree 299 list" promises something that isn't a
  machine-readable object (see [`connectors/rospatent.md`](../connectors/rospatent.md) §4).
- **Soviet-era / pre-1992 RU patent backfile** — present on FIPS;
  pre-INPADOC-window for some early documents.
- **IP Court of the Russian Federation (Суд по интеллектуальным
  правам)** decisions — [`ipc.arbitr.ru`](https://ipc.arbitr.ru/);
  Russian-only, anti-bot, no clean API. Distinct from register
  data; out of scope for this office's register synopsis.

The intersection of "unique to RU" and "high-value-given-current-
sanctions-context" is small. INPADOC + Patentscope cover the
sanctions-clean residual demand for cross-border prior-art and
family lookups.

## §3 Programmatic surfaces

Every Rospatent-operated programmatic surface is rated against the
zero-infra-proxy constraint **plus** the politics-economics overlay
documented in §5.

### FIPS new.fips.ru — public register UI

| Field | Value |
|---|---|
| Endpoint | [`new.fips.ru/en/informational-resources/information-retrieval-system/databases.php`](https://new.fips.ru/en/informational-resources/information-retrieval-system/databases.php) |
| Auth | Anonymous lookups for low volume; account required for sustained access (Russian-mobile dependency in practice) |
| Format | HTML / JS form posts; no documented REST contract; no OpenAPI |
| Rate limit | Undocumented; intermittent reachability from US/EU egress |
| ToS posture | No English ToS page documents foreign hosted-proxy reuse; Russian-language ToS not re-verified in this wave |
| Rating (zero-infra proxy) | 🔴 Red — HTML scrape; politics-economics overlay |
| Primary source | [FIPS EN about page](https://www.fips.ru/en/about/) |

Live register is HTML-only. Internal AJAX endpoints exist but are
undocumented and not contractually stable. Even setting the
sanctions overlay aside, this is shaped like INPI Brazil pePI or
CNIPA PSS — a no-API surface.

### Rospatent open-data / open-API portal

| Field | Value |
|---|---|
| Endpoint | [`online.rospatent.gov.ru/open-data/open-api`](https://online.rospatent.gov.ru/open-data/open-api) |
| Auth | Gosuslugi-gated registration; Russian-mobile dependency in practice |
| Format | JSON (per Russian-only documentation) |
| Rate limit | Not documented in primary sources reachable from outside the gate |
| ToS posture | Russian-only |
| Rating (zero-infra proxy) | 🔴 Red — Gosuslugi gate blocks foreign-developer onboarding; politics-economics overlay |
| Primary source | [Rospatent open-data portal](https://online.rospatent.gov.ru/open-data) |

This is the surface that *could* be a real REST API if the
Gosuslugi gate were navigable from outside Russia. As surveyed
2026-05, the practical foreign-developer onboarding path remains
blocked.

### Rospatent SearchPlatform — trademarks (launched 22 Jan 2024)

| Field | Value |
|---|---|
| Endpoint | [`searchplatform.rospatent.gov.ru/trademarks`](https://searchplatform.rospatent.gov.ru/trademarks) |
| Auth | None — free, account-less; 24/7 |
| Format | HTML SPA; not a documented REST contract |
| Rate limit | Not published |
| ToS posture | Russian-only |
| Rating (zero-infra proxy) | 🔴 Red — UI improvement, not an API surface; politics-economics overlay |
| Primary source | [Rospatent EN — search system](https://rospatent.gov.ru/en/products_services/search_system) |

The single material 2024 movement on the Russian side — a free,
account-less verbal + AI image trademark search. **Still UI-only.**
Does not change the rating; flagged here so future-us doesn't
re-discover it as a "new API."

### EAPO EAPATIS (Russia-adjacent, separate STATE.yaml row)

| Field | Value |
|---|---|
| Endpoint | [`eapo.org`](https://www.eapo.org/en/); [WIPO INSPIRE — EAPATIS](https://inspire.wipo.int/eurasian-patent-information-system-eapatis) |
| Auth | Free guest mode for EA-numbered docs + CISPATENT; paid for full search |
| Rating (zero-infra proxy) | 🔴 Red — rides on RU compliance/economics; USPTO termination explicitly covers EAPO |
| Primary source | [EAPO EN](https://www.eapo.org/en/) |

Tracked under [`RU/EAPO`](../../STATE.yaml) as a separate row; same
disposition as Rospatent for the same reasons.

### IP Court of the Russian Federation

| Field | Value |
|---|---|
| Endpoint | [`ipc.arbitr.ru`](https://ipc.arbitr.ru/) and the general arbitrazh portal at `kad.arbitr.ru` |
| Auth | None for the index |
| Rating | 🔴 Red — RU-only, anti-bot, no clean API; commercial RU scrapers are RU-counterparty |
| Primary source | [WIPO Magazine — Russian IP Court](https://www.wipo.int/wipo_magazine/en/2014/01/article_0006.html) |

Out of scope for this office's register synopsis; documented for
strategic memory.

## §4 Fees

**Policy: link only.** Rospatent / FIPS publishes a Russian-Ruble
(RUB) tariff covering **patents** (filing, search, examination,
substantive examination, publication, grant, annuities), **utility
models** (filing, examination, annuities), **industrial designs**
(filing, examination, grant, renewals), **trademarks** (filing,
examination, registration, renewals per class), **appellations of
origin / GIs**, plus separate schedules for **petitions, opposition
proceedings, and Patent Chamber (Палата по патентным спорам)
appeals**. International-route fees (PCT national-phase entry,
Madrid handling) are separate. Statutory basis: **Civil Code Part
IV** (Federal Law 230-FZ, 18 Dec 2006) + the patent-fee Decree
of the Government of the Russian Federation.

- **Official fee landing (RU):** [Rospatent — patent fees / Patent and Trademark Office Fees](https://rospatent.gov.ru/ru/documents/patent-and-trademark-office-fees) *(Russian-language; authoritative)*
- **Statutory basis:** [WIPO Lex 22547 — Civil Code Parts One–Four (2024)](https://www.wipo.int/wipolex/en/legislation/details/22547) (substantive IP provisions in Part Four)

Notable discount programs *(named only — no amounts, no dates)*:

- **Individual / inventor reductions** — natural persons filing in
  their own name receive reduced patent-fee rates under the
  patent-fee Decree.
- **SME (малое предприятие) reductions** — small-enterprise filings
  receive reduced rates.
- **Scientific / educational institution reductions** — accredited
  research institutions receive reduced rates on filing and
  examination.

Reproducing specific RUB amounts is out of scope per the
[fee-policy section of the template](../templates/office-synopsis.md)
— the official Russian-language schedule is authoritative.

## §5 Connector strategy

### What we cover today

Nothing on the RU register side. RU patent biblio + family is
accessed transitively via
[`patent_client_agents.epo_ops`](../regional/epo.md) (INPADOC).
Madrid IRs designating RU and Hague IRs designating RU flow
through the multilateral systems. PCT applications by RU applicants
flow through WIPO Patentscope.

### What we should NOT add (register side)

**Locked closure — politics + economics.** Future-us should **not
re-evaluate this absent a material shift in the sanctions and
reciprocity environment.** The closure is *not* "no API"; it is
"the politics and economics don't justify the engineering
investment, even where OFAC GL 31 permits the reading." Full
load-bearing analysis in [the 2026-05-18 wave file §9](../waves/2026-05-18-priority-2-synopses/ru-rospatent.md);
headline facts as of 2026-05:

- **Decree 299 (6 Mar 2022, in force)** — zeros compensation for
  unauthorized use of inventions, utility models, and designs held
  by persons from 48 "unfriendly states" (US, UK, all EU, AU, CA,
  JP, KR, CH, SG). Status unchanged per
  [yesmypatent — Feb 2025](https://www.yesmypatent.com/en/2025/02/11/russia-allows-protected-inventions-to-be-exploited-by-owners-from-non-allied-countries/);
  facially incompatible with [TRIPS Art. 31](https://www.wto.org/english/docs_e/legal_e/27-trips_04c_e.htm).
- **Decree 430 (20 May 2024)** — IP-acquisition gate; one-way valve
  on RU IP transactions.
- **USPTO termination (22 Mar 2022, unchanged)** — GPPH terminated
  per [Federal Register 4 Apr 2022](https://www.federalregister.gov/documents/2022/04/04/2022-06885/termination-of-global-patent-prosecution-highway-with-rospatent);
  Rospatent as ISA/IPEA terminated per
  [USPTO update](https://www.uspto.gov/about-us/news-updates/update-termination-rospatent-isa-and-ipea-international-applications).
- **EU 18th sanctions package (in force 19 Jul 2025)** — extends
  "No-Russia" clause to IP / know-how / trade secrets for CHP
  Items and brings software into the trade-sanctions perimeter
  ([EU Council press release](https://www.consilium.europa.eu/en/press/press-releases/2025/07/18/russia-s-war-of-aggression-against-ukraine-eu-adopts-18th-package-of-economic-and-individual-measures/);
  [EC announcement](https://finance.ec.europa.eu/news/eu-adopts-18th-package-sanctions-against-russia-2025-07-18_en)).
- **OFAC General License 31 (5 May 2022, unchanged through April
  2026)** — permits IP filing / prosecution / reading with
  Rospatent and EAPO ([OFAC general licenses](https://ofac.treasury.gov/selected-general-licenses-issued-ofac)).
  **GL 31 permits the law; it does not improve the economics.**
- **EPO suspension** — cooperation with Rospatent + EAPO suspended;
  unitary-effect requests from RU refused (10 Jul 2024). INPADOC RU
  biblio continues; legal-status remains partial.
- **WIPO has *not* suspended Russia** from PCT, Madrid, or Hague —
  RU remains a Contracting Party of all three as of 2026-05 per
  [WIPO directory — RU](https://www.wipo.int/directory/en/details.jsp?country_code=RU).
  Soft positive — RU patent data continues to flow through the
  multilateral systems into INPADOC and Patentscope.

The asymmetry vs. CNIPA is the calibration: **CNIPA is hard but
not hostile** — closure on no-API grounds ([`cn-cnipa.md`](cn-cnipa.md)).
**Rospatent is both hard *and* hostile** — closure on
politics+economics on top of no-public-REST.

**Specifically do not build:** a FIPS scraper or `new.fips.ru` HTML
parser; a Rospatent open-API portal client (Gosuslugi-gated); a
`searchplatform.rospatent.gov.ru` wrapper (UI, not API — the 2024
TM launch doesn't change this); an EAPATIS client (same
compliance/economics); an IP Court / arbitrazh scraper; any "Decree
299 affected patent" tracker (no canonical list exists); any
Russian commercial aggregator integration (RU counterparty, ruble
billing, secondary-sanctions risk).

### What we should add — the separable substantive-law workstream

**Recommend a `RU/CivilCode/Part4` static-law corpus as a separate
BACKLOG entry** — independent of the register-side closure; same
pattern as `IN/IPO/Statutes`, `DE/DPMA/Statutes`, `FR/Legifrance/IP`,
`TW/MOJ/TradeSecretsAct`. Primary source: [WIPO Lex 22547 — Civil
Code Parts One–Four (consolidated through 2024 amendments)](https://www.wipo.int/wipolex/en/legislation/details/22547);
older Part-Four-only consolidations at
[22106](https://www.wipo.int/wipolex/en/legislation/details/22106) /
[21655](https://www.wipo.int/wipolex/en/legislation/details/21655) /
[21034](https://www.wipo.int/wipolex/en/legislation/details/21034) /
[12785](https://www.wipo.int/wipolex/en/legislation/details/12785)
for diff history. Federal Law 230-FZ; 326 articles / 9 chapters
covering copyright, patents, TMs, GIs, trade secrets, plant
varieties, IC topographies — one master statute replaces 7-8
separate RU statute mirrors. Survives the register-side closure
because WIPO publishes the EN translation, the corpus is mirrored
once into our existing `StaticLawCorpus` pattern, and **runtime
never queries a Russian server**. Sequence after `BR/LPI/Statute`
in the priority-2 statute sweep; queue in [`BACKLOG.md`](../BACKLOG.md).

### Next steps

1. **Close the register-side synopsis task** in STATE.yaml — `rating: red_blocked` (unchanged), `connector_status: skipped` (unchanged), `next_action: monitor`, `last_verified: 2026-05-18`.
2. **File the `RU/CivilCode/Part4` BACKLOG entry** referencing this synopsis and [the wave-file §10 recommendation](../waves/2026-05-18-priority-2-synopses/ru-rospatent.md). Same pattern as `BR/LPI/Statute`.
3. **Monitor quarterly** for shifts in the WIPO posture ([WIPO Russia office news](https://www.wipo.int/en/web/office-russia/news)), OFAC GL 31 amendments ([OFAC general licenses](https://ofac.treasury.gov/selected-general-licenses-issued-ofac)), EU subsequent sanctions packages ([EU Council Russia sanctions hub](https://www.consilium.europa.eu/en/policies/sanctions-against-russia/)), and any Rospatent open-API foreign-developer onboarding announcement ([Rospatent EN news](https://rospatent.gov.ru/en/news)).
4. **Watch for Decree 299 designation orders** in the official Russian gazette ([pravo.gov.ru](http://pravo.gov.ru/)) — useful portfolio-risk context, but **do not promise users a canonical list** (one doesn't exist).
5. **Re-evaluate trigger:** a material loosening of the sanctions posture *and* a documented foreign-developer onboarding path on the Rospatent open API. **Both required.**

## §6 Open questions

- **Foreign-developer onboarding on the Rospatent open API.** Does it ever ship a path that bypasses the Gosuslugi gate? Watch [online.rospatent.gov.ru/open-data/open-api](https://online.rospatent.gov.ru/open-data/open-api).
- **Documented REST beneath `searchplatform.rospatent.gov.ru/trademarks`.** No primary source either way; internal AJAX undocumented.
- **EU 18th-package downstream-use semantics** for a US-hosted service serving EU users with RU-register-derived data. No primary source pins the operating-services interpretation; legal review needed before any future hosted-proxy attempt.
- **INPADOC RU legal-status coverage trend post-2022.** Pre-2022 gap persists per [INPADOC legal-status notes](https://cas-stnext.zendesk.com/hc/en-us/articles/30922098616333-INPADOCDB-and-INPAFAMDB-Legal-Status); quantitative trend not pinned.
- **Decree 299 designation orders.** Any reliable secondary tracker? No canonical primary register; fragmentary practitioner tracking only.
- **EAPO industrial-design extension (since 2021).** Coverage in EPO INPADOC + WIPO Hague Express? Open from the older detail survey; still open.

## §7 References

Primary sources only — Rospatent/FIPS own domains, WIPO Lex/WIPO directory, official US/EU government decree archives.

**Rospatent + FIPS:**
- [Rospatent (EN)](https://rospatent.gov.ru/en/) · [Rospatent — search system](https://rospatent.gov.ru/en/products_services/search_system) · [Rospatent EN news](https://rospatent.gov.ru/en/news)
- [FIPS (EN)](https://www.fips.ru/en/) · [FIPS about](https://www.fips.ru/en/about/) · [new.fips.ru EN databases](https://new.fips.ru/en/informational-resources/information-retrieval-system/databases.php)
- [Rospatent open-data portal](https://online.rospatent.gov.ru/open-data) · [open-API page](https://online.rospatent.gov.ru/open-data/open-api)
- [searchplatform.rospatent.gov.ru](https://searchplatform.rospatent.gov.ru/) · [TM search (launched 22 Jan 2024)](https://searchplatform.rospatent.gov.ru/trademarks)
- [WIPO INSPIRE — Russian Patent Base](https://inspire.wipo.int/russian-patent-base)

**Statutes (Civil Code Part IV — queued workstream):**
- [WIPO Lex 22547 — Civil Code Parts One–Four (2024)](https://www.wipo.int/wipolex/en/legislation/details/22547) *(primary for the queued corpus)* · [22106 (2023)](https://www.wipo.int/wipolex/en/legislation/details/22106) · [21655 (2022)](https://www.wipo.int/wipolex/en/legislation/details/21655) · [21034 (2021)](https://www.wipo.int/wipolex/en/legislation/details/21034) · [12785 (Parts 1–4 baseline)](https://www.wipo.int/wipolex/en/legislation/details/12785)

**Sanctions context (load-bearing for the closure):**
- [OFAC Russian Harmful Foreign Activities Sanctions program](https://ofac.treasury.gov/sanctions-programs-and-country-information/russian-harmful-foreign-activities-sanctions) · [OFAC selected general licenses](https://ofac.treasury.gov/selected-general-licenses-issued-ofac)
- [USPTO statement — engagement with Russia and EAPO (22 Mar 2022)](https://www.uspto.gov/about-us/news-updates/uspto-statement-engagement-russia-and-eurasian-patent-organization) · [USPTO ISA/IPEA termination](https://www.uspto.gov/about-us/news-updates/update-termination-rospatent-isa-and-ipea-international-applications) · [Federal Register — GPPH termination (4 Apr 2022)](https://www.federalregister.gov/documents/2022/04/04/2022-06885/termination-of-global-patent-prosecution-highway-with-rospatent)
- [EU Council — 18th sanctions package (18 Jul 2025)](https://www.consilium.europa.eu/en/press/press-releases/2025/07/18/russia-s-war-of-aggression-against-ukraine-eu-adopts-18th-package-of-economic-and-individual-measures/) · [EC announcement](https://finance.ec.europa.eu/news/eu-adopts-18th-package-sanctions-against-russia-2025-07-18_en) · [EU Council Russia sanctions hub](https://www.consilium.europa.eu/en/policies/sanctions-against-russia/)
- [TRIPS Agreement Art. 31 (WTO)](https://www.wto.org/english/docs_e/legal_e/27-trips_04c_e.htm) — compulsory-licensing standard relevant to Decree 299
- Decree 299 / Decree 430 primary gazette texts: monitor at [pravo.gov.ru](http://pravo.gov.ru/) (Russian-language; English summaries via secondary practitioner sources are linked in [the wave file](../waves/2026-05-18-priority-2-synopses/ru-rospatent.md))

**WIPO multilateral posture (RU not suspended):**
- [WIPO directory — Russian Federation](https://www.wipo.int/directory/en/details.jsp?country_code=RU) · [WIPO Office in the Russian Federation](https://www.wipo.int/en/web/office-russia/) · [WIPO Russia office news](https://www.wipo.int/en/web/office-russia/news)

**EPO RU coverage notes:**
- [INPADOC country coverage](https://cas-stnext.zendesk.com/hc/en-us/articles/30921938483085-INPADOCDB-and-INPAFAMDB-Country-Coverage) · [INPADOC legal-status](https://cas-stnext.zendesk.com/hc/en-us/articles/30922098616333-INPADOCDB-and-INPAFAMDB-Legal-Status)

**Detail survey + wave:**
- [`connectors/rospatent.md`](../connectors/rospatent.md) — 2026-05 detail survey · [`waves/2026-05-18-priority-2-synopses/ru-rospatent.md`](../waves/2026-05-18-priority-2-synopses/ru-rospatent.md) — 2026-05-18 grounded re-evaluation

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-18 | Initial synopsis. Register-side rated **🔴 red_blocked** — closure locked permanent on politics + economics grounds: Decree 299 (in force; zeros foreign-patentee compensation for "unfriendly states" incl. US/EU/UK/JP/KR/AU/CA/CH/SG), Decree 430 (IP-acquisition gate), USPTO termination (22 Mar 2022), EU 18th-package IP/know-how clauses (in force 19 Jul 2025), EPO suspension. OFAC GL 31 permits the law; the economics do not justify the engineering investment. No documented public REST behind the Gosuslugi gate; the 2024 `searchplatform.rospatent.gov.ru/trademarks` launch is a UI improvement, not an API. **Recommends `RU/CivilCode/Part4` static-law corpus as a separate BACKLOG entry** (WIPO Lex 22547 primary), in the pattern of `IN/IPO/Statutes` / `DE/DPMA/Statutes` / `FR/Legifrance/IP` / `TW/MOJ/TradeSecretsAct`. Material drift from older detail survey: (a) `searchplatform.rospatent.gov.ru/trademarks` launched 22 Jan 2024 as free, account-less; (b) EU 18th-package IP/know-how clauses (Jul 2025); (c) WIPO Lex 22547 is now the newest consolidation, superseding 22106 for the corpus primary. Decree 299 / 430 / OFAC GL 31 / USPTO / EPO / WIPO no-suspension posture all unchanged. | [waves/2026-05-18-priority-2-synopses/ru-rospatent.md](../waves/2026-05-18-priority-2-synopses/ru-rospatent.md) |
