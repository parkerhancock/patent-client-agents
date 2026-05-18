# ILPO Israel (IL) — national

**Layer:** national
**Jurisdiction:** IL (WIPO ST.3: IL)
**Issuing body:** Israel Patent Office (רשם הפטנטים, המדגמים וסימני המסחר) — registration unit inside the Ministry of Justice
**Rights administered:** patent, trademark, design, geographical indication (appellations of origin)
**Working languages:** Hebrew (controlling); English (EN locales on all three search portals; partial EN coverage of examination guidelines)
**Connector status:** **register: skip (no API)**; **statutes: planned** (revive `israel_statutes`, `StaticLawCorpus`-shape)
**Last verified:** 2026-05-18
**Manifest entry:** not yet listed in [`coverage/sources.yaml`](../../coverage/sources.yaml) — proposed split into `IL/ILPO/Register` (none) + `IL/ILPO/Statute` (planned)

**Detail surveys:**
- [`connectors/israel_pto.md`](../connectors/israel_pto.md) — 2026-05 detail survey (329 lines; 23-asset matrix, statute-heavy v1 recommendation)
- [`waves/2026-05-18-priority-2-synopses/il-ilpo.md`](../waves/2026-05-18-priority-2-synopses/il-ilpo.md) — 2026-05-18 grounded API discovery, register vs. statutes split

