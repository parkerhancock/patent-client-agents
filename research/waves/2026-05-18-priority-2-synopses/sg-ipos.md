# SG/IPOS — Grounded API discovery wave (2026-05-18)

Cross-references the [2026-05 detail survey](../../connectors/ipos_singapore.md);
synopsis at [`research/national/sg-ipos.md`](../../national/sg-ipos.md).

IPOS administers all five SG IP rights from one English-language agency, but
*for our zero-infra-proxy purposes* the surface looks very different from the
"all-in-one OAuth REST" pattern (IP Australia, EUIPO). Two register-side data
paths exist — **CorpPass-gated transactional APIs** and **data.gov.sg
collection 281** — and neither is a viable hosted-proxy substrate for the
authoritative register today. The substantive-law layer (statutes + manuals)
is the cleanest open surface and lives entirely outside IPOS's own systems
on [`sso.agc.gov.sg`](https://sso.agc.gov.sg/) and the IPOS `/about-ip/`
PDF tree.

## §1 Endpoint

Three distinct surfaces, three different posture profiles:

- **IP2SG transactional APIs** — `https://ip2sg.ipos.gov.sg/RPS/WC/API/APITokenRequest.aspx` is the documented entry point for the *filing* APIs that IPOS launched 1 Feb 2021 (TM filings/renewals/ICGS first, then patents and designs). IPOS describes these as letting "third parties to integrate key features from IP2SG into their own software solutions" but routes everything through IP2SG accounts; see the general [eServices entry page](https://www.ipos.gov.sg/eservices/) and the [IPOS Digital Hub circular (2 Jun 2022)](https://www.ipos.gov.sg/news/news-collection/circular--ipos-digital-hub-launch-on-2-june-2022/) for the system migration. Read-side: no documented bibliographic-search REST API at this layer.
- **data.gov.sg "IPOS applications API" (collection 281)** — `https://data.gov.sg/collections/281/view`. Three datasets: [Patent applications `d_c49410cc1e293b0a7213a433ab612067`](https://data.gov.sg/datasets/d_c49410cc1e293b0a7213a433ab612067/view), [Trademark applications `d_56058f817dc3708f8b97e0876335ac66`](https://data.gov.sg/datasets/d_56058f817dc3708f8b97e0876335ac66/view), [Design applications `d_63bfb01a27595bedef08da39a344402c`](https://data.gov.sg/datasets/d_63bfb01a27595bedef08da39a344402c/view). Each accepts a `lodgement_date=YYYY-MM-DD` parameter and returns `{"items":[...]}` JSON. The patent endpoint that the 2026-05 survey already flagged is still listed at the same URL.
- **IPOS Digital Hub HTML front door** — `https://digitalhub.ipos.gov.sg/FAMN/eservice/IP4SG/MN_BasicSearch` (and `MN_AdvancedSearch`, `MN_Journals`, `MN_TmSimilarMarkSearch`, `MN_TmIcgsSearch`). ASP.NET WebForms; the legacy host `https://www.ip2.sg/` still serves the simple-search forms. Per the [Digital Hub launch circular](https://www.ipos.gov.sg/news/news-collection/circular--ipos-digital-hub-launch-on-2-june-2022/), this surface replaced the legacy IP2SG UI on 2 June 2022.

Substantive-law surfaces (outside IPOS):

- **Singapore Statutes Online** — `https://sso.agc.gov.sg/`, operated by the [Legislation Division of the Attorney-General's Chambers](https://www.agc.gov.sg/our-roles/drafter-of-laws/singapore-statutes-online/). All SG IP acts addressable by act slug: [`Act/PA1994`](https://sso.agc.gov.sg/Act/PA1994) (Patents Act 1994), [`Act/TMA1998`](https://sso.agc.gov.sg/act/tma1998), [`Act/RDA2000`](https://sso.agc.gov.sg/Act/RDA2000), [`Act/IPOSA2001`](https://sso.agc.gov.sg/Act/IPOSA2001) (IPOS Act), [`Acts-Supp/23-2019`](https://sso.agc.gov.sg/Acts-Supp/23-2019) (IP Dispute Resolution Act 2019), and subsidiary legislation like [`SL/PA1994-R1`](https://sso.agc.gov.sg/SL/PA1994-R1) (Patents Rules) / [`SL/266-R1`](https://sso.agc.gov.sg/SL/266-R1) (Registered Designs Rules).
- **IPOS examination + work manuals** — [`/about-ip/patents/guides/`](https://www.ipos.gov.sg/about-ip/patents/guides/) and the parallel TM and Designs guide trees. PDF chapters served as static assets.

## §2 Auth

- **IP2SG / IPOS Digital Hub transactional APIs.** IP2SG account (Individual or Corporate) is the gating credential; per the [Digital Hub CorpPass integration notice](https://www.ipos.gov.sg/news/news-collection/circular--ipos-digital-hub-launch-on-2-june-2022/) the corporate path requires CorpPass admin authorization for the eService ID `IPOS-IP4SG-CP` (eService Name "Digital Hub - New National Registry System (IP4SG)"). Singpass is the foundation for Individual accounts. Both Singpass and CorpPass are SG-resident identity systems. **No primary source** documents a foreign-developer signup path for the transactional APIs; the public [eServices](https://www.ipos.gov.sg/eservices/) and [IP Professionals](https://www.ipos.gov.sg/manage-ip/resources/for-ip-professionals/) pages route everyone through Singpass/CorpPass.
- **data.gov.sg API.** Anonymous access works for testing; an API key is "strongly recommended" for production. Per the [API Rate Limits page](https://guide.data.gov.sg/developer-guide/api-overview/api-rate-limits), three tiers: anonymous (lowest), Dev (moderate, API key), Prod (highest, API key + priority support). Key signup is via a waitlist per the [extended deadline notice](https://guide.data.gov.sg/whats-new/extended-deadline-upgrade-to-api-keys-by-dec-31-2025); no SG-residency requirement is stated.
- **SSO + IPOS PDF tree.** No auth; public read.

## §3 Query language

- **data.gov.sg collection 281.** A single lookup parameter — `lodgement_date=YYYY-MM-DD` — per the [Patent applications dataset page](https://data.gov.sg/datasets/d_c49410cc1e293b0a7213a433ab612067/view). No structured-field query, no operators, no free text. Equivalent to "give me everything filed on this date" — useful as a daily-incremental walk, not as an ad-hoc search.
- **IPOS Digital Hub HTML.** Field-typed forms (number/applicant/title/class) with the standard ASP.NET `__VIEWSTATE` POST shape. Not REST.
- **SSO.** URL-addressable by act slug, section, and historical date; no documented full-text API.

## §4 Pagination

- **data.gov.sg.** The lodgement-date endpoint returns one date's worth in one envelope; no offset/limit pagination is documented at [collection 281](https://data.gov.sg/collections/281/view). Practical implication: pagination is by *date*, not by page.
- **IPOS Digital Hub HTML.** WebForms pagination via `__VIEWSTATE`-driven postbacks; brittle.

## §5 Response shape

- **data.gov.sg patent/TM/design.** JSON envelope `{"items":[...]}` with biblio fields (lodgement_date, application number, applicant, title). [Sample dataset page](https://data.gov.sg/datasets/d_c49410cc1e293b0a7213a433ab612067/view) exposes the field set; no document text, no claims, no legal status events.
- **IPOS Digital Hub HTML.** Heading-anchored HTML; result tables; PDF document downloads where exposed.

## §6 Coverage scope

- **data.gov.sg "Patent applications (API)" `d_c49410cc1e293b0a7213a433ab612067`** — coverage **Aug 2018 → Oct 2020**, confirmed unchanged 2026-05-18 ([dataset page](https://data.gov.sg/datasets/d_c49410cc1e293b0a7213a433ab612067/view)). This is the gap the 2026-05 survey flagged and it has not closed.
- **data.gov.sg "Trademark applications (API)" `d_56058f817dc3708f8b97e0876335ac66`** — TM data was last reported "current to May 2025" in the 2026-05 survey; the dataset page itself remains live, with public access ([dataset page](https://data.gov.sg/datasets/d_56058f817dc3708f8b97e0876335ac66/view)). Freshness should be re-verified against the page metadata before any user-visible commitment.
- **data.gov.sg "Design applications (API)" `d_63bfb01a27595bedef08da39a344402c`** — the design endpoint that the 2026-05 survey treated as "placeholder" is in fact present on the portal ([dataset page](https://data.gov.sg/datasets/d_63bfb01a27595bedef08da39a344402c/view)); same lodgement-date-only query semantics as patents and trademarks; freshness to verify empirically. *This is the single drift from the older detail survey.*
- **IPOS register full backfile.** Live on the Digital Hub HTML search; not exposed via any documented REST.
- **Substantive law.** SSO carries the full Patents Act 1994, TMA 1998, RDA 2000, Copyright Act 2021, GIA 2014, PVPA 2004, Layout-Designs of Integrated Circuits Act 1999, plus subsidiary rules.
- **IPOS journals.** Patents Journal A / B and Trade Marks Journal published weekly per the [Digital Hub Journals tree](https://digitalhub.ipos.gov.sg/FAMN/eservice/IP4SG/MN_Journals); the [Digital Hub launch circular](https://www.ipos.gov.sg/news/news-collection/circular--ipos-digital-hub-launch-on-2-june-2022/) confirms Friday weekly cadence resumed week of 6 June 2022.

## §7 Rate limits / quotas

- **data.gov.sg.** Per the [API Rate Limits page](https://guide.data.gov.sg/developer-guide/api-overview/api-rate-limits): 10-second buckets, 429 on overrun, "rate limit enforcement on data.gov.sg will kick in on December 31, 2025" — i.e. enforcement is live as of this synopsis date. API keys lift the limit. Specific per-tier numerics are not published on the public guide; they require a registered key to surface.
- **IP2SG transactional / Digital Hub HTML.** No published per-IP rate. Operational limits go via the IP2SG account.

## §8 Terms of service

- **Singapore Open Data Licence** (applies to data.gov.sg datasets) — [policy page](https://data.gov.sg/open-data-licence). Permits redistribution and commercial use with attribution; conspicuous-attribution notice required for derivatives.
- **data.gov.sg API terms of service** — [privacy and terms page](https://data.gov.sg/privacy-and-terms). "An Agency may monitor your Use of the API to improve the service, track usage, to ensure compliance with these Terms of Service, or for security purposes." Datasets are "as is" / "as available". No clause that prohibits hosted proxying.
- **IP2SG terms** — [IP2SG-UAT T&Cs](https://ip2sg-uat.ipos.gov.sg/Layouts/RPSWP/Common/TermsAndConditions.aspx). Designed for SG-resident filing agents; redistribution by an unaffiliated SaaS is not contemplated.
- **SSO** — [official SSO portal](https://sso.agc.gov.sg/). Crown-copyright-style government work; public read is permitted; the SSO Help pages describe consumption patterns but no documented bulk export.

## §9 Operational notes

- **English-language office.** No translation overhead; manuals and statutes are authoritative in English.
- **Mobile front door (IPOS Go).** Filing-only, not data; not relevant to this connector evaluation.
- **No geofencing observed on data.gov.sg or SSO** from US egress per public docs; IP2SG transactional flows enforce Singpass/CorpPass which is *identity-gated*, not IP-gated.
- **Digital Hub migration.** Stable since 2 June 2022 per the [launch circular](https://www.ipos.gov.sg/news/news-collection/circular--ipos-digital-hub-launch-on-2-june-2022/); the legacy `ip2.sg` host is still alive.
- **Open-data API tier rollout.** Rate-limit enforcement and key-tier waitlist live Dec 2025; mature now.

## §10 Rating

**Register-side rating: 🔴 red — no usable public REST for the authoritative register, plus the one open API has a Oct-2020 coverage hole for patents.** The IP2SG transactional APIs are filing-side and CorpPass-gated (SG-resident identity). The data.gov.sg `collection 281` endpoints are date-only lookups under a clean licence but expose biblio-only, with patents frozen for ~5 years and freshness elsewhere not pinned by primary source. The Digital Hub HTML is brittle ASP.NET — equivalent to "no API." There is no INPI-style or IP-Australia-style REST surface on the IPOS layer; INPADOC (`regional/epo.md`) is the operational substitute for SG patent biblio + family, and Madrid/Hague handle international-route TM/design transitively. **Statutes-side rating: 🟢 green** — SSO and the IPOS PDF tree are clean static-corpus material under the existing `StaticLawCorpus` pattern used by `ipo_in_statutes`, `dpma_statutes`, `legifrance_ip`, `tw_trade_secrets`.

## Drift vs the older detail survey

- **Design dataset on data.gov.sg.** The older [survey §"open questions" #3](../../connectors/ipos_singapore.md) treated the design endpoint as "placeholder in collection 281 but no live endpoint." Primary source as of 2026-05-18 shows [`d_63bfb01a27595bedef08da39a344402c`](https://data.gov.sg/datasets/d_63bfb01a27595bedef08da39a344402c/view) is in fact published with the same lodgement-date query semantics. This is the single material drift in this wave.
- **Patent API freshness.** The 2018→2020 freeze is unchanged; the older survey's open question #1 is *still* an open question.
- **Rate-limit timing.** The 2026-05 survey said "tightened 1 Nov 2025"; the [extended-deadline notice](https://guide.data.gov.sg/whats-new/extended-deadline-upgrade-to-api-keys-by-dec-31-2025) confirms enforcement landed 31 Dec 2025 instead. Minor calendar drift only.

## Connector-strategy implications

Two questions land here:

1. **Register layer.** Skip. There is no usable authoritative-register REST surface. INPADOC + Madrid + Hague + (optionally, far-future) a thin data.gov.sg wrapper cover most of what an agent would want. The data.gov.sg three datasets are a "nice to have" daily-walk, not a search substrate.
2. **Substantive-law layer (stale worktree).** The 2026-05 `sg_statutes` + `sg_manuals` worktree pre-dates the connector-standards sweep but **the underlying primary sources are stable and untouched** — SSO act slugs, IPOS PDF tree, IPOS Act, and IPDR Act 2019 are all currently addressable. Reviving the corpus under the current `StaticLawCorpus` shape (same pattern as `ipo_in_statutes`, `dpma_statutes`, `legifrance_ip`, `tw_trade_secrets`) is a half-day-per-asset job and lights up agent capability for SG filings, prosecution arguments, and SICC dispute work. **Recommend revive, not close.**
