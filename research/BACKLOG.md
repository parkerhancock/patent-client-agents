# IP Data Connector Backlog

Living index + ranked roadmap of jurisdictions/sources we've surveyed for
`patent-client-agents`. Originally lived at `research/connectors/_index.md`;
moved here 2026-05-16 to sit alongside [`COVERAGE_STRATEGY.md`](COVERAGE_STRATEGY.md)
as the second top-level strategic doc.

## How this doc relates to the rest of `research/`

- [`COVERAGE_STRATEGY.md`](COVERAGE_STRATEGY.md) — the *why* (IP-system layering, substitution rules, decision heuristics)
- **This doc** — the *what next* (ranked work queue with verdicts)
- [`multilateral/`](multilateral/), [`regional/`](regional/), [`national/`](national/) — per-office strategic synopses (current state, distilled from detail surveys + waves + reconciliation)
- [`connectors/`](connectors/) — detail surveys per office (the deep dives, dated mostly 2026-05; treat as canonical detail-research)
- [`waves/`](waves/) — time-stamped research products (frozen audit trail; latest: [`2026-05-16-registered-ip-discovery/`](waves/2026-05-16-registered-ip-discovery/))
- [`templates/`](templates/) — canonical synopsis template

## Reconciliation log — drift between original surveys and current state

The original Tier-1/2/3 surveys below were written before the 2026-05-16
registered-IP discovery wave. Where the wave's grounded research updates
or contradicts the original entries, the divergence is captured here so
the ranked roadmap below stays trustworthy as a planning artifact even
though specific lines are stale.

| Office | Original entry status | 2026-05-16 finding | Source |
|---|---|---|---|
| **KIPO** | "Tier 1 Rank 9-10; gated on confirming foreign-developer ServiceKey path" | API is real and clean, but **ToS §11 explicitly forbids sharing Authentication Keys** — proxy-as-a-service is barred. Architecture must be BYOK (env-gated, per-user keys). | [waves/2026-05-16-registered-ip-discovery/kipo-kipris-plus.md](waves/2026-05-16-registered-ip-discovery/kipo-kipris-plus.md) |
| **DPMA** | "Tier 2; DPMAconnectPlus paid contract" | Cost wasn't the blocker — **contract §3.2 explicitly prohibits passing data to third parties**, which a proxy connector does by definition. Use EPO OPS for DE patents. | [waves/2026-05-16-registered-ip-discovery/dpma-germany.md](waves/2026-05-16-registered-ip-discovery/dpma-germany.md) |
| **UKIPO** | "Tier 2; One IPO REST APIs in build, ships H2-2025/2026; don't scrape registers" | **One IPO Patents Service launched 2026-03-31 without a public search API.** IPO has explicitly stated "exact timeline for releasing APIs is still to be confirmed." Treat as red until announced. | [waves/2026-05-16-registered-ip-discovery/ukipo-uk.md](waves/2026-05-16-registered-ip-discovery/ukipo-uk.md) |
| **CIPO** | "Tier 2; CanLII + bulk + manuals path" | The entire ISED API Catalogue lists 3 APIs total across the department; the only CIPO entry is the Nice-class classification helper. **Zero REST search APIs across patents/TMs/designs.** CanLII remains the recommended path. | [waves/2026-05-16-registered-ip-discovery/cipo-canada.md](waves/2026-05-16-registered-ip-discovery/cipo-canada.md) |
| **WIPO PATENTSCOPE / Global Brand DB / Global Design DB** | "Tier 1 hard skip; ToS forbids automation" | Confirmed and grounded. PATENTSCOPE only offers paid SOAP/SFTP; Brand DB public API is restricted to "collaborating IP Offices"; UI now CAPTCHA-walled with AltCha proof-of-work. The original "skip" verdict stands; undocumented `public-api.branddb.wipo.int` suggests a future partner program. | [waves/2026-05-16-registered-ip-discovery/wipo-global-databases.md](waves/2026-05-16-registered-ip-discovery/wipo-global-databases.md) |
| **EUIPO Designs** | "RCD" terminology throughout | **Terminology changed 1 May 2025** to **REUD** (Registered European Union Design) under Reg. 2024/2822. Design renewal periods are 5/10/15/20 (4 renewals, terminate at year 25); application fees restructured (registration + publication merged into a single application fee). | — |
| **USPTO Trademarks** | "TEAS Plus / TEAS Standard" | TEAS Plus/Standard tiers retired in the 2025 trademark fee rulemaking; current model is a base application fee with surcharges. Patent small/micro discount tiers were adjusted in late 2022 (UAIA). | — |
| **EPO fees** | Default 2024 schedule | EPO schedule updated periodically by Administrative Council decision (see EPO Official Journal `CA/D` references). **Rule 7a EPC micro-entity discount** in force; stackable with Rule 6 language reduction. | — |
| **WIPO Hague Express** | "Tier 1 Rank 14 — polite scrape; trivial" | **CORRECTION: not a separable system.** Hague Express is just a `collection=Hague` filter on the Global Design Database UI — same backend, same compiled JS bundle, same ToS, same robots.txt disallow. There is no Hague-specific public API. The `wipo_hague_express` BACKLOG entry should be considered subsumed under the closed Global Design DB verdict. | [waves/2026-05-16-coverage-batch-2/wipo-hague.md](waves/2026-05-16-coverage-batch-2/wipo-hague.md) |
| **INPI France PISTE** | "Tier 3 Rank 1 — PISTE OAuth2 client + Légifrance + Judilibre" | **CORRECTION: PISTE does NOT host the INPI patent/TM/design APIs.** PISTE only fronts Légifrance / Judilibre / API Entreprise. The INPI register APIs live at `api-gateway.inpi.fr` with **session-bearer + XSRF token bound to a personal data.inpi.fr account** — not OAuth2. Free registration; 10 req/min throttle; 10K daily cap; 10K-result query cap. Right shape is BYOK for TMs + designs (skip patents — EPO OPS covers them). | [waves/2026-05-16-coverage-batch-2/fr-inpi.md](waves/2026-05-16-coverage-batch-2/fr-inpi.md) |
| **PIBD migration** | "summer 2026" | **PIBD jurisprudence froze 2026-03-11** (earlier than projected). Replacement on data.inpi.fr has no published API schema. Route FR IP case law to Judilibre via PISTE instead. | [waves/2026-05-16-coverage-batch-2/fr-inpi.md](waves/2026-05-16-coverage-batch-2/fr-inpi.md) |
| **TIPO Taiwan** | "Tier 3 Rank 3-4 — `cloud.tipo.gov.tw/S220/opdata` bulk + apiKey-header REST" | **API base moved (was `tiponet.tipo.gov.tw`, now `cloud.tipo.gov.tw`); auth corrected: `tk` query param, NOT `apiKey` header.** Swagger 2.0 verified live; 15 GET ops; Taiwan OGDL v1.0 (CC-BY-4.0-compatible AND explicitly permits sublicensing). **TWPAT being retired 2025-04-25** — iPKM at `cloud.tipo.gov.tw/S400` replaced it 2024-12-18. Per-record detail XMLs are on FTPS (proxy ships biblio-only). | [waves/2026-05-16-coverage-batch-2/tw-tipo.md](waves/2026-05-16-coverage-batch-2/tw-tipo.md) |
| **CNIPA China TM platform** | (no prior entry) | **Late 2025 regression: CNIPA's new trademark service requires CN mainland mobile + real-name verification for account registration.** Foreigners are now structurally excluded, not merely throttled. CNIPA's Dec 2024 ST.27 legal-status alignment is a positive drift — strengthens the "route via EPO OPS" recommendation. | [waves/2026-05-16-coverage-batch-2/cn-cnipa.md](waves/2026-05-16-coverage-batch-2/cn-cnipa.md) |
| **DPMA contract re-read** | "red_contract; §3.2 prohibits proxy use" | **CORRECTION: §3.2 prohibits *rebroadcasting the data records*, not self-hosted operation by the contracting party.** DPMAconnectPlus REST permits BYOK (EUR 200 one-time Datenempfänger contract, fixed-IP Basic-auth, no German residency, EU-SCC auto-attached). Moves DPMA register from red_contract → yellow_byok. Synopsis URL `dpmaconnectplusvertragsbedingungen.pdf` 404s; current contract is `standardvertrag_dpmaconnectplus.pdf` (Stand 01.04.2020). | [waves/2026-05-18-priority-2-synopses/dpma-byok-rating.md](waves/2026-05-18-priority-2-synopses/dpma-byok-rating.md) |
| **BR/INPI register vs. statutes split** | "yellow_paid; in_progress" | **Register is red_no_api** (live UI is CAPTCHA + ToS-hostile; RPI weekly XML + dados.gov.br annual are bulk-only — violates zero-infra-proxy). 2026-05 RPI-bulk worktree closes out. **LPI 9.279/1996 (PT + WIPO Lex EN) salvages** as a separate `BR/LPI/Statute` corpus under the static-law-module pattern. | [waves/2026-05-18-priority-2-synopses/br-inpi.md](waves/2026-05-18-priority-2-synopses/br-inpi.md) |
| **SG/IPOS register vs. statutes split** | "red_no_api; in_progress" | **Register closure confirmed** (IP2SG Singpass/CorpPass-gated to SG entities; data.gov.sg collection 281 patents frozen Aug 2018→Oct 2020; Digital Hub is __VIEWSTATE HTML). **2026-05 statutes worktree revives** as `SG/IPOS/Statute` corpus — sso.agc.gov.sg + IPOS PDFs are stable primary sources. |  [waves/2026-05-18-priority-2-synopses/sg-ipos.md](waves/2026-05-18-priority-2-synopses/sg-ipos.md) |
| **IL/ILPO register vs. statutes split** | "red_no_api; in_progress" | **Register closure confirmed** (Angular SPA + CSRF + reCAPTCHA + Glassbox session-capture is an explicit anti-automation perimeter; ASP.NET WebForms for TM/Design; data.gov.il TM CKAN feed bulk-shaped). **8 statutes salvage** as `IL/ILPO/Statute` — WIPO Lex has ILPO-authoritative EN translations of all of them (incl. Commercial Torts Law 5759-1999 standalone trade-secrets statute). | [waves/2026-05-18-priority-2-synopses/il-ilpo.md](waves/2026-05-18-priority-2-synopses/il-ilpo.md) |
| **RU/Rospatent + sanctions update** | "red_blocked; statutes only" | Register closure locked permanently. **EU 18th sanctions package (in force 19 Jul 2025)** extended No-Russia clauses to IP/know-how/trade secrets — load-bearing for downstream EU consumers. WIPO has NOT suspended RU (PCT/Madrid/Hague still routing). **Russian Civil Code Part IV** (WIPO Lex 22547, consolidated through 2024, 326 articles / 9 chapters) recommended as `RU/CivilCode/Part4` corpus — replaces 7–8 separate RU statute mirrors, never queries a Russian server. | [waves/2026-05-18-priority-2-synopses/ru-rospatent.md](waves/2026-05-18-priority-2-synopses/ru-rospatent.md) |

