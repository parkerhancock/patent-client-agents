# IPONZ New Zealand (NZ) — national

**Layer:** national
**Jurisdiction:** NZ (WIPO ST.3: NZ)
**Issuing body:** Intellectual Property Office of New Zealand (IPONZ), a business unit of the Ministry of Business, Innovation and Employment (MBIE)
**Rights administered:** patent, trademark, design, plant_variety, geographical_indication
**Working languages:** English
**Connector status:** **planned (yellow — BYOK, well-documented)**
**Last verified:** 2026-05-18
**Manifest entry:** not yet listed (planned)

**Detail surveys:**
- [`waves/2026-05-18-secondary-nationals-wave/nz-iponz.md`](../waves/2026-05-18-secondary-nationals-wave/nz-iponz.md) — 2026-05-18 grounded API discovery

**Higher layers covering this office transitively:**
- **NZ is NOT an EPC contracting state** → no EPO OPS / INPADOC coverage for NZ national patents.
- **NZ IS a PCT member** → PCT-level visibility via WIPO PATENTSCOPE; NZ national-phase detail still requires IPONZ.
- **NZ IS a Madrid member** (since 2012) → IR designations of NZ via WIPO Madrid Monitor.
- **NZ is NOT a Hague member** → no Hague IR design coverage of NZ.
- **NZ is NOT in the EU** → no EUIPO transitive coverage (no EUTM / RCD route).
- **PVR and GI** — no higher-layer substitute; IPONZ is sole source.

---

## §1 Mission

IPONZ is the sole national IP office of New Zealand — registrar for
NZ national patents, trade marks, designs, plant variety rights, and
geographical indications. Because **NZ is not an EPC contracting
state and not a Hague Agreement member**, none of the regional
shortcut routes (EPO OPS / INPADOC for patents, Hague for designs,
EUIPO for TMs/designs) carry NZ data. Madrid Monitor covers IR
designations of NZ trade marks, and PATENTSCOPE covers NZ at the
PCT layer, but **every NZ national-phase patent, every direct
national trade-mark filing, every NZ design, all PVR, and all GI
records require IPONZ as the primary surface**. IPONZ also hosts the
joint Trans-Tasman patent attorney register with IP Australia (an
attorney-licensing register, not subject-matter data), and a
voluntary "single application" co-filing concept exists with IP
Australia but does not produce a unified right.

What makes IPONZ a meaningful target despite the per-user
credentials: it ships **the single cleanest documented
per-subscriber API surface among secondary-nationals surveyed
2026-05-18** — a versioned v5 product on the MBIE shared API
gateway, with published OpenAPI spec, PDF data dictionaries, and an
explicit sandbox tier.

## §2 What's unique here

- **NZ national patents** — direct national filings *and* PCT
  national-phase entries; no EPC route, no EPO OPS substitute.
- **NZ trade marks** — national filings + IR designations under
  Madrid; the API exposes both.
