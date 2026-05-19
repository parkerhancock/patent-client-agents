# OMPIC Morocco (MA) — Patents/TMs/Designs/GI/Commercial Register API Discovery

**Date:** 2026-05-18
**Scope:** Determine whether the **Office Marocain de la Propriété
Industrielle et Commerciale (OMPIC)** — the integrated Moroccan
authority for patents, trademarks, designs, geographical indications,
and the Central Commercial Register (RCC) — exposes a public,
queryable REST/JSON/XML API a third-party developer can register for
and proxy at runtime, with zero infrastructure on our side. Bulk
dumps and HTML-only surfaces are a **red** verdict.

**TL;DR — Verdict: 🔴 red_no_api.** OMPIC is digitally mature by African
standards but exposes **no documented public REST/JSON/XML API** for
IP data. The free IP register sits on a JSP-based search portal at
[`search.ompic.ma`](http://search.ompic.ma/web/pages/marques/recherche_marque.jsp)
(trademarks/designs) and a separate EPO-built publication server at
[`patent.ompic.ma`](https://patent.ompic.ma/publication-server/) for
brevets — both HTML-only with no documented JSON layer. A second
register browser at [`patentregister.ompic.ma`](https://patentregister.ompic.ma/SearchPatent/searchByDepot?typeNum=EP&numDepot=15736535.4)
serves the National Patent Register. The paid commercial portal
[`directinfo.ma`](https://www.directinfo.ma/) (the renamed
`directompic.ma`) sells per-document Central Commercial Register
extracts plus TM/design/patent biblio lookups under a subscription
contract — its [Mentions légales](https://www.directinfo.ma/assets/documents/Mentions-legales-directinfo.pdf)
and [contrat d'abonnement](https://www.directinfo.ma/assets/documents/contrat_abonnement.pdf)
explicitly bind subscribers to OMPIC ToU and **do not advertise a B2B
API** — the [Nov 2017 guide d'utilisation](https://www.directinfo.ma/assets/documents/guide.pdf)
documents only an interactive multi-criteria HTML search interface.
OMPIC is **not listed** in the [WIPO IP API Catalog](https://apicatalog.wipo.int/)
(probed 2026-05-18 — 0 hits for OMPIC/MA). Transitive coverage is
better than typical Africa: Morocco is the **only African
[EPO Validation State](https://www.epo.org/en)** (in force since
**2015-03-01** per the [EPO-Morocco validation agreement](https://www.epo.org/en)),
so EPO INPADOC carries Moroccan patent biblio at decent fidelity; MA
is a **PCT** member since 1999-10-08 ([WIPO PCT accession press
release](https://www.wipo.int/pressroom/en/prdocs/1999/wipo_upd_1999_66.html)),
a **Madrid Protocol** member, and acceded to the **1999 Geneva Act of
the Hague Agreement** on 2022-04-22 ([WIPO Hague news](https://www.wipo.int/en/web/hague-system/w/news/2022/news_0020)).
National-only gaps remain: MA TM file histories, opposition records,
GIs, designs registry, and the Central Commercial Register.

---

## 1. Endpoints

| Host | Right(s) | Shape | Probe (2026-05-18) |
|---|---|---|---|
| [`www.ompic.ma`](http://www.ompic.ma/fr) | institutional site, FR/EN/AR content | Drupal HTML | HTTP 200 — content-only, no API |
| [`search.ompic.ma/web/pages/marques/recherche_marque.jsp`](http://search.ompic.ma/web/pages/marques/recherche_marque.jsp) | national TM search (also designs via sibling JSP paths) | JSP HTML form | HTTP 200 — free interactive search; no documented JSON backend |
| [`patent.ompic.ma/publication-server/`](https://patent.ompic.ma/publication-server/) | weekly patent publication server (EPO-built — see [help_en.html](https://patent.ompic.ma/publication-server/help_en.html)) | HTML + PDF | HTTP 200 — searchable by publication number, application number, IPC, date; PDFs downloadable; **no JSON API** |
| [`patent.ompic.ma/publication-server/search`](https://patent.ompic.ma/publication-server/search) | search interface | HTML form | HTTP 200 |
| [`patent.ompic.ma/publication-server/pdf-document?PN=...&iDocId=...`](https://patent.ompic.ma/publication-server/pdf-document?PN=MA58719+MA+58719&iDocId=21275&iepatch=.pdf) | publication PDF retrieval | PDF | HTTP 200 (predictable URL pattern but undocumented) |
| [`patentregister.ompic.ma/SearchPatent/`](https://patentregister.ompic.ma/SearchPatent/searchByDepot?typeNum=EP&numDepot=15736535.4) | National Patent Register information service — looks up legal status by deposit number, including EP validations | HTML | HTTP 200 — single-record HTML; no list/JSON endpoint |
| [`brevet.ompic.ma`](http://brevet.ompic.ma/) | alias for the patent publication server | HTML redirect | resolves to `patent.ompic.ma` |
| [`www.directinfo.ma`](https://www.directinfo.ma/) | paid Central Commercial Register + IP biblio portal (renamed from `directompic.ma`) | ASP/HTML SPA | HTTP 200 — login-walled paid lookups |
| [`www.directinfo.ma/recherche-multi-criteres`](https://www.directinfo.ma/recherche-multi-criteres) | multi-criteria search across RCC + TM + design + patent biblio | HTML | HTTP 200 — interactive only |
| [`www.directinfo.ma/assets/documents/Tarifs_liste_1.pdf`](https://www.directinfo.ma/assets/documents/Tarifs_liste_1.pdf) | published 2025 tariff list | PDF | HTTP 200 |
| [`www.edatage.ma/`](https://www.edatage.ma/) | OMPIC e-filing platform (industrial property filings) | HTML SPA | HTTP 200 — filing portal, not a data API |
| [`www.marquesaumaroc.ma`](http://www.marquesaumaroc.ma/fr/actualites/lancement-de-la-nouvelle-plateforme-wwwdirectinfoma) | OMPIC TM-focused sister portal | Drupal HTML | HTTP 200 — content-only |

Net: every IP-data surface is **HTML/PDF only**. No `/api/`, no Swagger,
no OpenAPI document, no JSON examples in any official OMPIC publication.
The patent publication server is an EPO-deployed instance — same family
as the **EPO publication server software** used by Tunisia (INNORPI) and
others — and EPO ships INPADOC/OPS as the documented machine layer for
these offices rather than a local API.

## 2. Auth

- **`ompic.ma`, `search.ompic.ma`, `patent.ompic.ma`, `patentregister.ompic.ma`**:
  fully **anonymous HTML** — no login, no token, no rate-limit headers
  observed.
- **`directinfo.ma`**: paid subscriber account (individual or
  organization). The published [contrat d'abonnement](https://www.directinfo.ma/assets/documents/contrat_abonnement.pdf)
  is a Moroccan-law personal/organizational subscription — the [2025
  tariff list](https://www.directinfo.ma/assets/documents/Tarifs_liste_1.pdf)
  prices document downloads per unit (RCC extracts, financial
  statements). **No machine-credential / OAuth / API-key flow is
  documented or advertised** anywhere on the directinfo.ma site or
  in the November 2017 [guide d'utilisation](https://www.directinfo.ma/assets/documents/guide.pdf).
- **`edatage.ma`** (e-filing): per-user account for filers; not a data
  API — no read endpoints.

## 3. ToU / contract posture

- OMPIC's institutional [Mentions légales](http://www.ompic.ma/fr/content/mentions-legales)
  asserts copyright over all site content (text, images, logos,
  downloadable documents) and invokes [Loi 09-08](http://www.ompic.ma/fr/content/mentions-legales)
  on personal-data protection.
- The [directinfo Mentions légales](https://www.directinfo.ma/assets/documents/Mentions-legales-directinfo.pdf)
  and [subscription contract](https://www.directinfo.ma/assets/documents/contrat_abonnement.pdf)
  are subject to **Moroccan law**, are personal/organizational
  subscriber contracts, and contain **no published API / redistribution
  clause** — because no API is offered. Mass scraping of the JSP search
  portals would clearly violate the institutional copyright assertion.
- No published "open data" / Creative Commons-style license for any
  IP register surface. OMPIC has **not** published any dataset on
  [data.gov.ma](https://www.data.gov.ma/) for industrial property
  (search returned only the institutional MCINET descriptor, no dataset).

## 4. What's transitively covered elsewhere

- **EPO Validation State (in force 2015-03-01)** — Morocco is the
  **first and only African country** with an EPO validation
  agreement ([Cabinet Chaillot — EPO validation scheme
  summary](https://www.chaillot.com/ip-news/updates-in-epo-validation-scheme)
  lists MA alongside MD/TN/KH/GE/LA). Any EP application filed
  on/after 2015-03-01 can be validated in MA — so **EP-validated
  Moroccan patents have full INPADOC/OPS coverage via EPO OPS**, which
  this library already proxies. Native MA filings (non-EP) still depend
  on OMPIC's national surfaces.
- **Madrid Protocol member** — international TMs designating MA are
  available via **WIPO Madrid Monitor**.
- **Hague Agreement** — MA acceded to the **1999 Geneva Act** on
  **2022-04-22** ([WIPO Hague news](https://www.wipo.int/en/web/hague-system/w/news/2022/news_0020)).
  International designs designating MA are visible via **WIPO Hague
  Express / Global Design Database**.
- **PCT contracting state since 1999-10-08** ([WIPO PCT accession press
  release](https://www.wipo.int/pressroom/en/prdocs/1999/wipo_upd_1999_66.html))
  — international phase visible via **WIPO PATENTSCOPE**.
- **Not** an ARIPO or OAPI member — MA is fully national for IP
  governance and is geographically outside both regional unions.

National-only gaps that EPO/WIPO bridges **do not** close:
1. National MA-route patent filings (non-EP, non-PCT-national-phase).
2. National TM file histories, status events, opposition records.
3. Industrial design registry (national filings predating Hague 1999
   accession + national-only filings).
4. Geographical indications register.
5. Central Commercial Register (RCC) — companies data behind the
   `directinfo.ma` paywall.

## 5. Verdict (zero-infra proxy): 🔴 red_no_api

OMPIC publishes search portals (`search.ompic.ma`,
`patent.ompic.ma`, `patentregister.ompic.ma`) and a paid commercial
portal (`directinfo.ma`) — **all HTML/PDF-only with no documented
JSON/REST/SOAP layer, no API key program, no developer portal, no
WIPO API Catalog listing as of 2026-05-18**. Despite Morocco's
above-average digital posture in MENA (e-filing on `edatage.ma`, an
EPO-built publication server, a renamed/relaunched commercial portal),
the office has not exposed machine endpoints to third parties. The
load-bearing bridge is **EPO OPS / INPADOC**, which carries MA
**validated** EP patents at high fidelity (MA being the only African
EPO Validation State) — combined with **WIPO Madrid Monitor**,
**Hague Express**, and **PATENTSCOPE**, this covers most Moroccan IP
of commercial interest. National-only MA gaps remain unrecoverable
without scraping in violation of OMPIC's copyright assertion.
Recommendation: **decline native MA connector; rely on EPO OPS +
WIPO bridges; revisit if OMPIC publishes API documentation on
`directinfo.ma` or surfaces in the WIPO API Catalog.**

## 6. References

- OMPIC institutional site (FR) — http://www.ompic.ma/fr (verified 2026-05-18)
- OMPIC Mentions légales — http://www.ompic.ma/fr/content/mentions-legales (verified 2026-05-18)
- OMPIC Recherche de Marque (search portal) — http://www.ompic.ma/fr/content/recherche-de-marque (verified 2026-05-18)
- OMPIC Recherche de Brevet d'Invention — http://www.ompic.ma/fr/content/recherche-de-brevet-dinvention (verified 2026-05-18)
- Live TM JSP search — http://search.ompic.ma/web/pages/marques/recherche_marque.jsp (verified 2026-05-18)
- Patent publication server — https://patent.ompic.ma/publication-server/ (verified 2026-05-18)
- Patent publication server help — https://patent.ompic.ma/publication-server/help_en.html (verified 2026-05-18)
- National Patent Register info service — https://patentregister.ompic.ma/SearchPatent/searchByDepot?typeNum=EP&numDepot=15736535.4 (verified 2026-05-18)
- directinfo.ma portal — https://www.directinfo.ma/ (verified 2026-05-18)
- directinfo Mentions légales (PDF) — https://www.directinfo.ma/assets/documents/Mentions-legales-directinfo.pdf (verified 2026-05-18)
- directinfo contrat d'abonnement (PDF) — https://www.directinfo.ma/assets/documents/contrat_abonnement.pdf (verified 2026-05-18)
- directinfo Tarifs 2025 (PDF) — https://www.directinfo.ma/assets/documents/Tarifs_liste_1.pdf (verified 2026-05-18)
- directinfo Guide d'utilisation Nov 2017 (PDF) — https://www.directinfo.ma/assets/documents/guide.pdf (verified 2026-05-18)
- OMPIC e-filing portal — https://www.edatage.ma/ (verified 2026-05-18)
- WIPO IP API Catalog — https://apicatalog.wipo.int/en (probed 2026-05-18; 0 OMPIC entries)
- WIPO PCT accession (Morocco) — https://www.wipo.int/pressroom/en/prdocs/1999/wipo_upd_1999_66.html (verified 2026-05-18)
- WIPO Hague Geneva Act accession (Morocco, 2022-04-22) — https://www.wipo.int/en/web/hague-system/w/news/2022/news_0020 (verified 2026-05-18)
- WIPO Madrid System Members — https://www.wipo.int/en/web/madrid-system/members/index (verified 2026-05-18)
- WIPO Morocco Country Profile — https://www.wipo.int/en/web/country-profiles/MA (verified 2026-05-18)
- EPO Validation scheme summary (lists MA at 2015-03-01) — https://www.chaillot.com/ip-news/updates-in-epo-validation-scheme (verified 2026-05-18; cited because EPO's own validation-states landing page is reorganized — Chaillot is a French/European-attorney firm's restatement of the EPO list)
- data.gov.ma (no OMPIC IP datasets) — https://www.data.gov.ma/ (probed 2026-05-18)
