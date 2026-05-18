# RU/Rospatent — wave file (2026-05-18 priority-2 synopses)

Grounded re-evaluation of **Rospatent** (Федеральная служба по
интеллектуальной собственности) against the zero-infra-proxy
constraint, with a fresh read of the post-2022 sanctions and
reciprocity posture as of 2026-05. Cross-references the existing
2026-05 detail survey at
[`connectors/rospatent.md`](../../connectors/rospatent.md); locks the
existing `red_blocked` rating with a politics+economics rationale
rather than a pure no-API rationale.

Rights covered on the register side: patent, utility model,
industrial design, trademark (incl. service marks, well-known marks,
Madrid extensions to RU), appellation of origin, geographical
indication. The substantive-law layer (Civil Code Part IV) is treated
as a **separate workstream** — see §10.

---

## 1. Endpoint

Rospatent and its operational arm **FIPS** (Federal Institute of
Industrial Property, Федеральный институт промышленной
собственности) expose three Russian-facing programmatic surfaces and
one English landing. There is no single documented public REST API
spanning all rights:

- **FIPS public search portal** — the live human-facing register, now
  served from [`new.fips.ru`](https://new.fips.ru/en/) (the
  `new1.fips.ru` host used by the older detail survey is a sibling
  staging-style hostname). EN-labelled databases catalogue at
  [`new.fips.ru/en/informational-resources/information-retrieval-system/databases.php`](https://new.fips.ru/en/informational-resources/information-retrieval-system/databases.php).
  HTML/JS form posts; no documented REST contract; no OpenAPI; no
  Swagger.
- **Rospatent open-data + open-API hub** — [`online.rospatent.gov.ru/open-data`](https://online.rospatent.gov.ru/open-data)
  and the open-API page at
  [`online.rospatent.gov.ru/open-data/open-api`](https://online.rospatent.gov.ru/open-data/open-api).
  Russian-only documentation; registration flows through Gosuslugi
  (Russian government identity service) with a Russian mobile-number
  requirement in practice.
- **Search Platform** — [`searchplatform.rospatent.gov.ru/`](https://searchplatform.rospatent.gov.ru/)
  is the modern SPA front-end. A **free, account-less trademark image
  + verbal search service** launched 22 Jan 2024 at
  [`searchplatform.rospatent.gov.ru/trademarks`](https://searchplatform.rospatent.gov.ru/trademarks)
  (per [Rospatent's English information page](https://rospatent.gov.ru/en/products_services/search_system)
  and secondary practitioner coverage from
  [S&O IP](https://so-ipr.com/news-events/publications/federal-service-intellectual-property-rospatent-has-launched-new-trademark-search-service-search-platform-information-system)).
  Image search is AI-backed. **This is the single most material 2024
  drift point versus the older detail survey** — but it's still a
  human-facing SPA, not a documented REST API; agent-friendly access
  is unchanged.
- **English information landing** — [`rospatent.gov.ru/en`](https://rospatent.gov.ru/en/)
  and [`fips.ru/en/`](https://www.fips.ru/en/) are EN portals, but
  detail records remain Russian-language.

Adjacent surfaces touched but out of scope:

- **EAPO** — Eurasian Patent Office at [`eapo.org`](https://www.eapo.org/en/)
  with EAPATIS guest mode and the Eurasian Register at
  [`inspire.wipo.int/eurasian-patent-information-system-eapatis`](https://inspire.wipo.int/eurasian-patent-information-system-eapatis) /
  [`inspire.wipo.int/eurasian-patent-register`](https://inspire.wipo.int/eurasian-patent-register).
  Russia-adjacent regional office; rides on the same compliance and
  economics analysis. STATE.yaml row [`RU/EAPO`](../../STATE.yaml) is
  tracked separately.
- **IP Court of the Russian Federation** — `ipc.arbitr.ru` and
  `kad.arbitr.ru`; Russian-only, anti-bot, no clean API. Out of
  scope for any v1 connector.

## 2. Auth

- **FIPS new.fips.ru**: anonymous lookups work for low volume;
  sustained access requires an account; no maintained Python client.
- **Rospatent open-data / open-API portal**: registration via
  **Gosuslugi** (the Russian government identity service) with
  Russian mobile-number friction. Documented at the
  [`online.rospatent.gov.ru/open-data/open-api`](https://online.rospatent.gov.ru/open-data/open-api)
  portal; full sign-up flow is Russian-language only. No primary
  source documents a foreign-developer onboarding path; the older
  detail survey records this as a practical block ([`connectors/rospatent.md`](../../connectors/rospatent.md)
  §2).
- **`searchplatform.rospatent.gov.ru/trademarks`**: no account
  required for the 2024 trademark search service per the Rospatent
  EN [search-system page](https://rospatent.gov.ru/en/products_services/search_system).
- **EAPO EAPATIS**: free guest mode for EA-numbered docs +
  CISPATENT; full search requires paid account.

**Foreign-developer accessibility:** the FIPS public search supports
unauthenticated browsing from US/EU egress with intermittent
reachability. The open-data portal's account flow has a
Russian-mobile dependency that is the practical block, not a written
policy.

## 3. Query language

- **new.fips.ru**: HTML form fields per database (patent number,
  applicant, IPC class, dates). No documented URL parameter grammar;
  internal AJAX endpoints exist but are undocumented and not
  contractually stable.
- **Rospatent open API**: a CQL/Lucene-like query DSL is documented
  on the [open-API page](https://online.rospatent.gov.ru/open-data/open-api),
  but only in Russian and behind the Gosuslugi gate.
- **searchplatform.rospatent.gov.ru/trademarks**: spelling /
  phonetics / semantics text search plus AI image search per
  [Rospatent EN](https://rospatent.gov.ru/en/products_services/search_system);
  field filters for Nice classes, holder, dates, application /
  registration numbers. **UI-only — no public REST contract.**

## 4. Pagination

- **new.fips.ru**: HTML hit lists; session-driven; no documented cap.
- **Rospatent open API**: documented but Russian-only +
  Gosuslugi-gated, so functional pagination semantics are not
  re-verifiable from outside.
- **searchplatform**: SPA pagination; not a documented REST envelope.

## 5. Response shape

- **new.fips.ru**: HTML records; Russian-language abstracts;
  EN abstract field present for some inventions but not consistently.
- **Rospatent open API**: per the portal's Russian-only documentation,
  JSON is the expected envelope. No primary source available outside
  the gate to sample.
- **searchplatform.rospatent.gov.ru/trademarks**: HTML / SPA JSON
  fragments; not a stable contract.

## 6. Coverage scope

- **Russian inventions** — full backfile via FIPS (Soviet-era /
  USSR documents present per [FIPS EN about page](https://www.fips.ru/en/about/)).
- **Utility models** — full RU backfile (Russia is a UM jurisdiction;
  ~10-15k UM applications/year pre-2022).
- **Industrial designs, trademarks, appellations of origin, GIs** —
  full backfile on FIPS.
- **Madrid IRs designating RU** — visible via FIPS and WIPO Madrid
  Monitor. WIPO has **not** suspended RU from Madrid; see §8.
- **Eurasian patents** — separately covered by EAPO (8 member
  states: Armenia, Azerbaijan, Belarus, Kazakhstan, Kyrgyzstan,
  Russia, Tajikistan, Turkmenistan); not reproduced in the FIPS
  registers.

**Transitive coverage from outside the FIPS surface:**

- **EPO INPADOC** — RU biblio + family continues post-2022. RU
  legal-status events were **partial pre-2022** per the
  [INPADOC country-coverage notes](https://cas-stnext.zendesk.com/hc/en-us/articles/30921938483085-INPADOCDB-and-INPAFAMDB-Country-Coverage)
  and [legal-status notes](https://cas-stnext.zendesk.com/hc/en-us/articles/30922098616333-INPADOCDB-and-INPAFAMDB-Legal-Status);
  the gap has not closed.
- **WIPO Patentscope** — PCT applications filed by RU applicants
  and PCT national-phase entries designating RU. Per
  [WIPO PCT country info — RU](https://www.wipo.int/directory/en/details.jsp?country_code=RU),
  Russia remains a PCT Contracting State and continues to be
  bilaterally functional.
- **WIPO Madrid Monitor** — Madrid IRs designating RU. RU is a
  Madrid member; no WIPO suspension as of 2026-05.

## 7. Rate limits / quotas

No primary-source rate-limit documentation found for the open-API
portal that is reachable from outside the Gosuslugi gate. FIPS
public search throttles aggressively on US/EU egress per the older
detail survey ([`connectors/rospatent.md`](../../connectors/rospatent.md)
§1) — no published per-IP threshold.

## 8. Terms of service

Russian government data is published under domestic open-data
arrangements; no English ToS page documents specifically authorize
or prohibit foreign hosted-proxy reuse. The compliance perimeter is
**not the FIPS ToS**; it is the broader sanctions context, treated
explicitly below in §9.

## 9. Operational notes — the load-bearing analysis

This is the section that makes the rating. The question is not "is
there an API"; the question is **whether building a connector for
RU registers is a defensible commitment of engineering budget given
the sanctions, reciprocity, and economics environment as of
2026-05**. The answer is no. Four sub-points:

### 9.1 Decree 299 (6 Mar 2022) — still in force as of 2026-05

Government Decree No. 299 amends the methodology under **Article 1360
of the Civil Code Part IV** (state-interest compulsory licensing).
For patent holders connected to states on Russia's "unfriendly
countries" list (48 jurisdictions including US, UK, all EU member
states, AU, CA, JP, KR, CH, SG), the compensation rate for
unauthorized use of inventions, utility models, and industrial
designs is set to **0% of proceeds**. The decree is operative only
when the Russian government issues a separate order designating
specific patents; only a handful of such designation orders have
appeared in the open record. Coverage as of Feb 2025 confirms the
decree remains in effect and unchanged ([yesmypatent — 11 Feb 2025](https://www.yesmypatent.com/en/2025/02/11/russia-allows-protected-inventions-to-be-exploited-by-owners-from-non-allied-countries/);
[National Law Review — Russian Decree Nullifies Unfriendly Country Patent Enforcement](https://natlawreview.com/article/war-and-peace-rospatent-protecting-trademarks-russia)).
The decree is widely viewed as facially incompatible with
**TRIPS Article 31** ("adequate remuneration" for compulsory
licensing); no WTO panel has adjudicated.

There is **no canonical Decree-299 designation register** to scrape
or proxy. Coverage is fragmentary, mediated by Russian-language
gazette notices and practitioner tracking. Building product around
"the Decree 299 list" promises something that doesn't exist as a
machine-readable object.

### 9.2 Decree 430 (20 May 2024) — IP acquisition gate

A separate Government Commission approval is required for Russian
persons to acquire IP rights from unfriendly-state persons. One-way
valve on RU IP transactions. Treated as substantive policy in the
static-law module (see §10), not a data source.

### 9.3 OFAC / EU / USPTO / EPO posture as of 2026-05

- **OFAC.** Russian Harmful Foreign Activities Sanctions Regs
  ([31 CFR Part 587](https://ofac.treasury.gov/sanctions-programs-and-country-information/russian-harmful-foreign-activities-sanctions))
  prohibit dealings with sanctioned RU persons broadly.
  **General License 31** (5 May 2022,
  [archived primary source](https://sanctions.org/turbofac/research/OFAC-Russia-related-General-License-31))
  authorizes filing, prosecution, maintenance, and defense of
  patents/TMs/copyrights with Rospatent and EAPO — including
  reading public Rospatent data and citing it. GL 31 is unchanged
  through April 2026 per OFAC's
  [selected general licenses page](https://ofac.treasury.gov/selected-general-licenses-issued-ofac).
- **EU 14th package (in force 25 Jun 2024).** Article 5s prohibits
  EU IP offices from *accepting new filings* from RU persons —
  filing-side block, not a data-access block.
- **EU 18th package (in force 19 Jul 2025).** Explicitly extends
  the "No-Russia" clause obligation to **intellectual property,
  know-how, and trade secrets** for items on the Common High
  Priority List; brings software into the trade-sanctions
  perimeter ([EU Council press release](https://www.consilium.europa.eu/en/press/press-releases/2025/07/18/russia-s-war-of-aggression-against-ukraine-eu-adopts-18th-package-of-economic-and-individual-measures/);
  [Ashurst overview](https://www.ashurst.com/en/insights/overview-of-the-eus-18th-sanctions-package/)).
  EU practitioners can still *read* RU registers; the operational
  IP supply-chain restrictions have tightened.
- **USPTO (22 Mar 2022, unchanged).** Terminated all engagement
  with Rospatent, EAPO, Belarus IP office.
  GPPH-with-Rospatent termination at
  [Federal Register 4 Apr 2022](https://www.federalregister.gov/documents/2022/04/04/2022-06885/termination-of-global-patent-prosecution-highway-with-rospatent);
  Rospatent as ISA/IPEA terminated per
  [USPTO update — termination of Rospatent as ISA and IPEA](https://www.uspto.gov/about-us/news-updates/update-termination-rospatent-isa-and-ipea-international-applications).
- **EPO.** Suspended cooperation with Rospatent and EAPO; refused
  unitary-effect requests from RU applicants (10 Jul 2024). INPADOC
  RU biblio continues; legal-status feed remains partial.

### 9.4 WIPO posture

WIPO has **not** suspended Russia from PCT, Madrid, or Hague — RU
remains a Contracting Party of all three multilateral systems as
of 2026-05 per the [WIPO directory entry for the Russian Federation](https://www.wipo.int/directory/en/details.jsp?country_code=RU)
and the [WIPO Russia office page](https://www.wipo.int/en/web/office-russia/).
WIPO's Russia office activities are reduced and politically
contested but technically operating. This is a **soft positive** —
RU patent data continues to flow through the multilateral systems
into INPADOC and Patentscope.

### 9.5 The economics

The sanctions perimeter permits reading public Rospatent data and
re-exposing it; OFAC GL 31 covers the law. But the economics don't
justify the engineering investment:

- Small US/EU agent demand for live RU register reads (the user base
  that would have driven a 2019-era RU connector has substantially
  withdrawn from RU IP practice).
- Declining data quality on the RU side (INPADOC RU legal-status
  was partial pre-2022 and has degraded).
- Brittle integration (Gosuslugi gate, Russian-mobile dependency,
  Russian-only documentation, intermittent reachability from
  Western IPs).
- A state that has explicitly abrogated reciprocity under Decree
  299 — the IP rights we'd be helping users read are, for those
  users, partly worth zero by Russian decree.

The asymmetry vs. CNIPA is the load-bearing comparison: **CNIPA is
hard but not hostile** (Chinese courts pay foreign patentees; IP5
cooperation continues; the closure rationale is no-API).
**Rospatent is both hard *and* hostile** — the closure rationale is
politics-economics on top of no-API.

## 10. Rating

**Rating: 🔴 red_blocked.** Locks the existing STATE.yaml row.

The closure is for **politics-economics reasons**, not for an
absence of any programmatic surface: a usable foreign-developer
read path *might* be technically buildable through the
`searchplatform` SPA or the open-API portal if one had a Gosuslugi
identity and accepted the brittleness. The rating is red because:

1. **Decree 299 abrogates the reciprocity assumption** for
   patents held by US/EU/UK/JP/KR/AU/CA/CH/SG persons — the
   underlying data is "compensation = 0%" for the user base most
   likely to be querying.
2. **OFAC GL 31 permits the *reading*** but the broader OFAC + EU
   18th-package sanctions environment is the practical operating
   constraint, especially the EU 18th-package IP/know-how clauses
   that tighten what an EU consumer of an RU-derived data feed can
   then do downstream.
3. **No documented public REST API** that meets the zero-infra-proxy
   constraint *from outside the Gosuslugi gate*. The 2024
   `searchplatform.rospatent.gov.ru/trademarks` launch is a UI
   improvement, not an API.
4. **Higher-layer transitive coverage suffices** for the residual
   demand — INPADOC + Patentscope + Madrid + Hague handle the
   sanctions-clean slice.

The **separable workstream** is the substantive-law layer: Russian
Civil Code Part IV (Federal Law 230-FZ, 18 Dec 2006, in force
2008-01-01; 326 articles / 9 chapters covering copyright, patents,
TMs, GIs, trade secrets, plant varieties, IC topographies, related
rights). This is cleanly licensable from outside Russia via WIPO
Lex and fits the existing `StaticLawCorpus` pattern used by
`ipo_in_statutes`, `dpma_statutes`, `legifrance_ip`, and
`tw_trade_secrets`. **Recommend a `RU/CivilCode/Part4` static-law
corpus as a separate BACKLOG entry, ordered after `BR/LPI/Statute`
to keep the priority-2 statute sweep coherent.** WIPO Lex hosts
multiple consolidated versions — the most current as of 2026-05 is
[WIPO Lex 22547 (Civil Code Parts One–Four, consolidated through
2024 amendments)](https://www.wipo.int/wipolex/en/legislation/details/22547);
the prior Part-Four-only consolidations at
[22106 (through 29 Jun 2023)](https://www.wipo.int/wipolex/en/legislation/details/22106)
and [21655 (through 25 Jul 2022)](https://www.wipo.int/wipolex/en/legislation/details/21655)
remain available for diff/history.

---

## Drift vs. the 2026-05 detail survey

The older [`connectors/rospatent.md`](../../connectors/rospatent.md)
captures the same situation accurately. Three material updates:

1. **`searchplatform.rospatent.gov.ru/trademarks` launched 22 Jan 2024**
   as a free, account-less verbal + AI image trademark search per
   [Rospatent EN](https://rospatent.gov.ru/en/products_services/search_system).
   The older survey treated `searchplatform` as Gosuslugi-gated end-to-end;
   the TM sub-surface is in fact open. Still UI-only; does not change the
   rating but is the single substantive 2024 movement on the Russian side.
2. **EU 18th sanctions package (in force 19 Jul 2025)** extends the
   "No-Russia" clause obligation to IP / know-how / trade secrets for
   Common High Priority List items and brings software into the trade
   perimeter. Tightens the downstream-use environment for EU users of
   any RU-derived data feed; reinforces the red rating.
3. **WIPO Lex 22547 (Civil Code Parts One–Four, consolidated through
   2024 amendments)** is the newest WIPO Lex consolidation; the
   older detail survey references 22106 (through 29 Jun 2023) and
   12785 (Parts 1–4 baseline). For the `RU/CivilCode/Part4`
   corpus, prefer 22547 as the canonical recent text and retain
   22106 / 21655 / 21034 as version history.

OFAC GL 31, Decree 299, Decree 430, USPTO termination, EPO
suspension, and the WIPO no-suspension posture are all unchanged
from the older detail survey.

## Recommended STATE.yaml resolution

No change to the rating:

- `rating: red_blocked` (unchanged)
- `rating_basis: Politics+economics — Decree 299 zeros foreign-patentee compensation; no documented public REST behind Gosuslugi gate; INPADOC + Patentscope + Madrid + Hague cover transitive residual demand`
- `connector_status: skipped` (unchanged)
- `next_action: monitor` (was `write_synopsis`; this wave closes the synopsis task)
- `last_verified: 2026-05-18`

Separate BACKLOG entry to queue:

- **`RU/CivilCode/Part4` — static-law corpus.** WIPO Lex
  [22547](https://www.wipo.int/wipolex/en/legislation/details/22547)
  primary; same `StaticLawCorpus` pattern as
  `ipo_in_statutes` / `dpma_statutes` / `legifrance_ip` /
  `tw_trade_secrets`. Cleanly licensed; English authoritative
  translation; replaces 7–8 separate RU statute mirrors (patents,
  TMs, designs, GIs, copyright, trade secrets, plant varieties,
  IC topographies) with one corpus. Half-day-to-one-day work.
  Ordered after `BR/LPI/Statute` in the priority-2 statute sweep.

## Sources (primary)

**Rospatent + FIPS:**
- [Rospatent home (EN)](https://rospatent.gov.ru/en/) · [Rospatent search-system page (EN)](https://rospatent.gov.ru/en/products_services/search_system)
- [FIPS home (EN)](https://www.fips.ru/en/) · [FIPS about page (EN)](https://www.fips.ru/en/about/)
- [new.fips.ru EN databases](https://new.fips.ru/en/informational-resources/information-retrieval-system/databases.php)
- [Rospatent open-data portal](https://online.rospatent.gov.ru/open-data) · [Rospatent open-API page](https://online.rospatent.gov.ru/open-data/open-api)
- [searchplatform.rospatent.gov.ru](https://searchplatform.rospatent.gov.ru/) · [searchplatform — trademarks (launched 22 Jan 2024)](https://searchplatform.rospatent.gov.ru/trademarks)
- [WIPO INSPIRE — Russian Patent Base](https://inspire.wipo.int/russian-patent-base)

**Statutes (Civil Code Part IV):**
- [WIPO Lex 22547 — Civil Code Parts One–Four (2024)](https://www.wipo.int/wipolex/en/legislation/details/22547)
- [WIPO Lex 22106 — Part Four (through 29 Jun 2023)](https://www.wipo.int/wipolex/en/legislation/details/22106)
- [WIPO Lex 21655 — Part Four (through 25 Jul 2022)](https://www.wipo.int/wipolex/en/legislation/details/21655)
- [WIPO Lex 21034 — Part Four (through 30 Apr 2021)](https://www.wipo.int/wipolex/en/legislation/details/21034)
- [WIPO Lex 12785 — Parts 1–4 baseline](https://www.wipo.int/wipolex/en/legislation/details/12785)

**Sanctions / decrees:**
- [OFAC Russian Harmful Foreign Activities Sanctions program](https://ofac.treasury.gov/sanctions-programs-and-country-information/russian-harmful-foreign-activities-sanctions)
- [OFAC selected general licenses page](https://ofac.treasury.gov/selected-general-licenses-issued-ofac)
- [Russia-related General License 31 (5 May 2022)](https://sanctions.org/turbofac/research/OFAC-Russia-related-General-License-31)
- [USPTO statement — engagement with Russia and EAPO (22 Mar 2022)](https://www.uspto.gov/about-us/news-updates/uspto-statement-engagement-russia-and-eurasian-patent-organization)
- [USPTO update — termination of Rospatent as ISA/IPEA](https://www.uspto.gov/about-us/news-updates/update-termination-rospatent-isa-and-ipea-international-applications)
- [Federal Register — GPPH with Rospatent termination (4 Apr 2022)](https://www.federalregister.gov/documents/2022/04/04/2022-06885/termination-of-global-patent-prosecution-highway-with-rospatent)
- [EU Council press release — 18th sanctions package (18 Jul 2025)](https://www.consilium.europa.eu/en/press/press-releases/2025/07/18/russia-s-war-of-aggression-against-ukraine-eu-adopts-18th-package-of-economic-and-individual-measures/)
- [European Commission — 18th sanctions package announcement](https://finance.ec.europa.eu/news/eu-adopts-18th-package-sanctions-against-russia-2025-07-18_en)

**WIPO posture:**
- [WIPO directory — Russian Federation](https://www.wipo.int/directory/en/details.jsp?country_code=RU)
- [WIPO Office in the Russian Federation](https://www.wipo.int/en/web/office-russia/)

**EPO RU coverage:**
- [INPADOC country coverage notes](https://cas-stnext.zendesk.com/hc/en-us/articles/30921938483085-INPADOCDB-and-INPAFAMDB-Country-Coverage)
- [INPADOC legal-status notes](https://cas-stnext.zendesk.com/hc/en-us/articles/30922098616333-INPADOCDB-and-INPAFAMDB-Legal-Status)

**Earlier detail survey:**
- [`connectors/rospatent.md`](../../connectors/rospatent.md) — 2026-05 detail survey
