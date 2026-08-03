# DPMA Germany (DE) — national

**Layer:** national
**Jurisdiction:** DE (WIPO ST.3: DE)
**Issuing body:** Deutsches Patent- und Markenamt (German Patent and Trade Mark Office)
**Rights administered:** patent, utility_model, trademark, design, copyright (registers; copyright is largely automatic in DE)
**Working languages:** German (primary); English (partial — some service pages, fee schedules)
**Connector status:** **shipped beta (BYOK)** — register support is mock-only tested; statutes are fully shipped
**Last verified:** 2026-08-03
**Manifest entries:** [`coverage/sources.yaml`](../../coverage/sources.yaml) rows `DE/DPMA/Patents`, `DE/DPMA/Trademarks`, and `DE/DPMA/Designs` are beta. `DE/DPMA/Statutes` is active.

**Detail surveys:**
- [`connectors/dpma.md`](../connectors/dpma.md) — 2026-05 detail survey (211 lines; covers DPMAregister UI, DEPATISnet, DPMAconnectPlus REST, backfile, BPatG/BGH case law, gesetze-im-internet)
- [`waves/2026-05-16-registered-ip-discovery/dpma-germany.md`](../waves/2026-05-16-registered-ip-discovery/dpma-germany.md) — 2026-05-16 grounded API discovery

**Higher layers covering this office transitively:**
- **EPO INPADOC** (via [`regional/epo.md`](../regional/epo.md)) — DE patent biblio + family; this is the recommended substitute for DPMA patent register data.
- **EUIPO** (via [`regional/euipo.md`](../regional/euipo.md)) — only for EU-level marks (EUTMs designating DE); pure DE national TMs are NOT covered.
- **WIPO Madrid / Hague** — Madrid IRs designating DE / Hague IRs designating DE; national-only filings are NOT covered.

---

## §1 Mission

DPMA is the largest national IP office in Europe and the home office for
the Bundespatentgericht (BPatG) and the Unified Patent Court's Munich
Central Division (mechanical engineering). Germany is strategic for any
European IP work — but the German federal data-access policy treats
register data as a paid product with strict redistribution terms.

For agents working on German patents, EPO OPS via INPADOC substitutes
for biblio/family at the regional layer. **National-only filings at
the TM and design level — and German utility models (Gebrauchsmuster),
a distinctive German right type not in EP — remain DPMA-exclusive**,
accessible via the DPMAconnectPlus REST API on a per-user BYOK basis:
each user signs their own Datenempfänger contract (EUR 200 one-time),
registers a fixed IP, and runs `patent-client-agents-mcp` locally with
their own credentials. The hosted demo at `mcp.patentclient.com` does
not carry DPMA credentials by design — the §3.2 prohibition on
rebroadcasting data records forecloses zero-infra proxy.

## §2 What's unique here
- **German utility models (Gebrauchsmuster, GebrMG)** — a registered right distinct from patents; not covered by EP filings; only path is DPMA.
- **National-only DE trademarks** — those filed directly with DPMA, not via Madrid IR or EUTM.
- **National-only DE designs** — those filed directly with DPMA, not via Hague IR or RCD/REUD.
- **Real-time DPMA file history** — DPMAregister UI has live file inspection; EPO OPS doesn't carry it.
- **DPMA-specific procedural events** — opposition, nullity, BPatG appeal status.

## §3 Programmatic surfaces

### DPMAconnectPlus REST API

