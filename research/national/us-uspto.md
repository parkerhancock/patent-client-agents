# USPTO United States (US) — national

**Layer:** national
**Jurisdiction:** US (WIPO ST.3: US)
**Issuing body:** United States Patent and Trademark Office (an agency of the Department of Commerce)
**Rights administered:** patent, trademark, design_patent (designs are handled as design patents in the US — different mechanism than other jurisdictions)
**Working languages:** English
**Connector status:** **active** (deepest connector in the catalog)
**Last verified:** 2026-05-16
**Manifest entries:**
- `US/USPTO/ODP/Applications` — `patent_client_agents.uspto_odp`
- `US/USPTO/ODP/PTAB` — same module
- `US/USPTO/ODP/Petitions` — same module
- `US/USPTO/PPUBS` — `patent_client_agents.uspto_publications`
- `US/USPTO/Assignments/Patents` — `patent_client_agents.uspto_assignments`
- `US/USPTO/OfficeActions` — `patent_client_agents.uspto_office_actions`
- `US/USPTO/BulkData` — `patent_client_agents.uspto_bulkdata`
- `US/USPTO/TSDR` — `patent_client_agents.uspto_tsdr`
- `US/USPTO/TMSearch` — `patent_client_agents.uspto_tmsearch`
- `US/USPTO/Assignments/Trademarks` — `patent_client_agents.uspto_trademark_assignments`
- `US/USPTO/MPEP` — `patent_client_agents.mpep` (substantive law)
- `US/USPTO/TMEP` — `patent_client_agents.tmep` (substantive law)

**Detail surveys:**
- Substantial existing knowledge across the connector codebase
- USPTO Applications (`uspto_odp` / `uspto_applications`) is the canonical §5.9 envelope template — see `src/patent_client_agents/mcp/tools/uspto.py`

**Higher / sibling layers carrying overlapping data:**
- **EPO INPADOC** — US patent biblio is in DOCDB, but USPTO ODP is **the authoritative real-time source** for US patents and adds prosecution depth INPADOC doesn't carry.
- **Google Patents** — covers US patents transitively; useful for prior-art search across foreign patents that USPTO doesn't issue.
- **WIPO PATENTSCOPE** — for PCT applications filed at USPTO as receiving office.

---

## §1 Mission

USPTO is the largest patent office in the world by application volume
and the source-of-record for US patents, trademarks, and design patents.
US is unusually open about data access — the agency operates under a
statutory open-data mandate that makes USPTO the cleanest API surface
of any major IP office globally. This is why USPTO is our deepest
connector by far: ~10 distinct services covering applications, PPUBS,
Assignments, OAs, PTAB, Petitions, TSDR, TM Search, TM Assignments,
Bulk Data, plus substantive-law layers (MPEP, TMEP, CAFC opinions, USITC).

If you only proxied one office's data, you'd proxy USPTO.