**Higher layers covering this office transitively:**
- **EPO INPADOC** (via [`regional/epo.md`](../regional/epo.md)) — IL patent biblio + family + legal events (~2011-present per [WIPO INSPIRE](https://inspire.wipo.int/system/files/juri/il.pdf)).
- **WIPO Madrid** (planned `multilateral/wipo-madrid.md`) — international TMs designating IL (IL is a Madrid Protocol member since 2010 per [WIPO Madrid members](https://www.wipo.int/madrid/en/members/)).
- **WIPO Hague** (planned `multilateral/wipo-hague.md`) — international designs designating IL (IL is a Hague member since 2020).
- **WIPO PATENTSCOPE** — PCT applications routed through ILPO as receiving office, and ILPO-issued ISRs / written opinions (IL has been an **ISA / IPEA since 2012-06-01** per the [USPTO notice](https://www.uspto.gov/sites/default/files/patents/law/notices/ilpo_isa-ipea.pdf)).

---

## §1 Mission

ILPO is the registration unit inside the Israeli Ministry of Justice
that administers all three registered IP rights (patents, trademarks,
designs) plus appellations of origin / geographical indications under
the 5725-1965 law. Plant breeders' rights sit separately at the Plant
Variety Council under the Ministry of Agriculture. Israel runs
roughly ~8,000 patent applications a year — a small register by IP5
standards, but disproportionately weighted toward pharma (Teva
inheritors), semiconductors, defense electronics, cyber, and software.
Beyond the register, two structural facts matter for agents working
Israeli IP: ILPO has been an **ISA / IPEA since 2012-06-01**, placing
it in the small club of ~16 offices that examine PCT applications for
the world, and Israel has a **standalone statutory trade-secrets
regime** in the Commercial Torts Law 5759-1999 — a regime that bundles
trade secrets, unregistered marks, and procedural remedies in one
instrument.

## §2 What's unique here

- **Israeli national patents, TMs, designs, and appellations of origin**
  — the authoritative register. EPO INPADOC + WIPO Madrid + WIPO Hague
  cover most of what agents touch transitively, leaving the
  national-only Israeli slice as the genuine ILPO-exclusive value.
- **Commercial Torts Law 5759-1999 — standalone statutory trade secrets**
  — distinct from US/UK/Canadian common-law breach-of-confidence
  baselines and from EU member-state Directive-2016/943 transpositions.
  Bundles trade secrets (Arts. 6-9), unregistered TMs, and procedural
  remedies (Anton Piller-style seizures, asset freezes) in one instrument.
  ([WIPO Lex 2375](https://www.wipo.int/wipolex/en/legislation/details/2375))
- **Designs Law 5777-2017** — modernised the register and introduced a
  **2-year blackout** post-registration during which designs are not
  publicly searchable. ([WIPO Lex 19434](https://www.wipo.int/wipolex/en/legislation/details/19434))
- **ILPO as PCT ISA / IPEA (2012-06-01-)** — ILPO-issued international
  search reports and written opinions flow into WIPO PATENTSCOPE under
  the standard PCT event flow; no separate IL feed is needed for them.
  ([PCT eGuide IL](https://pctlegal.wipo.int/eGuide/view-doc.xhtml?doc-code=IL&doc-lang=en))
- **Pre-1978 Israeli patent backfile (1902-1977)** — published Israeli
  applications before EPO INPADOC's coverage window starts. Niche but
  real for prior-art searches in older art.

## §3 Programmatic surfaces

### Patents Search SPA (`israelpatents.justice.gov.il`)

| Field | Value |
|---|---|
| Endpoint | `https://israelpatents.justice.gov.il/<lang>/search?AP_0_option=...` (Angular SPA over undocumented JSON backend) |
| Auth | None on the surface; CSRF + reCAPTCHA + Glassbox session capture on the JSON backend |
| Format | HTML envelope; per-record PDFs; undocumented internal JSON |
| Rate limit | None published; reCAPTCHA + Glassbox is the enforcement |
| ToS posture | Implicitly anti-automation; no standalone ToS page found |
| Rating (zero-infra proxy) | 🔴 **Red** — no public API; explicit anti-automation perimeter |
| Primary source | [Patents Search EN](https://israelpatents.justice.gov.il/en/home) |

The combination of **CSRF + reCAPTCHA + Glassbox** is an explicit
product decision against programmatic third-party use. No documented
JSON contract; reverse-engineering against a CAPTCHA gate is off-spec.

### Trademarks Search (`trademarks.justice.gov.il`)

| Field | Value |
|---|---|
| Endpoint | `https://trademarks.justice.gov.il/TradeMarkSearch/TradeMarkSearch?lang=en` |
| Auth | None |
| Format | ASP.NET MVC + Kendo UI HTML |
| Rate limit | None published |
| ToS posture | No published ToS page; session-cookie-based UI |
| Rating (zero-infra proxy) | 🔴 **Red** — HTML scrape only; the supported data substrate is data.gov.il |
| Primary source | [Trademarks Search EN](https://trademarks.justice.gov.il/TradeMarkSearch/TradeMarkSearch?lang=en) |

### Designs Search (`designsearch.justice.gov.il`)

| Field | Value |
|---|---|
| Endpoint | `https://designsearch.justice.gov.il/` |
| Auth | None |
| Format | ASP.NET MVC + Kendo UI HTML |
| Rate limit | None published |
| ToS posture | No published ToS page |
| Rating (zero-infra proxy) | 🔴 **Red** — HTML scrape only; 2-year post-registration blackout further narrows coverage value |
| Primary source | [Designs Search](https://designsearch.justice.gov.il/) |

### Patents Journal / Gazette

| Field | Value |
|---|---|
| Endpoint | `israelpatents.justice.gov.il/<lang>/patents-journal` (browsed inside the SPA) |
| Auth | None on browse; inherits the SPA's anti-automation surface for indexing |
| Format | HTML index + per-event PDFs |
| Rating (zero-infra proxy) | 🔴 **Red** — bound to the same SPA perimeter as the patents register |
| Primary source | [Patents Search EN](https://israelpatents.justice.gov.il/en/home) |

### data.gov.il — Trademark dataset (CKAN)

| Field | Value |
|---|---|
| Endpoint | `https://www.data.gov.il/` (CKAN backend at `/api/3/action/...`) |
| Auth | Free public reads; API key available for higher-volume / production use |
| Format | JSON envelope `{"result": {"records": [...]}}` |
| Rate limit | None pinned by primary source |
| ToS posture | Israeli government open-data programme; redistribution licence text not pinned by primary source in this wave — walk the dataset page before any redistribution claim |
| Rating (zero-infra proxy) | 🟡→🔴 **Yellow trending red** — clean CKAN feed, but **bulk-shaped**; under our zero-infra constraint, hosting an offline index of weekly TM dumps is off-spec |
| Primary source | [data.gov.il landing](https://www.gov.il/en/departments/data_gov_il/govil-landing-page) · [`datagovil-ckanext`](https://github.com/gov-il/datagovil-ckanext) |

This is the **only confirmed structured ILPO-source feed**. Whether
parallel patents or designs datasets exist on data.gov.il alongside
the TM feed is **not evidenced by primary source** as of 2026-05-18.

### Substantive law via WIPO Lex (statute mirror)

| Field | Value |
|---|---|
| Endpoint | [`wipo.int/wipolex/en/profile.jsp?code=IL`](https://www.wipo.int/wipolex/en/profile.jsp?code=IL) |
| Auth | None |
| Format | PDF + HTML; authoritative EN translations by ILPO / Ministry of Justice |
| Rating (zero-infra proxy) | 🟢 **Green** — clean static-corpus material; same shape as our existing `ipo_in_statutes`, `dpma_statutes`, `legifrance_ip`, `tw_trade_secrets` modules |
| Primary source | [WIPO Lex IL profile](https://www.wipo.int/wipolex/en/profile.jsp?code=IL) |

## §4 Fees

ILPO publishes a consolidated fee schedule in **NIS (Israeli new shekel)**
covering patents (filing, search, examination, grant, oppositions,
annual fees), trademarks (filing per class, renewal), and designs
(filing, renewal). The schedule is administered under the Patents
Regulations (Office Practice) 5728-1968 and parallel TM / Design
secondary legislation; rate-adjustment notices are published in the
official gazette and on the ILPO `gov.il` pages.

- **Official schedule (ILPO):** [`gov.il/en/departments/ilpo`](https://www.gov.il/en/departments/ilpo) — fee tables and rate-adjustment notices under the relevant department's "Fees" / "תעריפים" navigation
- **Statutory basis (Patents Regulations 5728-1968):** [WIPO Lex 19117](https://www.wipo.int/wipolex/en/legislation/details/19117)
- **Patents Law (parent statute):** [WIPO Lex 15167](https://www.wipo.int/wipolex/en/legislation/details/15167)

Notable discount categories (link-only — no amounts):

- **Small-entity / individual applicant reductions** under the Patents Regulations
  fee schedule.
- **ISA / IPEA reductions for Israeli-routed PCT applicants** (academic /
  student / pensioner tiers documented through the
  [PCT eGuide IL](https://pctlegal.wipo.int/eGuide/view-doc.xhtml?doc-code=IL&doc-lang=en)).

## §5 Connector strategy

The 2026-05 worktree at IL/ILPO built a single "ILPO statutes + TM bulk
catalog" module that never integrated; STATE.yaml shows
`connector_status: in_progress`. This synopsis splits that ambiguity
into two independent decisions, each with its own rating.

### Register layer — skip

**Rating: 🔴 red_no_api. Recommendation: skip, monitor.**

ILPO exposes **no public REST/JSON register API** for patents, TMs, or
designs. The Patents SPA is explicitly anti-automation (CSRF +
reCAPTCHA + Glassbox); the TM and Design portals are ASP.NET WebForms
with no API. The data.gov.il weekly TM dataset is clean and licensed
but **bulk-shaped** — under our zero-infra constraint ("proxy live APIs
at runtime; do NOT host bulk dumps, build search indexes, or maintain
offline corpora") a bulk feed has the same outcome as no API.

Coverage of the bibliographic essentials is provided transitively:

- IL patent biblio + family + legal events via [`patent_client_agents.epo_ops`](../regional/epo.md) (country code `IL`, 2011-present per [WIPO INSPIRE](https://inspire.wipo.int/system/files/juri/il.pdf)).
- Madrid IRs designating IL via planned `wipo_madrid` (IL is a Madrid member since 2010).
- Hague IRs designating IL via planned `wipo_hague` (IL is a Hague member since 2020).
- ILPO-issued ISR / written opinions via WIPO PATENTSCOPE under the standard PCT event flow.

The unique register-side coverage gaps — file-wrapper PDFs, Israeli
national-only TMs (~190k+ across the dataset), pre-2011 legal events,
and designs in the 2-year blackout window — exist but the demand is
too thin and the perimeter too hostile to justify the build. No
PIBD-style "documented migration in progress" announcement has been
made by ILPO.

### Statutes layer — revive

**Rating: 🟢 green. Recommendation: revive `israel_statutes` as a `StaticLawCorpus` module.**

The 2026-05 worktree's statute half is **salvageable independent of
the bulk-TM-catalog decision**. Eight core IP statutes, all with
authoritative ILPO / Ministry-of-Justice English translations on WIPO
Lex, addressable today:

1. [Patents Law 5727-1967](https://www.wipo.int/wipolex/en/legislation/details/15167)
2. [Patents Regulations (Office Practice) 5728-1968](https://www.wipo.int/wipolex/en/legislation/details/19117)
3. [Trade Marks Ordinance 5732-1972](https://www.wipo.int/wipolex/en/legislation/details/8200)
4. [Designs Law 5777-2017](https://www.wipo.int/wipolex/en/legislation/details/19434)
5. [Commercial Torts Law 5759-1999](https://www.wipo.int/wipolex/en/legislation/details/2375) — **standalone statutory trade secrets**
6. [Plant Breeders' Rights Law 5733-1973](https://www.wipo.int/wipolex/en/legislation/details/9524)
7. [Copyright Act 5768-2007](https://www.wipo.int/wipolex/en/legislation/details/11509)
8. [Appellations of Origin / GIs Law 5725-1965](https://www.wipo.int/wipolex/en/legislation/details/2373)

Same shape as our existing `ipo_in_statutes`, `dpma_statutes`,
`legifrance_ip`, and `tw_trade_secrets` modules — SQLite/FTS5 corpus
fronted by the standard `StaticLawCorpus` access layer. Manifest entry
proposal: `IL/ILPO/Statute`. The unique-feature row is the **Commercial
Torts Law 5759-1999** — bundling trade secrets, unregistered marks,
and procedural remedies in one statute is structurally different from
the common-law and EU-Directive baselines, and is the highest-leverage
agent payoff in the corpus.

### What we should NOT add

- **Patents Search SPA scraping.** Explicit anti-automation perimeter
  (CSRF + reCAPTCHA + Glassbox); no documented JSON contract; coverage
  of biblio + legal events duplicated by EPO INPADOC.
- **TM / Design ASP.NET portals scraping.** WebForms brittleness;
  data.gov.il is the supported substrate.
- **Hosted offline index of the data.gov.il weekly TM dataset.** Clean
  feed, but bulk → off-spec under current connector standards (same
  resolution we landed on for BR/INPI RPI XML in the sibling wave
  file [`br-inpi.md`](../waves/2026-05-18-priority-2-synopses/br-inpi.md)).
- **Patents Journal scraping.** Bound to the same SPA perimeter; EPO
  OPS covers the agent-relevant slice transitively.
- **Nevo / Takdin.** Subscription, scrape-hostile, out of budget.
- **Tel Aviv District Court / Supreme Court direct scrape.** Hebrew
  RTL, no public docket API; defer to Versa-Cardozo curated EN
  translations if a case-law layer is ever needed.

### Next steps

1. Spec the revived `israel_statutes` module against `CONNECTOR_STANDARDS.md`
   §6 and the canonical USPTO Applications migration template. Manifest
   entry `IL/ILPO/Statute`; one PR.
2. File `IL/ILPO/Register` as `none` / `closed_bulk_only` in STATE.yaml
   and add the rationale (this synopsis + the wave file) as
   reconciliation log on `BACKLOG.md`.
3. **Stretch (not queued now):** Versa-Cardozo curated EN translation
   mirror for the ~700 Israeli Supreme Court decisions, IP slice. Static
   HTML, public-mission project — confirm redistribution permission
   before any cache-and-serve pattern. Doubles as a precedent for
   future Versa-style curated-translation sources in other
   jurisdictions.
4. **Monitor (not work):** watch for a documented ILPO REST surface
   on `israelpatents.justice.gov.il` or a `gov.il` work-procedures
   developer announcement. None is signalled in 2026-05.

## §6 Open questions

- **data.gov.il IP dataset inventory.** Does ILPO publish parallel
  patents and / or designs datasets alongside the confirmed TM feed?
  Run CKAN `package_search` against the data.gov.il backend for
  `patents`, `מדגמים` (designs), `סימני מסחר` (TMs). Open since the
  2026-05 detail survey; still open.
- **data.gov.il open-data licence text.** No single primary-source page
  pinned in this wave for the redistribution clause; walk the dataset
  page + the [`datagovil-ckanext`](https://github.com/gov-il/datagovil-ckanext)
  repo docs before any user-facing redistribution claim.
- **Israel as Madrid / Hague member — coverage depth.** Confirm
  empirically that Madrid IRs designating IL and Hague IRs designating
  IL flow through INPADOC / Madrid / Hague Express at the expected
  fidelity, before claiming the transitive substitution closes the
  register-coverage gap.
- **Versa-Cardozo redistribution licence.** Public-mission translation
  project — confirm permission for cache-and-serve before queuing the
  stretch module.
- **ILPO examination guidelines EN coverage ratio.** What fraction of
  the [`work-procedure-db`](https://www.gov.il/he/Departments/DynamicCollectors/work-procedure-db?skip=0)
  is translated to EN? If <20%, an EN-subset mirror is a stub; if
  >50%, it's worth a proper MPEP-shape index.
- **Commercial Torts Law placement in the cross-cutting trade-secrets
  matrix.** Israel's statute combines trade secrets + unregistered TMs
  + procedural remedies — should it sit in the trade-secrets row of
  the cross-cutting index, the TM row, or both?

## §7 References

Primary sources only — `justice.gov.il`, `gov.il`, `data.gov.il`,
`wipo.int`, `pctlegal.wipo.int`, `knesset.gov.il`, `supreme.court.gov.il`,
`versa.cardozo.yu.edu`, `uspto.gov` (for the ISA / IPEA notice).

**ILPO portals + register search:**
- [ILPO unit (Ministry of Justice EN)](https://www.justice.gov.il/En/Units/ILPO/Pages/default.aspx)
- [ILPO on gov.il (EN)](https://www.gov.il/en/departments/ilpo)
- [Search Databases hub (EN)](https://www.justice.gov.il/En/Units/ILPO/Departments/Patents/Guides/Pages/SearchDatabases.aspx)
- [Patents Search EN home](https://israelpatents.justice.gov.il/en/home)
- [Trademarks Search EN](https://trademarks.justice.gov.il/TradeMarkSearch/TradeMarkSearch?lang=en)
- [Designs Search](https://designsearch.justice.gov.il/)
- [WIPO INSPIRE IL profile (PDF)](https://inspire.wipo.int/system/files/juri/il.pdf)

**Open data:**
- [data.gov.il landing (gov.il)](https://www.gov.il/en/departments/data_gov_il/govil-landing-page)
- [`datagovil-ckanext` repo (open-source CKAN extensions)](https://github.com/gov-il/datagovil-ckanext)

**Examination guidelines + work procedures:**
- [`gov.il` work-procedure-db (HE)](https://www.gov.il/he/Departments/DynamicCollectors/work-procedure-db?skip=0)

**Substantive law (WIPO Lex IL):**
- [WIPO Lex IL hub](https://www.wipo.int/wipolex/en/profile.jsp?code=IL)
- [Patents Law 5727-1967](https://www.wipo.int/wipolex/en/legislation/details/15167)
- [Patents Regulations 5728-1968](https://www.wipo.int/wipolex/en/legislation/details/19117)
- [Trade Marks Ordinance 5732-1972](https://www.wipo.int/wipolex/en/legislation/details/8200)
- [Designs Law 5777-2017](https://www.wipo.int/wipolex/en/legislation/details/19434)
- [Commercial Torts Law 5759-1999](https://www.wipo.int/wipolex/en/legislation/details/2375)
- [Plant Breeders' Rights Law 5733-1973](https://www.wipo.int/wipolex/en/legislation/details/9524)
- [Copyright Act 5768-2007](https://www.wipo.int/wipolex/en/legislation/details/11509)
- [Appellations of Origin / GIs Law 5725-1965](https://www.wipo.int/wipolex/en/legislation/details/2373)
- [Knesset (legislation portal, EN)](https://main.knesset.gov.il/en/)

**Courts (case-law layer, out of scope for v1):**
- [Supreme Court of Israel (EN)](https://supreme.court.gov.il/sites/en/Pages/home.aspx)
- [Versa — Cardozo Israeli Supreme Court Project, IP topic](https://versa.cardozo.yu.edu/topics/intellectual-property)
- [Versa — Trademarks topic](https://versa.cardozo.yu.edu/topics/trademarks)

**PCT (Israel as ISA / IPEA, 2012-06-01-):**
- [USPTO notice on ILPO as ISA / IPEA](https://www.uspto.gov/sites/default/files/patents/law/notices/ilpo_isa-ipea.pdf)
- [PCT eGuide IL](https://pctlegal.wipo.int/eGuide/view-doc.xhtml?doc-code=IL&doc-lang=en)
- [WIPO Madrid Protocol member list](https://www.wipo.int/madrid/en/members/)

**Detail survey + wave file:**
- [`connectors/israel_pto.md`](../connectors/israel_pto.md) — full 23-asset survey
- [`waves/2026-05-18-priority-2-synopses/il-ilpo.md`](../waves/2026-05-18-priority-2-synopses/il-ilpo.md) — 2026-05-18 grounded API discovery

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-18 | Initial synopsis. Resolved the stale "in_progress" IL/ILPO worktree by splitting register-side (🔴 red_no_api, skip — Angular SPA + reCAPTCHA + Glassbox, ASP.NET WebForms TM/design, bulk-only data.gov.il TM feed) from substantive-law-side (🟢 green, revive `israel_statutes` as `StaticLawCorpus` — same shape as DPMA / Légifrance / IPO India / Taiwan Trade Secrets corpora). Register rating confirms the existing `red_no_api` in STATE.yaml; statutes half lands as `planned`. Same split lens applied to BR/INPI in the sibling wave file. | [`waves/2026-05-18-priority-2-synopses/il-ilpo.md`](../waves/2026-05-18-priority-2-synopses/il-ilpo.md) |
