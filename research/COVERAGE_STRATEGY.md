# Coverage strategy — meta-document over registered-IP research

**Status:** living document. Last updated 2026-05-16.
**Purpose:** answer "do we need a connector for office X?" without re-running the analysis every time.

This is the meta-doc that sits above
[`research/`](.). It captures the *shape* of the IP system —
what's layered, what's national-only, where data flows — so we can
read each new connector candidate against the structure instead of
treating every office in isolation.

It complements but does not replace:

- [`CONNECTOR_STANDARDS.md`](../CONNECTOR_STANDARDS.md) — *how* to build a connector (per-tool envelope, provenance, lean+full, list-accept)
- [`coverage/sources.yaml`](../coverage/sources.yaml) — the manifest of what we cover today

This doc answers: *what* should we cover next, and *why*.

---

## §1 The IP system is layered

Three layers carry IP data, and the higher layers transitively cover
parts of the lower ones. Understanding which data flows up and which
stays at the bottom is the entire game.

```
┌─────────────────────────────────────────────────────────────────────┐
│  MULTILATERAL  — WIPO administers the international systems         │
│    PCT (patents)  Madrid (TMs)  Hague (designs)  WIPO Lex (statutes)│
└─────────────────────────────────────────────────────────────────────┘
                              │ extends to designated members
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  REGIONAL   — multi-state offices, one filing → many states         │
│    EPO (patents, 38 EPC states) + INPADOC (biblio of ~100 offices)  │
│    EUIPO (EUTM + RCD, 27 EU states) + TMview (national TM federator)│
│    EAPO  ARIPO  OAPI  GCC  UPC                                      │
└─────────────────────────────────────────────────────────────────────┘
                              │ designated → national phase
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  NATIONAL   — the office of record for each grant                   │
│    USPTO  JPO  KIPO  CNIPA  DPMA  INPI-FR  CIPO  UKIPO  ...         │
└─────────────────────────────────────────────────────────────────────┘
```

**The architectural insight:** a patent filed via PCT and entering the
German national phase shows up in WIPO PATENTSCOPE, EPO INPADOC, *and*
DPMA — but each layer carries different fields. Knowing which fields
flow up determines whether we need a DPMA connector at all.

---

## §2 What each layer carries — grounded

### Multilateral