**Status of the original ranked roadmap below:** still useful as a build-priority artifact, but every entry should be cross-checked against the reconciliation log above and the per-office synopsis files before commitment. The synopses are the current-state source of truth; this doc is the strategic queue.

---

## What we already have

| Module | Coverage |
|---|---|
| `uspto_odp` | US patent applications, PTAB, petitions |
| `uspto_applications` | High-level wrapper over ODP |
| `uspto_publications` | PPUBS (public search) |
| `uspto_assignments` | Patent assignments |
| `uspto_office_actions` | Office-action rejections, citations, full text |
| `uspto_petitions` | USPTO petitions |
| `uspto_bulkdata` | USPTO bulk-data product catalog |
| `uspto_tsdr` | US trademark status & document retrieval |
| `uspto_trademark_assignments` | TM assignments |
| `epo_ops` | EPO Open Patent Services (also surfaces CN via INPADOC) |
| `google_patents` | Google Patents scraping |
| `jpo` | Japan Patent Office |
| `cpc` | CPC classification lookups |
| `mpep` | Manual of Patent Examining Procedure |
| `tmep` | Trademark Manual of Examining Procedure |

In `law-tools` (portable into PCA if useful):
`copyright`, `legal_statutes`, `govinfo`, `federal_register`, `federal_rules`,
`uspto_tmsearch`, `agency_guidance`, `cafc`, `courtlistener`, `pacer`,
`scotus`, `sec_edgar`.

## How to read this folder

- `_index.md` (this file) — prioritized roadmap, cross-cutting notes
- `<office>.md` — per-jurisdiction survey: assets, auth, rate limits, formats, v1 scope, skip list, open questions
- New offices: copy an existing survey as a template; keep the cross-asset comparison table on top

---

# Tier 1 — Surveyed

WIPO, EUIPO, CNIPA, KIPO. Reports in this folder. Below is the synthesis.

## Tier 1 buildable v1 scope (ranked by leverage)

Ranked by (data value) × (access cleanliness) ÷ (engineering cost). Where two
connectors share auth/SDK pattern, they're grouped — the second is near-free
once the first is built.

| Rank | Module | Source | Why |
|---|---|---|---|
| 1 | `euipo_trademarks` | EUIPO Trademark Search API | OAuth 2.0 + OpenAPI 3 JSON, ~2M marks, modern stack, natural EU sibling to `uspto_tsdr` |
| 2 | `euipo_designs` | EUIPO RCD Search API | Same OAuth infra as #1, ~1.7M designs since 2003, image binaries |
| 3 | `euipo_bulkdata` | EUIPO Open Data Platform | Daily XML dumps, mirrors `uspto_bulkdata` pattern exactly |
| 4 | `wipo_lex` | WIPO Lex | Free polite scrape; ~50k statutes/treaties/decisions across ~200 jurisdictions; the *universal* substantive-law backbone |
| 5 | `eurlex_cellar` | EUR-Lex CELLAR (SPARQL + REST) | One client covers CJEU/General Court IP rulings AND EU statutory law (EUTMR 2017/1001, CDR 6/2002, Trade Secrets Dir 2016/943, GI Reg 2024/1143). Free, no auth |
| 6 | `euipo_guidelines` | EUIPO Examination Guidelines (TM + Design) | Static HTML/PDF; mirrors `mpep` / `tmep`; cheap |
| 7 | `wipo_patentscope_bulk` | PCT SFTP raw-data feed | paid SFTP; weekly XML for ~280k PCT/yr; cleanest WIPO data deal |
| 8 | `wipo_article6ter` | Article 6ter Express API | Free REST/JSON, no auth, small dataset (state emblems / IGO marks); 1-2 day wrapper |
| 9 | `kipo_kipris_patents` | KIPRIS Plus — patent endpoints | XML over ServiceKey; ~46 services × 126 products; **gated on confirming foreign-developer ServiceKey path** |
| 10 | `kipo_kipris_trademarks` | KIPRIS Plus — TM endpoints | Same auth as #9; Nice classes localize to EN; low marginal cost |
| 11 | `kr_statutes` | `law.go.kr/eng` fetcher | Patent / Trademark / Design Act + UCPA (trade secrets); small static fetcher mirroring `mpep` |
| 12 | `cn_via_epo_ops` | Extend `epo_ops` with CN helpers | Free, already-built backbone; `get_cn_biblio` / `get_cn_legal_events` recipes covering ~95% of practical CN patent needs |
| 13 | `wipo_patentscope_cn` | WIPO PATENTSCOPE CN feed | Free; full-text where EPO OPS lacks it; English MT |
| 14 | `wipo_hague_express` | Hague Express (post-2022 CN designs included) | Free polite scrape; trivial; also covers other Hague-system designs |
| 15 | `cn_statutes` | Static CN law corpus | Patent Law (2020), Implementing Regs (2024), Examination Guidelines (2026 ed.), Trademark Law, AUCL (trade secrets), Copyright Law, GI/PVP Regs — mirror once from WIPO Lex, expose article-by-article like `mpep` |
| 16 | `cn_gi` | CNIPA + MARA GI lists | Static tables, quarterly refresh, small |
| 17 | `cn_plant_variety` | MARA PVP browse | Browse-only HTML, no auth, ~25k records |

