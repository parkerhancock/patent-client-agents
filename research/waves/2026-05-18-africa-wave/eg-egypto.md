# EG — EGYPO + ITDA (now EAIP): Patents/UMs/TMs/Designs API Discovery

**Date:** 2026-05-18

**Scope:** Discovery synopsis for the Egyptian IP system —
historically split between **EGYPO** (Egyptian Patent Office, hosted
under the Academy of Scientific Research and Technology) for patents +
utility models, and the **Trademark and Industrial Designs Office**
(under the Internal Trade Development Authority, **ITDA**) for marks
+ designs. **Law No. 163 of 2023**
([WIPO Lex 22398](https://www.wipo.int/wipolex/en/legislation/details/22398))
consolidates both into a single **Egyptian Authority for Intellectual
Property (EAIP)** reporting to the Prime Minister, with a one-year
transition from 2024-08-05 (extendable by six months). Substantive law
remains [Law No. 82 of 2002](https://www.wipo.int/wipolex/en/legislation/details/1301)
(integrated patents, UMs, TMs, designs, copyrights, plant varieties).

**TL;DR:** **🔴 red_no_api across both offices.** EGYPO publishes its
register through a hosted **WIPO PUBLISH** instance at
[`egypo.gov.eg/wopublish-search/public/patents`](http://www.egypo.gov.eg/wopublish-search/public/patents)
— a server-rendered HTML form with no documented JSON/REST envelope
and no API-key program ([EGYPO portal](http://www.egypo.gov.eg/default.aspx?lang=en)).
ITDA's trademark surface is the [**monthly TM gazette PDF**](http://www.itda.gov.eg/jurnal-TM.aspx)
plus a basic accepted-mark web search; there is **no public trademark
register API** and **no public national design search of any shape**
([WIPO Egypt directory](https://www.wipo.int/directory/en/contact.jsp?country_id=53&type=ADMIN_IP)).
Neither office appears in the [WIPO IP API Catalog](https://apicatalog.wipo.int/)
(probed 2026-05-18). Useful transitive coverage exists: EG biblio is
carried in **EPO INPADOC** (Espacenet / OPS), Egypt is a **PCT
contracting state since 2003-09-06** (national-phase via EGYPO;
international stage reachable in PATENTSCOPE), and Egypt is a **Madrid
Protocol member since 2009-09-03**
([WIPO Notification 184](https://www.wipo.int/treaties/en/notifications/madridp-gp/treaty_madridp_gp_184.html))
so Madrid designations to EG reach the WIPO Global Brand Database.
Egypt is **not** a Hague designs member — national designs are
effectively unreachable as machine-readable data.

---

## §1 Endpoints

### EGYPO (patents + utility models, ASRT → EAIP)

| Host | Right(s) | Shape | Probe result |
|---|---|---|---|
| [`egypo.gov.eg/Search/Default.aspx`](http://www.egypo.gov.eg/Search/Default.aspx?lang=en) | Patents (granted), UMs | ASP.NET HTML form (`?lang=en` / `?lang=ar`). Filter by application no. + year from 1950 onward. | HTML hit list only; no JSON envelope; no permalink-friendly URLs. |
| [`egypo.gov.eg/wopublish-search/public/patents`](http://www.egypo.gov.eg/wopublish-search/public/patents) | Patents (publications + grants) | Hosted **[WIPO PUBLISH](https://www.wipo.int/en/web/ip-office-business-solutions)** instance (WIPO-developed back-office product) | HTML search form: patent no., application no., publication date, filing date, IPC field. **No JSON envelope, no documented REST API, no API-key program.** |
| [`egypo.gov.eg/page.aspx?id=22`](http://www.egypo.gov.eg/page.aspx?id=22&lang=en) | Utility models (info page) | Static HTML | Office info only; no register surface for UMs separate from patents. |
| EGYPO Patent Office Journal / Gazette | Patents + UMs | PDF / print | Distribution referenced from the [EGYPO Search page](http://www.egypo.gov.eg/Search/Default.aspx?lang=en); no public bulk-download index discovered. |
| Contact: `patinfo@egypo.gov.eg` | — | — | Per [WIPO IP Office directory entry for EG](https://www.wipo.int/directory/en/contact.jsp?country_id=53&type=ADMIN_IP). |

### ITDA / TM and Industrial Designs Office (TMs + Designs, ITDA → EAIP)

| Host | Right(s) | Shape | Probe result |
|---|---|---|---|
| [`itda.gov.eg`](https://www.itda.gov.eg/) | Office portal | HTML | Authority landing page (Arabic-primary; partial English). |
| [`itda.gov.eg/jurnal-TM.aspx`](http://www.itda.gov.eg/jurnal-TM.aspx) | Trademarks | Monthly **PDF gazette** (published 7th–9th of each month, online since 2013-03) | PDF only — accepted-mark particulars, cancellations, renewals. **No bulk feed, no XML companion, no JSON.** |
| ITDA TM web search UI | Trademarks (accepted / published only) | HTML form | Per the office, "displays published trademarks only" — partial coverage of pending and refused marks. No JSON, no REST. |
| National industrial designs register | Designs | — | **No public national designs search surface located.** WIPO Global Design Database lists no national EG collection — only EG-designations of [Hague filings](https://www.wipo.int/en/web/hague-system/how_hague_works) — and Egypt is not a Hague member, so coverage is essentially nil. |

### WIPO bridges (transitive coverage of EG rights)

| Host | EG coverage | Shape |
|---|---|---|
| [WIPO PATENTSCOPE](https://patentscope.wipo.int/) | EG-designated PCTs (international phase) | Free public REST + UI. |
| [EPO OPS / Espacenet](https://ops.epo.org/) | EG biblio via **INPADOC** (EG is among ~100 patent-issuing organizations EPO compiles from gazettes per [Espacenet coverage doc](https://worldwide.espacenet.com/help?locale=en_EP&method=handleHelpTopic&topic=coverageww)) | Registered REST (BYOK to EPO; free tier 4 GB/month). |
| [WIPO Madrid Monitor](https://www3.wipo.int/madrid/monitor/) / [Global Brand Database](https://branddb.wipo.int/) | Madrid designations to EG + Madrid filings of origin EG; EG national TM collection coverage is limited per [WIPO BrandDB coverage matrix](https://branddb.wipo.int/en/coverage) | Public search UI + documented data exports. |
| [WIPO IP API Catalog](https://apicatalog.wipo.int/) | **Neither EGYPO nor ITDA listed** as a participating institution (probed 2026-05-18). | — |

## §2 Auth

**EGYPO** — anonymous HTML browse only. No registered-developer
program; no API-key, OAuth, or basic-auth surface; no documented
bulk-data subscription channel. The hosted WIPO PUBLISH UI is the
public face; the underlying [WIPO PUBLISH](https://www.wipo.int/en/web/ip-office-business-solutions)
product does support office-internal REST endpoints, but EGYPO has
**not** published any developer-facing key program against them.

**ITDA** — anonymous HTML browse + monthly PDF gazette download. No
auth, no developer program, no programmatic register access of any
shape.

**WIPO transitive surfaces** — PATENTSCOPE anonymous; EPO OPS BYOK to
EPO; BrandDB anonymous. All three are already covered (or planned) by
existing connectors in the repo.

## §3 ToU / contract posture

Neither [`egypo.gov.eg`](http://www.egypo.gov.eg/default.aspx?lang=en)
nor [`itda.gov.eg`](https://www.itda.gov.eg/) publishes a discoverable
terms-of-use page, a structured `robots.txt` policy, or a
developer-API license. The substantive IP statute
[Law No. 82 of 2002 (WIPO Lex 1301)](https://www.wipo.int/wipolex/en/legislation/details/1301)
and the reorganization act
[Law No. 163 of 2023 (WIPO Lex 22398)](https://www.wipo.int/wipolex/en/legislation/details/22398)
treat register publications as official acts of the Egyptian State but
do not address machine ingestion, scraping, or third-party
redistribution. There is **no contract surface to license, no API ToS
to accept, and no published authority to deny** — proxying is neither
permitted nor prohibited in writing. By default in the IP-office
vertical we treat unaddressed as not buildable, because nothing about
the HTML form supports it anyway. The standing fees-policy (link, do
not mirror) applies to any cost schedule EGYPO or ITDA may publish.

## §4 What's transitively covered elsewhere

- **PCT (international phase):** Egypt acceded **2003-09-06** ([WIPO
  Egypt country profile](https://www.wipo.int/directory/en/details.jsp?country_code=EG);
  [PCT Applicant's Guide — Egypt](https://pctlegal.wipo.int/eGuide/view-doc.xhtml?doc-code=EG&doc-lang=en)).
  All EG-designated PCTs are reachable through [WIPO
  PATENTSCOPE](https://patentscope.wipo.int/) at full international-phase
  fidelity (front-page biblio, full text, drawings). National-phase
  entry routes through EGYPO and is **not** machine-readable.
- **Madrid Protocol:** Egypt acceded **2009-09-03** ([WIPO Notification
  TREATY/MADRIDP-GP/184](https://www.wipo.int/treaties/en/notifications/madridp-gp/treaty_madridp_gp_184.html)).
  Madrid international registrations designating EG (and EG-as-origin
  filings) are queryable via [WIPO Madrid Monitor](https://www3.wipo.int/madrid/monitor/)
  and the [Global Brand Database](https://branddb.wipo.int/).
- **EPO INPADOC:** EG patent biblio is part of EPO's INPADOC coverage
  ([Espacenet coverage doc](https://worldwide.espacenet.com/help?locale=en_EP&method=handleHelpTopic&topic=coverageww));
  reachable through EPO OPS (BYOK) at biblio + family fidelity. EG
  full-text is **not** in INPADOC.
- **Hague designs:** Egypt is **not** a Hague (1960 Act / 1999 Geneva
  Act) contracting party. The London Act (1934) — to which Egypt was
  historically party — was terminated 2016-10-18. **EG industrial
  designs are national-only**, and with no national online register
  surface, they are effectively unreachable as data.
- **ARIPO:** Egypt is an **observer**, **not** a member of ARIPO (per
  [Managing IP coverage](https://www.managingip.com/article/2a5bqo2drurt0bwqptbla/aripo-dg-speaks-out-on-the-banjul-protocol-and-paipo);
  [WIPO Egypt profile](https://www.wipo.int/directory/en/details.jsp?country_code=EG)).
  EG patents and marks do **not** flow through ARIPO
  Harare / Banjul.
- **EPC:** Egypt is **not** an EPC member; no EP-route coverage.
- **Gazettes:** EGYPO publishes a patent journal (referenced from its
  search page) — no public bulk index found. ITDA's [TM
  gazette](http://www.itda.gov.eg/jurnal-TM.aspx) is monthly PDF.
- **National-only gaps:** industrial designs (no national register
  surface), file histories, opposition records, complete TM register
  (only accepted / published marks appear online), and Arabic-only
  procedural documents.

## §5 Verdict (zero-infra proxy)

**EGYPO (patents + UMs): 🔴 red_no_api.** The only public surfaces are
HTML forms — the legacy
[`Search/Default.aspx`](http://www.egypo.gov.eg/Search/Default.aspx?lang=en)
and the hosted [WIPO PUBLISH
instance](http://www.egypo.gov.eg/wopublish-search/public/patents).
There is no JSON envelope, no documented REST, no registered-developer
program, and no bulk-data subscription. EGYPO does **not** appear in
the [WIPO IP API Catalog](https://apicatalog.wipo.int/). Best
transitive coverage for EG patents is **EPO OPS (INPADOC biblio +
family)** plus **PATENTSCOPE for EG-designated PCTs**, both reachable
through connectors already on the roadmap. No connector to build at
EGYPO itself.

**ITDA / TM + Designs Office: 🔴 red_no_api.** Trademark surface is
the monthly PDF gazette
([`itda.gov.eg/jurnal-TM.aspx`](http://www.itda.gov.eg/jurnal-TM.aspx))
plus a partial accepted-mark HTML search. Designs have **no public
register surface at all** — neither a national online search nor a
machine-readable bulk feed. Cleanest TM bridge is the **WIPO Global
Brand Database** for Madrid designations to/from EG; the national TM
collection is sparsely covered there per the [BrandDB coverage
matrix](https://branddb.wipo.int/en/coverage). Designs are effectively
a black hole — Egypt is not Hague, so the WIPO Global Design Database
holds nothing national for EG. No connector to build at ITDA itself.

**EAIP consolidation watch item.**
[Law 163 of 2023](https://www.wipo.int/wipolex/en/legislation/details/22398)
transferred competence from EGYPO + ITDA to a single Egyptian
Authority for Intellectual Property, with a transition deadline of
2024-08-05 (+6 months extendable to 2025-02-05). As of probe date
2026-05-18, EGYPO and ITDA still serve the live surfaces under their
legacy domains; EAIP has **no canonical web property discoverable** via
the WIPO Egypt directory entry. **Re-probe quarterly** for a new EAIP
portal, an API program, or domain consolidation — the consolidation
mandate explicitly calls out "creating comprehensive databases on IPRs
to enhance the intellectual property system's accessibility," which is
the language we would expect to precede a developer-facing surface.

## §6 References

- EGYPO portal: <http://www.egypo.gov.eg/default.aspx?lang=en> — last verified 2026-05-18
- EGYPO native search: <http://www.egypo.gov.eg/Search/Default.aspx?lang=en> — last verified 2026-05-18
- EGYPO WIPO PUBLISH instance: <http://www.egypo.gov.eg/wopublish-search/public/patents> — last verified 2026-05-18
- EGYPO utility model info page: <http://www.egypo.gov.eg/page.aspx?id=22&lang=en> — last verified 2026-05-18
- ITDA portal: <https://www.itda.gov.eg/> — last verified 2026-05-18
- ITDA monthly TM gazette: <http://www.itda.gov.eg/jurnal-TM.aspx> — last verified 2026-05-18
- WIPO IP Office directory (Egypt): <https://www.wipo.int/directory/en/contact.jsp?country_id=53&type=ADMIN_IP> — last verified 2026-05-18
- WIPO country profile EG: <https://www.wipo.int/directory/en/details.jsp?country_code=EG> — last verified 2026-05-18
- WIPO Lex Law 82/2002 (substantive IP law): <https://www.wipo.int/wipolex/en/legislation/details/1301> — last verified 2026-05-18
- WIPO Lex Law 163/2023 (EAIP establishment): <https://www.wipo.int/wipolex/en/legislation/details/22398> — last verified 2026-05-18
- WIPO Madrid Protocol Notification 184 (Egypt accession 2009-09-03): <https://www.wipo.int/treaties/en/notifications/madridp-gp/treaty_madridp_gp_184.html> — last verified 2026-05-18
- WIPO IP API Catalog (no EG entry): <https://apicatalog.wipo.int/> — last verified 2026-05-18
- WIPO Global Brand Database coverage matrix: <https://branddb.wipo.int/en/coverage> — last verified 2026-05-18
- WIPO IP Office Business Solutions (WIPO PUBLISH product): <https://www.wipo.int/en/web/ip-office-business-solutions> — last verified 2026-05-18
- EPO Espacenet coverage doc (INPADOC scope): <https://worldwide.espacenet.com/help?locale=en_EP&method=handleHelpTopic&topic=coverageww> — last verified 2026-05-18
- PCT Applicant's Guide — Egypt: <https://pctlegal.wipo.int/eGuide/view-doc.xhtml?doc-code=EG&doc-lang=en> — last verified 2026-05-18
