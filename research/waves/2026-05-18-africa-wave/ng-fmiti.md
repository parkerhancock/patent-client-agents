# FMITI Nigeria (NG) — Patents/Designs/TMs/Copyright API Discovery

**Date:** 2026-05-18
**Scope:** Determine whether the **Trademarks, Patents and Designs Registry**
(Commercial Law Department, **Federal Ministry of Industry, Trade and Investment** —
FMITI) and the **Nigerian Copyright Commission (NCC)** expose public, queryable
REST/JSON/XML APIs a third-party developer can register for and proxy at runtime
with zero infrastructure on our side. Bulk dumps and HTML-only surfaces are a
**red** verdict.

**TL;DR — Verdict: 🔴 red_no_api across the board.** Nigeria's IP registries are
end-user web portals only. The official **IPO Nigeria portal**
([`iponigeria.fmiti.gov.ng`](https://iponigeria.fmiti.gov.ng/)) and its
account-gated filing surface [`portal.iponigeria.com`](https://portal.iponigeria.com/auth/)
(SvelteKit SPA) expose **filing/renewal/availability-search functionality
behind authenticated agent accounts only** — no public REST/JSON layer, no
developer documentation. The parallel WIPO-style storefront
[`nipo.gov.ng`](https://nipo.gov.ng/) is a JSP static site whose "journals"
page links to dated `journals.jsp?id=YYYYMMDD` HTML pages — no programmatic
register. The **Nigerian Copyright eRegistration System (NCeRS)** at
[`eregistration.copyright.gov.ng`](http://eregistration.copyright.gov.ng/) is
an ASP.NET MVC web app (jQuery 1.7.1 stack) gated by login; `copyright.gov.ng`
itself returned **HTTP 502** during the 2026-05-18 probe. **Nigeria is not in
the [WIPO IP API Catalog](https://apicatalog.wipo.int/)** (0 hits for NG/Nigeria,
2026-05-18). The IPO portal's [Terms of Use](https://iponigeria.fmiti.gov.ng/terms-of-use/)
**expressly forbid reproducing, redistributing, republishing, or reverse-engineering
portal content** and require lawful, authorized use only — proxy reuse would
also depend on per-agent accreditation (only "trademark accredited attorneys
or agents" may search the trademark platform). The **NIPCOM/IPCOM bill** is
still pending (passed second reading at the House of Representatives years ago,
not enacted as of 2026-05-18), and the [National IP Policy & Strategy](https://www.wipo.int/en/web/office-nigeria/w/news/2025/nigeria-s-federal-executive-council-approves-national-intellectual-property-policy-and-strategy)
approved 2025-11-06 only **announces prospective** digitization of the registries.
Transitive bridges are weak: **Nigeria is not a Madrid Protocol member** (contra
the wave brief — verified against WIPO Madrid members 2026-05-18), **not** an
ARIPO/OAPI member (observer only), and not an EPC state.

---

## 1. Endpoints

| Host | Right(s) | Shape | Probe (2026-05-18) |
|---|---|---|---|
| [`iponigeria.fmiti.gov.ng`](https://iponigeria.fmiti.gov.ng/) | TM / Patents / Designs (FMITI marketing + journal index) | Next.js static HTML | HTTP 200, no API, links out to `portal.iponigeria.com` |
| [`portal.iponigeria.com/auth/`](https://portal.iponigeria.com/auth/) | TM / Patents / Designs filing + status + availability search | SvelteKit SPA, login-gated | HTTP 200, login wall, no public REST docs |
| [`portal.iponigeria.com/publications`](https://portal.iponigeria.com/publications/) | Trademark Journal index | SvelteKit SPA | HTTP 200, login may be required to enumerate |
| [`iponigeria.fmiti.gov.ng/resources/trademark-journal/`](https://iponigeria.fmiti.gov.ng/resources/trademark-journal/) | Trademark Journal landing | HTML | HTTP 200, links out to PDF journal issues |
| [`nipo.gov.ng`](https://nipo.gov.ng/) | Legacy NIPO portal (Hugo + JSP) | Static HTML | HTTP 200, no register API; `journals.jsp?id=YYYYMMDD` HTML only |
| [`nipo.gov.ng/login.jsp`](https://nipo.gov.ng/login.jsp), [`/trademark.jsp`](https://nipo.gov.ng/trademark.jsp), [`/patents.jsp`](https://nipo.gov.ng/patents.jsp) | Agent login + procedure descriptions | HTML | HTTP 200, no JSON |
| [`iponigeria.com`](https://www.iponigeria.com/) | Commercial Law Dept marketing mirror | HTML | HTTP 200, marketing only |
| [`copyright.gov.ng`](https://copyright.gov.ng/) | NCC main site (statute text, news) | HTML | **HTTP 502** at probe time (transient outage observed 2026-05-18) |
| [`eregistration.copyright.gov.ng`](http://eregistration.copyright.gov.ng/) | Nigerian Copyright eRegistration System (NCeRS) | ASP.NET MVC, login-gated | HTTP 200; advanced-search endpoint `/search/advance` returned HTTP 000 from edge (intermittent) |
| [`apicatalog.wipo.int`](https://apicatalog.wipo.int/) | WIPO IP API Catalog | SPA | HTTP 200, **0 NG entries** (probed 2026-05-18) |
| [`data.gov.ng`](https://data.gov.ng/) | National open-data portal | HTML | No IP-office datasets discovered |

**No machine surface.** All public-facing IP services are HTML/SPA portals
requiring authenticated agent accounts to reach filing/search/status endpoints.

## 2. Auth

- **IPO Nigeria portal** (`portal.iponigeria.com`): account registration gated;
  the [Trademark portal procedure documentation](https://nipo.gov.ng/trademark.jsp)
  states that filing/search is restricted to accredited trademark attorneys/agents.
  No published OAuth/API-key program. No developer documentation surfaced from
  the SPA bundle.
- **NCeRS** (`eregistration.copyright.gov.ng`): account creation form requires
  a valid email; payments via Remita (offline RRR code). No published API.
- **No public REST/JSON endpoints exist** — therefore no auth scheme to
  describe. Bulk corpora are not offered either (no data.gov.ng dataset, no
  WIPO API Catalog entry).

## 3. ToU / contract posture

The IPO Nigeria [Terms of Use](https://iponigeria.fmiti.gov.ng/terms-of-use/)
include the following load-bearing clauses (verbatim from the live page,
2026-05-18):

> "All Portal content, including but not limited to: Text, Logos, Software,
> System designs, Graphics, Interface components, **Databases**, Documentation
> are owned by or licensed to the Office of the Commercial Law Departmental,
> unless otherwise stated. Users shall not: **Reproduce, Modify, Distribute,
> Reverse engineer, Republish, Exploit** any Portal content without prior
> written authorization."

> "Users agree to use the Portal solely for lawful and authorized purposes…
> Users shall NOT: … Attempt unauthorized access to systems or accounts;
> Interfere with Portal functionality or security; … Use the Portal for
> fraudulent, unlawful, or abusive purposes; Impersonate another individual
> or organization."

These clauses bar proxying or republishing portal data as a hosted service
without prior written authorization from FMITI. Combined with agent-accreditation
gating, a multi-tenant proxy is contractually out of bounds.

The NCC site is statutory in scope (publishes the [Copyright Act 2022](https://www.copyright.gov.ng/CopyrightAct/CopyrightAct2023FinalPublication1.pdf)
and the [WIPO Lex entry](https://www.wipo.int/wipolex/en/legislation/details/21820));
NCeRS does not publish a developer-facing ToU separately from NCC's general
site, but the same redistribution prohibition is implied by Nigerian Copyright
Act §§ on database compilations.

## 4. What's transitively covered elsewhere

- **PCT (WIPO)** — Nigeria deposited its instrument of accession on
  **2005-02-08** ([TREATY/PCT/169](https://www.wipo.int/wipolex/en/treaties/notifications/details/treaty_pct_169)),
  contra the wave brief's "2005-05-08". NG-designated and NG-national-phase PCT
  filings are searchable via WIPO PATENTSCOPE.
- **Madrid Protocol** — **Nigeria is NOT a member as of 2026-05-18**
  (verified against [`https://www.wipo.int/madrid/en/members/`](https://www.wipo.int/madrid/en/members/);
  Nigeria does not appear in the members list). The wave brief's
  "2023-12-02 accession" claim is **refuted**. Accession remains an advocacy
  priority in commentary; no WIPO notification has issued.
- **Hague Agreement (Geneva Act)** — Nigeria's accession status was not
  independently verified via WIPO during this probe; treat the brief's
  "2017-12-12" date as unverified pending direct check of
  [Hague members](https://www.wipo.int/en/web/hague-system).
- **ARIPO / OAPI** — Nigeria is an **observer** at ARIPO, not a member
  ([ARIPO Member States](https://www.aripo.org/member-states)); not an OAPI
  member (OAPI is francophone). No transitive register coverage.
- **EPO INPADOC** — EPO documents INPADOC coverage across 100+ patent-issuing
  authorities ([EPO/INPADOC documentation](https://worldwide.espacenet.com/help?locale=en_EP&method=handleHelpTopic&topic=legalstatusqh));
  NG-specific coverage was not independently confirmed during this probe and
  should be treated as **best-effort bibliographic** at most, not a substitute
  for the NG register.
- **Gaps that cannot be covered transitively:** designs (national only), the
  Nigerian copyright register (NCeRS-only), file histories, agent correspondence,
  trademark journal full text in machine-readable form.

## 5. Verdict (zero-infra proxy)

- **Patents & Designs Registry (FMITI Commercial Law Dept):**
  🔴 **red_no_api**. No public REST/JSON. The `portal.iponigeria.com` SPA is
  agent-account gated; the `nipo.gov.ng` legacy site is static JSP. ToU bars
  reproduction/redistribution. No WIPO API Catalog entry. Not proxiable.
- **Trademarks Registry (FMITI Commercial Law Dept):** 🔴 **red_no_api**.
  Same portal as patents/designs; trademark search is restricted to accredited
  agents per the published procedure, and the ToU explicitly forbids
  republishing portal content. Not proxiable.
- **Nigerian Copyright Commission (NCC / NCeRS):** 🔴 **red_no_api**. NCeRS
  is a login-gated ASP.NET MVC portal; no public API. `copyright.gov.ng` was
  observed in 502 state during the probe. Not proxiable.
- **NIPCOM (proposed Industrial Property Commission):** N/A — **bill not
  enacted as of 2026-05-18**. The 2025 National IP Policy & Strategy
  ([NIPPS](https://www.wipo.int/en/web/office-nigeria/w/news/2025/nigeria-s-federal-executive-council-approves-national-intellectual-property-policy-and-strategy))
  proposes future digitization and merger of the registries, but no API
  surface yet exists.

## 6. References

- IPO Nigeria portal (FMITI Commercial Law Dept) — landing:
  <https://iponigeria.fmiti.gov.ng/> (last verified 2026-05-18)
- IPO Nigeria portal — Terms of Use:
  <https://iponigeria.fmiti.gov.ng/terms-of-use/> (last verified 2026-05-18)
- IPO Nigeria portal — Trademark Journal index:
  <https://iponigeria.fmiti.gov.ng/resources/trademark-journal/> (last verified 2026-05-18)
- IPO Nigeria filing portal (SvelteKit SPA):
  <https://portal.iponigeria.com/auth/> (last verified 2026-05-18)
- Legacy NIPO portal — landing, procedures, journals:
  <https://nipo.gov.ng/>, <https://nipo.gov.ng/trademark.jsp>,
  <https://nipo.gov.ng/patents.jsp>, <https://nipo.gov.ng/journals.jsp>
  (last verified 2026-05-18)
- Nigerian Copyright Commission — main site:
  <https://copyright.gov.ng/> (HTTP 502 at probe 2026-05-18)
- Nigerian Copyright eRegistration System (NCeRS):
  <http://eregistration.copyright.gov.ng/> (last verified 2026-05-18)
- Copyright Act 2022 (Act No. 8 of 2022) — official PDF:
  <https://www.copyright.gov.ng/CopyrightAct/CopyrightAct2023FinalPublication1.pdf>
- Copyright Act 2022 — WIPO Lex:
  <https://www.wipo.int/wipolex/en/legislation/details/21820>
- WIPO IP API Catalog (probed 2026-05-18, 0 NG entries):
  <https://apicatalog.wipo.int/> · index:
  <https://www.wipo.int/en/web/standards/ip-api-catalog/index>
- WIPO Country Profile — Nigeria:
  <https://www.wipo.int/en/web/country-profiles/NG>
- WIPO Directory — Nigeria contacts:
  <https://www.wipo.int/directory/en/details.jsp?country_code=NG>
- WIPO Nigeria Office:
  <https://www.wipo.int/en/web/office-nigeria/>
- WIPO Madrid System members (Nigeria NOT listed, 2026-05-18):
  <https://www.wipo.int/madrid/en/members/>
- WIPO PCT accession notification — Nigeria (TREATY/PCT/169, 2005-02-08):
  <https://www.wipo.int/wipolex/en/treaties/notifications/details/treaty_pct_169>
- ARIPO Member States (Nigeria = observer, not member):
  <https://www.aripo.org/member-states>
- Nigeria National IP Policy & Strategy (NIPPS) — WIPO Nigeria Office news,
  approved 2025-11-06:
  <https://www.wipo.int/en/web/office-nigeria/w/news/2025/nigeria-s-federal-executive-council-approves-national-intellectual-property-policy-and-strategy>
- FMITI Trademark procedure (Nigeria Trade Information Portal):
  <https://nigeriainfotrade.fmiti.gov.ng/procedure/247?l=en&includeSearch=false>
- Nigeria Trade Information Portal — IP Agents (PDF):
  <https://nigeriainfotrade.fmiti.gov.ng/media/IP%20Agents.pdf>