## Tier 1 hard skips

Across all four offices, these are *not worth* the engineering effort right now:

- **WIPO Global Brand Database** and **Global Design Database** — ToS forbids automation, anti-scrape defenses, not redistributable
- **Madrid Monitor bulk XML** — paid bulk; budget conversation, not engineering
- **PATENTSCOPE SOAP search service** — paid SOAP, poor stack fit; SFTP bulk gives most of the data cheaper
- **UPOV PLUTO** consumer side — no public bulk path, niche
- **CNIPA PSS / SBJ direct scrape** — CAPTCHA + JS + ToS-hostile + brittle; go via EPO OPS / Patentscope
- **CNIPA bulk data contracts** — need a Chinese entity counterparty
- **wenshu.court.gov.cn (Chinese court records)** — Chinese phone required since 2021-08, 600-result cap, effectively closed
- **K-PION** — inter-office only, not available to private developers
- **KSVS plant varieties** — niche, no API
- **NAQS Korean GIs** — no API; KIPO collective marks cover the agent use case
- **EUIPO eSearch Case Law** / **TMview / DesignView / TMclass / GIview** scraping — no documented API; contract-drift risk; for EU content use Open Data + CELLAR instead
- **eAmbrosia / GIview wrappers** — mid-migration to EUIPO under Reg. 2024/1143; wait for dust to settle

## Tier 1 open questions to resolve before scoping work

1. **EUIPO API quota numerics** — only the 429 error contract is published; real plan limits require a sandbox app or `apiteam@euipo.europa.eu`
2. **EUIPO OAuth flow** — confirm whether `clientCredentials` works for all read operations or some are gated to 3-legged `accessCode`
3. **KIPRIS Plus ServiceKey for foreigners** — `kiprisplus@kipi.or.kr` is the documented manual path; needs a real test before committing to a launch date
4. **KIPRIS Plus redistribution ToS (Articles 19-21)** — unclear whether the CoWork allowlist's cache-and-serve model counts as redistribution; legal read needed before exposing `download_url`
5. **WIPO Lex licensing for systematic mirroring** — statutes themselves are public-domain, but WIPO's bibliographic metadata layer may have separate ToS
6. **PCT SFTP feed scope** — does it include reassignments / legal-status updates, or only publication-week snapshots? (`patentscope@wipo.int`)
7. **CN 2026 Examination Guidelines translation lag** — ship current EN edition + CN diff, or wait for official EN?
8. **GI authority transfer (Reg. 2024/1143)** — eAmbrosia URL still on `ec.europa.eu/agriculture`; track migration to EUIPO infra

---

# Tier 2 — Surveyed

UKIPO, DPMA, CIPO, IP Australia, IPO India, INPI Brazil. Reports in this folder.
Below is the synthesis — the key headline is that **digital maturity varies wildly**, even among major Western offices.

## Tier 2 office digest

| Office | Live REST? | Bulk data? | Key v1 path | Standout / gotcha |
|---|---|---|---|---|
| **IP Australia** | OAuth 2.0 JSON ✓ | IP RAPID weekly CC-BY ✓✓ | Wrap full API + bulk | **Likely the easiest connector on the entire roadmap.** All four IP rights from one agency; OpenAPI'd; no prior Python client |
| **CIPO** | None (mid-NGP migration) | IP Horizons ST.36 weekly ✓ | CanLII + bulk + manuals | **CanLII is the real prize** — free JSON REST covering FC/FCA/SCC + TMOB + PAB + statutes. More developer-friendly than half the patent offices |
| **DPMA** | DPMAconnectPlus paid contract; no free REST | Paid backfile only | DEPATISnet scrape + gesetze-im-internet + RiI XML | **Utility models (Gebrauchsmuster) only path** — EPO OPS doesn't cover them; Germany is the heavy GM jurisdiction |
| **UKIPO** | **Coming H2-2025/2026** ("One IPO" REST APIs in build) | TMJ weekly XML; on-request bulk | MoPP + TM Manual + statutes (legislation.gov.uk CLML/AKN) | **Don't scrape registers** — they'll be obsoleted in ~12 months when One IPO ships |
| **INPI Brazil** | None | RPI XML weekly ✓ + dados.gov.br annual ✓ | RPI XML parser + LPI mirror | **Unified LPI statute** (Lei 9.279/96 covers patents, designs, marks, GIs, trade secrets in one law) — feature for static-law module pattern |
| **IPO India** | **Zero** | None | Static law/MPPP + Patent Journal PDFs + Delhi HC IPD | Every live asset is CAPTCHA-gated; canonical records are 200-500MB weekly PDF journals; lean on static side |

## Tier 2 buildable v1 scope (ranked)

