# CIPC South Africa (ZA) — Patents/TMs/Designs/Copyright API Discovery

**Date:** 2026-05-18
**Scope:** Determine whether the **Companies and Intellectual
Property Commission (CIPC)** — the South African authority for
patents, trademarks, designs, and copyright deposits since 2011 —
exposes a public, queryable REST/JSON/XML API a third-party
developer can register for and proxy at runtime, with zero
infrastructure on our side. Bulk dumps and HTML-only surfaces are a
**red** verdict.

**TL;DR — Verdict: 🔴 red_blocked.** CIPC operates a modern
APIVerse Hub at [`developer.cipc.co.za`](https://developer.cipc.co.za/)
with OAuth 2.0 + RESTful design and an **announced** IPS API
("API suite that allows clients to search all Trademarks, Design,
Patents and Copyright applications data") — but as of 2026-05-18
the IPS API card is marked **"Coming Soon"** alongside Filing,
XBRL, DDR, Streaming, and Documents (only Authorisation, Companies,
and BO have a live `Subscribe` button — see card states in the
[APIVerse Hub landing HTML](https://developer.cipc.co.za/)). Even if
the IPS API ships, CIPC's [Terms and Conditions of Use](https://eservices.cipc.co.za/TermsConditions.aspx)
**explicitly prohibit creating "works and/or software materials
derived from or which are based on the contents found on this site"**
and restrict commercial reuse to "service provision to client(s)" —
i.e., bespoke per-client deployment, not a hosted multi-tenant proxy.
The live IP register today is the ASP.NET WebForms portal at
[`iponline.cipc.co.za`](https://iponline.cipc.co.za/) (Free Patent /
TM / Design / Copyright searches at `*.aspx`) — HTML-only, no JSON
layer. CIPC is **not listed** in the [WIPO IP API Catalog](https://apicatalog.wipo.int/)
(probed 2026-05-18 — 0 hits for CIPC/ZA). Transitive bridges are
weak: SA is **not** a Madrid member (no Madrid Monitor coverage),
**not** an ARIPO member (no transitive ARIPO coverage), and EPO
INPADOC ZA coverage is documented as **historically intermittent**
(see §4).

---

## 1. Endpoint

| Host | Right(s) | Shape | Probe (2026-05-18) |
|---|---|---|---|
| [`developer.cipc.co.za`](https://developer.cipc.co.za/) (APIVerse Hub) | dev portal landing — IPS, Filing, XBRL, DDR, Streaming, Documents APIs | HTML SPA + OAuth2 sign-in | HTTP 200; **IPS API card marked "Coming Soon"** (only Authorisation/Companies/BO are subscribe-able) |
| [`apim.cipc.co.za/api-details`](https://apim.cipc.co.za/) | API gateway — per-product subscription page | Azure APIM HTML | `/` → HTTP 404; product detail pages reachable for live products only |
| [`guide.cipc.co.za`](https://guide.cipc.co.za/) | API documentation + pricing | static docs site | TLS handshake fails from US egress (`sslv3 alert handshake failure` — see §5) — search-engine-cached content confirms Authorisation, Companies, BO APIs only; no IPS reference under `/api-documentation/` |
| [`iponline.cipc.co.za/Patents/Search/FreePTSearch.aspx`](https://iponline.cipc.co.za/Patents/Search/FreePTSearch.aspx) | live patent register search | ASP.NET WebForms HTML | HTTP 200 (31 KB) — login-or-free-search form |
| [`iponline.cipc.co.za/Trademarks/Search/FreeTMSearch.aspx`](https://iponline.cipc.co.za/Trademarks/Search/FreeTMSearch.aspx) | live TM register search | ASP.NET WebForms HTML | HTTP 200 (31 KB) |
| [`iponline.cipc.co.za/Designs/Search/FreeDSSearch.aspx`](https://iponline.cipc.co.za/) | live design register search | ASP.NET WebForms HTML | HTTP 200 |
| [`iponline.cipc.co.za/Copyrights/Search/FreeCRSearch.aspx`](https://iponline.cipc.co.za/) | live copyright register search | ASP.NET WebForms HTML | HTTP 200 |
| [`patentsearch.cipc.co.za`](https://patentsearch.cipc.co.za/) | legacy patent search (referenced by [Smit & Van Wyk](https://www.svw.co.za/patent-search/)) | — | HTTP 404 — surface decommissioned / merged into `iponline.cipc.co.za` |
| [`eservices.cipc.co.za`](https://eservices.cipc.co.za/) | eServices portal (companies primary, IP secondary) | ASP.NET HTML | HTTP 200 |
| Patent Journals (Journal Publication Dates) | weekly patent gazette | PDF | linked from [`iponline.cipc.co.za`](https://iponline.cipc.co.za/) "Patent Journals" menu — PDF-only, no XML/JSON companion |

The IP register today is the four `iponline.cipc.co.za/*/Search/Free*Search.aspx` HTML
forms — server-rendered WebForms, ViewState-bound, no documented JSON
backend. The developer portal's **IPS API** is the *planned* JSON
surface but is not yet live.

## 2. Auth

- **`developer.cipc.co.za` / `apim.cipc.co.za`**: **OAuth 2.0**
  ([Authorization](https://guide.cipc.co.za/getting-started/authorization)
  per docs), required for all subscribed APIs. Per-developer account
  via `/signin` — requires CIPC customer registration. **Annual
  subscription** runs 1 April – 31 March with 30-day sandbox access
  per [Subscription docs](https://guide.cipc.co.za/pricing/subscription).
  Tokens are per-subscriber, non-transferable (see §3).
- **`iponline.cipc.co.za` Free \*Search.aspx**: anonymous browse for
  hit list; login required for full record / certified extracts.
  Account is the same CIPC customer account used across eServices.
- **`eservices.cipc.co.za`**: CIPC customer login.

There is **no IPS API live today** — auth for the planned surface
will follow the same OAuth 2.0 + annual-subscription model as the
live Companies/BO APIs.

## 3. ToU / contract posture

The [Terms and Conditions of Use](https://eservices.cipc.co.za/TermsConditions.aspx)
(eServices, same legal basis as the dev portal — see [APIVerse Hub
T&Cs link](https://apim.cipc.co.za/terms_conditions) which 404s but
is referenced from the [dev-portal footer](https://developer.cipc.co.za/))
contain three load-bearing clauses against a hosted-proxy posture:

1. **Derived-works prohibition:** *"prohibited from creating works
   and/or software materials derived from or which are based on the
   contents found on this site"* — a hosted MCP proxy that mirrors,
   normalizes, or restructures CIPC register data would be a derived
   work by plain reading.
2. **Commercial-reuse restriction:** *"use of information, content or
   material from CIPC website or channels for business and/or
   commercial purposes must be used and/or distributed only if such
   use, transmission and/or distribution is part of the service
   provision to client(s), and use, distribution and/or transmission
   of such information, content and/or material must be limited to
   that specified client(s)"* — i.e., bespoke per-client deployment,
   not a hosted multi-tenant API.
3. **No publication / redistribution:** *"publish, modify, copy,
   download, upload in any manner, post, broadcast or transmit,
   reverse engineer or disenable, display, or distribute or in any
   way exploit any of the contents"* — categorical bar without the
   client-bound carve-out above.

Token-handling clauses in the API T&Cs (per search-engine snapshot
of [apim.cipc.co.za/terms_conditions](https://apim.cipc.co.za/terms_conditions))
forbid sharing, sublicensing, or assigning Tokens to third parties.
A hosted proxy that fans out one developer's Token to many end users
is incompatible with this posture even if the IPS API ships.

## 4. What's transitively covered elsewhere

- **EPO INPADOC (transitive via EPO OPS)**: ZA is a documented INPADOC
  country code, but coverage is **historically intermittent** — per
  the peer-reviewed [Schmoch et al. study (SAJEMS 2021)](https://scielo.org.za/scielo.php?script=sci_arttext&pid=S2222-34362021000100028):
  *"for many years the applications were not documented
  electronically; then for some years this documentation was realized
  by INPADOC, and discontinued again after a while"* — i.e., partial
  biblio/family fidelity for ZA national-route patents that have an
  EP/PCT counterpart, gaps for ZA-only filings and for stretches when
  INPADOC discontinued the feed.
- **WIPO PATENTSCOPE National Collection**: ZA appears in
  PATENTSCOPE's national collections per [svw.co.za](https://www.svw.co.za/patent-search/);
  same caveat as INPADOC — coverage depth not guaranteed.
- **Madrid Monitor (WIPO)**: **not applicable.** South Africa is
  **not yet a Madrid Protocol contracting party** as of 2026-05-18.
  Approval to ratify dates to September 2003 but accession has been
  repeatedly delayed; the Trade Marks Amendment Bill was expected at
  the executive authority in September 2025 per the
  [Spoor & Fisher 2025 brief](https://spoor.com/madrid-protocol-in-africa/)
  and the [Adams & Adams Madrid Protocol 2025 review](https://www.adams.africa/wp-content/uploads/2025/09/Madrid-Protocol-2025.pdf).
  *(This refutes the prompt's context bullet — SA is not in fact a
  Madrid member.)* Once accession lands, ZA international
  registrations will reach Madrid Monitor; national-only ZA marks
  never will.
- **ARIPO Harare Protocol**: **not applicable.** South Africa is
  **not** on the [ARIPO Harare Protocol contracting-states list](https://www.wipo.int/wipolex/en/treaties/details/204)
  (21 contracting states: BW, CV, SZ, GM, GH, KE, LS, LR, MU, MW,
  MZ, NA, RW, ST, SL, SC, SD, TZ, UG, ZM, ZW — ZA absent). *Confirms
  the prompt's context bullet.* No transitive ARIPO coverage for ZA
  patents.
- **EPO EPC**: **not applicable.** SA is not an EPC contracting
  state — EPO coverage of ZA is INPADOC only, never as designated
  EP filing. *Confirms the prompt's context bullet.*

**National-only gaps with no proxy substitute:**

- ZA-only patents without EP/PCT counterparts (INPADOC partial).
- ZA designs and ZA copyright deposits (no transitive surface — not
  in Madrid/ARIPO/INPADOC).
- File histories for any ZA right (CIPC `iponline.cipc.co.za` HTML
  only; gated behind login for full records).
- Patent Journal gazette items (PDF-only at CIPC, no machine-readable
  feed).
- South Africa operates a **depository (non-substantive-examination)
  patent system** — so "file history" data for ZA patents has less
  procedural richness than for examined systems (no office actions,
  no rejections to mine). The gap is therefore less painful than for
  the US/EP/JP examining offices — there is materially less data
  worth proxying.

## 5. Verdict (zero-infra proxy)

**🔴 red_blocked.**

Three independent blockers:
1. **The IP API does not yet exist.** CIPC's IPS API is "Coming
   Soon" on the [APIVerse Hub](https://developer.cipc.co.za/); only
   Companies + BO + Authorisation are live. No timeline published.
2. **Terms prohibit a hosted proxy even when the API ships.** The
   [eServices T&Cs](https://eservices.cipc.co.za/TermsConditions.aspx)
   bar derived works and restrict commercial reuse to bespoke
   "service provision to client(s)" with non-transferable tokens —
   structurally incompatible with our zero-infra MCP proxy posture.
3. **Today's live register is HTML-only.** The
   `iponline.cipc.co.za/*/Search/Free*Search.aspx` ASP.NET WebForms
   surfaces are not a stable JSON layer and have no documented
   programmatic access path; CIPC is **not** in the
   [WIPO IP API Catalog](https://apicatalog.wipo.int/).

Surprising observation: the `guide.cipc.co.za` TLS endpoint failed
from US egress with `sslv3 alert handshake failure` — a likely
cipher-suite or client-cert filter that compounds the structural
blocker. The CIPC infrastructure pattern (modern Azure APIM front
door + locked-down docs subdomain) is mid-modernization; revisit on
IPS API GA announcement and on any T&C revision that opens
multi-tenant redistribution.

**No connector to build at CIPC.** Coverage of ZA IP rights flows
transitively through EPO INPADOC (partial, biblio + family) for
patents with an EP/PCT counterpart; nothing covers ZA-only designs,
ZA copyright deposits, or full ZA file histories. Watch items:
(a) Madrid Protocol accession (Trade Marks Amendment Bill — September
2025 target slipped); (b) IPS API GA on APIVerse Hub; (c) T&C
revision permitting third-party redistribution.

## 6. References

- CIPC APIVerse Hub (dev portal landing): [developer.cipc.co.za](https://developer.cipc.co.za/) (probed 2026-05-18 — IPS/Filing/XBRL/DDR/Streaming/Documents all "Coming Soon"; Authorisation/Companies/BO live)
- CIPC API documentation site: [guide.cipc.co.za](https://guide.cipc.co.za/) (probed 2026-05-18 — TLS handshake fails from US egress; search-engine cache confirms no IPS API content)
- CIPC API Authorization docs: [guide.cipc.co.za/getting-started/authorization](https://guide.cipc.co.za/getting-started/authorization)
- CIPC API Subscription docs: [guide.cipc.co.za/pricing/subscription](https://guide.cipc.co.za/pricing/subscription)
- CIPC Azure APIM gateway: [apim.cipc.co.za](https://apim.cipc.co.za/)
- CIPC APIM Terms and Conditions: [apim.cipc.co.za/terms_conditions](https://apim.cipc.co.za/terms_conditions)
- CIPC IP Online (live IP register portal): [iponline.cipc.co.za](https://iponline.cipc.co.za/) (probed 2026-05-18 — ASP.NET WebForms, Free Patent/TM/Design/Copyright searches all HTTP 200)
- Patent Free Search: [iponline.cipc.co.za/Patents/Search/FreePTSearch.aspx](https://iponline.cipc.co.za/Patents/Search/FreePTSearch.aspx)
- Trademark Free Search: [iponline.cipc.co.za/Trademarks/Search/FreeTMSearch.aspx](https://iponline.cipc.co.za/Trademarks/Search/FreeTMSearch.aspx)
- CIPC eServices Terms and Conditions of Use (load-bearing for redistribution clauses): [eservices.cipc.co.za/TermsConditions.aspx](https://eservices.cipc.co.za/TermsConditions.aspx)
- CIPC main site IP section: [cipc.co.za/?page_id=1423](https://www.cipc.co.za/?page_id=1423)
- WIPO IP API Catalog: [apicatalog.wipo.int](https://apicatalog.wipo.int/) (probed 2026-05-18 — CIPC/ZA not listed)
- WIPO Madrid System Members: [wipo.int/en/web/madrid-system/members/index](https://www.wipo.int/en/web/madrid-system/members/index) (probed 2026-05-18 — ZA absent)
- Madrid Protocol in Africa — Spoor & Fisher 2025: [spoor.com/madrid-protocol-in-africa](https://spoor.com/madrid-protocol-in-africa/) (Trade Marks Amendment Bill targeting September 2025 submission)
- Adams & Adams — Madrid Yearly Review 2025 (Africa): [adams.africa/.../Madrid-Protocol-2025.pdf](https://www.adams.africa/wp-content/uploads/2025/09/Madrid-Protocol-2025.pdf)
- WIPO Lex — ARIPO Harare Protocol contracting states: [wipo.int/wipolex/en/treaties/details/204](https://www.wipo.int/wipolex/en/treaties/details/204) (21 states, ZA absent)
- Schmoch et al., SAJEMS 2021 — INPADOC coverage of ZA characterized as historically intermittent: [scielo.org.za/scielo.php?...](https://scielo.org.za/scielo.php?script=sci_arttext&pid=S2222-34362021000100028)
- EU IP Helpdesk — IP Country Fiche: South Africa (background): [intellectual-property-helpdesk.ec.europa.eu/.../Africa_IP-Country-Fiche_SOUTH%20AFRICA.pdf](https://intellectual-property-helpdesk.ec.europa.eu/system/files/2022-05/Africa_IP-Country-Fiche_SOUTH%20AFRICA.pdf)
- CIPC IP Reference Guide for SMMEs (background, 2025): [cipc.co.za/.../Intellectual-Property-Reference-Guide-for-Small-Law-Firms-SMMEs.pdf](https://www.cipc.co.za/wp-content/uploads/2025/05/Intellectual-Property-Reference-Guide-for-Small-Law-Firms-SMMEs.pdf)
