# OPA Austria (AT) — national

**Layer:** national
**Jurisdiction:** AT (WIPO ST.3: AT)
**Issuing body:** Österreichisches Patentamt (Austrian Patent Office, ÖPA / OPA)
**Rights administered:** patent, utility_model (Gebrauchsmuster), trademark, design (Muster); plus supplementary protection certificates (SPCs) and semiconductor topographies
**Working languages:** German (primary); English (bilingual see.ip UI, partial English on institutional pages — all gazettes and bulk publications are German-only)
**Connector status:** **skipped** (no programmatic surface; AT patents already covered transitively via EPO OPS / INPADOC)
**Last verified:** 2026-05-18
**Manifest entry:** not listed in [`coverage/sources.yaml`](../../coverage/sources.yaml) — AT is covered transitively via `WO/EPO`

**Detail surveys:**
- [`waves/2026-05-18-secondary-nationals-wave/at-opa.md`](../waves/2026-05-18-secondary-nationals-wave/at-opa.md) — 2026-05-18 grounded API discovery

**Higher layers covering this office transitively:**
- **EPO OPS / INPADOC** (via [`regional/epo.md`](../regional/epo.md)) — AT patent biblio + family + legal events. Austria is an EPC contracting state and a UPC member, and the EPO's Principal Directorate Patent Information is **located in Vienna** ([INPADOC was founded under a 1972 agreement between WIPO and the Austrian government](https://en.wikipedia.org/wiki/INPADOC)). This is the strongest INPADOC ingestion path of any EPC member.
- **EUIPO** (via planned `regional/euipo.md`) — EUTMs designating AT and Community designs (RCDs / REUDs). Pure AT-national-only TMs and designs are **NOT** covered.
- **WIPO Madrid Monitor / Hague Express** — Madrid IRs designating AT / Hague IRs designating AT; national-only filings remain ÖPA-exclusive.
- **UPC** (via shipped `upc_decisions` connector) — Austria is a UPC contracting state (the [UP system started 2023-06-01](https://inspire.wipo.int/system/files/juri/at.pdf)); UPC-routed disputes affecting AT are reachable via that connector.

---

## §1 Mission

ÖPA is the Austrian national IP office — the only authoritative
registrar for AT national patents, AT utility models (`Gebrauchsmuster`),
AT national trademarks, AT national designs (`Muster`), and Austrian
supplementary protection certificates. It also operates the historical
*Privilegiensammlung* archive of pre-1899 Austro-Hungarian patent
privileges (~95k digitized documents at
[`privilegien.patentamt.at`](https://privilegien.patentamt.at/)).

Because Austria is an EPC contracting state, an EU member, and a UPC
member, most "Austrian patents" in commercial circulation are EP-routed
(covered by EPO OPS) and most "Austrian trademarks" of any scale are
EUTMs (covered by EUIPO). The INPADOC ingestion path for AT is
particularly tight because the EPO's Patent Information directorate
sits in **Vienna** and INPADOC itself was launched under a 1972
WIPO–Austrian-government agreement. ÖPA's genuine value-add for agents
is the AT-national-only slice — utility models, national-only TMs and
designs, and live AT file history — none of which has a public API.

## §2 What's unique here
- **AT utility models (`Gebrauchsmuster`)** — distinct national right (~10-year term, no novelty/inventive-step examination, product-only), per [ÖPA utility-models page](https://www.patentamt.at/en/patents/apply-for-patents/utility-models). Not in EP filings.
- **AT national-only trademarks** — filed directly with ÖPA, not via Madrid and not as EUTMs.
- **AT national-only designs (`Muster`)** — filed directly with ÖPA, not via Hague and not as RCDs.
- **AT patent file history (`Akteneinsicht`)** — live file inspection through see.ip; not in EPO OPS.
- **AT-specific procedural events** — oppositions, nullity, SPC live status at ÖPA-register fidelity.
- **Pre-1899 *Privilegiensammlung* archive** — Austro-Hungarian patent privileges 1852–1899; niche but real for deep prior-art.

## §3 Programmatic surfaces

Every ÖPA-operated surface is 🔴 Red against the zero-infra-proxy
constraint. There is **no documented public REST/JSON/XML API** for
patents, utility models, trademarks, or designs, and **no ÖPA entry**
in the [WIPO IP API Catalog](https://apicatalog.wipo.int/) (probed
2026-05-18 via [`/api/apis`](https://apicatalog.wipo.int/api/apis):
179 office APIs across DPMA, EPO, EUIPO, IP Australia, JPO, MOIP KOREA,
UPRP, USPTO, WIPO, Kazakhstan — zero from ÖPA).

| Surface | Right(s) | Endpoint | Auth | Format | Rating |
|---|---|---|---|---|---|
| **see.ip** (register search) | patent / UM / TM / design | [seeip.patentamt.at](https://seeip.patentamt.at/) (routes `/patentsuche`, `/markesuche`, `/mustersuche`, `/NPatentSuche`) | none | Next.js SPA, Server Actions (opaque RSC payloads) | 🔴 |
| **patentamt.at downloads** (gazettes) | patent / UM / TM / design | [`/en/downloads/publications/`](https://www.patentamt.at/en/downloads/publications/) | none | PDF only (monthly *Patentblatt* I/II, *Gebrauchsmusterblatt*, *Markenanzeiger*, *Musteranzeiger*) | 🔴 |
| **data.gv.at — ÖPA datasets** | administrative only | [search `q=patentamt`](https://www.data.gv.at/api/hub/search/search?q=patentamt) | none, CC-BY 4.0 | 9 hits, all PDFs (ordinance, procurement, org chart, publications index) — **no register data** | 🔴 |
| **Online services** (filing portal) | applicant-side filing | [`/en/online-services/`](https://www.patentamt.at/en/online-services/) | personal | Web forms | 🔴 (not a search surface) |
| **privilegien.patentamt.at** | historical archive (1852–1899) | [`privilegien.patentamt.at`](https://privilegien.patentamt.at/) (CNAME → `oepma.intranda.com`) | none | intranda Goobi viewer; HTML; IIIF available at page level but not advertised | 🔴 (historical only) |

Material details for the most consequential of these:

- **see.ip 2026 relaunch** ([news 2026-03-05](https://www.patentamt.at/en/all-news/news-detail/artikel/search-smarter-with-the-new-seeip)) was a UI modernization (Next.js SPA replacing the prior ASP.NET app). It did **not** ship with an API, **not** announce a developer programme, and **dropped** the legacy `/Help/DownloadHelp?searchType=…` download helpers (404 on probe). SPA data calls are Next.js Server Actions — same-origin, RSC-encoded, unversioned, rebuilt on every deploy.
- **patentamt.at downloads** ship monthly as PDFs with the explicit notice on the publications page: *"NOTICE! Downloads are only available in German."* Annual *Jahresübersicht* PDFs back to ~2015.
- **data.gv.at footprint** is administrative only: e.g. *Patentamtsverordnung 2019 - PAV*, *Vertrag Serverankauf 2025-10-10*, *Geschäftsverteilung und Personaleinteilung*, *Publikationen des Österreichischen Patentamts* index. The bulk-register substrate that DPMA and other EU offices publish on national OGD portals **does not exist** for ÖPA.
- **Terms of use.** [patentamt.at/impressum](https://www.patentamt.at/impressum) is explicit: *"Die Inhalte der Website sind für den persönlichen Gebrauch bestimmt. Wir weisen ausdrücklich darauf hin, dass jede weiter gehende Verwendung oder Vervielfältigung der Inhalte dieser Website, insbesondere die kommerzielle Nutzung und Weitergabe an Dritte, einer schriftlichen Zustimmung des Österreichischen Patentamtes bedarf."* — content is personal-use only; commercial use and third-party disclosure require **written consent**. see.ip inherits this via its footer.

## §4 Fees

ÖPA publishes fee schedules (in EUR) covering patents (filing, search,
publication, grant, annuities), utility models (filing, search,
registration, renewals), trademarks (filing per class, renewal), designs
(filing, renewal), supplementary protection certificates, semiconductor
topographies, and miscellaneous services (file inspection, certified
copies, priority documents). Statutory basis is the **Patentamtsgebühren-
gesetz (PAG)** and the **Patentamtsverordnung 2019 (PAV)**, with
specific rates set by ministerial regulation and adjusted by ÖPA
publication.

- **Official fee schedule:** [Downloads → Fees (EN)](https://www.patentamt.at/en/downloads/fees) — *Gebühren- und Entgeltblätter — Anmelde-, Recherchen- und Verfahrensgebühren und Serviceentgelte (Stand 1.4.2026)* (German PDF; downloads are German-only).
- **Annual / renewal fees:** [Manage Patents → Annual Fees](https://www.patentamt.at/en/patents/manage-patents/annual-fees) ([Information on Annual and Renewal Fees PDF](https://www.patentamt.at/fileadmin/root_oepa/Dateien/AnnualFeesInfo.pdf)).
- **Procedural basis:** [*Patentamtsverordnung 2019 - PAV* on data.gv.at](https://www.data.gv.at/datasets/patentamtsverordnung-2019-pav~~1?locale=de) (CC-BY 4.0).

Notable discount programs *(name only — no amounts or dates per policy)*:

- **Patent.Scheck** — patent-search voucher subsidising prior-art searches for SMEs; see [Patent.Scheck service page](https://www.patentamt.at/patente-1/1/beratung-recherche/patent-scheck).
- **PRIO-Anmeldung** — provisional patent application providing a 1-year priority slot at a reduced fee, per the [WIPO INSPIRE Austria PDF](https://inspire.wipo.int/system/files/juri/at.pdf).

## §5 Connector strategy

### What we cover today

- **AT patent biblio + family + legal events** — transitively via
  [`patent_client_agents.epo_ops`](../regional/epo.md) (country code `AT`).
  Particularly strong ingestion because EPO Patent Information sits in
  Vienna and INPADOC was founded under a 1972 WIPO–Austria agreement.
- **EUTMs designating AT and Community designs (RCD/REUD)** —
  transitively via the planned EUIPO connector.
- **Madrid IRs / Hague IRs designating AT** — via planned WIPO Madrid / Hague connectors.
- **UPC-routed disputes touching AT** — via shipped `upc_decisions` connector.

### What we should add

**Nothing in the form of a direct ÖPA connector.** The rating is
🔴 **Red — `red_no_api`** — there is no programmatic surface to
proxy, BYOK, or contract against. Connector status: **skipped**.

If we want richer AT coverage beyond what EPO OPS / EUIPO / WIPO
already provide, the only realistic avenues are to monitor ÖPA for a
developer-programme announcement and to stand up a separate AT
substantive-law / case-law layer via `ris.bka.gv.at` (out of scope for
this synopsis).

### What we should NOT add

- **see.ip HTML scrape or Server-Action reverse-engineering.** Opaque,
  unversioned RSC endpoints that rebuild on every deploy; plus a ToS
  conflict from the Impressum's personal-use clause. Strategic memory:
  do not re-evaluate.
- **patentamt.at gazette PDF mirror.** PDFs only, German only,
  unstructured; doesn't extend agent-usable data beyond EPO OPS.
- **data.gv.at "ÖPA" datasets.** Administrative PDFs (procurement
  contracts, org chart, publications index), not register data.
- **privilegien.patentamt.at scrape.** Pre-1900 historical archive
  only; not live-register coverage. Possible future research
  artefact via IIIF, not a connector.

### Next steps

1. Watch [`patentamt.at/en/all-news/`](https://www.patentamt.at/en/all-news/) for a developer-programme announcement.
2. Watch the [WIPO IP API Catalog](https://apicatalog.wipo.int/) for ÖPA entries — the canonical signal an office has shipped a public API.
3. Re-evaluate when ÖPA appears on either signal. Until then, route AT patent queries to EPO OPS and document the AT-national-only TM / design / utility-model gap as a known limitation.

## §6 Open questions

- **Bilateral "Datenabgabe" path.** Did the 2026 see.ip relaunch include a private licensable interface ÖPA is willing to offer bilaterally? Institutional pages are silent; worth a direct enquiry to `info@patentamt.at` before final closure.
- **EUIPN CTI deployment.** Does ÖPA participate in the EUIPN [Common Tools Integration](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI) — and if so, does that translate into developer-facing TMview / DesignView ingest beyond the consumer UI? AT data flowing to TMview / DesignView is confirmed by EUIPO news, but that is the EUIPO surface.
- **AT utility-model coverage in INPADOC.** Empirical probe needed to confirm what fraction of `AT U` (utility models) live in INPADOC vs. ÖPA-only — the single most material gap if AT utility models become research-relevant.
- **AT IP case law programmatic access.** Is `ris.bka.gv.at` the authoritative path for Handelsgericht Wien IP rulings? Confirm before any AT case-law connector spec.

## §7 References

Primary sources only — `patentamt.at`, `seeip.patentamt.at`,
`privilegien.patentamt.at`, `data.gv.at`, `ris.bka.gv.at`,
`apicatalog.wipo.int`, `inspire.wipo.int`.

**Service overviews:**
- [Austrian Patent Office (EN home)](https://www.patentamt.at/en/)
- [see.ip — register search portal](https://seeip.patentamt.at/)
- [News: Search smarter with the new see.ip (2026-03-05)](https://www.patentamt.at/en/all-news/news-detail/artikel/search-smarter-with-the-new-seeip)
- [Online services / filing portal (EN)](https://www.patentamt.at/en/online-services/)
- [Trademarks → Services & Searches → Search](https://www.patentamt.at/en/trademarks/services-searches/search)
- [Patents → Apply for Patents → Search](https://www.patentamt.at/en/patents/apply-for-patents/search)

**Substantive rights:**
- [Utility Models (Gebrauchsmuster) overview (EN)](https://www.patentamt.at/en/patents/apply-for-patents/utility-models)
- [Austrian Patent Act 1970 — English translation (PDF)](https://www.patentamt.at/fileadmin/root_oepa/Dateien/Patente/PA_Gesetze/PatG_englisch.pdf)
- [WIPO INSPIRE Austria jurisdiction PDF](https://inspire.wipo.int/system/files/juri/at.pdf)

**Downloads (gazettes, fees, statistics):**
- [Downloads → Publications (EN)](https://www.patentamt.at/en/downloads/publications/)
- [Downloads → Fees (EN)](https://www.patentamt.at/en/downloads/fees)
- [Downloads → Statistics (EN)](https://www.patentamt.at/en/downloads/statistics/)
- [Annual and Renewal Fees Info PDF](https://www.patentamt.at/fileadmin/root_oepa/Dateien/AnnualFeesInfo.pdf)
- [General Fees Info PDF](https://www.patentamt.at/fileadmin/root_oepa/Dateien/Allgemein/Infoblatt_Gebuehren.pdf)

**Legal terms:**
- [Impressum (DE) — copyright + personal-use clause](https://www.patentamt.at/impressum)
- [Imprint (EN)](https://www.patentamt.at/en/imprint)
- [Data Security (EN)](https://www.patentamt.at/en/data-security)
- [Datenschutz (DE)](https://www.patentamt.at/datenschutz)

**Open data + procedural ordinance:**
- [data.gv.at search query for "patentamt"](https://www.data.gv.at/api/hub/search/search?q=patentamt)
- [Patentamtsverordnung 2019 - PAV (data.gv.at dataset)](https://www.data.gv.at/datasets/patentamtsverordnung-2019-pav~~1?locale=de)
- [Publikationen des Österreichischen Patentamts (data.gv.at dataset)](https://www.data.gv.at/datasets/publikationen-des-oesterreichischen-patentamts?locale=de)

**Historical archive:**
- [125 years Austrian Patent Office](https://www.patentamt.at/en/125years)
- [Privilegiensammlung — historical patent privileges 1852-1899](https://privilegien.patentamt.at/)

**Cross-office context:**
- [WIPO IP API Catalog (canonical inventory)](https://apicatalog.wipo.int/) — probed 2026-05-18; 0 ÖPA entries
- [EUIPN Common Tools Integration (CTI)](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI) — TMview / DesignView back-office bridge
- [INPADOC (Wikipedia)](https://en.wikipedia.org/wiki/INPADOC) — historical founding under 1972 WIPO–Austria agreement

**Detail surveys + waves:**
- [`waves/2026-05-18-secondary-nationals-wave/at-opa.md`](../waves/2026-05-18-secondary-nationals-wave/at-opa.md) — 2026-05-18 grounded API discovery

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-18 | Initial synopsis; rating **`red_no_api`**. Findings: (a) the 2026 see.ip relaunch (announced [2026-03-05](https://www.patentamt.at/en/all-news/news-detail/artikel/search-smarter-with-the-new-seeip)) is a Next.js UI modernization with no developer API and dropped the legacy ASP.NET `Help/DownloadHelp` helpers; (b) ÖPA has **zero entries** in the [WIPO IP API Catalog](https://apicatalog.wipo.int/) as of probe date (179 office APIs across 10 organisations, all non-AT); (c) ÖPA's [data.gv.at](https://www.data.gv.at/api/hub/search/search?q=patentamt) footprint is 6 administrative PDFs + 1 ordinance — no register data; (d) [patentamt.at Impressum](https://www.patentamt.at/impressum) restricts content to personal use and gates commercial / third-party redistribution on written consent. Strategic memory: AT is reachable transitively via EPO OPS (Austria sits unusually close to INPADOC — EPO Patent Information directorate is in Vienna), EUIPO (EUTMs / RCDs), and WIPO Madrid / Hague (IR designations). Genuine national-only gaps — AT `Gebrauchsmuster`, AT-national-only TMs / designs, AT file history — have no programmatic path. | [waves/2026-05-18-secondary-nationals-wave/at-opa.md](../waves/2026-05-18-secondary-nationals-wave/at-opa.md) |