- **NZ designs** — entire register; no Hague IR substitute (NZ is
  not in the Hague Agreement). Substantive law is the
  [Designs Act 1953 No 65](https://www.legislation.govt.nz/act/public/1953/0065/latest/DLM281071.html) —
  one of the oldest still-in-force IP statutes globally.
- **NZ plant variety rights (PVR)** — UI-only on the Case Management
  Facility (`EXTRA_pvr_qbe`); not in the v5 API.
- **NZ geographical indications** — static register page; not in
  the v5 API. Includes the NZ wine PGI register.
- **NZ patent file documents** — only via the IPONZ document-
  retrieval SOAP operation (Base64-encoded payload), not in any
  upstream layer.
- **Joint Trans-Tasman patent attorney register** with IP Australia
  ([`ttipattorney.gov.au`](https://www.ttipattorney.gov.au/)).

## §3 Programmatic surfaces

### IPONZ API v5 (MBIE shared API gateway)

| Field | Value |
|---|---|
| Endpoint (prod) | `https://api.business.govt.nz/gateway/iponz/v5/` |
| Endpoint (sandbox) | `https://api.business.govt.nz/sandbox/iponz/…` |
| Developer portal | [`portal.api.business.govt.nz/api/iponz`](https://portal.api.business.govt.nz/api/iponz) |
| Auth | RealMe login → MBIE subscription key + optional OAuth2 bearer; chargeable operations require a registered IPONZ user with direct-debit/credit billing |
| Format | REST + JSON (search, renewals, public-data); SOAP + XML (document retrieval, application submit, correspondence) |
| Rate limit | per-subscription quota in portal (Azure APIM); `/trademarksearch` capped at 2,000 hits per call |
| ToS posture | per-subscriber API use free for registered IPONZ users; **register data carved out of Crown-copyright re-use grant** ([copyright statement](https://www.iponz.govt.nz/about-iponz/copyright/)) |
| Rating (zero-infra proxy) | 🟡 **Yellow — BYOK** |
| Primary source | [IPONZ API page](https://www.iponz.govt.nz/about-iponz/iponz-api/) → [portal entry](https://portal.api.business.govt.nz/api/iponz) |

Documented v5 surface covers **patents, trade marks, and designs**.
The data-dictionary PDFs on the portal list the field inventory for
each: [Patent Information](https://portal.api.business.govt.nz/content/IPONZ%20API%20-%20Patent%20Information%20data%20dictionary.pdf),
[Trade Mark Information](https://portal.api.business.govt.nz/content/IPONZ%20API%20-%20Trade%20Mark%20Information%20data%20dictionary.pdf),
[Design Information](https://portal.api.business.govt.nz/content/IPONZ%20API%20-%20Design%20Information%20data%20dictionary.pdf),
[Submit Trade Mark](https://portal.api.business.govt.nz/content/IPONZ%20API%20-%20Submit%20Trade%20Mark%20data%20dictionary.pdf),
[Submit Patent](https://portal.api.business.govt.nz/content/IPONZ%20API%20-%20Submit%20Patent%20data%20dictionary.pdf).
Why yellow rather than green: there is **no anonymous public-search
tier** — every caller needs their own RealMe + IPONZ subscription
key. Clean, but the per-user posture rules out a single-credential
hosted proxy.

### Case Management Facility (consumer search UI)

| Field | Value |
|---|---|
| Endpoint | [`app.iponz.govt.nz/app/Extra/Default.aspx?op=…`](https://app.iponz.govt.nz/) |
| Auth | session cookies; RealMe for logged-in flows |
| Format | ASP.NET HTML (302 → `Qbe.aspx?sid=…`) |
| Rating | 🔴 Red — HTML SPA; Imperva WAF actively defends against scraping; the v5 API is the better target for patents / TMs / designs |
| Primary source | linked from [IPONZ home navigation](https://www.iponz.govt.nz/) |

Carries five route groups: `EXTRA_pt_qbe` (patents),
`EXTRA_tm_qbe` (trade marks), `EXTRA_ds_qbe` (designs),
`EXTRA_pvr_qbe` (plant variety rights), `EXTRA_Activity_qbe`
(Online Journal). **PVR has no v5 API equivalent — it lives only
here.** GI is similar.

### IPONZ dataset on catalogue.data.govt.nz

| Field | Value |
|---|---|
| Endpoint | [`catalogue.data.govt.nz/dataset/iponz`](https://catalogue.data.govt.nz/dataset/iponz) |
| Auth | none |
| Format | dataset metadata points back to the API as access path; statistical exports ("application volumes since 2014") |
| Rating | 🔴 Red against zero-infra proxy — pointer record, not a register data feed |
| Primary source | NZ open-data catalogue |

Confirms no bulk register feed exists. The dataset record advertises
the API as the access path. The CKAN catalogue itself sits behind a
Distil bot challenge so direct CKAN-API search needs a real
User-Agent and session cookies.

### WIPO IP API Catalog

| Field | Value |
|---|---|
| Endpoint | [`apicatalog.wipo.int`](https://apicatalog.wipo.int/) |
| Result | **0 IPONZ entries** as of 2026-05-18 probe (179 total across DPMA, EPO, EUIPO, IP Australia, JPO, MOIP KOREA, QAZ, UPRP, USPTO, WIPO) |
| Rating | informational — confirms IPONZ has not (yet) self-registered against the canonical inventory, despite running a documented API |

## §4 Fees

**Policy: link only.**

IPONZ publishes fee schedules (in NZD; GST 15% additionally where
the requester is in NZ) covering patents (filing, examination,
maintenance, acceptance, renewals), trade marks (per class
application, renewal, opposition), designs (filing, renewal), plant
variety rights, and miscellaneous services (file inspection,
certified copies). Statutory basis sits in the three primary Acts:
the [Patents Act 2013 No 68](https://www.legislation.govt.nz/act/public/2013/0068/latest/whole.html),
the [Trade Marks Act 2002 No 49](https://www.legislation.govt.nz/act/public/2002/0049/latest/dlm164240.html),
and the still-current [Designs Act 1953 No 65](https://www.legislation.govt.nz/act/public/1953/0065/latest/DLM281071.html),
each with implementing regulations setting the fee tables.

- **Patent fees:** [IPONZ — Patent fees](https://www.iponz.govt.nz/get-ip/patents/fees/)
- **Trade mark fees:** [IPONZ — Trade mark fees](https://www.iponz.govt.nz/get-ip/trade-marks/fees/)
- **Design fees:** [IPONZ — Design fees](https://www.iponz.govt.nz/get-ip/designs/fees/)
- **Fee review consultations (MBIE):** [Consultation on changes to IPONZ fees](https://www.mbie.govt.nz/have-your-say/consultation-on-changes-to-fees-charged-by-the-intellectual-property-office-of-nz)
- **PCT national-phase fees (NZ):** [PCT Applicant's Guide — New Zealand](https://pctlegal.wipo.int/eGuide/view-doc.xhtml?doc-code=NZ&doc-lang=en)

Notable discount programmes *(name only — no amounts or dates per
policy)*:

- **PCT national-phase rate** — reduced filing fee applies when
  entering NZ from a PCT international application, per IPONZ's
  patent-fees page.
- **API access free for registered IPONZ users** — there is no fee
  for *use of the API* (statutory transaction fees still apply).

## §5 Connector strategy

### What we cover today

- **Madrid IRs designating NZ** — transitively via planned WIPO
  Madrid Monitor connector.
- **NZ at the PCT layer** — transitively via planned WIPO
  PATENTSCOPE coverage.
- **Trans-Tasman attorney register data** — out of scope for
  subject-matter IP coverage.
- **Nothing direct** — IPONZ has no shipped connector and IP
  Australia coverage does *not* cross the Tasman.

### What we should add (planned — yellow, BYOK)

- **`patent_client_agents.iponz`** — env-gated BYOK connector
  against the MBIE-gateway v5 surface. Pattern: mirror the shipped
  `ip_australia_*` template. Initial scope:
  - `iponz_common` — shared MBIE-gateway scaffold (subscription
    key + optional OAuth2 bearer; sandbox vs prod base URL toggle).
  - `iponz_patents` — `POST /patentsearch`, case-number lookup,
    "updated since" delta sync, document retrieval (SOAP).
  - `iponz_trademarks` — `POST /trademarksearch` (≤2,000 hits),
    case lookup, delta sync. Carries both national and IR
    designations.
  - `iponz_designs` — analogous search + lookup + retrieval.
  - Env gates: `IPONZ_SUBSCRIPTION_KEY` + optional
    `IPONZ_OAUTH_CLIENT_ID` / `IPONZ_OAUTH_CLIENT_SECRET`.

**Closes the entire NZ patent / TM / design coverage gap.** The
unique value: there is no upstream substitute for NZ patents (no EPC
route), and no Hague substitute for NZ designs. Madrid only covers
the IR-designation slice of TMs.

### What we should NOT add (and why)

- **Case Management Facility (`app.iponz.govt.nz`) HTML scrape.**
  ASP.NET session-bound, Imperva-defended, ToS personal-use carve-
  out; the v5 API is the better target.
- **PVR / GI connector — yet.** No documented API surface. PVR is
  CMF-UI-only (`EXTRA_pvr_qbe`); GI is a static register page.
  Strategic memory: revisit only if IPONZ extends the v5 API to
  cover PVR or GI, or if a separate documented feed appears.
- **`catalogue.data.govt.nz` dataset scrape.** The dataset
  advertises the API as the access path; no parallel bulk feed
  exists. Distil bot defence on the CKAN host makes scraping
  hostile.
- **Sharing infra with the `ip_australia_*` connectors.** Despite
  Trans-Tasman branding, the two offices run **independent
  developer platforms** — IPONZ on MBIE Azure APIM
  (`api.business.govt.nz`), IP Australia on a separate OAuth2
  server (`portal.api.ipaustralia.gov.au`) fronting
  `api.business.gov.au`. **No credential reuse; separate
  connectors.**

### Next steps

1. **Subscribe to the IPONZ API Product** under a project RealMe
   identity to obtain a sandbox subscription key. The MBIE API
   support team may request "further information" before approval
   — be transparent that this is for a hosted research-tooling
   layer with end-users supplying their own future credentials.
2. **Download the v5 OpenAPI spec + data-dictionary PDFs** from
   the portal once subscribed, and persist them in
   `research/openapi/iponz-v5.json` (or the equivalent).
3. **Probe the sandbox** end-to-end on patent / TM / design search
   + case lookup + delta-sync + document retrieval, confirming
   actual quota and pagination behaviour.
4. **Write `specs/nz-iponz-connector-spec.md`** following the
   `ip_australia_*` template — env-gated tools, sandbox/prod
   toggle, shared `iponz_common` scaffold, polite caching (5 min
   for status, 24 h for record bodies), retry on Azure APIM 429s.
5. **Open question to clarify with IPONZ support** — whether a
   "public-data-only" subscription tier exists that we can offer
   to end-users without the direct-debit billing requirement
   (chargeable operations would be out of scope for the proxy).

## §6 Open questions

- **Anonymous "public search" tier.** Does any path exist to call
  the v5 patent/TM/design search operations without a direct-debit
  billing arrangement? The IPONZ landing page is clear about
  charged-operation gating but ambiguous about read-only access.
  Worth asking [`helpdesk@mail.api.business.govt.nz`](mailto:helpdesk@mail.api.business.govt.nz).
- **OAuth2 vs subscription-key floor.** Is the OAuth2 bearer
  strictly optional, or required for certain operations
  (renewals / submissions)? Portal docs say "optionally"; sandbox
  testing would confirm.
- **Pagination mechanics.** TM search caps at 2,000 hits — what is
  the cursor/offset convention for deltas exceeding that?
- **PVR API surface.** Does an undocumented PVR endpoint exist in
  the v5 product, or is PVR truly UI-only? Worth asking IPONZ.
- **GI register format.** The static register page hints at a
  small enumerable list (NZ wine PGIs primarily); is there a
  downloadable canonical list separate from the page HTML?
- **Single Application Process — current state.** Is the AU-NZ
  voluntary co-filing path actually live in production via the
  v5 IPONZ API and the IP Australia API in 2026? AJ Park's 2026
  writeup is sceptical; an authoritative MBIE / IPA confirmation
  would close the question.
- **Bot-defence posture under sustained load.** The Imperva /
  Distil layer is friendly to authenticated subscription-key
  traffic, but production-pattern throttle is unconfirmed.

## §7 References

Primary sources only — `iponz.govt.nz`, `mbie.govt.nz`,
`api.business.govt.nz`, `legislation.govt.nz`, `pctlegal.wipo.int`,
`apicatalog.wipo.int`, `data.govt.nz`.

**API + developer documentation:**
- [IPONZ API landing](https://www.iponz.govt.nz/about-iponz/iponz-api/)
- [IPONZ API product on the MBIE portal](https://portal.api.business.govt.nz/api/iponz)
- [MBIE API platform home](https://portal.api.business.govt.nz/)
- [MBIE API support — subscriptions](https://support.api.business.govt.nz/s/article/api-subscriptions)
- [MBIE three-legged OAuth2 documentation](https://support.api.business.govt.nz/customer/portal/articles/2667515-three-legged-oauth2-authentication)
- [IPONZ v5 — Patent Information data dictionary (PDF)](https://portal.api.business.govt.nz/content/IPONZ%20API%20-%20Patent%20Information%20data%20dictionary.pdf)
- [IPONZ v5 — Trade Mark Information data dictionary (PDF)](https://portal.api.business.govt.nz/content/IPONZ%20API%20-%20Trade%20Mark%20Information%20data%20dictionary.pdf)
- [IPONZ v5 — Design Information data dictionary (PDF)](https://portal.api.business.govt.nz/content/IPONZ%20API%20-%20Design%20Information%20data%20dictionary.pdf)
- [IPONZ v5 — Submit Patent data dictionary (PDF)](https://portal.api.business.govt.nz/content/IPONZ%20API%20-%20Submit%20Patent%20data%20dictionary.pdf)
- [IPONZ v5 — Submit Trade Mark data dictionary (PDF)](https://portal.api.business.govt.nz/content/IPONZ%20API%20-%20Submit%20Trade%20Mark%20data%20dictionary.pdf)
- [IPONZ INID code list (PDF)](https://www.iponz.govt.nz/assets/pdf/about-iponz/INID-Codes.pdf)
- [Case Management Facility (consumer)](https://app.iponz.govt.nz/)

**Substantive law (NZ statutes via `legislation.govt.nz`):**
- [Patents Act 2013 No 68](https://www.legislation.govt.nz/act/public/2013/0068/latest/whole.html)
- [Trade Marks Act 2002 No 49](https://www.legislation.govt.nz/act/public/2002/0049/latest/dlm164240.html)
- [Designs Act 1953 No 65](https://www.legislation.govt.nz/act/public/1953/0065/latest/DLM281071.html)
- [Privacy Act 2020](https://www.legislation.govt.nz/act/public/2020/0031/latest/LMS23193.html) — referenced by IPONZ Terms of Use

**Fees:**
- [Patent fees](https://www.iponz.govt.nz/get-ip/patents/fees/)
- [Trade mark fees](https://www.iponz.govt.nz/get-ip/trade-marks/fees/)
- [Design fees](https://www.iponz.govt.nz/get-ip/designs/fees/)
- [MBIE consultation on changes to IPONZ fees](https://www.mbie.govt.nz/have-your-say/consultation-on-changes-to-fees-charged-by-the-intellectual-property-office-of-nz)
- [PCT Applicant's Guide — New Zealand](https://pctlegal.wipo.int/eGuide/view-doc.xhtml?doc-code=NZ&doc-lang=en)

**Legal terms + reuse:**
- [IPONZ copyright statement](https://www.iponz.govt.nz/about-iponz/copyright/) — *registers carved out of personal/in-house reuse grant*
- [IPONZ terms of use](https://www.iponz.govt.nz/about-iponz/terms-of-use/)
- [govt.nz copyright and attribution (CC-BY 4.0)](https://www.govt.nz/about/using-this-website/copyright-and-attribution/)

**Trans-Tasman context:**
- [Joint Trans-Tasman registration regime for IP attorneys](https://www.iponz.govt.nz/patent-attorneys/joint-trans-tasman-registration-regime-for-ip-attorneys/)
- [`ttipattorney.gov.au` — Trans-Tasman IP Attorneys Regulation](https://www.ttipattorney.gov.au/)
- [International cooperation (IPONZ)](https://www.iponz.govt.nz/about-iponz/international-cooperation/)
- [IP Australia "How to apply for IP overseas"](https://www.ipaustralia.gov.au/international-ip/how-to-apply-for-ip-overseas)

**Cross-office context:**
- [WIPO IP API Catalog](https://apicatalog.wipo.int/) — probed 2026-05-18; 0 IPONZ entries
- [Intellectual Property Office of New Zealand (govt.nz directory)](https://www.govt.nz/organisations/intellectual-property-office-of-nz/)
- [IPONZ dataset on catalogue.data.govt.nz](https://catalogue.data.govt.nz/dataset/iponz)

**Detail surveys + waves:**
- [`waves/2026-05-18-secondary-nationals-wave/nz-iponz.md`](../waves/2026-05-18-secondary-nationals-wave/nz-iponz.md) — 2026-05-18 grounded API discovery

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-18 | Initial synopsis; rating **`yellow_byok`**. Findings: (a) IPONZ ships a documented, versioned **v5 API** on the **MBIE shared API gateway** at [`api.business.govt.nz/gateway/iponz/v5/`](https://portal.api.business.govt.nz/api/iponz) (sandbox: `…/sandbox/iponz/…`) with portal at [`portal.api.business.govt.nz/api/iponz`](https://portal.api.business.govt.nz/api/iponz), covering patents, trade marks, and designs through REST/JSON + legacy SOAP/XML; (b) authentication is per-user — RealMe login → MBIE subscription key → optional OAuth2 bearer, with chargeable operations gated on a registered-IPONZ-user direct-debit/credit arrangement; (c) v5 PDF data dictionaries are downloadable from the portal; (d) NZ is **not EPC**, so EPO OPS / INPADOC carries **none** of the patent register — the IPONZ API is the only programmatic path; NZ is also **not Hague**, so designs have no IR substitute; (e) plant variety rights and geographical indications are **NOT** in the v5 API — PVR sits behind the Case Management Facility (`EXTRA_pvr_qbe`), GI on a static register page; (f) the [IPONZ copyright statement](https://www.iponz.govt.nz/about-iponz/copyright/) **explicitly carves the registers out** of the personal/in-house Crown-copyright reuse grant — register reuse is on a subscription contract basis; (g) **Trans-Tasman sibling check** — IPONZ does **NOT** share the `ip_australia_*` OAuth2 infrastructure: IPONZ runs on MBIE Azure APIM (`api.business.govt.nz`, shared with NZBN / Companies / PPSR / Disclose); IP Australia runs on a separate OAuth2 server at [`portal.api.ipaustralia.gov.au`](https://portal.api.ipaustralia.gov.au/). The joint AU-NZ "single application process" is a co-filing convention, not a unified API; (h) the [WIPO IP API Catalog](https://apicatalog.wipo.int/) holds zero IPONZ entries as of probe (179 office APIs across 10 organisations). Connector verdict: **planned** — mirror the shipped `ip_australia_*` BYOK template (`iponz_common` + `iponz_patents` + `iponz_trademarks` + `iponz_designs`); PVR + GI uncovered until IPONZ extends the v5 surface. | [waves/2026-05-18-secondary-nationals-wave/nz-iponz.md](../waves/2026-05-18-secondary-nationals-wave/nz-iponz.md) |
