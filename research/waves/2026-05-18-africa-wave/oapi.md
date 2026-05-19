# Organisation Africaine de la Propriété Intellectuelle (OAPI) — Unitary Patents/TMs/Designs/UMs/GIs API Discovery

**Date:** 2026-05-18
**Scope:** Determine whether **OAPI** — the intergovernmental
unitary IP office headquartered in Yaoundé, Cameroon serving 17
francophone African states under the **Bangui Agreement** (Annex I
patents · II utility models · III trademarks · IV designs · V trade
names · VI GIs · VII copyright · VIII unfair competition · IX
layout-designs · X plant varieties) — exposes a public, queryable
REST/JSON/XML API that a third-party developer can register for and
proxy at runtime. Bulk dumps and HTML-only surfaces are a **red**
verdict.

**TL;DR — Verdict: 🔴 red_no_api.** OAPI's only public register surface
is a WIPO-IPAS-derived **"OAPI Online Search System"** (WoPublish)
deployed on a bare-IP host at
[`http://195.24.202.12:9092/wopublish-search/public/{patents,trademarks,designs}`](http://195.24.202.12:9092/wopublish-search/public/patents)
— linked directly from
[`oapi.int/en/service/online-services/`](https://oapi.int/en/service/online-services/),
HTTP-only (no TLS), JSESSIONID-bound HTML/JavaScript SPA, French-default
UI, **no documented JSON/REST API, no robots.txt-compliant bulk export, no
OpenAPI spec, no rate-card**. WIPO INSPIRE itself states the load-bearing
fact verbatim:
**"OAPI does not have an Online Register. It has an Online Gazette."**
([inspire.wipo.int/system/files/oapi.pdf](https://inspire.wipo.int/system/files/oapi.pdf),
p. 1). The "Online Gazette" is the **BOPI (Bulletin Officiel de la
Propriété Industrielle)**, published as **PDF only** at
[`oapi.int/en/media/official-bulletin-of-the-pi/`](https://oapi.int/en/media/official-bulletin-of-the-pi/)
and on the `siege.oapi.int` publication server — no ST.96 XML companion,
no JSON feed, no machine-readable index. OAPI is **not listed** in the
[WIPO IP API Catalog](https://apicatalog.wipo.int/) (0 hits for OAPI/OA,
probed 2026-05-18). The June-2024 e-filing rollout
([sabaip.com](https://www.sabaip.com/oapi-trademark-practices-updates-and-new-e-filing-system/),
[cwbip.com](https://cwbip.com/insights/news/2024/oapi-launches-e-filing-trademarks))
covers **trademark filing only** (search/file/renew/recordal/oppose) —
patents are explicitly excluded from phase 1, and the filing portal is
agent-account-gated, not a public read API. This is the unitary office
for **17 sovereign states**, and there is **no national-office substitute**
for any of them.

---

## 1. Endpoints

| Host | Right(s) | Shape | Probe (2026-05-18) |
|---|---|---|---|
| [`oapi.int`](https://oapi.int/en/) | institutional WordPress site | HTML | HTTP 200 (218 KB); no API surface, no `/api/` paths beyond `wp-json/oembed` |
| [`oapi.int/en/service/online-services/`](https://oapi.int/en/service/online-services/) | service catalog page | HTML | HTTP 200; **outbound-links** to three WoPublish endpoints below |
| [`http://195.24.202.12:9092/wopublish-search/public/patents`](http://195.24.202.12:9092/wopublish-search/public/patents) | OAPI patent register (incl. UMs) | IPAS WoPublish HTML SPA (Apache-Coyote/1.1) | HTTP 302 → 200; JSESSIONID-bound; titled "OAPI Online Search System"; fields per WIPO ST.96 schema (IPC, CPC, PCT, gazette refs) — **no JSON endpoint exposed** |
| [`http://195.24.202.12:9092/wopublish-search/public/trademarks`](http://195.24.202.12:9092/wopublish-search/public/trademarks) | trademark register (MR regional + MD Madrid) | IPAS WoPublish HTML SPA | HTTP 200; result-count visible: **45,544 MR + 18,087 MD** records on landing |
| [`http://195.24.202.12:9092/wopublish-search/public/designs`](http://195.24.202.12:9092/wopublish-search/public/designs) | industrial design register | IPAS WoPublish HTML SPA | HTTP 200; same engine |
| [`oapi.int/en/media/official-bulletin-of-the-pi/`](https://oapi.int/en/media/official-bulletin-of-the-pi/) | **BOPI** Official Bulletin index (6 series: patents, UMs, designs, marks, trade names, GIs, plant varieties) | WordPress archive of PDFs | HTTP 200; bulletins linked monthly back to 2016 — **PDF only**, no XML |
| [`http://siege.oapi.int/publication/{brevet,marque,dmi,ig}/YYYY/bopi-N/`](http://siege.oapi.int/publication/brevet/2023/bopi-4/) | direct BOPI PDF server | static PDFs over HTTP | reachable; no listing API |
| [`oapi.int/en/protect-the-pi/prior-art-search/`](https://oapi.int/en/protect-the-pi/prior-art-search/) | paid prior-art search service | HTML form / paid contract | not a public API — request-form workflow |
| OAPI Lex (case-law DB, launched 2025) | jurisprudence | HTML | announced [2025-06](https://oapi.int/en/2025/06/29/loapi-launches-its-case-of-case-lawyers-a-major-advance-for-pi-rights-in-french-speaking-africa/); not a register/gazette |
| [`apicatalog.wipo.int`](https://apicatalog.wipo.int/) | WIPO IP API Catalog | — | **0 entries** for office code OA / OAPI (probed 2026-05-18) |

The WoPublish frontend is OAPI's only register-search surface. It is
the standard WIPO IPAS public-search component (WoPublish), deployed
on an unencrypted, bare-IP origin with no documented machine endpoint.
The trademark database is the most populated (~63K records). The
patents/designs databases are populated but record counts are not
exposed on landing.

## 2. Auth

- **WoPublish public search** (`195.24.202.12:9092`): no auth — cookie
  session (`JSESSIONID`, `psusr`) issued on first GET. Read-only HTML;
  no token/key flow, no documented JSON.
- **OAPI e-filing portal for trademarks** (launched 2024-06-03 per
  [sabaip.com](https://www.sabaip.com/oapi-trademark-practices-updates-and-new-e-filing-system/),
  [cwbip.com](https://cwbip.com/insights/news/2024/oapi-launches-e-filing-trademarks)):
  accredited-agent account gated; write-only filing/renewal/opposition;
  no read API. Hard-copy supporting docs still required.
- **`oapi.int` institutional site**: no auth.
- **BOPI PDFs on `siege.oapi.int`**: no auth, no listing API, no XML
  companion.

## 3. ToU / contract posture

- **No published terms of use** found at `oapi.int` for the online
  search system. The
  [Online Services page](https://oapi.int/en/service/online-services/)
  lists the databases without an accompanying ToU, license, or
  redistribution clause.
- The WoPublish portal exposes no robots.txt or API ToU; default WIPO
  IPAS deployments are operated under bilateral office-WIPO agreements
  rather than third-party API terms.
- Working language is **French** (UI defaults to FR; English toggle
  present but partial). Any commercial proxy of OAPI data would, in the
  absence of an explicit policy, fall under the Bangui Agreement Art. 39
  *et seq.* publication regime — meaning publication of BOPI content is
  authorized by OAPI itself but redistribution permissions for the
  register-search corpus are silent.
- Practical implication: **no green light** to proxy, **no explicit red
  light** either — but the *absence of any documented API* makes the
  question moot.

## 4. Member states + transitive coverage matrix

OAPI is the **only** IP office for all 17 contracting states
(confirmed by both [oapi.int Bangui Agreement page](https://oapi.int/en/legal-framework/bangui-agreement/)
and [WIPO INSPIRE OAPI profile](https://inspire.wipo.int/system/files/oapi.pdf)).
Bangui Agreement Art. 2 makes the OAPI title unitary across all members:
"OAPI registrations automatically extend to all Member States; it is
neither necessary nor possible to designate individual member states."

| ST.3 code | State | OAPI member | National IP office substitute? |
|---|---|---|---|
| BJ | Benin | yes | **none** — OAPI exclusive |
| BF | Burkina Faso | yes | **none** — OAPI exclusive |
| CM | Cameroon | yes (host state) | **none** — OAPI exclusive |
| CF | Central African Republic | yes | **none** — OAPI exclusive |
| TD | Chad | yes | **none** — OAPI exclusive |
| KM | Comoros | yes | **none** — OAPI exclusive |
| CG | Republic of Congo | yes | **none** — OAPI exclusive |
| CI | Côte d'Ivoire | yes | **none** — OAPI exclusive |
| GQ | Equatorial Guinea | yes | **none** — OAPI exclusive |
| GA | Gabon | yes | **none** — OAPI exclusive |
| GN | Guinea | yes | **none** — OAPI exclusive |
| GW | Guinea-Bissau | yes | **none** — OAPI exclusive |
| ML | Mali | yes | **none** — OAPI exclusive |
| MR | Mauritania | yes | **none** — OAPI exclusive |
| NE | Niger | yes | **none** — OAPI exclusive |
| SN | Senegal | yes | **none** — OAPI exclusive |
| TG | Togo | yes | **none** — OAPI exclusive |

Bangui Agreement revision history: original 1977-03-02 (in force
1982-02-08), revised 1999-02-24 (in force 2002-02-28), further revised
2015-12-14 (**in force 2020-11-14** per
[oapi.int Bangui Agreement page](https://oapi.int/en/legal-framework/bangui-agreement/)).
The 2020 revision modernized GIs, plant varieties (new Annex X), and
copyright (Annex VII).

**Transitive coverage via EPO / WIPO:**

- **EPO INPADOC / OPS**: OAPI is included as office code `OA` in WIPO
  ST.3. INPADOC families pick up OAPI publications when applicants
  designate OAPI via PCT (OAPI is a PCT regional Receiving/designated
  Office per [WIPO PCT applicant guide](https://www.wipo.int/pct/en/texts/pdf/oa.pdf)).
  WIPO INSPIRE: **"A large number of OAPI patents Full Publications are
  available on Espacenet"** ([inspire.wipo.int OAPI profile](https://inspire.wipo.int/system/files/oapi.pdf)).
  EPO OPS therefore provides usable biblio + family coverage for OAPI
  patents — this is the recommended bridge for downstream consumers.
- **WIPO PATENTSCOPE**: ingests OAPI publications via the PCT national/
  regional phase entries; OAPI is selectable as a collection.
- **Madrid Monitor**: OAPI **acceded to the Madrid Protocol** effective
  2015-03-05, so trademark designations of OAPI **are** visible via
  WIPO Madrid Monitor for international registrations — this explains
  the 18,087 "MD Marque internationale" records visible on the WoPublish
  trademarks landing alongside 45,544 "MR Marque régionale" records.

**Strategic implication:** OAPI is structurally **different from ARIPO**
— ARIPO grants are extension-style (members retain national offices and
national registers parallel to ARIPO grants), whereas OAPI grants are
**unitary** under one register. For these 17 states there is no national
substitute, so OAPI's weak digital posture is the **upper bound** on
data accessibility for the entire francophone African IP zone. EPO
INPADOC/OPS and WIPO PATENTSCOPE are the only mature machine-readable
bridges; everything else is PDF + HTML.

## 5. Verdict (zero-infra proxy): 🔴 red_no_api

OAPI does **not** expose any documented public REST/JSON/XML API for
any of its 10 Bangui Annex rights. The register-search surface is a
WIPO IPAS WoPublish HTML SPA on an HTTP-only bare-IP origin; the BOPI
gazette is PDF-only; the 2024 e-filing portal is write-only and
agent-gated; the WIPO IP API Catalog lists nothing for OA. WIPO INSPIRE
itself states the load-bearing fact: "OAPI does not have an Online
Register. It has an Online Gazette." Bridging via EPO OPS and WIPO
PATENTSCOPE captures patents (PCT-routed) and Madrid trademarks but
misses utility models, designs, trade names, GIs, copyright,
layout-designs, and plant varieties — all of which exist only as PDF
BOPI entries. A zero-infrastructure runtime proxy of OAPI is **not
feasible** today. Re-evaluate when (a) the 2024 e-filing platform
publishes a read-side JSON API, (b) WoPublish is replaced by a
documented IPAS REST layer, or (c) OAPI appears in the WIPO API
Catalog.

## 6. References

- OAPI Online Services page —
  [`https://oapi.int/en/service/online-services/`](https://oapi.int/en/service/online-services/)
  (last verified 2026-05-18). Links to the three WoPublish endpoints.
- OAPI Online Search System (WoPublish — patents) —
  [`http://195.24.202.12:9092/wopublish-search/public/patents`](http://195.24.202.12:9092/wopublish-search/public/patents)
  (probed 2026-05-18; HTTP 302→200; JSESSIONID set).
- OAPI Online Search System (WoPublish — trademarks) —
  [`http://195.24.202.12:9092/wopublish-search/public/trademarks`](http://195.24.202.12:9092/wopublish-search/public/trademarks)
  (probed 2026-05-18; 45,544 MR + 18,087 MD records visible).
- OAPI BOPI Official Bulletin index —
  [`https://oapi.int/en/media/official-bulletin-of-the-pi/`](https://oapi.int/en/media/official-bulletin-of-the-pi/)
  (last verified 2026-05-18; PDF only; 6 series).
- OAPI BOPI direct PDF server (example) —
  [`http://siege.oapi.int/publication/brevet/2023/bopi-4/`](http://siege.oapi.int/publication/brevet/2023/bopi-4/).
- OAPI Bangui Agreement page —
  [`https://oapi.int/en/legal-framework/bangui-agreement/`](https://oapi.int/en/legal-framework/bangui-agreement/)
  (1977 original; 1999 revision in force 2002; 2015 revision in force
  2020-11-14).
- OAPI Bangui Agreement (English consolidated text PDF) —
  [`https://www.oapi.int/wp-content/uploads/2023/11/anglais.pdf`](https://www.oapi.int/wp-content/uploads/2023/11/anglais.pdf).
- WIPO INSPIRE OAPI patent register profile —
  [`https://inspire.wipo.int/system/files/oapi.pdf`](https://inspire.wipo.int/system/files/oapi.pdf)
  (load-bearing: "OAPI does not have an Online Register. It has an
  Online Gazette.").
- WIPO Lex — Bangui Agreement treaty record —
  [`https://www.wipo.int/wipolex/en/treaties/details/227`](https://www.wipo.int/wipolex/en/treaties/details/227).
- WIPO PCT applicant guide — OAPI (OA) regional chapter —
  [`https://www.wipo.int/pct/en/texts/pdf/oa.pdf`](https://www.wipo.int/pct/en/texts/pdf/oa.pdf).
- WIPO IP API Catalog —
  [`https://apicatalog.wipo.int/`](https://apicatalog.wipo.int/)
  (probed 2026-05-18; 0 entries for OA/OAPI).
- WIPO Members directory — OAPI contact —
  [`https://www.wipo.int/members/en/contact.jsp?dir_id=1`](https://www.wipo.int/members/en/contact.jsp?dir_id=1).
- OAPI 2024-06 e-filing launch (trademarks only) — secondary
  confirmation: [`sabaip.com`](https://www.sabaip.com/oapi-trademark-practices-updates-and-new-e-filing-system/),
  [`cwbip.com`](https://cwbip.com/insights/news/2024/oapi-launches-e-filing-trademarks).
- OAPI Lex jurisprudence database launch (2025-06) —
  [`https://oapi.int/en/2025/06/29/loapi-launches-its-case-of-case-lawyers-a-major-advance-for-pi-rights-in-french-speaking-africa/`](https://oapi.int/en/2025/06/29/loapi-launches-its-case-of-case-lawyers-a-major-advance-for-pi-rights-in-french-speaking-africa/).