| Rank | Module | Source | Why |
|---|---|---|---|
| 1 | `ip_australia` (full) | IP RAPID weekly bulk + Patents/TM/Designs REST APIs | Cleanest stack surveyed; one sprint covers all four IP rights with weekly freshness, CC-BY 2.5 AU, no per-call fees |
| 2 | `canlii` | CanLII REST | Free JSON API key, async-ready; covers Patent Act, Trademarks Act, FC/FCA/SCC IP rulings, TMOB + PAB decisions in one client |
| 3 | `cipo_bulkdata` | CIPO IP Horizons (ST.36 weekly XML + TM XML+PNG + quarterly research CSV) | Mirrors `uspto_bulkdata` exactly; free, no auth, comprehensive |
| 4 | `cipo_manuals` | MOPOP / TEM / IDOP S3 single-HTML mirrors | One GET per manual; mirrors `mpep`/`tmep` shape |
| 5 | `dpma_depatisnet` | DEPATISnet expert-search scrape + per-doc PDF fetch | Only path to German utility model (Gebrauchsmuster) corpus; EPO OPS doesn't expose GM as a distinct right-type |
| 6 | `de_statutes` | gesetze-im-internet.de per-act XML zip | PatG / MarkenG / GebrMG / DesignG / UrhG / GeschGehG; English PDFs from DPMA Language Service for several |
| 7 | `de_caselaw` | rechtsprechung-im-internet.de XML + CE-BPatG Zenodo dump | BGH (daily XML feed) + BPatG (deep Zenodo corpus) — real DE patent-litigation data layer |
| 8 | `ukipo_mopp` | UK Manual of Patent Practice | Static HTML, OGL v3.0; ~1 day, mirrors `mpep` exactly |
| 9 | `ukipo_tm_manual` | UK Manual of Trade Marks Practice | Same shape as #8, pairs to give complete UK examination corpus |
| 10 | `uk_statutes` | legislation.gov.uk CLML + Akoma Ntoso fetcher | PA 1977, TMA 1994, RDA 1949, CDPA 1988, Trade Secrets Regs 2018; **point-in-time queries** (a feature `legal_statutes` USC fetcher can't match) |
| 11 | `inpi_rpi` | INPI Brazil RPI weekly bulletin (ZIP+XML) | Eight sections (patents, TM, designs, GIs, IC topographies, software, tech contracts, communications); stable schema since 2017-01-31; spine of all BR coverage |
| 12 | `inpi_opendata` | dados.gov.br annual biblio dumps | Thin CKAN wrapper + ZIP+CSV reader; pairs with RPI for current vs. historical |
| 13 | `brazil_law` | LPI 9.279/96 + Lei 9.609 + 9.610 + 9.456 + 11.484 + Bloco I + Bloco II | Unified-statute design is a feature; one mirror replaces 4-5 separate statute corpora |
| 14 | `in_statutes` | Indian Patents Act / TM Act / Designs Act / GI Act / Copyright Act / PPV&FR + Patents Rules 2024 + MPPP | Mirror once from indiacode.nic.in + ipindia.gov.in; zero CAPTCHA, full text always available |
| 15 | `in_journals` | IPO India Patent Office Journal + Trade Marks Journal (weekly PDFs) | Predictable URLs, no auth, mechanically trivial — but ~50GB/yr storage; canonical source for Controller decisions |
| 16 | `in_delhi_hc_ipd` | Delhi HC IP Division docket | Only post-IPAB appellate substrate; structured, free, reliable, growing fast |
| 17 | `cipo_decisia` (stretch) | TMOB + PAB Decisia RSS + HTML | Use CanLII for the JSON path; Decisia HTML/RSS only as fallback for full text |
| 18 | `uk_caselaw` (stretch) | Find Case Law public API + LegalDocML | Patents Court / IPEC / CoA / UKSC; **gated on whether to apply for the free R&D computational-use licence** |
| 19 | `au_austlii` (stretch) | AustLII SINO CGI for APO hearings + Federal Court IP | Niche; defer until tribunal coverage demand emerges |

## Tier 2 hard skips

- **DPMAconnectPlus (v1)** — contract paperwork + username/password (generationally behind EUIPO OAuth); reconsider only if a paying customer needs DE prosecution file wrappers
- **DPMA paid backfile XML** — redundant with EPO OPS for DE patent publications
- **MyCIPO Patents** — account-scoped, no public API; revisit post-NGP
- **CPD / Canadian TM / Canadian Designs live scrapers (v1)** — viable but brittle mid-NGP; bulk + CanLII covers most needs
- **Ipsum / One IPO Search scraping (v1)** — wait for the H2-2025/2026 REST API; brittle scraper now obsoleted in 12 months
- **UK TM and Design register scraping (v1)** — same reasoning; revisit when One IPO TM/Design APIs ship
- **BAILII** — ToS forbids automated crawling; use Find Case Law instead
- **InPASS scraping (v1)** — CAPTCHA + ASP.NET viewstate + frequent downtime; EPO OPS / Google Patents / Patentscope cover biblio
- **TM Public Search / Designs Public Search (IN)** — CAPTCHA-everywhere; commercial providers exist for hard requirements
- **Form 27 bulk (IN)** — no index, no API; per-patent CAPTCHA iteration; specialty project only
- **pePI scraping (BR)** — CAPTCHA + ToS-hostile; RPI XML + dados.gov.br reconstruct equivalent data
- **TRF/PJe court dockets (BR)** — fragmented per region, no API; use commercial aggregators if needed
- **UPC CMS API** — important but orthogonal to DPMA; spin out as its own connector card

## Tier 2 open questions

1. **One IPO API release timing and shape** — OAuth-gated or open? OpenAPI before GA? Contact `information@ipo.gov.uk`
2. **Find Case Law licensing** — does the free R&D computational-use licence permit caching under CoWork's allowlist model? May need transactional licence
3. **CIPO NGP roadmap** — public bibliographic REST API on the horizon, or staying ST.96-internal? Watch CIPO WIPO CWS contributions
4. **IP RAPID layout** — same ~40 IPGOD tables, or a leaner registry slice? Fetch the dataset page; data dictionary not yet inspected
5. **DPMA DEPATISnet scrape etiquette** — no explicit robots policy beyond standard; confirm acceptable QPS empirically with a `User-Agent` identifying patent-client-agents
6. **RPI XML schema versioning** — INPI bumps layouts periodically (`...versao_103.pdf`). Pin and migrate, or auto-detect?
7. **IPO India CAPTCHA strategy** — ship 2Captcha/Anti-Captcha integration as optional dep, or hard-skip every CAPTCHA-gated endpoint?
8. **IPO India journal storage** — patent journals 200-500MB/week (~50GB/yr). Ingest+strip-to-text and discard PDFs, or mirror PDFs?
9. **CanLII redistribution ToS** — does it permit caching detail JSON and re-exposing via our MCP tool? Confirm with their feedback channel before scaling key usage
10. **EUR-Lex CELLAR ECLI vs CE-BPatG identifiers** — required for cross-linking BPatG/BGH to EU CJEU IP decisions

---

# Combined buildable v1 leaderboard (Tier 1 + Tier 2 + Tier 3)

Top 16 across all tiers + UPC by leverage (data value × access cleanliness ÷ engineering cost):

1. **`ip_australia`** (T2) — full OAuth suite + IP RAPID weekly bulk. One sprint, four IP rights, no prior Python competitor.
2. **`euipo_trademarks` + `euipo_designs` + `euipo_bulkdata`** (T1) — modern OAuth on shared scaffolding; ~3.7M TMs + 1.7M designs.
3. **`canlii`** (T2) — free JSON REST covering Canadian courts + statutes + TMOB + PAB. Highest leverage per LOC of anything surveyed.
4. **`piste_dila` + `legifrance` + `judilibre`** (T3) — one OAuth client, two APIs: French statutes (CPI + Code commerce L.151 trade secrets) and IP case law (Cass + CA Paris + TJ Paris 3e chambre IP from 2024-12-31).
5. **`upc_cms` + `upc_decisions` + `upc_statutes` + `epo_ops` UP helpers** (UPC) — Unified Patent Court coverage: case lookups via OAuth2 Public API + PDF/A decision harvester + UPCA/RoP/Fees + opt-out and Unitary Patent register helpers on existing EPO OPS. **Opt-out registry is the unique high-value asset** (answers "is this EP in UPC jurisdiction?"). No prior Python tooling; commercial trackers (JUVE, Bristows, Unified Patents Portal) are HTML UIs only.
6. **`wipo_lex`** (T1) — universal substantive-law backbone (~50k docs, ~200 jurisdictions); unlocks statute coverage everywhere else.
7. **`eurlex_cellar`** (T1) — CJEU IP rulings + EU statutory law in one SPARQL/REST client; useful far beyond EUIPO.
8. **`cipo_bulkdata` + `cipo_manuals`** (T2) — ST.36 weekly + S3 single-HTML manuals; both mirror existing PCA patterns exactly.
9. **`tipo_bulkdata` + `tipo_api` + `tw_statutes`** (T3) — TIPO ships a real REST API + clean bulk portal + standalone Trade Secrets Act in EN; one of the cleanest non-IP5 stacks surveyed.
10. **`dpma_depatisnet` + `de_caselaw`** (T2) — only path to Gebrauchsmuster corpus + real DE patent-litigation data layer.
11. **`ukipo_mopp` + `ukipo_tm_manual` + `uk_statutes`** (T2) — MPEP-shape × 2 + CLML statute fetcher with point-in-time queries.
12. **`wipo_patentscope_bulk`** (T1) — paid SFTP for weekly PCT XML; cleanest WIPO data deal.
13. **`inpi_rpi` + `brazil_law`** (T2) — weekly XML bulletin + unified LPI corpus; whole BR stack in two modules.
14. **`israel_statutes` + `israel_data_gov_il`** (T3) — 8-statute mirror (incl. unusual Commercial Torts Law statutory trade secrets) + weekly TM CKAN feed; statute-heavy "register-light" build pattern.
15. **`inpi_bulk`** (T3) — INPI SFTP for D&M ST.86 (parser shared with EUIPO) + patents/TM weekly XML; bulk-first pattern, defer live INPI API to v2.
16. **`sg_statutes` + `sg_manuals` + `sg_datagovsg`** (T3) — Singapore Statutes Online + IPOS examination/work manuals + thin data.gov.sg wrapper; modest but covers the SG agent surface.

**Below the leaderboard but still in scope** (T1+T2+T3):
- KIPO (T1) — pending foreign-developer ServiceKey verification
- CN coverage (T1) — best as recipes on `epo_ops` + `wipo_lex`, not a standalone module
- IPO India (T2) — static law/MPPP + Patent Office Journals + Delhi HC IPD docket
- IN/BR/KR statutes via the universal `StaticLawCorpus` pattern
- Stretch goals: `cipo_decisia`, `uk_caselaw` (Find Case Law w/ licence), `au_austlii`, `inpi_directives`, `israel_examination_guidelines`, `versa_supreme_court`, `sg_caselaw`, `aripo_journal`, `ru_statutes` (statutes only — live RU connector is skipped)

**Tier 3 skips (do nothing):** OAPI, GCC + member-state offices except SAIP watch list, live Rospatent/FIPS, ARIPO standalone module.

---

---

# Tier 3 — Surveyed

TIPO Taiwan, IPOS Singapore, INPI France, Rospatent, ARIPO, OAPI, GCC Patent Office, Israel PTO. Reports in this folder. Headline: **digital maturity varies even more wildly than Tier 2**, and four of the eight offices are dominated by existing/planned coverage (skip verdicts).

## Tier 3 office digest

| Office | Verdict | One-line summary |
|---|---|---|
| **INPI France** | **Build** | data.inpi.fr is a real EUIPO-grade bulk channel + **PISTE OAuth2** unlocks Légifrance (CPI + Code commerce L.151 trade secrets) and Judilibre (TJ Paris IP chamber from 2024-12-31, Cour de cassation, CA Paris) in one client |
| **TIPO Taiwan** | **Build** | Real REST API + clean bulk portal + standalone **Trade Secrets Act in English** (Taiwan was 2nd country after Sweden with one); IP Court docket Chinese-only — skip; non-WIPO-member, no PCT/Madrid/Hague/INPADOC bridges |
| **Israel PTO** | **Build (statute-heavy, register-light)** | Register portal is Angular SPA with reCAPTCHA + Glassbox — skip; data.gov.il CKAN has weekly TM dataset; **8 IP statutes have authoritative EN translations** on WIPO Lex; Commercial Torts Law 5759-1999 is unusual statutory trade-secret regime with statutory damages |
| **IPOS Singapore** | **Build (modest)** | IP2SG transactional APIs CorpPass-gated to SG entities — skip; data.gov.sg shallow (patents frozen Aug 2018-Oct 2020, TM current to May 2025); v1 is static law + manuals + thin open-data wrapper. Materially behind IP Australia on open-API maturity despite reputation |
| **Rospatent** | **Skip live; ship statutes only** | OFAC GL 31 permits reads, but Decree 299 zeros foreign-patentee compensation from "unfriendly states" + Decree 430 gates IP acquisition. Economics + hostility = skip live; ship `ru_statutes` (Civil Code Part 4) + EPO OPS RU recipes |
| **ARIPO** | **Skip standalone** | Patent/design coverage already in `epo_ops` (country code `AP`); Banjul/Harare/Arusha/Swakopmund protocols already mirrored in WIPO Lex; only marginal asset is monthly ARIPO JOURNAL PDFs (optional ~2-3 day overlay) |
| **OAPI** | **Skip** | Patents already in `epo_ops` (country code `OA`); Bangui Agreement (10 annexes — unified statute pattern like Brazil LPI) already in WIPO Lex; no public REST, no online register, no bulk feed |
| **GCC Patent Office** | **Skip all six** | Closed for new applications since 2021-01-06; existing unitary register sunsets toward ~2041. Of six national offices, only SAIP has a usable public search UI. Watch list, not v1 |

## Tier 3 buildable v1 scope (ranked)

| Rank | Module | Source | Why |
|---|---|---|---|
| 1 | `piste_dila` + `legifrance` + `judilibre` | DILA PISTE OAuth2 broker | **One OAuth client, two APIs**. CPI + Code commerce L.151 (trade secrets — they sit in commercial code, NOT in CPI) + Cass / CA Paris pôle 5 / TJ Paris 3e chambre IP cases. The TJ Paris feed turns France from "covered by EPO+EUIPO" into "covered end-to-end including litigation intelligence" |
| 2 | `inpi_bulk` | INPI SFTP weekly XML — patents + TMs + designs (ST.86 v1.0, shared with EUIPO) | Real bulk channel comparable to EUIPO Open Data; ahead of DPMA (paid). Free after registration. ST.86 parser amortizes with `euipo_designs` |
| 3 | `tipo_bulkdata` | `cloud.tipo.gov.tw/S220/opdata` weekly gazettes | No auth, ZIP+XML, stable schema; mirrors `uspto_bulkdata` / `euipo_bulkdata` / `cipo_bulkdata` / `inpi_rpi`. Highest-leverage TIPO asset |
| 4 | `tipo_api` | TIPO OpenData REST API (apiKey header) | Closest TIPO equivalent to USPTO ODP; biblio-only. Has published OAS spec |
| 5 | `tw_statutes` | Taiwan IP statutes on `law.moj.gov.tw/ENG` | 7 statutes including **standalone Trade Secrets Act** + IC Layout + Patent Linkage Regs; ~1 day on `StaticLawCorpus` |
| 6 | `israel_statutes` | 8 Israeli IP statutes from WIPO Lex (Patents Law 5727-1967, TM Ordinance, Designs Law 5777-2017, **Commercial Torts Law 5759-1999**, Plant Breeders' Rights Law, Copyright Act, AO/GI Law, Patent Regs) | All have authoritative EN translations by ILPO; Commercial Torts Law is unusual statutory trade-secret regime worth its own row |
| 7 | `israel_data_gov_il` | data.gov.il CKAN — weekly TM dataset | Only confirmed structured ILPO feed; Singapore-style "free, weekly, attribution" pattern. Open question: do patents/designs datasets exist alongside? |
| 8 | `sg_statutes` | Singapore Statutes Online (`sso.agc.gov.sg`) | Patents Act 1994, TMA 1998, RDA 2000, Copyright Act 2021, GIA 2014, PVPA 2004, Layout-Designs Act 1999. One fetch, MPEP-shape |
| 9 | `sg_manuals` | IPOS Patent Examination Guidelines + TM/Design Work Manuals + Practice Directions | Free, English, PDF; mirror once via `StaticLawCorpus` |
| 10 | `sg_datagovsg` | data.gov.sg IPOS APIs + curated datasets | Real open-data tier under Singapore Open Data Licence; TM register current to May 2025 |
| 11 | `sg_journals` | IPOS Patent + Trade Marks Journals (weekly PDFs from Digital Hub) | Predictable URLs; fills the data.gov.sg patent-API freshness gap |
| 12 | `ru_statutes` | Civil Code of the Russian Federation Part 4 (WIPO Lex 22106) + Decree 299 + Decree 430 | Same `StaticLawCorpus` pattern as DE/UK/BR/IN/CN. Live RU connector is a skip for economics reasons; statutes are still legitimate to mirror |
| 13 | `inpi_directives` (stretch) | INPI examination directives (Patents, TM, Designs) — PDF | Half-day each via `StaticLawCorpus`. French-only — agent value depends on French-capable caller or MT |
| 14 | `israel_examination_guidelines` (stretch) | ILPO `work-procedure-db` PDFs (EN subset) | Per-procedure PDFs, less unified than MPEP/TMEP; mirror EN-available subset |
| 15 | `versa_supreme_court` (stretch) | Cardozo Versa — ~700 EN Israeli Supreme Court translations | Free, public-mission, static HTML. Also a precedent for any future Versa-style curated translation source in other jurisdictions |
| 16 | `aripo_journal` (stretch) | ARIPO JOURNAL monthly PDFs from `eservice.aripo.org/ppb/pjd/` | ~130 issues since 2015; the only ARIPO-direct asset that adds value over `epo_ops` + `wipo_lex` |

## Tier 3 hard skips

- **ILPO Patents Search SPA** — Angular + reCAPTCHA + Glassbox; biblio duplicated by EPO OPS INPADOC; file-wrapper PDFs the only unique value
- **Israel TM/Designs register scraping** — data.gov.il TM feed + Hague Express (Tier 1) dominate
- **TWPAT / TWPAT-simple / TWPAT6 scraping** — JS + anti-proxy + session cookies; route via TIPO API + bulk
- **GPSS (Taiwan)** — account-gated; TW portion overlaps bulk; foreign coverage via EPO OPS / Google Patents / USPTO ODP already
- **TIPO judgment.judicial.gov.tw / IPCC scraping** — no API; CN-only; Lawsnote paywalled
- **IP2SG transactional APIs** — CorpPass + GIRO + SG-entity gating
- **IPOS Digital Hub ASP.NET WebForms scraping** — brittle and redundant with data.gov.sg + journals
- **LawNet (Singapore)** — paywalled; WorldLII/CommonLII for SGHC/SGCA
- **eLitigation scrape (SG)** — same WebForms brittleness; ToS unclear
- **ASPEC metadata** — no public API; visibility comes through national records
- **PIBD direct scrape** — migrating to data.inpi.fr summer 2026; scraper obsoleted in months
- **INAO scraping (FR GIs)** — Reg 2024/1143 moved industrial/artisanal GIs to EUIPO; agri/wine via EC eAmbrosia
- **RNE direct wrapper for IP work** — `pappers_api` (commercial third-party) covers assignee normalization
- **FIPS / Rospatent scraping** — see Rospatent skip verdict above
- **EAPATIS** — Eurasian Patent Office; rides on Rospatent compliance/economics analysis; skip
- **ARIPO Regional IP Database scraping** — robots.txt `Disallow: /` + `Crawl-delay: 600`; Apache Tomcat 7.0.47 + Struts; covered by `epo_ops` AP code
- **OAPI WIPO Publish HTML scrape** — bare IPv4 endpoint; covered by `epo_ops` OA code
- **GCCPO + Gulf member-state register scraping** — see GCC skip verdict
- **Nevo / Takdin (Israel)** — subscription, scrape-hostile

## Tier 3 watch list (re-check quarterly)

1. **PIBD migration to data.inpi.fr** — announced for summer 2026; if it ships with a real REST/JSON API, French case-law coverage gets cheaper
2. **SAIP API under Saudi Vision 2030** — Saudi Arabia's IP office is the only Gulf national that might flip from skip to build
3. **UAE MoET "Patent Hive" 2025 initiative** — could expand UAE Open Data
4. **GCCPO replacement regime** — discussions of a relaunched or replaced unified Gulf patent
5. **TIPO Trade Secrets Act 2024-2025 draft amendment** — raises criminal exposure to NT$10M / 5 years (NT$50M cross-border); pin current version
6. **TIPO `g0v` projects / Judicial Yuan open court data** — if a Lawsnote-equivalent open feed appears, IP Court (IPCC) flips from skip to in-scope
7. **Russia sanctions environment** — material change could re-open the FIPS connector question
8. **ARIPO Arusha Protocol (plant varieties)** in force 2024-11-24 — adoption pace matters
9. **OAPI 2024 Bangui revision** — Annexes I/II added substantive examination + pre-grant opposition effective 2025-01-01
10. **WIPO Lex "Taiwan Province of China" labeling** — political; decide jurisdiction string for client output
11. **Singapore ASPEC+ April 2026 metadata exchange** — any PCT-PPH-style XML feed worth tracking?

---

# UPC (Unified Patent Court) — targeted survey

Surveyed separately because it's a transnational court, not a Tier 1/2/3 jurisdiction. Launched 1 June 2023; ~17 EU members participate (Romania joined Sept 2024; ES + HR non-signatories; CY, CZ, EL, HU, IE, PL, SK signatories not yet ratified). Court of First Instance has Local + Regional + Central Divisions (Munich / Paris / **Milan**, the latter being the post-Brexit replacement for London for life sciences); Court of Appeal sits in Luxembourg.

## UPC asset digest

| Asset | Endpoint | Auth | Format | Verdict |
|---|---|---|---|---|
| **CMS Public API v1.4** | `api-prod.unified-patent-court.org/upc/public/api/v4/` | OAuth2 bearer (1800s; X-API-KEY retired) | JSON | **Build** — but during new-CMS transition only `search_case` / `search_case_types` / `list_languages` are guaranteed; other endpoints need live validation |
| **Decisions index** | `/en/decisions-and-orders` | None | HTML index → per-decision PDF/A | **Build** — PDF/A is mandated format; case IDs `UPC_CFI_n/yyyy` / `UPC_CoA_n/yyyy`; EN/FR/DE plus local LD language; **no native ECLI**; no structured JSON feed |
| **Opt-out registry** | UI list at `/en/registry/opt-out` + CMS read endpoint | None for UI; CMS gated | HTML / JSON | **Build — highest-leverage UPC asset.** Tells you whether a traditional EP patent is in UPC jurisdiction; pairs with `epo_ops` to answer that for any EP number |
| **Unitary Patent register** | Lives at **EPO**, not UPC | None | Per EPO Register | **Extend `epo_ops`** — Register service supports UP search; UPP marker C0, B7000/B920 elements in B8/B9 publications carry status. Helpers, not a new module |
| **A2A API v2.6** | `cms.unified-patent-court.org` (A2A) | OAuth2 | JSON | **Skip** — regulated representative filing channel; no agent value |
| **Legal texts** (UPCA, RoP 18th ed., Fee schedule, Code of Conduct) | `/en/court/legal-documents` | None | HTML / PDF | **Build via `StaticLawCorpus`** |
| **Hearing schedules** | Per division calendars | None | HTML | Optional — small and per-division |

## UPC v1 scope

| Rank | Module | Why |
|---|---|---|
| 1 | `upc_cms` | OAuth2 Public API for case lookups; **fourth bench-test of `OAuth2ClientCredentialsClient`** after EUIPO / IP Australia / PISTE — by the time this lands the abstraction is hardened |
| 2 | `upc_decisions` | PDF/A harvester for the public decisions index; structured per-case metadata + decision text; pairs with planned `de_caselaw` and `judilibre` for citation graphs |
| 3 | `upc_statutes` | UPCA + Rules of Procedure (18th ed.) + Fee schedule + Code of Conduct via `StaticLawCorpus` |
| 4 | `epo_ops` UP helpers | Wrap `get_unitary_patent_status(ep_number)` + `get_opt_out_status(ep_number)` as recipes on existing EPO OPS — no new module |

## UPC skip list

- **A2A API** — representative filing channel, requires regulated UPC representative credentials; out of scope
- **Hearing schedules per division** — small and per-LD; defer
- **Confidential dockets** — much UPC docket data is sealed; only public layer is in scope

## UPC open questions

1. **Public API endpoint surface post-transition** — only 3 endpoints currently confirmed accessible (the new CMS migration is ongoing); need live registration to validate the rest
2. **ECLI assignment** — UPC decisions don't have native ECLI; do we synthesize an ID compatible with `StructuredCaseLawClient`?
3. **Opt-out CMS endpoint vs UI list parity** — are they the same data, or does CMS expose richer per-patent metadata?
4. **Redistribution ToS** — UPC's data-reuse stance for cache-and-serve through MCP not explicitly documented
5. **Volume trajectory** — ~883 cases by May 2025; JUVE reports 50% YoY infringement growth in 2025. Storage budget for PDF/A decisions over 5 years?

## What UPC fills in EU coverage

UPC was the unanswered piece in the previous European-coverage question: it gives us a **transnational court layer** that no Tier 1/2/3 surveys covered. Combined with the planned EUIPO trio + `eurlex_cellar` + DE/FR national courts + UKIPO (UK is non-UPC but adjacent), this rounds out European IP litigation coverage to the practical limit for the participating-state subset. **Coverage gap that remains**: ES, PL, HR, IE national IP courts (large national markets, not in UPC, no national module).

---

# US gap analysis (separate from international)

Stuff we should add to or port into `patent-client-agents` independent of the international push.

## Confirmed gaps

- **TBMP** — Trademark Trial and Appeal Board Manual of Procedure. Mirrors `mpep` / `tmep` exactly. Published HTML on USPTO; trivial new module `tbmp/`.
- **USPTO Patent Examiner Guidelines for Design Applications** — there is no formal "MPEP for designs", but USPTO publishes design-specific guidance that practitioners cite. Worth a small module or extending `mpep` to surface design-specific chapters.

## Port from `law-tools` into `patent-client-agents` (or via the unified import path)

Already exists in `law-tools` — decide whether to re-export, re-home, or leave cross-imported:

- `legal_statutes` — 35 USC (Patents), 15 USC ch. 22 (Lanham/Trademarks), 17 USC (Copyright). Critical for any patent/TM agent to cite primary law.
- `govinfo` — 37 CFR (Patents and Trademarks), Federal Register. Regulatory complement to statutes.
- `copyright` — US Copyright Office records (registration catalog). Sole copyright registration system in the US.
- `uspto_tmsearch` — already in law-tools but not in PCA. Check whether this overlaps `uspto_tsdr` or fills a gap.

**Decision needed:** do these stay in law-tools and PCA cross-imports them, or do we re-home into PCA so the wheel is self-contained?

## Out-of-PCA-but-relevant for legal agents

These probably belong in `law-tools` (not PCA) but worth flagging as adjacent:

- `cafc` (Federal Circuit decisions) — already in law-tools; primary IP case-law source
- `courtlistener` / `pacer` — district court IP litigation
- `usitc` — Section 337 investigations (patent + TM exclusion orders) — already in law-tools

---

# Trade secrets law sweep

Trade secrets are statute-only (no registry). For agent coverage, what matters is access to the statutes and case law:

| Jurisdiction | Instrument | Source | Status |
|---|---|---|---|
| US Federal | **Defend Trade Secrets Act** (DTSA, 18 USC § 1836) | `govinfo` / `legal_statutes` (law-tools) | Already covered if we port |
| US States | **Uniform Trade Secrets Act** (adopted 48 states + DC, NY uses common law) | State-by-state; partial via `legiscan` (law-tools) | Patchy |
| EU | **Trade Secrets Directive 2016/943** | CELEX `32016L0943` via `eurlex_cellar` (Tier 1 plan) | Covered by Tier 1 EUR-Lex client |
| China | **Anti-Unfair Competition Law** Arts. 9-10 (2019 amend.) | WIPO Lex `legislation/details/19557`; planned `cn_statutes` mirror | Covered by Tier 1 CN static law corpus |
| Korea | **Unfair Competition Prevention and Trade Secret Protection Act** (UCPA) | `law.go.kr/eng`; planned `kr_statutes` fetcher | Covered by Tier 1 KR statute fetcher |
| Japan | **Unfair Competition Prevention Act** (UCPA, JP) | JPO publishes EN; **gap — not in our current `jpo` module** | Add a small statutes file |
| UK | **Trade Secrets (Enforcement, etc.) Regulations 2018** (SI 2018/597) + common law breach of confidence | legislation.gov.uk CLML/AKN via planned `uk_statutes` | Covered by Tier 2 |
| Germany | **Gesetz zum Schutz von Geschäftsgeheimnissen (GeschGehG, 2019)** | gesetze-im-internet.de via planned `de_statutes` | Covered by Tier 2 |
| Canada | **No federal statute** — common law breach of confidence (Lac Minerals v. Corona, 1989 SCC); Quebec CCQ arts. 1457/1472; Criminal Code s.391 (2020) | n/a (nothing to wrap) | Nothing to do |
| Australia | **No statute** — common law breach of confidence | n/a | Nothing to do |
| India | **No statute** — common law breach of confidence + contract; **Protection of Trade Secrets Bill 2024 pending** | 22nd Law Commission Report; planned `in_statutes` mirror once bill passes | Watch bill |
| Brazil | **LPI Art. 195** (no separate statute — sits inside the unified IP law) | planalto.gov.br via planned `brazil_law` | Covered by Tier 2 |
| Taiwan | **Trade Secrets Act 1996** (J0080028) — 2nd country after Sweden with a standalone statute; criminal penalties 2013; NSA "core key technology" overlay 2022 | `law.moj.gov.tw/ENG` via planned `tw_statutes` | Covered by Tier 3 — **standout asset** |
| Israel | **Commercial Torts Law 5759-1999** Arts. 6-9 — unusual: statutory trade secrets + unregistered TMs + procedural remedies (Anton Piller-style seizures); statutory damages up to NIS 100k without proof | WIPO Lex `2375` via planned `israel_statutes` | Covered by Tier 3 |
| Russia | **Civil Code Part 4** (Ch. 75 — secret of production / know-how, Arts. 1465-1472); Federal Law 98-FZ on Trade Secrets (2004) | WIPO Lex 22106 via planned `ru_statutes` | Covered by Tier 3 (statutes only — live RU connector skipped) |
| Singapore | **No statute** — common law breach of confidence + Cybersecurity Act 2018 (amended 2024) criminal overlay | n/a (nothing to wrap) | Nothing to do |
| OAPI | **Bangui Agreement Annex VIII** — unified protection across 17 Francophone African states | WIPO Lex via planned `wipo_lex` | Covered by Tier 1 |
| Other | UTSA (US state law), various national statutes | TBD | Tier 4+ |

**Practical takeaway:** if we ship Tier 1 + US statutes port + JP UCPA + Tier 2 (UK/DE/BR) + Tier 3 (TW/IL/RU), we have trade-secret statutory coverage for **all four IP5 offices + EU + UK + DE + BR + TW + IL + RU + OAPI** — call it the 98% answer. **CA / AU / IN / SG have no trade-secret statutes** — only common law breach of confidence — so there's nothing to wrap there. Notable standouts: Taiwan was the 2nd country after Sweden to enact a standalone TS Act; Israel's Commercial Torts Law bundles trade secrets with unregistered marks and procedural remedies; Russia's Decree 299 (zeroing compensation for "unfriendly" patentees) is the political wrinkle to track.

---

# Cross-cutting infrastructure opportunities

Tier 1+2 surveys surfaced clear patterns that benefit *multiple* future connectors.

## Reusable abstractions to build once

1. **`StaticLawCorpus` base** — the MPEP-shape keeps recurring as the cheapest reliable win. Now backing 12+ planned modules: UKIPO MoPP, DPMA gesetze-im-internet, CIPO MOPOP/TEM/IDOP, IPO India MPPP, INPI Brazil LPI, KR statutes, CN statutes, plus existing `mpep`/`tmep`. Standard surface: `get_section(citation)`, `search(query)`, version pin, EN/native parallel. Build the base once; future Tier 3 statute fetchers become near-zero-cost.

2. **`BulkXMLFeed` base + ST.36/ST.96/ST.66/ST.86 parsers** — WIPO standards are the lingua franca: USPTO bulk, CIPO IP Horizons, EUIPO Open Data, DPMA backfile, INPI RPI XML, IPGOD/IP RAPID all converge here. Bundle XSDs as `resources/wipo_standards/`; every bulk parser reuses them. Output to parquet for downstream analytics.

3. **`OAuth2ClientCredentialsClient` base** — EUIPO (TM + Design + bulk), IP Australia (Patents/TM/Design APIs), UPC CMS all use OAuth 2.0 client_credentials with sandbox/prod split. Same handshake, different scopes. One auth helper covers all of them.

4. **`StructuredCaseLawClient` base** — LegalDocML and Akoma Ntoso are emerging as the common standard for court decisions: Find Case Law (UK) ships LegalDocML; EUR-Lex CELLAR uses Akoma Ntoso via CDM; legislation.gov.uk uses both CLML and Akoma Ntoso; rechtsprechung-im-internet.de ships per-decision XML. Common parser + ECLI identifier normalization unlocks cross-jurisdiction citation graphs.

## Free / unified gateways worth building first

5. **WIPO Lex as the universal substantive-law backbone** — ~200 jurisdictions, free, polite scrape. If we build `wipo_lex` first, we cover Tier 3 statutes opportunistically — no per-office statute fetcher needed for jurisdictions where Lex's coverage suffices.

6. **CanLII as the Canadian one-stop** — free JSON REST covering FC/FCA/SCC + TMOB + PAB + Patent Act + Trademarks Act + provincial statutes with point-in-time. More developer-friendly than half the patent offices surveyed. Lead with it for any CA work.

7. **EUR-Lex CELLAR as the EU one-stop** — CJEU/General Court IP rulings + EU statutory law (EUTMR, CDR, Trade Secrets Directive, GI Reg 2024/1143, future AI Act IP provisions) in one client. SPARQL + REST, no auth.

## Discovery and reference layers

8. **WIPO API Catalog (`apicatalog.wipo.int`)** — meta-index of IP-office APIs. Useful as a discovery seed when scoping Tier 3 offices; saves WebSearch time.

9. **WIPO INSPIRE catalogue** — patent-database directory used in 4 of our 4 Tier 1 surveys and most of Tier 2; functions as the WIPO-curated "is this office's data feasible?" answer key. Worth a thin wrapper.

## Skip-list patterns to recognize early

10. **CAPTCHA + ASP.NET WebForms / Oracle APEX** — the IPO India / INPI Brazil pePI / CNIPA PSS-SBJ family. Don't even start scoping unless paying for a CAPTCHA-solving dep. Spot the pattern in Tier 3 (Rospatent, ARIPO) and skip directly.

11. **"REST API is in build, ships next year"** — UKIPO One IPO is the canonical example. When an office advertises an imminent OpenAPI, scraping today is wasted work. Watch list, don't wrap.

---

# Next actions

1. **Build the reusable abstractions before the first wave of connectors.**
   - `StaticLawCorpus` base (one shape, 12+ planned modules ride on it)
   - `BulkXMLFeed` + `WipoStandards` parsers (ST.36/ST.96/ST.66/ST.86 reused across 6+ feeds)
   - `OAuth2ClientCredentialsClient` base (EUIPO + IP Australia + UPC CMS)
   - `StructuredCaseLawClient` base (LegalDocML + Akoma Ntoso + ECLI)
   Investing here first amortizes across the whole Tier 1+2 leaderboard.

2. **Implementation order for first sprint** (highest leverage, fewest external dependencies):
   - **`ip_australia`** (full suite — OAuth bench-tests the abstraction; IP RAPID bench-tests bulk pattern)
   - **`canlii`** (JSON REST, ~1 day, lights up CA courts + statutes + tribunals)
   - **`euipo_trademarks`** (validates EUIPO OAuth/quota model)
   - **`wipo_lex`** (unlocks substantive-law coverage for Tier 3 without per-office work)

3. **Second sprint** — `euipo_designs` + `euipo_bulkdata` + `cipo_bulkdata` + `cipo_manuals` + UK MoPP/TM Manual/statutes. All ride on abstractions from sprint 1.

4. **Validation tasks to run before committing to a launch date for each:**
   - KIPRIS Plus foreign-developer registration via `kiprisplus@kipi.or.kr` — measure turnaround
   - EUIPO API real quota numerics — register a sandbox app or contact `apiteam@euipo.europa.eu`
   - Find Case Law (UK) computational-use licence — does the free R&D form permit our CoWork cache-and-serve model?
   - CanLII redistribution ToS for cache-and-serve through our MCP tool

5. **Architecture call needed:** decide statutes/copyright porting strategy — re-home from `law-tools` to PCA, or cross-import? Affects whether PCA is the "all IP data" wheel or stays patent/TM-focused. Same question applies to whether `canlii` and `eurlex_cellar` live in PCA, in `law-tools`, or in `law_tools_core`.

6. **Watch list (re-check quarterly):**
   - **UKIPO One IPO REST APIs** — H2-2025/2026 promised; flips UK from scrape-only to first-class API stack
   - **CIPO NGP roadmap** — public bibliographic REST API on the horizon, or staying ST.96-internal?
   - **WIPO PATENTSCOPE REST migration** — no announced date
   - **EUIPO eSearch Case Law API** — possible 2026-2027
   - **GI authority transfer to EUIPO** under Reg 2024/1143 — eAmbrosia URL still on `ec.europa.eu/agriculture`
   - **CN 2026 Examination Guidelines** English release
   - **India Protection of Trade Secrets Bill 2024** — passage triggers statute mirror addition

7. **All three tiers surveyed.** Tier 3 in particular surfaced one standout build (INPI France via PISTE), two clean modest builds (TIPO, Israel), one modest-but-niche build (IPOS), and four skip verdicts (Rospatent, ARIPO, OAPI, GCC). See the Tier 3 watch list above for SAIP / UAE Patent Hive / PIBD migration / Russia sanctions environment / OAPI 2024 Bangui revision.

8. **Revised first sprint** (incorporating Tier 3): `ip_australia` → `canlii` → `euipo_trademarks` → `wipo_lex` → **`piste_dila` + `legifrance` + `judilibre`** (validates `OAuth2ClientCredentialsClient` for the third time after EUIPO and IP Australia; gives French statutes + IP case law in one client).
