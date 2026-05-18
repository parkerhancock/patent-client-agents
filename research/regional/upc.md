# UPC Unified Patent Court (UPC) — regional

**Layer:** regional
**Jurisdiction:** n/a (supranational court; 18 EU contracting member states as of 2026-05 — AT, BE, BG, DK, EE, FI, FR, DE, IT, LV, LT, LU, MT, NL, PT, RO, SI, SE)
**Issuing body:** Unified Patent Court (Court of First Instance: Munich / Paris / Milan Central Divisions, 13 Local Divisions + Nordic-Baltic Regional Division; Court of Appeal: Luxembourg)
**Rights administered:** patent (judicial — first-instance and appellate jurisdiction over Unitary Patents and, subject to opt-out, traditional European Patents)
**Working languages:** English, French, German (Central Division + Court of Appeal); local procedural languages at the Local Divisions (DE, IT, NL, FR, SE/EN, etc.)
**Connector status:** **active** (both decisions feed and statutes corpus shipped in v0.11.0; CMS Public Read API blocked on enrollment — see §6)
**Last verified:** 2026-05-18
**Manifest entries:**
- [`UPC/UPC/Decisions`](../../coverage/sources.yaml) — `patent_client_agents.upc_decisions`
- [`UPC/UPC/Statutes`](../../coverage/sources.yaml) — `patent_client_agents.upc_statutes`

**Detail surveys:**
- [`connectors/upc.md`](../connectors/upc.md) — 2026-05 detail survey (668 lines, includes the 2026-05-13 empirical CMS-API enrollment probe)
- [`waves/2026-05-18-priority-1-shipped/upc.md`](../waves/2026-05-18-priority-1-shipped/upc.md) — distilled shipped-state research note

**Sibling layers carrying overlapping data:**
- **EPO OPS** ([`regional/epo.md`](epo.md)) — Unitary Patent Register lives at the EPO, **not** the UPC. UP status, designated-state coverage, and the `C0` publication marker for unitary effect are surfaced via the EPO European Patent Register service. The UPC is the *court*; the EPO is the *registry*.
- **National IP courts** — many UPC cases run in parallel with national infringement / nullity actions (e.g. DE BPatG, TJ Paris). Cross-linking requires bespoke identifier mapping; not folded into either shipped UPC connector today.
- **CJEU** — preliminary references the UPC may make to the CJEU on EU law questions. Coverage planned via `eurlex_cellar`, **not** a UPC surface.

---

## §1 Mission

The Unified Patent Court is the single supranational forum for litigating
Unitary Patents and (subject to opt-out during the transitional period)
traditional European Patents within the contracting EU member states.
It went live **2023-06-01**, jointly with the Unitary Patent system. It
is **not** part of the CJEU/General Court system even though the Court
of Appeal sits in Luxembourg; UPC and CJEU are parallel court systems
that intersect only via preliminary references on EU law questions.

For agents, the UPC matters for three reasons that no other entity in
the catalog covers: (1) it is the **only** source of substantive case
law on the scope and validity of European Patents under a unified
European jurisprudence (national courts produce parallel but
non-binding national rulings); (2) its rules — the UPC Agreement
(UPCA) and the Rules of Procedure (RoP, 18th draft in force 2022-09-01)
— are themselves a novel and rapidly-developing body of substantive
patent procedural law; and (3) its **opt-out registry** is the
authoritative answer to *"does the UPC have jurisdiction over this
EP?"*, which is increasingly load-bearing for European patent strategy.

## §2 What's unique here