| Field | Value |
|---|---|
| Endpoint | `https://dpmaconnect.dpma.de/dpmaws/rest-services/` (separate services per right) |
| Auth | HTTP Basic (username + password); signed Datenempfänger contract required (per user) |
| Format | XML on ST.36 (patents) / ST.66 (TMs) / ST.86 (designs) extension schemas |
| Cost | EUR 200 one-time connection fee (§4.2); per-record retrieval free; optional Frontfile/backfile packages priced separately |
| Rate limit | 1,000 hits per search query for production accounts; 100 for test accounts; §2.2 lets DPMA cap volume if a user impairs availability |
| ToS posture | §3.2 forbids **rebroadcasting the data records** to third parties (with carve-out for purpose §3.1(b)); §2.1 requires a registered, non-dynamic IP — exactly the self-host shape. **Per-user BYOK is permitted; zero-infra proxy is not.** |
| Rating (BYOK) | 🟢 **Green for self-hosted per-user access** — same shape as JPO / KIPO / TIPO / INPI France |
| Rating (zero-infra proxy) | 🔴 Red — §3.2 redistribution prohibition forecloses this |
| Primary sources | [DPMAconnectPlus overview (DE)](https://www.dpma.de/recherche/datenabgabe/dpmaconnect/index.html) · [Interface spec (DE PDF)](https://www.dpma.de/docs/recherche/dienste/schnittstellenbeschreibungdpmaconnectplus.pdf) · [Standardvertrag DPMAconnectPlus, Stand 01.04.2020 (DE PDF)](https://www.dpma.de/docs/recherche/dienste/standardvertrag_dpmaconnectplus.pdf) |

The API is technically attractive — structured `Expertenrecherche` query
syntax (Boolean + 50+ INID-coded fields like `INH=` (proprietor),
`AT=` (application), `IC=` (IPC class), `WAKZ=` (PCT family)),
production-grade XSDs. The legal posture is more permissive than the
older synopsis claimed: §3.2 prohibits **rebroadcasting the data
records** (zero-infra proxy ruled out), not self-hosted operation by
the contracting party. §2.1's fixed-IP requirement is in fact the
self-host shape — no shared cloud egress IP unless pre-registered.
Foreign signup is permitted (Anlage 1 accepts any country; §8 ships
EU Standard Contractual Clauses for non-EU/EEA Datenempfänger).
See [`waves/2026-05-18-priority-2-synopses/dpma-byok-rating.md`](../waves/2026-05-18-priority-2-synopses/dpma-byok-rating.md)
for the contract re-read.

### DPMAregister web UI

| Field | Value |
|---|---|
| Endpoint | `register.dpma.de` |
| Auth | none (CAPTCHA on some endpoints) |
| Format | HTML, CSV/XLSX export (≤cap), PDF for in-register file inspection |
| ToS posture | UI use only; scraping not encouraged |
| Verdict | 🔴 Red — UI scraping is brittle and against the spirit of the access policy |

### DEPATISnet (patent search UI)

| Field | Value |
|---|---|
| Endpoint | `depatisnet.dpma.de` |
| Auth | none |
| Format | HTML, CSV/XLSX (≤100 rows), PDF/TIFF |
| ToS posture | Public UI; scraping not formally addressed |
| Verdict | 🔴 Red — overlaps EPO OPS DE coverage; brittle |

### DPMA backfile bulk

| Field | Value |
|---|---|
| Endpoint | Contract-gated bulk delivery (DPMA datenabgabe) |
| Cost | Paid provision per package |
| Format | WIPO ST.36 patents, ST.86 designs, images |
| Verdict | 🔴 Red — bulk doesn't fit our zero-infra constraint |

## §4 Fees

DPMA publishes separate fee schedules for patents, utility models,
designs, and trademarks. Statutory basis is the **Patentkostengesetz
(PatKostG)** — German Patent Costs Act. DPMAconnectPlus (the bulk API
contract) has its own separate access fee.

- **Official schedule (EN):** [DPMA — Fees and Costs (English)](https://www.dpma.de/english/services/fees/index.html)
- **Official schedule (DE):** [DPMA — Gebühren](https://www.dpma.de/service/gebuehren/index.html)
- **Statutory basis:** [Patentkostengesetz (PatKostG)](https://www.gesetze-im-internet.de/patkostg/) — full text at gesetze-im-internet.de.


## §5 Connector strategy

### What we cover today

- [`patent_client_agents.dpma_register`](../../src/patent_client_agents/dpma_register/) — six env-gated DPMAconnectPlus tools for German patents and utility models, national trademarks, and national designs. This beta is tested only with synthetic XML fixtures. Live account compatibility is not verified.
- [`patent_client_agents.dpma_statutes`](../../src/patent_client_agents/dpma_statutes/) — bundled SQLite/FTS5 corpus of the six core German IP Acts (PatG, MarkenG, GebrMG, DesignG, UrhG, GeschGehG); manifest entry `DE/DPMA/Statutes`.
- DE patent biblio + family via [`patent_client_agents.epo_ops`](../regional/epo.md) (transitive).

### Community validation needed

- A DPMAconnectPlus account holder should test the beta from its registered static IP. Sanitized XML samples are welcome if they contain no credentials, personal data, or confidential records.
- Until that validation occurs, describe the connector as provisional or beta support. Do not call it production-ready or live-verified.

### What we should NOT add (and why)

- **DPMA-as-zero-infra-proxy on the hosted demo** — §3.2 prohibits us rebroadcasting the data records to third parties. The hosted demo at `mcp.patentclient.com` cannot carry DPMAconnectPlus credentials; that's a design boundary, not a build gap.
- **DEPATISnet scrape** — brittle, UI-only, and redundant with EPO OPS DE coverage at the biblio/family layer. 5,000-hit/day per-IP cap on the UI is explicitly anti-automation.
- **DPMAregister live scrape** — same; CAPTCHA-gated, same 5,000/day cap, redirects volume users to DPMAconnectPlus.

### What we *could* add later

- **`dpma_caselaw`** — BPatG decisions via rechtsprechung-im-internet.de XML feed + BGH via the RiI daily feed. Substantive law / case law layer, no register proxy. See [`connectors/dpma.md`](../connectors/dpma.md) §7 for the asset details.

### Next steps

1. Seek live community validation without collecting or sharing credentials.
2. Adjust XML field mappings only after sanitized real responses show a schema difference.
3. Watch BPatG case-law coverage as a substantive-law expansion target.

## §6 Open questions

- **Signup operational path.** §3.2 of the standard contract permits BYOK; the open question is *how* to submit it — postal-only ("Präsidentin des DPMA, 80297 München") or signed-PDF email? Test-account workflow vs. production-account workflow? Both undocumented in primary sources read so far.
- **VAT treatment for non-EU contracting parties.** EUR 200 base fee per §4.2; §8 ships EU-SCC for non-EU/EEA Datenempfänger but doesn't address VAT.
- **DPMAregister modernization timeline.** No primary source found.

## §7 References

Primary sources only.

**Service overviews:**
- [DPMAconnectPlus overview (EN)](https://www.dpma.de/english/search/data_supply_services/dpmaconnect/index.html)
- [DPMA Search & Information Products (EN)](https://www.dpma.de/english/search/data_supply_services/index.html)

**Technical specs:**
- [Interface spec — DPMAconnectPlus (DE PDF)](https://www.dpma.de/docs/recherche/dienste/schnittstellenbeschreibungdpmaconnectplus.pdf)
- [Legacy DPMAconnect SOAP API spec (DE PDF)](https://www.dpma.de/docs/recherche/dienste/dpmaconnectapibeschreibung.pdf)

**Legal terms:**
- [Standardvertrag DPMAconnectPlus, Stand 01.04.2020 (DE PDF)](https://www.dpma.de/docs/recherche/dienste/standardvertrag_dpmaconnectplus.pdf) — the actual standard contract; §3.2 prohibits rebroadcasting data records (carve-out for purpose 1(b)). The older URL `dpmaconnectplusvertragsbedingungen.pdf` cited in the 2026-05-16 synopsis returns DPMA's 404 page.
- [Anlage 1 — Datenpaket-Bestellblatt (DE PDF)](https://www.dpma.de/docs/recherche/dienste/anlage_2_standardvertragdpmaconnectplus.pdf)
- [Anlage 2 — EU-Standardvertragsklauseln (DE PDF)](https://www.dpma.de/docs/recherche/dienste/anlage_3_standardvertragdpmaconnectplus.pdf)

**Fees:**
- [DPMA fees (EN)](https://www.dpma.de/english/services/fees/index.html)
- Patentkostengesetz (PatKostG) — statutory basis

**Detail survey + wave:**
- [`connectors/dpma.md`](../connectors/dpma.md) — full 211-line asset survey
- [`waves/2026-05-16-registered-ip-discovery/dpma-germany.md`](../waves/2026-05-16-registered-ip-discovery/dpma-germany.md)

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-16 | Initial synopsis. Reconciled the original "Tier 2 paid+contract" framing — the actual blocker is **contract §3.2 (no third-party redistribution)**, not the EUR 200 cost. | [waves/2026-05-16-registered-ip-discovery/dpma-germany.md](../waves/2026-05-16-registered-ip-discovery/dpma-germany.md) |
| 2026-05-18 | **BYOK unlock.** Contract re-read of the actual `standardvertrag_dpmaconnectplus.pdf` (Stand 01.04.2020) — earlier framing "§3.2 prohibits proxy use" was a misread of a clause that actually prohibits **rebroadcasting the data records**, with an explicit carve-out for purpose §3.1(b). Self-hosted per-user access by the contracting party is permitted; the older URL the synopsis cited (`dpmaconnectplusvertragsbedingungen.pdf`) 404s. Rating updated red_contract → yellow_byok; connector queued. | [waves/2026-05-18-priority-2-synopses/dpma-byok-rating.md](../waves/2026-05-18-priority-2-synopses/dpma-byok-rating.md) |
| 2026-08-03 | Rechecked the service page, interface description, and standard contract. Corrected the design schema reference to ST.86 and promoted the connector to `spec_ready`. | [specs/de-dpma-connector-spec.md](../specs/de-dpma-connector-spec.md) |
| 2026-08-03 | Shipped `dpma_register` as a beta with synthetic XML tests. Live DPMAconnectPlus compatibility remains unverified, and community validation is invited. | [`patent_client_agents.dpma_register`](../../src/patent_client_agents/dpma_register/) |