| System | Operator | Scope | Data carried | Primary source |
|---|---|---|---|---|
| **PCT** | WIPO | International patent applications, ~150 designated countries | Application data; published in 18-month publication | [WIPO PCT](https://www.wipo.int/en/web/pct) |
| **PATENTSCOPE** | WIPO | PCT + national collections WIPO has agreements with | Biblio + full text where available | [PATENTSCOPE](https://patentscope.wipo.int/) |
| **Madrid System** | WIPO | International TMs | 116 members covering 132 countries | [WIPO Madrid Members](https://www.wipo.int/en/web/madrid-system/members/index) |
| **Hague System** | WIPO | International designs | 79 contracting parties covering 96 countries | [WIPO Hague Members](https://www.wipo.int/web/hague-system/members) |
| **WIPO Lex** | WIPO | Statutes + treaties + judgments for ~200 jurisdictions | Statutes text | [WIPO Lex](https://www.wipo.int/wipolex/) |

**Important: Madrid + Hague are opt-in.** A trademark filed only at
USPTO (no Madrid designation) is not in Madrid. A design filed only at
JPO (no Hague designation) is not in Hague. Coverage via the
multilateral layer is partial.

### Regional

| Office | Scope | What it carries | What it doesn't |
|---|---|---|---|
| **EPO** | 38 EPC states, plus PCT national-phase entries | EP applications/grants; INPADOC biblio for ~100 offices; INPADOC legal events for ~50 offices; DOCDB families; EP full text | National-only filings; full text outside EP + ~30 collections; prosecution file wrappers; office actions; assignments |
| **EUIPO** | 27 EU states for EUTMs and RCDs | EU Trade Marks, Registered Community Designs; **TMview** federated search frontend over national TM registers | Underlying national rights register data (TMview is search-only over national-office data, not a unified register) |
| **UPC** | ~17 EU states for Unitary Patents | UP decisions, UP Court decisions | National revocation / opposition |
| **EAPO / ARIPO / OAPI / GCC** | Eurasian / African regional / Gulf | Regional patents | Mostly bulk; limited API surfaces |

**Primary sources:**
- [Espacenet INPADOC legal-status help](https://worldwide.espacenet.com/help?locale=en_EP&method=handleHelpTopic&topic=legalstatusqh) — INPADOC scope
- [EUIPO trade-mark availability search](https://www.euipo.europa.eu/en/trade-marks/before-applying/availability) — TMview confirmation

### National

Each national office is its own register of record. Carries:
- All filings made directly at that office (national-only)
- The national-phase entries of PCT applications designating it
- Full prosecution file history (almost always national-office only)
- Office actions, oppositions, post-grant proceedings (national-office only)
- Assignments / ownership changes (national-office only)
- Real-time status (vs. INPADOC's lag)

---

## §3 Coverage matrix — who covers what

For each (jurisdiction, right, data-type) cell, the matrix shows what
the higher layers cover transitively. A 🔴 means no higher-layer
substitute exists — the only path is the national office. The colors
answer "do we need a national connector for this cell?"

### Patents

| Data type | Multilateral | Regional (EPO INPADOC) | National office adds |
|---|---|---|---|
| **Biblio** | PCT in PATENTSCOPE | DOCDB ~100 offices | Real-time + national-language metadata |
| **Family** | — | DOCDB simple + INPADOC extended | (nothing meaningful) |
| **Full text** | PCT in PATENTSCOPE | EP + ~30 collections | National-language full text for the rest |
| **Legal events** | — | INPADOC ~50 offices | Real-time status for offices not in INPADOC |
| **Prosecution file** | — | — | 🔴 National-office only |
| **Office actions** | — | — | 🔴 National-office only |
| **Assignments** | — | — | 🔴 National-office only |
| **Post-grant (PTAB/opposition/UPC)** | — | UPC (for UP) | 🔴 National-office only |

**Reading:** for biblio, family, and (for ~50 offices) legal events, **EPO INPADOC via EPO OPS is the workhorse**. National patent connectors are worth building only when the national office adds prosecution / office actions / assignments / post-grant or fills an INPADOC gap.

### Trademarks

| Data type | Multilateral | Regional (EUIPO + TMview) | National office adds |
|---|---|---|---|
| **EU-level TMs (EUTMs)** | Madrid IRs designating EU | EUIPO direct | (n/a) |
| **National TMs in EU member states** | Madrid IRs designating that state | TMview federated search (search-only) | Full register, prosecution, post-grant |
| **National TMs outside EU** | Madrid IRs designating that state | — | 🔴 National-office only |
| **TM prosecution / oppositions** | — | EUIPO (for EUTMs) | 🔴 National-office only for national TMs |
| **TM assignments** | — | EUIPO (for EUTMs) | 🔴 National-office only for national TMs |

**Reading:** TMs are *less* layered than patents. EUIPO covers only EU-level rights. TMview is a *search frontend* over national registers, not a unified register. **Madrid does not eliminate the need for national-TM connectors** — Madrid only carries IRs that designate that country.

### Designs

| Data type | Multilateral | Regional (EUIPO RCDs) | National office adds |
|---|---|---|---|
| **EU-level designs (RCDs)** | Hague IRs designating EU | EUIPO direct | (n/a) |
| **National designs in Hague members** | Hague IRs designating that state | — | National designs not filed via Hague |
| **National designs outside Hague** | — | — | 🔴 National-office only |
| **Design prosecution** | — | EUIPO (for RCDs) | 🔴 National-office only for national designs |

**Reading:** designs are the *least* layered right. National design registers are the only path for most jurisdictions outside Hague designations.

### Copyright

Copyright is **not** filed/registered in most jurisdictions — it
arises automatically. The US is unusual in operating a Copyright
Office register. No multilateral / regional substitute exists, and
most jurisdictions have no register to connect to at all.

| Jurisdiction | Source |
|---|---|
| **US** | USCO (already covered) |
| **Most others** | No register exists |

### Trade secrets

No register anywhere — trade secrets are protected by statute, not by
registration. The work here is **statute coverage**, not register
coverage. See substantive-law strategy below.

### Substantive law (statutes, manuals, guidelines, case law)

| Data type | Multilateral | Regional | National |
|---|---|---|---|
| **Statutes** | WIPO Lex (~200 jurisdictions) | — | Each office publishes its own |
| **Examination manuals** | — | EPO Guidelines, EUIPO Guidelines | MPEP (US), MoPP (UK), MPPP (IN), Examination Practice (each) |
| **Case law** | — | UPC decisions, CAFC (US Fed Circuit) | National courts |

**Reading:** WIPO Lex is the workhorse for cross-jurisdictional
statutes. National statute corpora (our recent IPO India, DPMA, Légifrance, TIPO
fan-out) add value when WIPO Lex's coverage is shallow, the local
text is more current, or the user expects native citation forms.

---

## §4 Decision rules — when to build a national connector

A national connector is worth building when **at least one** of these is true:

1. **The national office is the unique source.** Trade marks outside Madrid IRs. Designs outside Hague IRs. Prosecution file wrappers (always). Office actions. Assignments. Post-grant proceedings. → 🔴 cells in §3.

2. **The national office is the authoritative real-time source** even though INPADOC carries the data with a lag. USPTO ODP is the canonical example — INPADOC has US biblio, but ODP is fresher, has more fields, and is the source of truth for prosecution.

3. **The national office adds native-language full text** that INPADOC + EPO full-text don't carry. JPO Japanese full text is the canonical example.

4. **The national office is genuinely free + proxyable.** This is the constraint that
[the 2026-05-16 discovery wave](registered-ip-discovery-2026-05-16/00-summary.md) just narrowed dramatically. See §5.

A national connector is **not** worth building when:

- The data is already in EPO INPADOC at the same fidelity (e.g., DE patent biblio — go through EPO OPS, skip DPMAregister).
- The national office is closed off legally (DPMA contract §3.2, KIPO ToS key-sharing prohibition without per-user BYOK, WIPO non-IP-office tier).
- The national office has no API and only bulk / HTML (UKIPO post-IPSUM, CIPO across all rights).

---

## §5 Current state — assessment after the 2026-05-16 wave

### Active in `coverage/sources.yaml` (22 registered-IP + 18 substantive-law = 40 sources)

| Layer | Coverage |
|---|---|
| Multilateral | WIPO Lex ✓ ; Google Patents (proxy for PCT search) ✓ |
| Regional | EPO OPS ✓ ; EPO CPC ✓ ; EUIPO TMs ✓ ; EUIPO Designs ✓ ; UPC ✓ |
| National | US (USPTO ODP/PPUBS/PTAB/Petitions/Assignments/OAs/BulkData/TSDR/TMSearch/USCO/USITC) ✓ ; JP (JPO) ✓ ; AU (IP Australia patents/TMs/designs/bulk) ✓ |
| Substantive law | MPEP, TMEP, EPC, EPO Guidelines, EPO CaseLaw, PCT Guidelines, UP Guidelines, UPC Statutes, UPC Decisions, UKIPO MoPP, CAFC, CanLII, WIPO Lex, IN/IPO Statutes, IN/IPO MPPP, DE/DPMA Statutes, FR/Légifrance, TW/MOJ Trade Secrets ✓ |

### Sitting on branches, not yet integrated (HANDOFF wave)

- CanLII expansion (CA case law deepening) — verified, on `feature/ipo-india-connector` branch
- INPI Brazil bulk (BR registered-IP-adjacent, Shape E catalog only) — verified, on worktree
- IPOS Singapore statutes + manuals (SG substantive law) — verified, on worktree
- ILPO Israel statutes + TM bulk (IL substantive law + Shape E TM catalog) — verified, on worktree
- DPMA / Légifrance / TIPO trade secrets (now verifier-clean as of 2026-05-16) — on current branch

### Closed off by the 2026-05-16 discovery wave

| Office | Conclusion | Synopsis |
|---|---|---|
| **DPMA Germany registers** | Contract §3.2 prohibits proxy. Use EPO OPS for DE patents; DE TMs/designs remain a gap with no proxyable path. | [national/de-dpma.md](national/de-dpma.md) |
| **UKIPO registers** | IPSUM retired Jan 2025; One IPO replacement HTML-only; designs queued behind TMs in a multi-year transformation. No timeline. | [national/gb-ukipo.md](national/gb-ukipo.md) |
| **CIPO Canada registers** | Zero REST APIs across all rights. HTML + bulk only. | [national/ca-cipo.md](national/ca-cipo.md) |
| **WIPO PATENTSCOPE / Global Brand DB / Global Design DB** | All ToS-prohibited for automated queries on the public surfaces; programmatic access is paid SOAP or "collaborating IP Offices only." | [multilateral/wipo-patentscope.md](multilateral/wipo-patentscope.md), [multilateral/wipo-global-brand-db.md](multilateral/wipo-global-brand-db.md), [multilateral/wipo-global-design-db.md](multilateral/wipo-global-design-db.md) |

### Still on the table (post-2026-05-16)

| Office | Path | Why | Synopsis |
|---|---|---|---|
| **KIPO Korea** | BYOK connector (env-gated tools, no key on our infra) | KR is a top-5 office; real API; ToS-clean if per-user. | [national/kr-kipo.md](national/kr-kipo.md) |
| **TMview** (EUIPO-hosted federated TM search) | Discovery research needed | Could be the TM analogue of INPADOC if it has a public API. The 2026-05-16 research wave flagged it; not yet probed. | (queued) |
| **DesignView** (likely EUIPO-hosted, design federation) | Discovery research needed | Same hypothesis as TMview. | (queued) |
| **INPI France registers** | Discovery research needed | Currently only have Légifrance statutes; INPI Open Data API exists per memory but unverified. | (queued) |
| **TIPO Taiwan registers** | Discovery research needed | Currently only have trade-secrets statute. | (queued) |
| **CNIPA China** | Risk-assessment first | Limited APIs; geofencing; political risk. | (queued) |

---

## §6 Substitution rules — quick reference

When a user asks for jurisdiction X coverage, apply in order:

1. **Patents biblio + family + (legal events for ~50 offices):** route through **EPO OPS** (`search_epo`, `get_epo_biblio`, `get_epo_family`, `get_epo_legal_events`). Skip national patent register connectors unless they meet a §4 trigger.

2. **Patents full text (where available):** EPO OPS `get_epo_fulltext` for EP + the ~30 collections it carries; Google Patents (`search_google_patents`) for broader coverage including national full text where Google has it scraped.

3. **Trade marks (EU-level + Madrid IRs designating EU):** EUIPO (`search_euipo_trademarks`, `get_euipo_trademark`).

4. **Trade marks (national outside EU):** national connectors required. Currently: US/USPTO ✓ ; AU/IPAustralia ✓ ; JP/JPO ✓ . Gaps everywhere else, mostly with no proxyable path under our constraints.

5. **Designs (EU-level + Hague IRs designating EU):** EUIPO RCDs (`search_euipo_designs`, `get_euipo_design`).

6. **Designs (national outside EU):** national connectors required. Currently: AU/IPAustralia ✓ ; JP/JPO ✓ . Gaps elsewhere.

7. **Prosecution / office actions / assignments / post-grant:** national connectors required, no substitutes exist. Currently: US/USPTO ✓ (deepest) ; JP/JPO ✓ (partial). Gaps for all other jurisdictions.

8. **Statutes:** WIPO Lex first (`search_wipo_lex_legislation`), then national corpora for jurisdictions where we have them or where the user expects native citation forms.

9. **Examination manuals + guidelines:** EPO Guidelines, EUIPO Guidelines, national manuals where we have them (MPEP, MoPP, MPPP).

10. **Case law:** UPC Decisions, CAFC Opinions, CanLII, plus jurisdiction-specific tribunals via national connectors (USPTO PTAB ✓ , Petitions ✓ , Office Actions ✓).

---

## §7 Research index

The research/ folder restructured on 2026-05-16. Current shape:

- **Per-office synopses** (~150-200 lines each, current state, integrates latest findings):
  - [`multilateral/`](multilateral/) — WIPO systems
  - [`regional/`](regional/) — EPO, EUIPO, UPC, …
  - [`national/`](national/) — US, JP, KR, DE, GB, CA, AU, …
- **Detail surveys** (~200-400 lines each, pre-2026-05-16, asset-by-asset deep dive):
  - [`connectors/`](connectors/) — preserved as canonical detail-research location
- **Time-stamped research products** (frozen audit trail):
  - [`waves/`](waves/) — see [`waves/2026-05-16-registered-ip-discovery/`](waves/2026-05-16-registered-ip-discovery/) for the wave that triggered this restructure
- **Strategic top-level docs**:
  - This file ([`COVERAGE_STRATEGY.md`](COVERAGE_STRATEGY.md)) — strategic theory + decision rules
  - [`BACKLOG.md`](BACKLOG.md) — ranked work queue + reconciliation log of drift between original surveys and current state
- **Templates**:
  - [`templates/office-synopsis.md`](templates/office-synopsis.md) — canonical synopsis template

| Wave | Date | Subject | Files |
|---|---|---|---|
| Registered-IP discovery | 2026-05-16 | KIPO + WIPO trio + DPMA + UKIPO + CIPO | [`waves/2026-05-16-registered-ip-discovery/`](waves/2026-05-16-registered-ip-discovery/) |
| Tool-surface audit | 2026-05-14 | Existing tools vs CONNECTOR_STANDARDS §5 | [`tool-surface-audit-2026-05-14.md`](tool-surface-audit-2026-05-14.md) |

Future research waves to add here as they happen.

---

## §10 Fee data — out of scope

We deliberately do **not** mirror fee schedules. Every synopsis §4
describes the structural shape of an office's fees (categories charged,
local currency, named discount programs) and links to the office's
official schedule page. That's the entire fee story in this repo.

Reasons:

- Fees drift; mirrored amounts go stale and mislead readers.
- The office's own page is the only authoritative source at any moment.
- Building a "fee schedule MCP tool" would commit us to a permanent
  re-research treadmill across dozens of offices in dozens of currencies
  with dozens of rulemaking cadences. Not our job.

If a downstream user needs structured fee data, they should follow the
official link and consume the office's own (often machine-readable)
schedule directly.

---

## §11 Conventions

- **WIPO ST.3 codes** for jurisdictions (`US`, `JP`, `KR`, `DE`, `EP`, `EM`, …).
- **Layer-prefix in synopsis filenames** — `multilateral/wipo-*.md`, `regional/<office>.md`, `national/<iso2>-<office>.md`.
- **Verdicts**: 🟢 (green / proxy-compatible / shipped), 🟡 (yellow / conditional / BYOK only), 🔴 (red / blocked / skipped), ⏳ (watch / pending).
- **Synopsis = current-state** living document; **survey = detail research** (older); **wave = frozen time-stamped product**.
- Last-verified date on every synopsis; refresh quarterly minimum.
- Every claim of fact links to a primary source. Third-party blogs are not acceptable citations.

---

## §8 Open questions

1. **Does TMview have a public API?** EUIPO operates it; if so, it could be the TM analogue of INPADOC and substitute for many national-TM connectors. **Highest-leverage open question.**

2. **Does DesignView have a public API?** Likely EUIPO-operated under the same model. If yes, same substitution play for national-design connectors.

3. **INPI France Open Data API** — referenced but unverified. Patents + TMs reported. Needs the same discovery rigor we just applied to DPMA / UKIPO / CIPO.

4. **TIPO Taiwan via gov.tw Open API portal** — referenced but unverified. We now have TW trade-secrets statute; if TIPO has a clean API, TW registered-IP coverage becomes feasible.

5. **WIPO partner-API program** — there are signals WIPO is building one (undocumented `public-api.branddb.wipo.int` endpoint observed 2026-05-16). Recheck quarterly via the [WIPO API Catalog](https://apicatalog.wipo.int/).

6. **CIPO NGP / UKIPO One IPO timelines** — both mid-modernization with no published API release dates. Recheck quarterly.

7. **Coverage budget for paid commercial tiers** — PATENTSCOPE paid SOAP (CHF 600–2,000/yr); DPMAconnectPlus paid contract (EUR 200 + signed paper). Both have ToS restrictions that may bar proxy use even after payment — need a deeper read before treating either as an option.

---

## §9 How to update this doc

When a new connector ships, update §5 (current state). When a research
wave runs, add a row to §7 (research index) and update §8 (open
questions) — resolve answered ones, add newly-surfaced ones. When the
underlying IP system structure changes (new regional system,
Madrid/Hague membership shift, WIPO partner API opens), update §1–§3.

This doc should stay at ≤500 lines; if it grows, split off appendices.
