# IPONZ New Zealand (NZ) — Patents, Trade Marks, Designs, PVR, GI API Discovery

**Date:** 2026-05-18
**Scope:** Determine whether the Intellectual Property Office of New
Zealand (IPONZ; a business unit of the Ministry of Business, Innovation
and Employment, MBIE) exposes a public, queryable REST/JSON/XML API
that we can proxy at runtime, zero infrastructure on our side. Bulk
dumps and HTML-only surfaces = red verdict; BYOK with per-user creds
= yellow; documented unauthenticated public-data feeds = green.

**TL;DR:** **Yellow — BYOK, well-documented, but per-user credentials.**
IPONZ ships a documented, versioned API behind the **MBIE API
gateway** at [`api.business.govt.nz/gateway/iponz/v5/`](https://portal.api.business.govt.nz/api/iponz)
(sandbox: `…/sandbox/iponz/…`). The portal is at
[`portal.api.business.govt.nz/api/iponz`](https://portal.api.business.govt.nz/api/iponz)
and the public IPONZ landing page is
[`iponz.govt.nz/about-iponz/iponz-api/`](https://www.iponz.govt.nz/about-iponz/iponz-api/).
Authentication is **RealMe** (NZ federated digital ID, the same login
used for the consumer IPONZ Case Management Facility) gated through
an MBIE-issued **subscription key** plus an optional **OAuth2 bearer
token** — i.e. *per-subscriber credentials, no anonymous access*.
The API covers patents, trade marks, designs (the three primary
registers), with REST/JSON for the public-data and renewal flows and
legacy SOAP/XML for the document-retrieval and submit flows; **v5**
data dictionaries are published as PDFs on the portal. Use of the API
itself is **free for registered IPONZ users** (`iponz.govt.nz`),
though official statutory fees apply to any chargeable transactions
(filings, renewals). Plant variety rights and geographical
indications appear on `iponz.govt.nz` as separate registers, but the
v5 API surface is documented for patents / TMs / designs only.

Trans-Tasman sibling check: IPONZ does **NOT** share the IP Australia
OAuth2 infrastructure. IP Australia runs at
[`portal.api.ipaustralia.gov.au`](https://portal.api.ipaustralia.gov.au/)
(distinct OAuth2 server; gateway host
`api.business.gov.au/ip-australia/…`), while IPONZ runs on the **MBIE
API Cloud** (Azure API Management at `api.business.govt.nz/gateway/…`,
shared with NZBN, Companies Register, PPSR, Disclose, Tenancy Bond,
etc.). The two offices co-operate on a joint Trans-Tasman patent
attorney register and have a Single Application Process concept on
paper, but the developer surfaces are independent platforms — no
shared OAuth realm, no shared client-credentials issuance, no shared
gateway. **Conclusion: NZ does not free-ride on the AU connector we
already ship.**

There is **one IPONZ entry on `catalogue.data.govt.nz`** —
[`/dataset/iponz`](https://catalogue.data.govt.nz/dataset/iponz) —
but it advertises the API as the access path; "application volumes
since 2014" appear to be published as small statistical exports, not
bulk register dumps. The [WIPO IP API Catalog](https://apicatalog.wipo.int/)
holds **zero IPONZ entries** as of probe (`/api/apis?size=200` → 179
results across DPMA, EPO, EUIPO, IP Australia, JPO, MOIP KOREA, QAZ,
UPRP, USPTO, WIPO — no NZ).

---

## 1. Endpoint

IPONZ ships its programmatic surface through the **MBIE API Cloud**
(MBIE = Ministry of Business, Innovation and Employment; IPONZ is an
MBIE business unit). The gateway hosts five distinct online IPONZ
surfaces:

| Surface | Host | Right(s) | Shape |
|---|---|---|---|
| IPONZ API v5 (production) | `api.business.govt.nz/gateway/iponz/v5/` | patent / TM / design | REST + SOAP, OAuth2/sub-key |
| IPONZ API v5 (sandbox) | `api.business.govt.nz/sandbox/iponz/…` | patent / TM / design | same shape, test data |
| Developer portal | [`portal.api.business.govt.nz/api/iponz`](https://portal.api.business.govt.nz/api/iponz) | docs + subscription | OpenAPI spec download, data dictionaries, RealMe subscribe flow |
| Case Management Facility (consumer search UI) | [`app.iponz.govt.nz/app/Extra/Default.aspx?...`](https://app.iponz.govt.nz/) | patent / TM / design / PVR / GI / Online Journal | ASP.NET (302 → `Qbe.aspx`); session-cookied |
| Institutional CMS | [`iponz.govt.nz`](https://www.iponz.govt.nz/) | content, fees, guidance | Imperva-fronted SilverStripe nginx |

The MBIE gateway is shared with **NZBN** ([`portal.api.business.govt.nz/api/nzbn`](https://portal.api.business.govt.nz/api/nzbn)),
**Companies Register**, **PPSR**, **Disclose**, **Tenancy Bond**, and
others; the IPONZ product is one tenant. The Azure API Management
signature (`x-azure-ref: 20260518T220520Z-…`, `appId=cid-v1:…`) on
the gateway 404 from
`api.business.govt.nz/gateway/iponz/v5/` confirms the platform.

The five-IP-rights nature of IPONZ is reflected in the
**Case Management Facility** routes ([from the IPONZ home page
markup](https://www.iponz.govt.nz/about-iponz/iponz-api/)):

- Patents — `EXTRA_pt_qbe` (e.g. [search](https://app.iponz.govt.nz/app/Extra/Default.aspx?op=EXTRA_pt_qbe&fcoOp=EXTRA__Default&directAccess=true))
- Trade marks — `EXTRA_tm_qbe`
- Designs — `EXTRA_ds_qbe`
- Plant variety rights — `EXTRA_pvr_qbe`
- Geographical indications — separate static [register page](https://www.iponz.govt.nz/about-ip/geographical-indications/register)
- Online journal — `EXTRA_Activity_qbe`

The v5 API data dictionaries on the portal cover **patents, trade
marks, and designs only** (PDFs:
[Patent Information](https://portal.api.business.govt.nz/content/IPONZ%20API%20-%20Patent%20Information%20data%20dictionary.pdf),
[Trade Mark Information](https://portal.api.business.govt.nz/content/IPONZ%20API%20-%20Trade%20Mark%20Information%20data%20dictionary.pdf),
[Design Information](https://portal.api.business.govt.nz/content/IPONZ%20API%20-%20Design%20Information%20data%20dictionary.pdf),
[Submit Trade Mark](https://portal.api.business.govt.nz/content/IPONZ%20API%20-%20Submit%20Trade%20Mark%20data%20dictionary.pdf),
[Submit Patent](https://portal.api.business.govt.nz/content/IPONZ%20API%20-%20Submit%20Patent%20data%20dictionary.pdf)).
PVR and GI are register-only via the Case Management Facility UI;
no documented API.

A separate `api.business.govt.nz` discovery endpoint exists at
[`/api/apis/info?name=IPONZ&version=v4&provider=mbiecreator`](https://api.business.govt.nz/api/apis/info?name=IPONZ&version=v4&provider=mbiecreator)
and [`?name=Patent-Information&version=v1&provider=mbiecreator`](https://api.business.govt.nz/api/apis/info?name=Patent-Information&version=v1&provider=mbiecreator) —
returns the API descriptor metadata that the SPA portal renders.

---

## 2. Auth

**Per-user credentials are mandatory.** There is no anonymous public
access to the IPONZ API.

The flow ([IPONZ API page](https://www.iponz.govt.nz/about-iponz/iponz-api/),
[MBIE API support article on subscriptions](https://support.api.business.govt.nz/s/article/api-subscriptions)):

1. **RealMe login** — the NZ federated digital-identity service,
   the same login used for the consumer IPONZ Case Management
   Facility. Reuses an existing IPONZ user account if the caller
   has one (i.e. registered patent attorneys / IP agents bring
   their existing identity).
2. **Subscribe to the IPONZ API Product** through
   [`portal.api.business.govt.nz/api/iponz`](https://portal.api.business.govt.nz/api/iponz).
   The MBIE API support team may request additional information
   before approving the subscription (the portal docs explicitly
   say this).
3. **Receive a subscription key** scoped to the subscription
   (typical Azure APIM `Ocp-Apim-Subscription-Key` pattern; not
   confirmed in code without subscribing).
4. **Optionally generate an OAuth2 bearer token** for additional
   security on top of the subscription key. MBIE supports a
   [three-legged OAuth2 flow](https://support.api.business.govt.nz/customer/portal/articles/2667515-three-legged-oauth2-authentication)
   for APIs that require it; the IPONZ Product appears to use
   subscription-key-plus-optional-bearer rather than mandatory
   OAuth client-credentials.
5. **For chargeable operations** (filing, renewal payments) the
   subscriber must be a registered IPONZ user with a **direct
   debit or direct credit payment arrangement** set up — production
   access for those operations is gated on the billing relationship.

The MBIE gateway is one of two NZ government API platforms (the
other is `api.gov.au` — Australia; *not* available for NZ apps).
The pattern is **clean BYOK** in the same shape as the IP Australia
shipped connector, but the credential issuance and OAuth realm are
unrelated. Each end-user of our hosted proxy would need their own
RealMe + IPONZ subscription.

---

## 3. Query Language

**Documented, structured, but read it as POSTs with JSON request
bodies, not a query DSL.**

From the v5 data dictionaries
([Trade Mark Information](https://portal.api.business.govt.nz/content/IPONZ%20API%20-%20Trade%20Mark%20Information%20data%20dictionary.pdf)
PDF index and synthesised search summaries):

- **`POST /trademarksearch`** — search of the TM register; returns
  up to **2,000 trade marks** matching the request criteria.
- **`POST /patentsearch`** — analogous patent register search
  (inferred from the parallel structure; data dictionary names
  the "Patent Information" operations).
- **`POST /designsearch`** — analogous design register search.
- **Case-number lookups** — given a patent / TM / design case
  number, return full public bibliographic data + document index
  (covers biblio, status, parties, classifications).
- **"Updated since" lists** — operations that return patents / TMs
  / designs updated within a specified date range, including new
  applications. Useful for delta sync.
- **Renewal-check operations** — POST that checks whether a given
  case has an outstanding renewal or maintenance fee.
- **`POST /paymentevent`** — submit a renewal/maintenance fee
  payment (gated on the registered-IPONZ-user + direct-debit
  arrangement).
- **`POST /submittrademark`**, **`POST /submitpatent`** — file new
  applications (also gated on billing arrangement).
- **Document retrieval** — SOAP operation that returns a register
  document as **Base64-encoded** content given a document
  identifier obtained from the search/info operations.
- **Correspondence** — task and discussion correspondence
  operations for ongoing-examination flow (the "fully automate
  retrieval and loading of notifications and documents into your
  own case management systems" feature; targeted at IP-agent
  software).

The v5 surface is a **collection of operations** rather than a
unified query DSL — there is no SolR/Lucene Boolean grammar
documented, but the data-dictionary PDFs expose the field
inventory for request payloads. JSON for the search and renewal
flows; XML/SOAP for the document and submit flows (the "legacy
SOAP" path).

---

## 4. Pagination

Not surfaced directly in the IPONZ landing-page documentation, but
the `/trademarksearch` operation caps response size at **2,000 hits
per call** ([per portal docs](https://portal.api.business.govt.nz/api/iponz)).
For datasets larger than the cap, callers iterate via date-range
filtering on the "updated since" operations rather than an
offset/limit. Exact pagination mechanics (cursor, page-size cap,
ordering) are in the OpenAPI spec downloadable from the portal
after subscription; not publicly inspected in this probe.

---

## 5. Response Shape

The v5 API is **a mixed-format collection**:

- **REST + JSON** — search and renewal operations (the modern path,
  per [IPONZ API landing](https://www.iponz.govt.nz/about-iponz/iponz-api/)).
- **SOAP + XML** — document retrieval (Base64-encoded payload),
  application submission, correspondence — the legacy operations
  inherited from the pre-v5 SOAP services.

The data dictionaries are **flattened views of the XML structure**
([per the Trade Mark Information data dictionary PDF intro](https://portal.api.business.govt.nz/content/IPONZ%20API%20-%20Trade%20Mark%20Information%20data%20dictionary.pdf)).
JSON responses are structured renderings of the same field tree.

Fields covered (synthesised from portal data-dictionary titles):
case number, status, applicant/owner, attorney/agent, priority,
classification (IPC + CPC for patents, Nice for TMs, Locarno for
designs), filing/registration/grant dates, claims/specification
identifiers, mark-image identifiers (for TMs), document index.
INID codes documented at
[`iponz.govt.nz/assets/pdf/about-iponz/INID-Codes.pdf`](https://www.iponz.govt.nz/assets/pdf/about-iponz/INID-Codes.pdf).

---

## 6. Coverage Scope

What the v5 API covers (from the data dictionary inventory):

| Right | API coverage |
|---|---|
| **NZ national patents** | full bibliographic + status + documents + filing |
| **NZ trade marks** (national + IR designations) | full bibliographic + status + documents + filing |
| **NZ designs** | full bibliographic + status + documents + filing |
| **Plant variety rights (PVR)** | UI-only (Case Management Facility `EXTRA_pvr_qbe`); no documented API |
| **Geographical indications (GI)** | static register page only; no documented API |

NZ's **statutory basis** for each register:

- Patents — [Patents Act 2013 No 68](https://www.legislation.govt.nz/act/public/2013/0068/latest/whole.html)
  on `legislation.govt.nz`.
- Trade marks — [Trade Marks Act 2002 No 49](https://www.legislation.govt.nz/act/public/2002/0049/latest/dlm164240.html).
- Designs — [Designs Act 1953 No 65](https://www.legislation.govt.nz/act/public/1953/0065/latest/DLM281071.html) —
  *yes, 1953; commentary describes it as "[living on borrowed time](https://www.lexology.com/library/detail.aspx?g=2abdfae8-f2f8-42be-8447-2621e7e4972f)"*.

**Higher-layer substitutes already in our stack** (the
"transitive coverage" check):

- **NZ is NOT an EPC contracting state** → no EPO OPS / INPADOC
  coverage for NZ national patents. (Australia is also non-EPC,
  but we cover AU directly via the shipped IP Australia
  connectors; the same logic motivates a direct NZ connector.)
- **NZ IS a PCT member** → PCT national-phase entries into NZ are
  trackable on PATENTSCOPE (WIPO) at the PCT-level only, but NZ
  national bibliographic detail still requires IPONZ.
- **NZ IS a Madrid member** (since 2012) → IR designations of NZ
  are visible on **WIPO Madrid Monitor**.
- **NZ is NOT a Hague member** → no Hague IR coverage of NZ
  designs.
- **NZ is NOT in the EU** → no EUIPO transitive coverage.
- **PVR / GI** — no higher-layer substitute; IPONZ is sole source.

**Genuine national-only gaps requiring IPONZ:**

- NZ patent biblio + status (especially national-phase entries
  from PCT and direct national filings).
- NZ trade marks (both national-only and IR-designation).
- NZ designs (entire register — no Hague substitute).
- NZ plant variety rights.
- NZ geographical indications (the NZ Wine PGI register).
- NZ patent file documents (Akteneinsicht equivalent — only via
  the IPONZ document-retrieval SOAP operation).

---

## 7. Rate Limits / Quotas

Not published on the public IPONZ landing page. MBIE's gateway is
Azure API Management, which typically applies per-subscription
quotas configurable at the product level. Subscribers see their
quota and throttle limits in the portal after subscribing
([MBIE API subscriptions support article](https://support.api.business.govt.nz/s/article/api-subscriptions)).
The TM-search 2,000-result-per-call cap (§3) is documented; deeper
quota / per-second-throttle figures are not.

---

## 8. Terms of Service

The legal posture has **two distinct layers** — the website / API
docs vs. the **register data itself**:

### Website + content (permissive Crown copyright)

The [IPONZ copyright statement](https://www.iponz.govt.nz/about-iponz/copyright/)
says:

> "The information provided on the Intellectual Property Office of
> New Zealand website, **excluding the intellectual property
> registers**, may be reproduced for personal or in house use free
> of charge without further permission…"

Translation: the website's *guidance content* (and gazette PDFs)
can be reproduced for personal / in-house use free of charge. The
**register data itself is explicitly carved out** from that
permission — *exactly* the data the API serves. The IPONZ social
channels (and most other MBIE content) sit under the [govt.nz
Creative Commons Attribution 4.0 International policy](https://www.govt.nz/about/using-this-website/copyright-and-attribution/);
**the IPONZ registers do not**.

### API-specific terms (per-subscription, contract-bound)

The [IPONZ API landing page](https://www.iponz.govt.nz/about-iponz/iponz-api/)
points subscribers to the MBIE platform. Use of the API itself is
"**free for registered users of the IPONZ system**" — i.e. there
is no API access fee, but you must be a registered IPONZ user to
subscribe, which is also the path to direct-debit / direct-credit
arrangements for chargeable transactions.

The MBIE API platform terms ([support portal](https://support.api.business.govt.nz/s/))
apply to all MBIE-gateway tenants (NZBN, Companies, PPSR, IPONZ,
etc.) — standard government-API click-through, not a published
open-data licence.

### IPONZ website terms of use

[`iponz.govt.nz/about-iponz/terms-of-use/`](https://www.iponz.govt.nz/about-iponz/terms-of-use/)
covers the website + social channels but is silent on bulk reuse
of the registers (deferring to the copyright statement above).

**Bottom line on ToS for a hosted proxy:** No published open-data
licence covers IPONZ register data. The API itself is fine to use
*for the subscriber's own purposes*, but reselling / republishing
the register data through a third-party proxy without an explicit
agreement is a grey area at best. **The clean shape is BYOK** —
each end-user of our hosted offering provides their own IPONZ
subscription credentials and the proxy is just transport.

---

## 9. Operational Notes

- **Language.** English only (NZ is monolingual for IP purposes;
  Te Reo Māori is the other official language but the IP registers
  are English).
- **Imperva / Distil bot protection.** Both
  [`iponz.govt.nz`](https://www.iponz.govt.nz/) and
  [`data.govt.nz`](https://catalogue.data.govt.nz/) (the CKAN
  catalogue) sit behind **Imperva** WAF (`x-cdn: Imperva`,
  `x-iinfo: …` headers observed on probe; the CKAN catalogue
  served a "Pardon Our Interruption" Distil bot challenge to a
  curl probe). Programmatic clients need to identify themselves
  properly (User-Agent + bearer token) — anonymous browser-mimic
  scraping is actively defended against.
- **Azure API Management.** The gateway is Azure APIM
  (`x-azure-ref` + `appId=cid-v1:…` headers on 404 responses from
  `api.business.govt.nz/gateway/…`). Subscription key likely
  follows the standard `Ocp-Apim-Subscription-Key` header
  convention, but unconfirmed without an active subscription.
- **MBIE API platform shape.** [`portal.api.business.govt.nz`](https://portal.api.business.govt.nz/)
  is a developer-portal SPA listing all MBIE-gateway tenants —
  IPONZ alongside NZBN, Companies Register, PPSR, Disclose,
  Tenancy Bond, Companies Entity Role Search, etc. **The IPONZ
  surface follows the same operational pattern as those siblings**
  — it is not a one-off.
- **Trans-Tasman patent attorney register** is genuinely joint
  with IP Australia (see [`ttipattorney.gov.au`](https://www.ttipattorney.gov.au/)),
  but that's an attorney-licensing register, **not** patent /
  TM / design subject-matter data. It does not affect the IPONZ
  API surface posture.
- **"Single Application Process".** Announced in 2011 ([per the
  IP Australia / Treasury submission archive](https://www.treasury.govt.nz/sites/default/files/2024-05/pc-inq-stter-dr-089-ip-australia.pdf)),
  the joint AU-NZ single-patent-filing concept allows applicants
  to file co-pending patents in both countries through either
  office's portal. The **AJ Park** firm's writeup
  ([2026](https://www.ajpark.com/insights/have-you-heard-about-australia-and-new-zealands-single-patent-application-sorry-you-heard-wrong/))
  is unusually clear that this is **not** a single application
  producing a single right — it's two parallel applications
  filed in a single transaction. **The underlying APIs remain
  separate.** This is not the same as the EPC / Unitary Patent
  model.
- **`catalogue.data.govt.nz` IPONZ dataset** points back to the
  API as the access path. The "application volumes since 2014"
  appear to be statistical exports (small tables), not bulk
  register dumps. Verifying the resource manifest needs CKAN
  query access (blocked by the Distil challenge on raw curl).
- **Designs Act 1953.** NZ's design register still operates under
  a 1953 statute — long-running policy effort to modernise has
  not concluded. NZ is not a Hague Agreement member, so there is
  no IR design route into NZ.
- **No bulk feeds.** Unlike SE/PRV (CC0 / CC BY 4.0 FTP feeds) or
  DE/DPMA (DEPATISnet bulk), IPONZ does not publish bulk-data
  XML/CSV feeds for the registers. The API is the *only*
  programmatic surface.

---

## 10. Verdict

| Right | Verdict | One-sentence reason |
|---|---|---|
| **Patents** | 🟡 **Yellow — BYOK** | Documented v5 API with RealMe subscription + Azure APIM gateway; per-user credential issuance; clean OAuth2 path for high-volume callers. |
| **Trade marks** | 🟡 **Yellow — BYOK** | Same API, same auth shape, same v5 data dictionaries. |
| **Designs** | 🟡 **Yellow — BYOK** | Same API, same auth shape. |
| **Plant variety rights** | 🔴 **Red — no API** | UI-only Case Management Facility (`EXTRA_pvr_qbe`); v5 data dictionaries do not list PVR operations. |
| **Geographical indications** | 🔴 **Red — no API** | Static register page only; no documented programmatic surface. |

**Overall: 🟡 Yellow — BYOK, well-documented.** IPONZ ships the
single cleanest documented per-user-credentials API surface among
the secondary-nationals surveyed 2026-05-18: an MBIE-platform
shared-gateway tenant (`api.business.govt.nz/gateway/iponz/v5/`)
with RealMe-based subscription, Azure APIM throttling, downloadable
OpenAPI spec, and detailed PDF data dictionaries for patents, trade
marks, and designs. The blocker against a green rating is that **no
anonymous access path exists** — every caller needs their own RealMe
identity + IPONZ subscription key + optional OAuth2 bearer. The
copyright statement explicitly carves register data out of the
permissive Crown-copyright re-use grant that covers the rest of
`iponz.govt.nz`. Bulk feeds do not exist. **The connector shape is
BYOK** — same shape as the shipped IP Australia connector trio, but
on different infrastructure (MBIE Azure APIM in NZ vs. AGW + custom
OAuth2 server at `portal.api.ipaustralia.gov.au` in AU). The two
sister offices co-operate on the Trans-Tasman attorney register and
a voluntary co-filing concept, but their developer surfaces are
**independent**. NZ does **not** free-ride on the AU connector.

**Strategic memory:** If we ship a NZ connector it should mirror
the `ip_australia_*` BYOK template — env-gated tool registration
(`IPONZ_SUBSCRIPTION_KEY` + optional `IPONZ_OAUTH_CLIENT_ID/SECRET`),
per-right submodules sharing a common `iponz_common` scaffold, and
honest documentation that production access requires RealMe + a
direct-debit billing arrangement for any chargeable operation. PVR
and GI sit outside the v5 surface and would remain uncovered (Case
Management Facility scraping is closed by the Imperva WAF and
website-terms personal-use carve-out). Re-evaluate if IPONZ
publishes an open public-search anonymous tier — monitor
[`iponz.govt.nz/about-iponz/iponz-api/`](https://www.iponz.govt.nz/about-iponz/iponz-api/)
and the [WIPO IP API Catalog](https://apicatalog.wipo.int/) for
that signal.