- **UPC case law** — first-instance and Court-of-Appeal decisions on EP
  scope, validity, infringement, and provisional measures. ~946 CFI
  cases by end-2025 per [Bird & Bird's UPC in numbers](https://www.twobirds.com/en/insights/2026/the-upc-in-numbers-32-months-of-action),
  growing ~50% YoY. The corpus is small but the precedent value per
  decision is unusually high — there is no other source of UPC case law.
- **UPCA + Rules of Procedure** — the substantive corpus that governs
  every UPC proceeding. Free PDFs on
  [`unifiedpatentcourt.org/en/court/legal-documents`](https://www.unifiedpatentcourt.org/en/court/legal-documents).
  No third party hosts the canonical text; the Casalonga interactive
  cross-reference is useful but not authoritative.
- **Opt-out registry** — the only authoritative source for whether a
  given traditional EP has been opted out of UPC jurisdiction. Surfaced
  by the UPC via the CMS public search at
  [`/en/registry/opt-out`](https://www.unifiedpatentcourt.org/en/registry/opt-out)
  (UI) and the v5.3 CMS Public Read API (`/v5/opt-out/list`,
  `/v5/opt-out/patentStatus`) — but the read-API host blocks
  unenrolled callers at TLS handshake. See §3 / §6.
- **Case-ID taxonomy** — `UPC_CFI_n/yyyy` (Court of First Instance),
  `UPC_CoA_n/yyyy` (Court of Appeal), `ACT_NNNNNN/yyyy` (CMS action
  IDs). ECLI is **not** systematically assigned; downstream
  normalization with national EU case-law databases needs a custom map.

## §3 Programmatic surfaces

### Decisions and Orders index (HTML + PDF/A)

| Field | Value |
|---|---|
| Endpoint | `https://www.unifiedpatentcourt.org/en/decisions-and-orders` (also `/fr/...`, `/de/...`) |
| Auth | none |
| Format | HTML index pages → PDF/A per decision (mandated by RoP for all UPC documents) |
| Rate limit | not published; observed polite limits, no 429s on 1 RPS |
| ToS posture | permissive for public-record consumption |
| Rating (zero-infra proxy) | 🟢 **Green** — shipped at [`patent_client_agents.upc_decisions`](../../src/patent_client_agents/upc_decisions/) |
| Primary source | [Decisions and Orders](https://www.unifiedpatentcourt.org/en/decisions-and-orders) |

Drupal Views-backed listing. Per-decision detail pages at `/en/node/<id>` are gated by Cloudflare's interactive challenge, but **the listing rows already carry every structured field needed** (case ID, division, type of action, parties, PDF URL), so our harvester reads only the listing pages. Pagination via `?page=N` (0-indexed) — and beware the Drupal quirk that `?page=0` renders the *empty* template; omit the param entirely for the first page. PDF/A attachments are not Cloudflare-gated and stream directly.

### UPCA + Rules of Procedure (statutes corpus)

| Field | Value |
|---|---|
| Endpoint | `https://www.unifiedpatentcourt.org/en/court/legal-documents` |
| Auth | none |
| Format | PDF + HTML (UPCA, Statute of the UPC = Annex I, Rules of Procedure, Rules on Court Fees and Recoverable Costs, Code of Conduct for Representatives) |
| Rate limit | n/a — static documents |
| ToS posture | permissive — official treaty + RoP text |
| Rating | 🟢 **Green** — shipped at [`patent_client_agents.upc_statutes`](../../src/patent_client_agents/upc_statutes/), bundled SQLite/FTS5 corpus + EN/FR/DE parallel |
| Primary source | [UPC legal documents](https://www.unifiedpatentcourt.org/en/court/legal-documents) |

Frozen snapshot in a bundled SQLite/FTS5 corpus following the same `StaticLawCorpus` pattern as `mpep`, `epc`, `ipo_in_statutes`, `dpma_statutes`, and `legifrance_ip`. `get_corpus_status()` exposes `corpus_synced_at` / `corpus_version` for the CONNECTOR_STANDARDS §4 provenance stamp.

### CMS Public Read API v5.3 (search + opt-out registry — blocked)

| Field | Value |
|---|---|
| Endpoint | `https://api-prod.unified-patent-court.org/upc/public/api/v5/` (presumed; pre-prod equivalent at `api-pre-prod...`) |
| Auth | OAuth2 bearer (1800-second lifetime) — replaces the legacy `X-API-KEY` |
| Format | JSON (10 GET-only paths, 64 schema definitions per `swagger_v5-3.json`) |
| Rate limit | not published |
| ToS posture | enrollment-only — registration channel undocumented as of 2026-05 |
| Rating | 🔴 **Red** today — read-API host rejects TLS at the network layer from unenrolled clients (no `ServerHello` returned). Filing-UI Keycloak credentials do **not** bootstrap into read-API access; they are separate systems. See [`connectors/upc.md`](../connectors/upc.md) §6 of the 2026-05-13 update. |
| Primary sources | [Swagger v5.3 JSON](https://www.unifiedpatentcourt.org/sites/default/files/upc_technical_files/swagger_v5-3.json) (Cloudflare-gated for direct GETs; canonical snapshot at [`research/openapi/upc_cms_public_api_v5-3.json`](../openapi/upc_cms_public_api_v5-3.json)); [Opt-Out Register UI](https://www.unifiedpatentcourt.org/en/registry/opt-out); [v1.4 PDF (superseded)](https://www.unifiedpatentcourt.org/sites/default/files/upc_documents/upc-cms-public-api-documentation_v1_4.pdf) |

The v5.3 spec defines `/v5/cases`, `/v5/documents/{caseType}/{number}/{year}`, `/v5/documents/download/{id}`, `/v5/opt-out/list`, `/v5/opt-out/patentStatus`, `/v5/opt-out/statusTypes`, `/v5/representatives`, `/v5/representatives/representationEntitlements`, `/v5/languages`, and `/v5/caseTypes`. Of these, `/v5/opt-out/list` is the highest-leverage public-API asset — it answers *"is this EP opted out?"*. Enrollment workflow is undocumented; the Athena contact form is the only known channel. The auth model (OAuth-only vs OAuth + mTLS vs OAuth + IP allowlist) is **unresolved**; [DigiCert/QuoVadis publishes "UPC Authentication Certificates"](https://www.digicert.com/tls-ssl/unified-patent-court-certificates) which is suggestive of mTLS being part of the picture but not dispositive.

### A2A API (write-side, regulated)

Not in scope. The CMS A2A API is the representative-law-firm filing channel (opt-out submission and case filings). OAuth2-gated, regulated, and mis-use has live-case consequences. Skip absent a paying customer who is a UPC representative.

## §4 Fees

**Policy: link only.** Reproducing fee amounts is *not our job* — fee
schedules drift, and only the authoritative source is current.

The UPC publishes its fee schedule in **EUR**, covering case-management
fees (proportional to value-in-dispute), opposition / counterclaim
fees, appeal fees, fee reductions for SMEs / natural persons /
non-profits / universities, and the (currently zero) **opt-out / opt-out
withdrawal** fees. The Table of Court Fees and Recoverable Costs is
adopted by the UPC Administrative Committee and consolidated in the
"Rules on Court Fees and Recoverable Costs" document on the legal-documents
page.

- **Official schedule:** [Rules on Court Fees and Recoverable Costs (UPC legal documents)](https://www.unifiedpatentcourt.org/en/court/legal-documents)
- **Statutory basis:** [UPC Agreement (UPCA), Article 36](https://www.unifiedpatentcourt.org/en/court/legal-documents) — court financing and fees
- **Rate adjustment notices:** UPC Administrative Committee decisions published at [unifiedpatentcourt.org news](https://www.unifiedpatentcourt.org/en/news)

Notable discount / exemption programs *(name + one-line eligibility — no amounts or dates)*:

- **SME / natural-person / non-profit / university discount** — 40% reduction on certain fees per Table of Court Fees Pt. 1.
- **Opt-out / opt-out withdrawal** — currently no fee, per the consolidated Table.

## §5 Connector strategy

### What we cover today

- [`patent_client_agents.upc_decisions`](../../src/patent_client_agents/upc_decisions/) — HTML scrape of the decisions-and-orders index. Surfaces: `search_decisions()` (paginated, filterable by `judgement_type` / `court_type` / `division` / `proceedings_lang`), `get_decision(case_id)` (canonical-ID lookup; walks pages), `download_decision_pdf(url)` (PDF/A binary), plus `list_divisions()` / `list_languages()` to discover filter IDs. Case-ID canonicalization handles all observed source variants (`UPC_CFI_1747/2025`, `UPC-CFI-478/2025`, `UPC_CFI_0001695/2025`, `UPC_CoA_335/2023`, `UPC-COA-35/2026`, `ACT_551054/2023`).
- [`patent_client_agents.upc_statutes`](../../src/patent_client_agents/upc_statutes/) — bundled SQLite/FTS5 corpus of UPCA + Statute (= Annex I) + RoP + Court Fees Rules + Code of Conduct. Instrument aliases accepted (`upca`, `rop`, `rules of procedure`, `fees`, `coc`, `statute`). EN/FR/DE parallel. `search()` supports `and` / `or` / `adj` / `exact` syntax via FTS5 with BM25 ranking; `get_instrument()` returns full text; `get_corpus_status()` returns snapshot date / version for §4 provenance stamping.

### What we could add

1. **Decision PDF/A text extraction** — neither connector parses the PDF body today; callers fetch the binary and OCR / extract themselves. A `decision_text(case_id)` helper that runs `pdfminer` against the PDF/A would unlock "find decisions discussing inventive step" agentic flows. The corpus is small enough (~thousands of decisions, not millions) that bulk extraction is tractable.
2. **CMS Public Read API client** — `upc_cms` with the v5.3 surface, gated on enrollment resolution (§6 #1). High-leverage if/when enrollment opens up: `/v5/opt-out/list` and `/v5/opt-out/patentStatus` would let us answer *"is this EP opted out?"* programmatically, pairing with `epo_ops` UP-aware helpers for a complete EP-status picture. The OAuth2 scaffold is already battle-tested by `euipo_*` (`OAuth2ClientCredentialsAuth` in `law_tools_core.oauth2`); ~2-3 days end-to-end if auth turns out to be OAuth-only, longer if mTLS is required.
3. **EPO OPS UP-aware helpers** — `get_unitary_patent_package(ep_number)`, `get_upc_opt_out_status(ep_number)`. The UP register lives at the EPO, not the UPC, and OPS already exposes `C0` + `B7000` / `B920` markers for unitary effect. These would live in `epo_ops`, not a UPC module.
4. **Decision metadata enrichment** — link each row's parties to canonical applicant entities, add procedural-language detection, normalize division names to a stable taxonomy. Useful for analytics but not load-bearing for the v1 connector.

### What we should NOT add

- **CMS A2A API wrapper** — regulated filing channel for representative law firms. Wrapping it doesn't add agent value (you can't agentically file opt-outs on behalf of unrelated proprietors), mis-use has live-case consequences, and OAuth-only credentials would need to be per-firm. Skip unless a paying customer is a UPC representative.
- **PACER-style live filings index** — RoP 262 / 262A confidentiality + per-document Registry vetting kills the cost-benefit. Decisions and orders are public; pleadings and exhibits are presumptively confidential. No equivalent of PACER for the UPC.
- **Commercial tracker scraping** (United Patents, upc.law, Osborne Clarke, Wolters Kluwer, Bristows, JUVE Patent) — ToS-hostile, redundant given the CMS+decisions feed, brittle HTML.
- **CJEU IP rulings via UPC** — wrong gateway; planned `eurlex_cellar` handles CJEU directly. UPC ↔ CJEU intersect only via preliminary references.

### Next steps

1. **Submit the Athena contact-form enrollment query** drafted in [`connectors/upc.md`](../connectors/upc.md) §6 — this is the only documented channel to resolve the CMS Public Read API enrollment workflow. Until that's answered, the read API stays blocked at 🔴 red.
2. **Spec the EPO OPS UP helpers** as a small follow-on PR against `epo_ops` (not a new module) — cheap, unblocks "is this EP opted out?" via the OPS register markers without needing UPC CMS enrollment.
3. **Watch PMAC opening (2026-06-02)** — the Patent Mediation and Arbitration Centre may publish anonymized awards / consent decrees, either as a separate feed or folded into the existing decisions registry. Watch-list item.

## §6 Open questions

- **CMS Public Read API enrollment.** Pending the Athena-form response. Specifically: (a) is read-API enrollment separate from CMS Filing UI signup, (b) does it require a QuoVadis/DigiCert client TLS cert (mTLS), (c) does it require source-IP allowlisting, and (d) what is the canonical public-facing base URL (the Swagger's `host: upcbe` is an internal placeholder).
- **Long-term API stability.** The UPC's own public developer documentation is young — the v1.4 PDF (Feb 2023) is still linked from `/en/registry/it-developers` despite being superseded by v5.3 Swagger. Expect further surface drift through 2026-2027 as the new-CMS rollout completes.
- **Opt-out withdrawal asymmetry.** Opt-out *creation* is over the A2A API; *withdrawal* of an existing opt-out is web-UI-only via the CMS Front Office. That's a hard product constraint — agents using any opt-out write surface must understand the asymmetry.
- **Decisions feed text extraction quality.** PDF/A decisions vary in layout extractability across divisions. A spot-check across 10 decisions per division is required before committing to a structured "decision text" feed (Open Q #5 in the detail survey).
- **ECLI assignment.** UPC doesn't natively assign ECLIs. Cross-linking to national EU case-law databases (`eurlex_cellar`, planned `de_caselaw`) requires either synthetic `ECLI:EU:UPC:yyyy:nnn` identifiers (risky — not official) or native `UPC_*/yyyy` IDs with a sidecar map. Default to native + optional sidecar.
- **PMAC data surface (2026-06-02 onward).** Will the Patent Mediation and Arbitration Centre publish a structured feed of awards / consent decrees, or fold into the existing UPC decisions registry?

## §7 References

Primary sources only.

**Court + court structure:**
- [Unified Patent Court — homepage](https://www.unifiedpatentcourt.org/en)
- [Court presentation (structure, divisions, seats)](https://www.unifiedpatentcourt.org/en/court/presentation)
- [UPC member states (current 18)](https://www.unifiedpatentcourt.org/en/organisation/upc-member-states)

**Data feeds:**
- [Decisions and Orders index](https://www.unifiedpatentcourt.org/en/decisions-and-orders) — operational source for `upc_decisions`
- [Opt-Out Register (public search)](https://www.unifiedpatentcourt.org/en/registry/opt-out) — authoritative opt-out registry; structured access via CMS API only
- [For IT developers (developer portal landing)](https://www.unifiedpatentcourt.org/en/registry/it-developers)
- [CMS Public API v5.3 Swagger JSON](https://www.unifiedpatentcourt.org/sites/default/files/upc_technical_files/swagger_v5-3.json) — current authoritative read-API spec (Cloudflare-gated; canonical offline copy at [`research/openapi/upc_cms_public_api_v5-3.json`](../openapi/upc_cms_public_api_v5-3.json))
- [CMS Public API v1.4 PDF (superseded)](https://www.unifiedpatentcourt.org/sites/default/files/upc_documents/upc-cms-public-api-documentation_v1_4.pdf)
- [CMS A2A API v2.6](https://www.unifiedpatentcourt.org/sites/default/files/upc_documents/upc-cms-a2a-api-documentation_v2_6.pdf) — write-side, regulated
- [Update on public APIs following new-CMS launch](https://www.unifiedpatentcourt.org/en/news/update-public-apis-following-launch-first-phase-new-cms-roll-out)
- [Automated opt-outs via A2A API — 2025-07-28 update](https://www.unifiedpatentcourt.org/en/news/new-cms-release-automated-opt-outs-a2a-api-update-28-july-2025)

**Substantive law:**
- [UPC legal documents (UPCA / Statute / RoP / Fees / Code of Conduct)](https://www.unifiedpatentcourt.org/en/court/legal-documents)
- [Unitary Patent system on EPO](https://www.epo.org/en/applying/european/unitary)
- [Unitary Patent information in EPO patent knowledge](https://www.epo.org/en/searching-for-patents/helpful-resources/unitary-patent-information)

**Enrollment / contact:**
- [Athena contact form](https://athena.unifiedpatentcourt.org/marketplace/formcreator/front/formdisplay.php?id=1) — only documented contact channel for read-API enrollment questions
- [DigiCert/QuoVadis — UPC Authentication Certificates](https://www.digicert.com/tls-ssl/unified-patent-court-certificates) — suggestive of mTLS as part of the access model

**Detail survey:**
- [`connectors/upc.md`](../connectors/upc.md) — 2026-05 detail survey including the 2026-05-13 empirical CMS-API enrollment probe (§6 update)

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-18 | Initial synopsis. Distilled from [`connectors/upc.md`](../connectors/upc.md) (668 lines) and the v0.11.0 shipped state of `upc_decisions` + `upc_statutes`. Flagged CMS Public Read API as 🔴 red pending Athena-form enrollment resolution; decisions feed + statutes corpus rated 🟢 green. | — |
