# JPO Japan (JP) — national

**Layer:** national
**Jurisdiction:** JP (WIPO ST.3: JP)
**Issuing body:** Japan Patent Office (特許庁 / Tokkyochō)
**Rights administered:** patent, utility_model, trademark, design
**Working languages:** Japanese (primary); English (partial via JPlatPat EN + JPO English site)
**Connector status:** **active** (BYOK)
**Last verified:** 2026-05-16
**Manifest entries:**
- [`JP/JPO`](../../coverage/sources.yaml) — `patent_client_agents.jpo`

**Detail surveys:**
- *No standalone `connectors/jpo.md` exists* — coverage is established and the connector is operational.

**Higher / sibling layers carrying overlapping data:**
- **EPO INPADOC** — JP patent biblio + family (INPADOC has strong JP coverage); legal events partial
- **WIPO Madrid** — international TMs designating JP (JP is a Madrid member since 2000)
- **WIPO Hague** — international designs designating JP (JP is a Hague member since 2015)
- **WIPO PATENTSCOPE** — JP-filed PCT applications + JP-designated national-phase records

---

## §1 Mission

JPO is one of the IP5 offices — the third-largest patent office in the
world by recent application volume. Japan administers all four
traditional registered IP rights from one agency. JPO's online search
system (J-PlatPat) is the consumer-facing UI; the JPO API for developers
is the programmatic surface used by our connector.

For agents working on Japanese prior art, prosecution, or post-grant
review, JPO is the authoritative source for Japanese-language full text
and JP-specific procedural events. EPO INPADOC substitutes for JP
patent biblio + family at the regional layer.

## §2 What's unique here
- **Japanese-language patent full text** (EPO OPS full-text doesn't cover JP applications in native Japanese for the most part)
- **Real-time JP patent prosecution status** (vs. INPADOC's lag)
- **JP utility models** — Japan is a top global jurisdiction for UM filings
- **National-only JP trademarks** — not in Madrid IRs
- **National-only JP designs** — not in Hague IRs
- **JP-specific procedural events** — opposition, invalidation trials
- **PCT national-phase number lookup** — JPO assigns its own national-phase number; we expose `get_jpo_pct_national_phase_number`
- **JPO Applicant Identification** — Japanese applicant codes ↔ name lookups

## §3 Programmatic surfaces

### JPO API for developers

| Field | Value |
|---|---|
| Endpoint | JPO API gateway (Japanese government infrastructure) |
| Auth | Username + password (account-based) — `JPO_API_USERNAME` + `JPO_API_PASSWORD` |
| Format | JSON / XML (varies per endpoint) |
| Rate limit | Account-tier-specific; not fully published |
| ToS posture | Permissive for proxy with proper credentials (per existing connector ToS handling) |
| Verdict (zero-infra proxy) | 🟢 **Green** — operational |

Important operational note: **JPO origin server filters Cloud Run
egress harder than residential IPs** — same egress pattern as USPTO
TESS. Test JPO API access per deployment; some research has had to
route through web.archive.org when direct JPO origin is blocked.

### J-PlatPat web UI

| Field | Value |
|---|---|
| Endpoint | `https://www.j-platpat.inpit.go.jp/` |
| Auth | none (some advanced features session-based) |
| Format | HTML |
| ToS posture | UI use only; not the recommended path |
| Verdict | 🔴 Red for scraping |

We expose a helper `get_jpo_jplatpat_url(application_number)` for
direct URL construction without scraping.

## §4 Fees

JPO publishes patent, trade mark, and design fee schedules in JPY.
Patent annuities **and** examination requests are **claim-count-dependent
at every band** — a structural quirk worth knowing when modeling
prosecution cost.

- **Official schedule (EN):** [JPO fee schedule](https://www.jpo.go.jp/e/system/process/tesuryo/hyou.html)
- **Statutory basis:** Patent Act, Utility Model Act, Design Act, and Trademark Act, with fees set in supplementary tables.


## §5 Connector strategy

### What we cover today

The full set:
- `get_jpo_progress` / `get_jpo_progress_simple` — application status
- `get_jpo_applicant_by_code` / `get_jpo_applicant_by_name` — applicant lookups
- `get_jpo_patent_cited_documents` — citation data
- `get_jpo_patent_divisional_info` — divisional family
- `get_jpo_priority_info` — priority chain
- `get_jpo_pct_national_phase_number` — PCT → JP national-phase mapping
- `get_jpo_number_reference` — number-system conversions
- `get_jpo_registration_info` — registration record
- `get_jpo_documents` — document retrieval
- `get_jpo_jplatpat_url` — direct URL construction

All env-gated on `JPO_API_USERNAME` + `JPO_API_PASSWORD`.

### What we should improve

- **§5.9 envelope sweep** — completed 2026-05-15 ✅. Including the `get_jpo_applicant_by_*` collapse to a single tool and `get_jpo_jplatpat_url` / `get_jpo_number_reference` first-sentence rewrites.
- **Cloud Run egress** — see operational note in §3; per-deployment verification.

### What we should NOT add

- **J-PlatPat scraping** — UI-only, brittle, against the spirit of access policy.

### Template value

JPO is the **canonical BYOK template for username+password auth**
(versus IP Australia's OAuth2 BYOK). Both patterns coexist in the
codebase. KIPO BYOK will resemble JPO architecturally (per-user API key
on every call, no OAuth dance) rather than IP Australia's pattern.

## §6 Open questions

- **JPO API access tier limits** — not fully published; relevant for capacity planning if user demand scales.
- **JPO Cloud Run egress** — confirmed blocked from our standard cloud network; recommend documenting per-deployment workaround.
- **2022-04-01 fee schedule freshness** — the schedule has been stable for 4+ years; next revision date not announced.

## §7 References

Primary sources only.

**APIs + portals:**
- [JPO English site](https://www.jpo.go.jp/e/index.html)
- [J-PlatPat (search UI)](https://www.j-platpat.inpit.go.jp/)
- [JPO API for developers](https://www.jpo.go.jp/e/system/laws/sesaku/data/openapi.html)

**Fees:**
- [JPO fee schedule (EN)](https://www.jpo.go.jp/e/system/process/tesuryo/hyou.html)
- [JPO fee schedule (JP)](https://www.jpo.go.jp/system/process/tesuryo/index.html)

**Substantive law:**
- [Japan Patent Act (EN)](https://www.japaneselawtranslation.go.jp/en/laws/view/3915) — via Japanese Law Translation Database

**Detail in this repo:**
- `src/patent_client_agents/mcp/tools/international.py` — JPO MCP tools (§5.9 envelope, ✅)
- [`CONNECTOR_STANDARDS.md`](../../CONNECTOR_STANDARDS.md) — connector contract

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-16 | Initial synopsis. Confirmed JPO Cloud Run egress blocked per memory note. | — |
