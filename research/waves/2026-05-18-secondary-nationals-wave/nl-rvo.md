# Octrooicentrum Nederland (NL / RVO) — Patent + Benelux IP API Discovery

**Date:** 2026-05-18
**Scope:** Determine whether **Octrooicentrum Nederland** (Netherlands Patent
Office, a department of the Rijksdienst voor Ondernemend Nederland / RVO)
exposes a public, queryable REST/JSON/XML API that we can proxy at runtime,
with zero infrastructure on our side. Bulk dumps and HTML-only surfaces are
a **red** verdict; BYOK-per-user is **yellow**. Because Benelux trademarks
and designs flow through a separate body — the **Benelux Office for
Intellectual Property** (BOIP, `boip.int`) — that surface was probed in the
same sweep.

**TL;DR: red_no_api.** Neither Octrooicentrum Nederland nor BOIP publishes
a documented public REST/JSON/XML API for register queries. The genuine
register interface is the **BPP eRegister** at
[`https://mijnoctrooi.rvo.nl/fo-eregister-view/`](https://mijnoctrooi.rvo.nl/fo-eregister-view/)
— a server-rendered Struts2 application whose only structured outputs are
(a) a **saved-search RSS feed** subscription (per-query, registered through
the UI), (b) **per-result XML/PDF document downloads** at
`/fo-eregister-view/download/downloadFileXML`, and (c) a **CSV export
capped at 1,000 rows** at `/fo-eregister-view/download/exportCSV`. None of
these is a documented public API and none is suitable as a runtime
programmatic surface for arbitrary queries. The eRegister's own About
page is explicit that NL **already feeds a daily delta to the EPO's
Federated Register Service**
([`fo-eregister-view/about/home.action`](https://mijnoctrooi.rvo.nl/fo-eregister-view/about/home.action))
— meaning EPO OPS / EP Register is the canonical programmatic
indirection for NL bibliographic data. **Zero entries from NL or BOIP in
the [WIPO IP API Catalog](https://apicatalog.wipo.int/api/apis)** (probed
2026-05-18: 179 office APIs across DPMA / EPO / EUIPO / IP Australia /
JPO / MOIP Korea / QAZ / UPRP / USPTO / WIPO; **zero** from RVO or BOIP).
The [data.overheid.nl dataset
`octrooiregister-nederland-01`](https://data.overheid.nl/dataset/octrooiregister-nederland-01)
is **the same Struts2 search UI relabeled** as a dataset — the JSON-LD
distribution literally lists `fileFormat: XLS` and `contentUrl:
https://mijnoctrooi.rvo.nl/fo-eregister-view/?locale=nl` with description
"Output in xsl [sic] or rss" — i.e. **the dataset entry IS the same UI
plus the RSS subscription**, not a bulk file or a feed endpoint. BOIP
gates its entire public site behind a Google reCAPTCHA on
`robots.txt` (probed 2026-05-18), publishes no developer page in `/en/`,
and routes its TM/design data to the public through **EUIPN TMview /
DesignView** — back-office integration via the [EUIPN Common Tools
Integration (CTI)](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI),
not a BOIP-operated API. Verdict: **red_no_api**; no direct connector is
warranted. NL patents are already covered transitively via
`patent_client_agents.epo_ops` (EP-NL validations + the FRS daily feed
of NL bibliographic data) and BOIP TMs/designs route via the planned
EUIPO TMview/DesignView surface.

---

## 1. Endpoint

There is **no documented public REST/JSON/XML API endpoint** for either
RVO/Octrooicentrum or BOIP. The closest things to "endpoints" are
application URLs of server-rendered web apps.

### 1.1 BPP eRegister (RVO/Octrooicentrum) — the real register UI

**Base host:** `https://mijnoctrooi.rvo.nl/fo-eregister-view/`

**Technology:** Apache Struts2 server-rendered application (URLs follow
the `.action` convention). All searches are submitted as HTML form POSTs
to `register/*.action`; responses are HTML tables. The application is
the NL leg of the **Benelux Patent Platform** (BPP) — a shared IT system
between NL/BE/LU patent offices; the BE leg lives at
[`bpp.economie.fgov.be/fo-eregister-view/`](https://bpp.economie.fgov.be/fo-eregister-view/)
and the LU leg at
[`patent.public.lu/bpp-portal/`](https://patent.public.lu/bpp-portal/).

**About-page statement** (the canonical primary source for what the
register is — [`/fo-eregister-view/about/home.action`](https://mijnoctrooi.rvo.nl/fo-eregister-view/about/home.action),
text reproduced verbatim):

> *"According to the Dutch Patent Act 1995, the Dutch patent register
> is managed by the Dutch Patent Office. The Dutch patent register
> contains information on published Dutch patent applications and
> patents from 1912 onwards, granted European patents valid for the
> Netherlands from 1978 onwards, applications for special protection
> certificates and granted certificates, and registered topographic
> design for semi-conductor products. ... The NL Patent register
> provides a **daily feed of selected bibliographical data on European
> patents in Netherlands to the Federated Register Service of the
> European Patent Office**."*

The application is described as serving four UI languages (Dutch,
English, German, French) on the help page; the about page corrects this
to Dutch + English. Last register update probed 2026-05-18 04:35:07 CEST
(from the about page).

**No swagger, no openapi, no v3/api-docs, no rest, no api endpoint.**
Probed 2026-05-18 — all `/api`, `/rest`, `/swagger-ui.html`,
`/v3/api-docs`, `/search/api` paths return 404:

```
404 https://mijnoctrooi.rvo.nl/fo-eregister-view/api
404 https://mijnoctrooi.rvo.nl/fo-eregister-view/rest
404 https://mijnoctrooi.rvo.nl/fo-eregister-view/swagger-ui.html
404 https://mijnoctrooi.rvo.nl/fo-eregister-view/v3/api-docs
404 https://mijnoctrooi.rvo.nl/fo-eregister-view/search/api
404 https://mijnoctrooi.rvo.nl/bpp-portal/api
404 https://mijnoctrooi.rvo.nl/bpp-portal/rest
```

### 1.2 BPP eRegister structured outputs — three of them, all UI-side

What *does* exist, embedded in the eRegister JS at
[`/fo-eregister-view/resources/scripts/exportToCSV.js`](https://mijnoctrooi.rvo.nl/fo-eregister-view/resources/scripts/exportToCSV.js)
and surfaced in the advanced-search HTML at
[`/fo-eregister-view/search/advanced`](https://mijnoctrooi.rvo.nl/fo-eregister-view/search/advanced):

| Output | URL | Auth | Format | Cap | Surface posture |
|---|---|---|---|---|---|
| Saved-search RSS subscription | UI button labeled "RSS" → `javascript:showRSSFeed()` populates a URL with current query | none | RSS 2.0 | per-query, paged | **Subscription per saved query**, not a general API |
| Per-document XML download | `POST /fo-eregister-view/download/downloadFileXML` | none | XML (WIPO ST.96 patent-document schema, document-level) | one document per call | Single-document fetch, requires `docId` derived from a prior HTML search |
| Bulk CSV export of result list | `POST /fo-eregister-view/download/exportCSV` | none | CSV | **`maxExportResults = 1000`** | Bibliographic-only, capped at 1k rows |

The CSV cap is hard-coded:
```js
var maxExportResults = 0;
maxExportResults = 1000;
msg['form.validation.export.maxResults'] = "Too many results to export! "
  + "Only the first" + " " + maxExportResults + " " + "results are included in the export file.";
```

The cap, the requirement to perform the HTML search first, and the
opaque `docId` derivation rule out treating any of these as a runtime
"search the register for X via JSON" API.

### 1.3 data.overheid.nl `octrooiregister-nederland-01` — *not* a feed

[The dataset entry](https://data.overheid.nl/dataset/octrooiregister-nederland-01)
on the Dutch federal open-data portal looks like it might be a bulk
file but **isn't**. The JSON-LD `distribution` block (extracted
2026-05-18) records:

```json
{
  "@type": "DataDownload",
  "contentUrl": "https://mijnoctrooi.rvo.nl/fo-eregister-view/?locale=nl",
  "name": "Nederlands octrooiregister",
  "description": "Deelselecties zijn mogelijk op basis van rechtsoort: Certificaat (ABC), Europees octrooi (EP-NL), Nederlands octrooi en Topografie (chipsrecht), octrooinummer, IPC klasse, uitvinder, gemachtigde, aanvrager/houder. Output in xsl of rss.",
  "license": "CC-BY (4.0)",
  "fileFormat": "XLS",
  "contentSize": " KB",
  "encodingFormat": "",
  "uploadDate": "",
  "dateModified": ""
}
```

The `contentUrl` is the same Struts2 search UI. `fileFormat: XLS` is
nominal — there is no bulk XLS file behind the link, only the
per-search 1,000-row export the UI offers. `dateModified` on the
dataset itself is **2020-03-27**; the dataset is effectively dormant
metadata pointing at the live UI. Useful only to confirm the
**CC-BY 4.0 license** that nominally covers the data.

### 1.4 BOIP — Benelux TMs and designs

**Base host:** [`https://www.boip.int/`](https://www.boip.int/en)

BOIP is the Benelux Organization for Intellectual Property's office
arm, registering trademarks and designs across the BE+NL+LU territory.
It is **not** part of RVO and is **not** the NL patent surface — but
since the NL question is patents-specific, we cross-probed BOIP in the
same wave to confirm whether it has any independent programmatic
surface worth surveying.

**Probe results (2026-05-18):**

- `boip.int/robots.txt` → **Google reCAPTCHA challenge** before any
  content. Same for `boip.int/sitemap.xml`. Any structured crawl is
  gated by JS-rendered captcha.
- [`/en/ip-professionals/registration-maintenance/tools`](https://www.boip.int/en/ip-professionals/registration-maintenance/tools)
  → no API mentions; lists consumer-facing search tools
  (BOIP Search, TMview, DesignView).
- [`/en/entrepreneurs/about-boip`](https://www.boip.int/en/entrepreneurs/about-boip)
  → no developer page, no `/developers`, no `/api`, no `/open-data`.
- BOIP has **zero entries** in the WIPO IP API Catalog
  ([`apicatalog.wipo.int/api/apis`](https://apicatalog.wipo.int/api/apis), 179 results, no BX/BENELUX/BOIP organization).

**BOIP's actual programmatic surface is indirection through EUIPN
shared tools**, not its own API. The
[EUIPN Common Tools Integration (CTI)](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI)
is a back-office bridge from each national office's IT system into
[TMview](https://www.euipn.org/en/tools/TMview) and DesignView. BOIP's
TM/design records flow into TMview/DesignView via CTI; users hit those
EUIPN-hosted tools (the EUIPO API surface), not BOIP directly. BOIP
news pieces describing TMview / DesignView accessions (e.g.
[Costa Rica joins TMview and DesignView](https://www.boip.int/en/entrepreneurs/news/costa-rica-joins-tmview-and-designview))
exclusively describe access *through* TMview/DesignView, never an own
BOIP API.

### 1.5 WIPO IP API Catalog — zero NL/BX entries

Probed
[`https://apicatalog.wipo.int/api/apis?size=200`](https://apicatalog.wipo.int/api/apis?size=200)
on 2026-05-18 and tallied 179 office APIs:

```
DPMA: 1   EPO: 6   EUIPO: 10   IP Australia: 5   JPO: 40
MOIP KOREA: 90   QAZ: 1   UPRP: 3   USPTO: 19   WIPO: 4
NL / Benelux / BOIP / Octrooicentrum / RVO: 0
```

No keyword hit for "NL", "Benelux", "BOIP", "RVO", "Octrooi", or
"Netherlands" in any of the 179 entries. The canonical signal that an
IP office has shipped a public API — listing it on the WIPO catalog —
**has not fired** for either NL/RVO or BOIP.

---

## 2. Auth

**None of the public surfaces require auth** (the eRegister explicitly
states "The NL Patent register does not require any subscription and is
available for all" — [about page](https://mijnoctrooi.rvo.nl/fo-eregister-view/about/home.action)).
However, **none of them is a public API either**. The auth-required
surfaces — MyPage (digital patent dossiers, applicant-side) and
Online Filing (eOLF) — are personal-account portals at
[`mijnoctrooi.mypage.rvo.nl`](https://mijnoctrooi.mypage.rvo.nl/) and
[`efiling.mijnoctrooi.rvo.nl`](https://efiling.mijnoctrooi.rvo.nl/),
strictly applicant-side, not a search surface.

BOIP gates its consumer site behind reCAPTCHA but, again, has no API
surface to authenticate against.

---

## 3. Query language

The eRegister's advanced-search HTML form supports a structured AND/OR
boolean expression on these fields (extracted from
[`/fo-eregister-view/search/advanced`](https://mijnoctrooi.rvo.nl/fo-eregister-view/search/advanced)):
patent number, application number, publication number, IPC class,
inventor, applicant/holder, representative (`gemachtigde`), priority
data, dates, and right type (national patent, EP-NL, SPC, semiconductor
topography). Wildcards `*` and `?` supported; the help page lists 27
stop words eRegister ignores (`a, an, and, are, as, at, be, but, by,
for, if, in, into, is, it, no, not, of, on, or, such, that, the,
their, then, there, these, they, this, to, was, will, with`). This is
all UI-side — the parameters become hidden HTML form fields, not URL
query strings, on a Struts2 POST.

No documented query DSL; no JSON request body; no GraphQL; no CQL.

---

## 4. Pagination

eRegister returns HTML grids paginated client-side; CSV export caps the
underlying result list at 1,000 rows (`maxExportResults = 1000`). The
RSS subscription paginates via standard RSS `<channel>` paging
controlled by the underlying saved-query. There is no `cursor`,
`offset`, or `nextPageToken` semantics exposed as URL params.

---

## 5. Response shape

- **Search results:** server-rendered HTML grid.
- **CSV export:** flat row-per-patent with bibliographic fields, capped 1k.
- **Document XML download:** WIPO ST.96 patent-document XML (document-level), per-document only.
- **RSS feed:** RSS 2.0, per-saved-query, item = match.

The **document XML** is the closest thing to structured data the
eRegister offers, but it's document-level (you have to already know the
`docId` from a prior HTML search) and there is no documented full-list
fetch that returns structured XML rows.

---

## 6. Coverage scope

Per the eRegister About page:

- **Published Dutch patent applications + patents from 1912 onwards.**
- **Granted European patents valid for the Netherlands from 1978 onwards.**
- **NL Supplementary Protection Certificate applications + granted SPCs.**
- **Registered topographic designs for semi-conductor products.**

Critically, the same About page states: *"The NL Patent register
provides a **daily feed of selected bibliographical data on European
patents in Netherlands to the Federated Register Service of the
European Patent Office**."* This means **EPO OPS / EP Register
captures the EP-NL slice with daily freshness** — the most
commercially-relevant slice (granted EPs validated in NL).

The genuine NL-national-only slice (national NL patent applications,
NL SPCs at register fidelity, NL semiconductor topographies, NL file
history) is what isn't in INPADOC — and that's what has no API.

**De Industriële Eigendom** (the NL patent gazette) is published
weekly in PDF via the
[Octrooi-informatie Portal](https://www.rvo.nl/octrooiportal). PDF
only; no structured-bulletin endpoint.

**Benelux trademarks + designs** at the BOIP register — administrative
coverage of BE+NL+LU — flow into TMview / DesignView via EUIPN's
back-office CTI integration. The "BOIP as a programmatic source" is
really "EUIPO TMview/DesignView as the front, BOIP via CTI as the
back". Direct BOIP access is consumer-only.

---

## 7. Rate limits

None published. The eRegister Disclaimer page is silent on
rate-limiting; the Drupal-based BPP portal at `mijnoctrooi.rvo.nl/bpp-portal/`
runs on the same infrastructure. RVO publishes general "open data"
guidance at [`rvo.nl/onderwerpen/open-data`](https://www.rvo.nl/onderwerpen/open-data)
but does not extend it to register-search traffic.

---

## 8. Terms of service

[BPP eRegister Disclaimer](https://mijnoctrooi.rvo.nl/fo-eregister-view/disclaimer/home.action)
+ the [bpp-portal Drupal disclaimer](https://mijnoctrooi.rvo.nl/bpp-portal/nl/disclaimer)
govern. The register is **CC-BY 4.0** per the
[`data.overheid.nl` JSON-LD distribution](https://data.overheid.nl/dataset/octrooiregister-nederland-01)
(`"license": "http://creativecommons.org/licenses/by/4.0/deed.nl"`).
Attribution to Rijksdienst voor Ondernemend Nederland / Octrooicentrum
Nederland required if redistributed. No proxy-prohibition clause; the
problem isn't *legal* (data is CC-BY) but *technical* — there is no
API to proxy.

BOIP's data, in contrast, is gated behind a reCAPTCHA, has no published
license posture for register search results, and any direct scrape
would trip the reCAPTCHA gate.

---

## 9. Ops notes

- **EP-NL is reachable today via EPO OPS** — that covers the
  commercially-relevant majority of "Netherlands patents". Adding NL
  via RVO would expand coverage to NL-only patents + national SPCs +
  semiconductor topographies + register-fidelity legal status.
- **The Struts2 eRegister is brittle** — same shape as the IP Australia
  pre-OAuth legacy register and the AT see.ip pre-2026 ASP.NET app.
  Any scrape would target Struts2 `.action` POSTs with HTML response
  bodies; document XML is per-doc only.
- **BOIP's reCAPTCHA gate** rules out any direct programmatic touch
  even for "research-grade" probes — the captcha fires on `robots.txt`
  itself. This isn't a soft signal; it's a hard one.
- **EUIPN TMview / DesignView is the right Benelux indirection** for
  TMs and designs. When the EUIPO connector lands, BOIP-administered
  records will be reachable through it. That's the work item.
- **Watch the WIPO IP API Catalog.** When NL or BOIP appears there,
  re-evaluate. Until then, do not rebuild on speculation.

---

## 10. Verdict

**🔴 red_no_api.**

There is no documented public REST/JSON/XML API at Octrooicentrum
Nederland or BOIP. The BPP eRegister's structured outputs are
saved-search RSS subscriptions, document-level XML downloads, and a
1k-row capped CSV — none of which is a "search the register for X
programmatically" API. The data is CC-BY 4.0 (so license isn't the
blocker), but the technical surface isn't there to proxy.

Strategic implications:

1. **NL patents are already covered transitively** via
   `patent_client_agents.epo_ops` — both EP-NL validations and the
   FRS daily feed of NL bibliographic data. The EPO Patent Register
   ingests RVO's daily bibliographic delta; that's the canonical
   programmatic indirection.

2. **Benelux TM / design coverage routes through the planned EUIPO
   connector** (TMview / DesignView), not through BOIP directly.
   BOIP's records reach the public via the EUIPN CTI back-office
   bridge to TMview/DesignView.

3. **The genuine NL-national-only gaps** — NL national patent file
   history, register-fidelity NL SPC status, NL semiconductor
   topographies — have no programmatic path. Document this gap;
   don't try to solve it with a fragile Struts2 scrape.

4. **Watch [`apicatalog.wipo.int`](https://apicatalog.wipo.int/)** —
   the canonical signal an office has shipped a public API. NL and
   BX both absent as of 2026-05-18.

Connector status: **skipped**. Do not build an RVO connector. Do not
build a BOIP connector. Route NL patent queries through EPO OPS; route
Benelux TM/design queries through the planned EUIPO connector.

---

## Appendix — what was probed

Surfaces hit on 2026-05-18 with `curl -sL -A "Mozilla/5.0"`:

- `https://mijnoctrooi.rvo.nl/bpp-portal/en/` — BPP portal, Drupal 11, navigation only.
- `https://mijnoctrooi.rvo.nl/bpp-portal/en/eRegister` — link card to the eRegister UI.
- `https://mijnoctrooi.rvo.nl/fo-eregister-view/` — eRegister Struts2 app.
- `https://mijnoctrooi.rvo.nl/fo-eregister-view/about/home.action` — about page (FRS daily-feed statement).
- `https://mijnoctrooi.rvo.nl/fo-eregister-view/help/home.action` — help page (RSS saved-query confirmation; wildcards; 27-word stop list).
- `https://mijnoctrooi.rvo.nl/fo-eregister-view/search/advanced` — advanced-search form (CSV cap 1000; downloadFileXML endpoint).
- `https://mijnoctrooi.rvo.nl/fo-eregister-view/resources/scripts/exportToCSV.js` — client-side export logic.
- 404 probes: `/fo-eregister-view/api`, `/rest`, `/swagger-ui.html`, `/v3/api-docs`, `/search/api`, `/bpp-portal/api`, `/bpp-portal/rest`.
- `https://english.rvo.nl/topics/patents-intellectual-property-rights/about-patent-office` — RVO marketing page.
- `https://data.overheid.nl/dataset/octrooiregister-nederland-01` — federal open-data dataset entry (JSON-LD distribution extracted).
- `https://www.boip.int/en/` (and tools, about, search, BPP-SQ, open-data, sitemap.xml, robots.txt) — all gated by Google reCAPTCHA challenge HTML.
- `https://apicatalog.wipo.int/api/apis?size=200` — WIPO IP API Catalog, 179 entries, zero NL/BX hits.
- `https://inspire.wipo.int/system/files/juri/nl.pdf` — WIPO INSPIRE NL country profile (BPP described; no API mention).
- `https://bpp.economie.fgov.be/fo-eregister-view/help/home.action` — BE sibling eRegister (same Struts2 app; same RSS-subscription / CSV-export limits).
