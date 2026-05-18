# OPA Austria (AT) — Patents, Utility Models, Trademarks, Designs API Discovery

**Date:** 2026-05-18
**Scope:** Determine whether the Österreichisches Patentamt (Austrian
Patent Office, ÖPA / OPA) exposes a public, queryable REST/JSON/XML API
that we can proxy at runtime, zero infrastructure on our side. Bulk
dumps and HTML-only surfaces are a **red** verdict, equally as useful
as a "green" because they lock the decision.

**TL;DR:** **Red — no public API.** Austria's only register-search
surface is **see.ip** ([`seeip.patentamt.at`](https://seeip.patentamt.at/)),
a Next.js single-page app rebuilt in early 2026 ([news 2026-03-05 —
"Search smarter with the new see.ip"](https://www.patentamt.at/en/all-news/news-detail/artikel/search-smarter-with-the-new-seeip)).
Its data calls are Next.js Server Actions — same-origin, opaque,
unversioned, and intended for browser consumption only. There is **no
documented REST/JSON/XML API**, **no developer portal**, and **no entry
for Austria in the [WIPO IP API Catalog](https://apicatalog.wipo.int/)**
(probed 2026-05-18: 179 entries across DPMA, EPO, EUIPO, IP Australia,
JPO, KIPO/MOIP KOREA, UPRP, USPTO, WIPO, and Kazakhstan — zero from
ÖPA). The Austrian Patent Office's footprint on Austria's open-data
portal `data.gv.at` is **6 PDFs + 1 ordinance — no register data, no
bulk feeds, no machine-readable IP data**. Bulk publications
(`Patentblatt`, `Gebrauchsmusterblatt`, `Markenanzeiger`,
`Musteranzeiger`) ship monthly **as PDFs only** —
[downloads page](https://www.patentamt.at/en/downloads/publications/).
The [patentamt.at Impressum](https://www.patentamt.at/impressum)
explicitly forecloses commercial reuse and third-party disclosure
without written consent. AT patents are already reachable transitively
via **EPO OPS / INPADOC** (Austria is an EPC contracting state and a
UPC member); EUTMs designating AT and Community designs via **EUIPO**;
Madrid IRs designating AT via **WIPO Madrid Monitor**. The genuine
national-only gaps — **AT utility models (`Gebrauchsmuster`), AT-only
national TMs, AT-only national designs, the AT patent file history** —
have no programmatic surface we can proxy.

---

## 1. Endpoint

ÖPA's online surface is split across four hosts; **none** expose a
documented programmatic interface.

| Surface | Host | Right(s) | Shape |
|---|---|---|---|
| see.ip (register search) | [`seeip.patentamt.at`](https://seeip.patentamt.at/) | patent / utility model / trademark / design | Next.js SPA, Server Actions |
| patentamt.at (institutional) | [`www.patentamt.at`](https://www.patentamt.at/en/) | content + downloads (PDFs) | TYPO3 CMS, HTML |
| privilegien.patentamt.at (historical) | [`privilegien.patentamt.at`](https://privilegien.patentamt.at/) | pre-1899 Austro-Hungarian privileges (95k docs) | intranda Goobi viewer, HTML/IIIF |
| Online services (filing portal) | [`www.patentamt.at/en/online-services/`](https://www.patentamt.at/en/online-services/) | filing only — not search | Web forms |

**see.ip** routes (Next.js dynamic routes — all client-rendered):

- `/patentsuche` — patent search (national + EP-designating-AT + supplementary protection certificates)
- `/markesuche` — trade-mark search (national + IR + EUTM)
- `/mustersuche` — design (Muster) search
- `/Marke/Details/{regNr}/{year}` — legacy detail-page deep links (preserved for SEO; 200 OK)
- `/NPatentSuche` — national patent search route (linked from
  [news 2026-03-05](https://www.patentamt.at/en/all-news/news-detail/artikel/search-smarter-with-the-new-seeip))

Probes 2026-05-18: `/Help/DownloadHelp?searchType=EPatent` returns 404
(the legacy ASP.NET XML-download helper from the prior see.ip
generation is gone). The Next.js Server Actions referenced inside the
client bundles (`_next/static/chunks/...`) are RSC-encoded payloads
posted to the same origin — they have no published contract, are not
versioned, and the encoded action IDs rebuild on every deploy. They
are not a viable target for a third-party connector.

---

## 2. Auth

There is **no API to authenticate against.** see.ip is anonymous
public-access (no login wall for search; no API key issuance flow
documented). The filing portal under
[`www.patentamt.at/en/online-services/`](https://www.patentamt.at/en/online-services/)
requires personal authentication for applicant-side filing — that's
not a search surface.

No primary source advertises:

- An API key or OAuth client-credentials flow.
- A developer registration portal.
- A paid-data agreement equivalent to DPMA's *DPMAconnectPlus* or
  KIPO's *KIPRIS Plus*.

Confirmed by absence: the [WIPO IP API Catalog](https://apicatalog.wipo.int/)
lists 179 office APIs as of 2026-05-18 (DPMA, EPO, EUIPO, IP Australia,
JPO, MOIP KOREA, UPRP, USPTO, WIPO, Kazakhstan QAZ) — **zero entries
under ÖPA / Austrian Patent Office / Österreichisches Patentamt /
"AT"**. Probe payload `GET https://apicatalog.wipo.int/api/apis?size=200`,
filtered for `austri`, `oepa`, `patentamt.at` strings — 0 matches.

---

## 3. Query Language

**Not applicable.** see.ip is a browser UI; the underlying Server-Action
endpoints accept opaque RSC-encoded payloads, not a documented query
DSL. There is no SolR Lucene surface (as INPI France offers), no
Boolean field grammar (as DPMA's `Expertenrecherche` offers), no JSON
schema published.

Users issue queries through HTML forms at `/patentsuche`, `/markesuche`,
`/mustersuche`. The fields exposed in the UI (per the [search how-to
news](https://www.patentamt.at/en/all-news/news-detail/artikel/search-smarter-with-the-new-seeip)):
application/publication number, applicant name, classification (IPC for
patents, Vienna codes for marks, Locarno for designs), date ranges, and
legal status. These are not exposed as a queryable API contract.

---

## 4. Pagination

**Not applicable.** No API contract published. The SPA paginates
client-side (visible from the UI), but the underlying Server Actions
are not a stable interface to call from a third party.

---

## 5. Response Shape

**No public response schema.** see.ip's UI renders structured data
(numbers, dates, status codes, parties, classifications), but the only
machine-readable export documented on the see.ip site or the patentamt.at
documentation is the **PDF download** of the relevant gazette issue or
register extract — both human-readable, not structured.

The legacy see.ip (ASP.NET) at the prior URL did expose `Help/DownloadHelp`
download helpers (e.g.
[`/Help/DownloadHelp?searchType=EPatent`](http://seeip.patentamt.at/Help/DownloadHelp?searchType=EPatent),
[`/Help/DownloadHelp?searchType=Marke`](http://seeip.patentamt.at/Help/DownloadHelp?searchType=Marke)
in the Google search index) — these now return **404** on the rebuilt
2026 platform. The new platform has not announced any replacement
download API.

---

## 6. Coverage Scope

What see.ip indexes (per
[`seeip.patentamt.at/`](https://seeip.patentamt.at/) home page and the
[WIPO INSPIRE Austria jurisdiction PDF](https://inspire.wipo.int/system/files/juri/at.pdf)):

| Right | Coverage |
|---|---|
| **National AT patents** | from **1900** to present (>100k national patents, utility models, and SPCs) |
| **European patents designating AT** | full EP biblio + legal-status validated in AT |
| **Supplementary Protection Certificates (SPCs)** | per ÖPA registry |
| **AT national trademarks** | full national TM register |
| **International trademarks (Madrid IR) designating AT** | per WIPO ingestion |
| **EU trademarks (EUTM)** | via EUIPO ingestion (designate AT by virtue of EU membership) |
| **AT national designs (Muster)** | full national design register |

**Historical layer:** [`privilegien.patentamt.at`](https://privilegien.patentamt.at/)
hosts ~95,000 digitized Austro-Hungarian patent privileges 1852-1899
([Privilegiensammlung overview, Austrian National Library
note](http://othes.univie.ac.at/3971/) and the [125-years anniversary
microsite](https://www.patentamt.at/en/125years)). Pre-1900 archive
only — viewer (Goobi/intranda); not an API.

**Higher-layer substitutes already in our stack:**

- **AT patents (biblio + family + legal events):** EPO OPS via
  [`patent_client_agents.epo_ops`](../../src/patent_client_agents/epo_ops/).
  Austria is an EPC contracting state and a UPC member; AT national
  filings are covered in INPADOC with the standard EPO OPS
  country-code path. The INPADOC entity itself was [founded under a
  WIPO–Austrian government agreement in
  1972](https://en.wikipedia.org/wiki/INPADOC) and the EPO's Principal
  Directorate Patent Information is **located in Vienna**, which makes
  AT one of the offices with the deepest INPADOC ingestion.
- **EUTMs designating AT and Community designs (RCD/REUD):** EUIPO
  ([`dev.euipo.europa.eu`](https://dev.euipo.europa.eu/)). Pure AT
  national TMs and designs are **NOT** covered there.
- **Madrid IRs designating AT, Hague IRs designating AT:** WIPO
  ([Madrid Monitor](https://www.wipo.int/madrid/monitor/), [Hague
  Express](https://www.wipo.int/designdb/hague/)).

**Genuine national-only gaps that have no programmatic substitute:**

- AT utility models (`Gebrauchsmuster`) — a distinctive AT right with
  shorter (~10-year) protection and no examination of novelty/
  inventive step; [overview](https://www.patentamt.at/en/patents/apply-for-patents/utility-models).
  Not in EP filings — only path is ÖPA. Mirrors the DE Gebrauchsmuster
  shape but on a smaller volume.
- AT national-only TMs (filed directly with ÖPA, not via Madrid IR
  and not as EUTMs).
- AT national-only designs (filed directly with ÖPA, not via Hague IR
  and not as RCDs).
- AT-specific procedural events (oppositions, nullity proceedings,
  SPC live status) at the fidelity the ÖPA register holds.
- AT patent file history (file inspection / Akteneinsicht).

---

## 7. Rate Limits / Quotas

**Not published.** No primary source documents API rate limits because
no API is offered. see.ip browser usage is presumably subject to
ordinary anti-abuse throttling at the CDN / WAF layer, but there is no
documented quota for programmatic use.

---

## 8. Terms of Service

The legal posture is set by the **patentamt.at Impressum** (which see.ip
inherits — see.ip's footer links its legal notice to
[`patentamt.at/impressum`](https://www.patentamt.at/impressum) and
[`patentamt.at/datenschutz`](https://www.patentamt.at/datenschutz)).

Verbatim from
[`https://www.patentamt.at/impressum`](https://www.patentamt.at/impressum)
(probed 2026-05-18):

> "Urheberrecht © Österreichisches Patentamt. Die Urheber- und
> Nutzungsrechte der auf den Seiten bereitgestellten Informationen und
> Gestaltungselemente liegen beim Österreichischen Patentamt. … Die
> Inhalte der Website sind für den persönlichen Gebrauch bestimmt. Wir
> weisen ausdrücklich darauf hin, dass jede weiter gehende Verwendung
> oder Vervielfältigung der Inhalte dieser Website, insbesondere die
> kommerzielle Nutzung und Weitergabe an Dritte, einer schriftlichen
> Zustimmung des Österreichischen Patentamtes bedarf."

Translation: "Copyright © Austrian Patent Office. The copyright and
usage rights to the information and design elements provided on the
pages lie with the Austrian Patent Office. … The content of the
website is intended for personal use. We expressly note that any
further use or reproduction of the content of this website,
**in particular commercial use and disclosure to third parties,
requires the written consent of the Austrian Patent Office**."

**Bottom line on ToS:** Even if a programmatic surface existed,
patentamt.at's stated policy is **personal-use only**, with commercial
or third-party redistribution gated on prior written consent. There is
no published license (CC-BY, Etalab, Open Licence) that would override
that default. Building a hosted proxy that serves see.ip data to
third-party users — without a separate signed agreement with ÖPA —
would conflict with the Impressum's stated terms.

The handful of ÖPA assets that **are** on `data.gv.at` (see §6 of
synopsis) are released under **CC-BY 4.0 / `http://publications.europa.eu/resource/authority/licence/CC_BY`**
per their data.gv.at metadata (probed via the
[`/api/hub/search/search?q=patentamt`](https://www.data.gv.at/api/hub/search/search?q=patentamt)
endpoint) — but those assets are administrative PDFs (ordinances,
contract notices), **not register data**.

---

## 9. Operational Notes

- **Language.** see.ip is bilingual (DE / EN, language switch in the
  Next.js shell). All bulk publications and gazette PDFs are
  **German-only** — explicit notice on the publications and fees pages:
  "NOTICE! Downloads are only available in German." Source:
  [`patentamt.at/en/downloads/publications`](https://www.patentamt.at/en/downloads/publications/).
- **Recent platform change.** see.ip was rebuilt and relaunched in
  early 2026 as a Next.js SPA replacing the prior ASP.NET application;
  announced [2026-03-05 — "Search smarter with the new see.ip"](https://www.patentamt.at/en/all-news/news-detail/artikel/search-smarter-with-the-new-seeip).
  The new platform did **not** ship with an API, did **not** announce
  a developer programme, and **dropped** the legacy `/Help/DownloadHelp`
  download helpers that the old platform exposed.
- **Geofencing.** No primary source documents IP allowlisting or
  geofencing. Probes from US egress 2026-05-18 hit see.ip cleanly.
- **DNS / WAF posture.** see.ip is fronted by Vercel / Cloudflare-style
  CDN (Next.js `_next/static/chunks/*`); www.patentamt.at runs Apache
  on `85.158.225.220` (Citrix NetScaler `citrix_ns_id` cookie observed
  on responses) — a load-balancer signature. Routine egress filtering
  not detected on these probes.
- **DPMA / ÖPA contrast.** Germany's *DPMAconnectPlus* exposes a paid
  REST surface on per-user contract (see
  [`research/national/de-dpma.md`](../../national/de-dpma.md)). ÖPA
  publishes **nothing equivalent**. The asymmetry is notable: AT
  routes its programmatic patent users to EPO OPS by design, since
  the EPO's Patent Information directorate is **in Vienna** and ÖPA
  has effectively delegated machine-readable AT patent dissemination
  upstream.
- **Open-data footprint on `data.gv.at`.** Probed `data.gv.at`'s CKAN-
  successor search endpoint
  [`/api/hub/search/search?q=patentamt`](https://www.data.gv.at/api/hub/search/search?q=patentamt) —
  9 hits, all PDFs, mostly administrative:
  1. *Patentamtsverordnung 2019 - PAV* (the patent-office procedural
     ordinance) — PDF, modified 2025-09-08.
  2. *Publikationen des Österreichischen Patentamts* — PDF index,
     modified 2025-10-06.
  3. *Vertrag Serverankauf vom 10.10.2025* — administrative
     procurement contract, modified 2025-11-20.
  4. *Geschäftsverteilung und Personaleinteilung* — internal
     organisation chart, modified 2025-08-01.
  5. *Vergabeverfahren Zahlungsinformationssystem Konzeptionsphase* —
     procurement notice, modified 2025-11-24.
  6. *Patentamt* (generic catalog entry, modified 2026-02-12).

  None of these are register data or bulk patent/TM/design feeds.
- **Patent register online (legacy reference).** The WIPO INSPIRE
  Austria jurisdiction note ([`inspire.wipo.int/system/files/juri/at.pdf`](https://inspire.wipo.int/system/files/juri/at.pdf))
  describes Austria's "Online Register and Online Gazette" in
  bibliographic terms — DE/EN UI, legal-status retrievable, applicant/
  inventor and priority-data search — confirming the consumer-facing
  capability without describing any machine surface.
- **Historical archive.** [`privilegien.patentamt.at`](https://privilegien.patentamt.at/)
  is operated on intranda's Goobi viewer (CNAME → `oepma.intranda.com`).
  IIIF likely available at the manifest level; not advertised. Out of
  scope for live-register coverage.

---

## 10. Verdict

| Right | Verdict | One-sentence reason |
|---|---|---|
| **Patents** | 🔴 **Red — covered transitively** | EPO OPS / INPADOC covers AT patents at biblio + family + legal-status fidelity (EPO Patent Information is in Vienna); ÖPA offers no API and ToS prohibits commercial reuse of see.ip content. |
| **Utility models** | 🔴 **Red — no path** | AT `Gebrauchsmuster` is a genuine national-only right with no programmatic surface; see.ip is browser-only; no developer programme. |
| **Trademarks** | 🔴 **Red — no path** | AT national-only TMs have no API; EUIPO covers EUTMs designating AT; Madrid Monitor covers IR designations of AT. |
| **Designs** | 🔴 **Red — no path** | AT national-only designs (Muster) have no API; EUIPO RCD covers Community designs; Hague Express covers Hague IRs designating AT. |

**Overall:** **🔴 Red — `red_no_api`.** Austria publishes **no public
register API** (REST, JSON, XML, SOAP, or otherwise), is not listed in
the [WIPO IP API Catalog](https://apicatalog.wipo.int/) (the canonical
inventory of office APIs), released `data.gv.at` data only for
administrative PDFs (not register data), and the patentamt.at Impressum
forecloses commercial reuse without written consent. The 2026 see.ip
relaunch was a UI modernization, not an API rollout. The decision is
**locked**: AT patents are reachable transitively (EPO OPS), and the
genuine national-only gaps (AT utility models, AT-only national TMs,
AT-only national designs, AT file history) have no zero-infra path
and no BYOK path either, because there is **no API to BYOK against**.
Strategic memory: do not re-evaluate until ÖPA publishes a developer
programme — monitor [`patentamt.at/en/all-news/`](https://www.patentamt.at/en/all-news/)
for that announcement.