## §2 What's unique here
- **Full prosecution file wrappers** (file history, IDS, transactions) via ODP and bulk
- **Real-time application status** (vs. INPADOC's lag of weeks-to-months)
- **Office actions full text** with structured rejection codes
- **PTAB proceedings** (IPR, PGR, CBM, Interference, Appeal decisions)
- **Petitions** (revival, extensions, etc.)
- **Patent + trademark assignment history** with structured reel/frame
- **TSDR** (Trademark Status and Document Retrieval) — TM file history, opposition records
- **TM Search** (the modernized USPTO TM search)
- **Design patent register** (US handles industrial designs as a class of patent, not as a separate right)

## §3 Programmatic surfaces

### USPTO Open Data Portal (ODP)

| Field | Value |
|---|---|
| Endpoint | `https://api.uspto.gov/` |
| Auth | API key (free; obtained via developer.uspto.gov) |
| Format | JSON |
| ToS posture | Permissive; explicit open-data policy |
| Verdict | 🟢 Green — operational |
| Primary source | [USPTO Open Data Portal](https://developer.uspto.gov/) |

Covers applications, PTAB, Petitions in one API.

### PPUBS (Patent Public Search)

| Field | Value |
|---|---|
| Endpoint | `https://ppubs.uspto.gov/dirsearch-public/` |
| Auth | none (cookie-based session for advanced features) |
| Format | JSON |
| Verdict | 🟢 Green — operational via [`patent_client_agents.uspto_publications`](../../src/patent_client_agents/uspto_publications/) |

### USPTO Bulk Data products

| Field | Value |
|---|---|
| Endpoint | `https://developer.uspto.gov/data` |
| Auth | API key for catalog browsing |
| Format | various — XML, PDF, CSV per product |
| Verdict | 🟢 Green for catalog navigation; bulk delivery is bulk-shaped (not used for live proxy) |

### TSDR (Trademark Status & Document Retrieval)

| Field | Value |
|---|---|
| Endpoint | `https://tsdrapi.uspto.gov/ts/` |
| Auth | TSDR_API_KEY (free; signup via TSDR portal) |
| Format | JSON / XML / ZIP per request |
| Verdict | 🟢 Green |

### TM Search (modernized TM register)

| Field | Value |
|---|---|
| Endpoint | `https://tmsearch.uspto.gov/` |
| Auth | varies (some endpoints public, some session-based) |
| Verdict | 🟢 Green — operational via [`patent_client_agents.uspto_tmsearch`](../../src/patent_client_agents/uspto_tmsearch/) |
| Note | Egress filtering concern: TESS (predecessor) was blocked from Cloud Run egress. TM Search may have similar filtering — verify per deployment. |

## §4 Fees

USPTO publishes patent and trademark fee schedules in USD with
entity-size tiers (large / small / micro). Patent categories: filing,
search, examination, issue, maintenance (years 3.5 / 7.5 / 11.5), RCE,
appeal forwarding, and a long list of procedural fees. Trademark
categories: application per class (with a base + surcharges
structure post-2025), Statement of Use, renewal.

- **Official schedule:** [USPTO Fee Schedule](https://www.uspto.gov/learning-and-resources/fees-and-payment/uspto-fee-schedule)
- **Consolidated PDF:** [USPTO-fee-schedule_current.pdf](https://www.uspto.gov/sites/default/files/documents/USPTO-fee-schedule_current.pdf)
- **Statutory basis:** 35 USC + 37 CFR Part 1 (patents) / 37 CFR Part 2 (trademarks). USPTO fee-setting authority is under §10 of the Patent Act (UAIA); confirm whether that authority is still in force when consulting figures, as it has a statutory sunset.

Discount programs:

- **Small entity** — reduced rate on most patent fees (eligibility under 37 CFR 1.27).
- **Micro entity** — further-reduced rate (37 CFR 1.29).
- **Trademark TEAS Plus / Standard tiers were retired** in the 2025 trademark fee rulemaking; the current model is a base application fee with surcharges (free-text ID, missing info, oversized ID).

*(frozen at the date written; consult the official URLs above for current figures).*

## §5 Connector strategy

### What we cover today

The full USPTO catalog. ~10 distinct connector modules (see manifest entries above). USPTO is the only office where we ship near-complete coverage across applications + publications + assignments + office actions + PTAB + petitions + TM search + TSDR + bulk data catalog + substantive-law layers (MPEP, TMEP).

### What we should improve

- **TBMP** (Trademark Trial and Appeal Board Manual) — `BACKLOG.md` US Gap Analysis identifies this as a small new module. Mirrors MPEP/TMEP shape.
- **Design Patent Examiner Guidelines** — no formal "MPEP for designs"; consider adding as a small module or extending MPEP to surface design-specific chapters.

### What we should NOT add

- **Pre-grant publications scraping outside PPUBS** — PPUBS already covers this; alternative scrapers are redundant.
- **Bulk-only ingestion** — runs against the zero-infra constraint; ODP + PPUBS + TSDR cover the live-search needs.

### Next steps

1. Update fee logic anywhere it references TEAS Plus/Standard or pre-UAIA (50%/75%) discount tiers — both are stale as of 2025-01-18.
2. Ship TBMP (~1 day per BACKLOG estimate).
3. Watch for USPTO Director §10 sunset (2026-09-16) — fee rulemaking cadence may shift.

## §6 Open questions

- **What happens after §10 sunset?** Will Congress reauthorize, or does fee-adjustment revert to formal rulemaking only?
- **Are there post-grant proceedings beyond IPR/PGR/CBM that we don't expose?** Worth reviewing PTAB tool scope.
- **TM Search Cloud Run egress** — confirmed problematic for TESS predecessor; verify TM Search per deployment.

## §7 References

Primary sources only.

**APIs:**
- [USPTO Open Data Portal](https://developer.uspto.gov/) — ODP / PPUBS / TSDR / TM Search developer docs
- [TSDR API](https://tsdrapi.uspto.gov/)
- [USPTO Patent Center](https://patentcenter.uspto.gov/) — application detail UI

**Fees:**
- [USPTO Fee Schedule](https://www.uspto.gov/learning-and-resources/fees-and-payment/uspto-fee-schedule)
- [FY2025 Patent Fee Rule (89 FR 91898)](https://www.federalregister.gov/documents/2024/11/20/2024-26821/setting-and-adjusting-patent-fees-during-fiscal-year-2025)
- [FY2025 Trademark Fee Rule (89 FR 91062)](https://www.federalregister.gov/documents/2024/11/18/2024-26644/setting-and-adjusting-trademark-fees-during-fiscal-year-2025)

**Statutory:**
- [35 USC](https://uscode.house.gov/browse/prelim@title35) — patents
- [37 CFR](https://www.ecfr.gov/current/title-37) — patent + trademark regulations

**Detail in this repo:**
- `src/patent_client_agents/mcp/tools/uspto.py` — canonical §5.9 envelope template
- [`CONNECTOR_STANDARDS.md`](../../CONNECTOR_STANDARDS.md) — connector contract

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-16 | Initial synopsis. Noted TEAS Plus/Standard tiers retired in the 2025 trademark fee rulemaking; UAIA small/micro discount tiers were adjusted in late 2022. Any cached fee logic should be re-derived from the official schedule. | — |
