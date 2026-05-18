# Octrooicentrum Nederland (NL/RVO) — national

**Layer:** national
**Jurisdiction:** NL (WIPO ST.3: NL)
**Issuing body:** Octrooicentrum Nederland (Netherlands Patent Office), a department of the Rijksdienst voor Ondernemend Nederland (RVO), itself an agency of the Dutch Ministry of Economic Affairs and Climate Policy
**Rights administered:** patent, supplementary protection certificate (SPC, incl. paediatric extension), semiconductor topography. **NOT** trademark / design — those are Benelux-administered by BOIP (see §2).
**Working languages:** Dutch (primary), English (eRegister dual-language; German and French listed in the help index but not implemented on the about page)
**Connector status:** **skipped** (no programmatic surface; NL patents already covered transitively via EPO OPS / EP Register via the daily NL→FRS feed)
**Last verified:** 2026-05-18
**Manifest entry:** not listed in [`coverage/sources.yaml`](../../coverage/sources.yaml) — NL is covered transitively via `WO/EPO`

**Detail surveys:**
- [`waves/2026-05-18-secondary-nationals-wave/nl-rvo.md`](../waves/2026-05-18-secondary-nationals-wave/nl-rvo.md) — 2026-05-18 grounded API discovery

**Higher layers covering this office transitively:**
- **EPO OPS / INPADOC / EP Register** (via [`regional/epo.md`](../regional/epo.md)) — NL patent biblio + family + legal events for EP-NL validations, and the **NL Patent Office feeds a daily delta of selected NL bibliographic data to the EPO's Federated Register Service** ([eRegister About page](https://mijnoctrooi.rvo.nl/fo-eregister-view/about/home.action)). This is the canonical indirection: NL data reaches programmatic consumers through the EPO, not RVO.
- **EUIPO TMview / DesignView** (via planned `regional/euipo.md`) — Benelux trademarks and designs administered by BOIP flow into TMview/DesignView via the [EUIPN Common Tools Integration](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI) back-office bridge. BOIP-administered records reach agents through the EUIPN tools, not a BOIP API.
- **EUIPO** — EUTMs designating NL+BE+LU and Community designs (RCDs / REUDs). Benelux-only TMs and designs remain BOIP-exclusive on the registration side.
- **WIPO Madrid Monitor / Hague Express** — Madrid IRs designating the Benelux territory; Hague IRs designating BX.
- **UPC** (via shipped `upc_decisions` connector) — Netherlands is a UPC contracting state ([UP system started 2023-06-01](https://inspire.wipo.int/system/files/juri/nl.pdf)); UPC-routed disputes affecting NL are reachable via that connector.

---

## §1 Mission

Octrooicentrum Nederland (OCNL) is the Dutch national patent office —
the only authoritative registrar for NL national patents (since 1912),
NL Supplementary Protection Certificates (including paediatric
extensions), and NL semiconductor topographies. It runs the
[Netherlands Patent Register](https://mijnoctrooi.rvo.nl/fo-eregister-view/?locale=en)
on the **Benelux Patent Platform** (BPP), an IT system shared with the
Belgian and Luxembourg patent offices. Trademark and design protection
in the Benelux territory is *not* run by RVO — it is administered by
the separate **Benelux Office for Intellectual Property** (BOIP) at
[`boip.int`](https://www.boip.int/en), a Benelux Organization for
Intellectual Property body. Because the Netherlands is an EPC
contracting state, an EU member, and a UPC contracting state (UP system
live since 2023-06-01), most "Dutch patents" in commercial circulation
are EP-routed (covered by EPO OPS), most "Dutch trademarks" of any
scale are EUTMs (covered by EUIPO), and the NL Patent Office itself
explicitly feeds a daily bibliographic delta to the EPO's Federated
Register Service. OCNL's genuine value-add for agents is the
NL-national-only slice — NL national patents that never went EP, NL
SPCs at register fidelity, NL semiconductor topographies, and live NL
file history — none of which has a public API.

## §2 What's unique here

- **NL national patents (`Octrooi`)** — published Dutch applications and patents since 1912; not routed through EP. Per [WIPO INSPIRE NL](https://inspire.wipo.int/system/files/juri/nl.pdf) Dutch PCT national-phase entry is only available *via* an EP.
- **NL SPCs + paediatric SPCs** — register-fidelity legal status (e.g. "lapsed" on a specific date because of non-payment), not in INPADOC.
- **Registered topographic designs for semi-conductor products** — niche but real.
- **Live NL file history / dossier** — accessible through the eRegister "Documents" tab; not in EPO OPS.
- **NL patent gazette — *De Industriële Eigendom*** — weekly PDF via the [Octrooi-informatie Portal](https://www.rvo.nl/octrooiportal); the *Bijblad bij De Industriële Eigendom* is the quarterly supplement.
- **Benelux trademarks and designs administered by BOIP** — Benelux-territory rights (BE+NL+LU) that are *not* EUTMs and *not* Madrid IRs; the registration is genuinely Benelux-administered, even though the data surfaces through TMview/DesignView via CTI.

## §3 Programmatic surfaces

Every NL/RVO and BOIP surface is 🔴 Red against the zero-infra-proxy
constraint. There is **no documented public REST/JSON/XML API** for
NL patents, NL SPCs, Benelux trademarks, or Benelux designs, and
**zero entries from RVO or BOIP** in the [WIPO IP API
Catalog](https://apicatalog.wipo.int/) (probed 2026-05-18 via
[`/api/apis?size=200`](https://apicatalog.wipo.int/api/apis?size=200):
179 office APIs across DPMA, EPO, EUIPO, IP Australia, JPO, MOIP
Korea, QAZ, UPRP, USPTO, WIPO — zero from NL or BX).

| Surface | Right(s) | Endpoint | Auth | Format | Rating |
|---|---|---|---|---|---|
| **BPP eRegister** (NL register search) | patent / SPC / topography | [mijnoctrooi.rvo.nl/fo-eregister-view](https://mijnoctrooi.rvo.nl/fo-eregister-view/?locale=en) (Struts2 `.action` POSTs) | none | server-rendered HTML; per-doc XML download; CSV export capped at 1,000 rows; per-saved-query RSS subscription | 🔴 |
| **Octrooi-informatie Portal — gazette** | patent | [`rvo.nl/octrooiportal`](https://www.rvo.nl/octrooiportal) | none | PDF only (weekly *De Industriële Eigendom*, quarterly *Bijblad*) | 🔴 |
| **data.overheid.nl** — `octrooiregister-nederland-01` | patent | [data.overheid.nl](https://data.overheid.nl/dataset/octrooiregister-nederland-01) (CC-BY 4.0) | none | `contentUrl` is the same Struts2 UI; `fileFormat: XLS` is nominal; description "Output in xsl of rss"; `dateModified: 2020-03-27` | 🔴 (dormant metadata pointing at the UI; not a bulk feed) |
| **BPP Portal** (RVO front door) | patent | [`mijnoctrooi.rvo.nl/bpp-portal/en`](https://mijnoctrooi.rvo.nl/bpp-portal/en) | none | Drupal 11 navigation site; links to eRegister, MyPage, eOLF, news | 🔴 (no data surface) |
| **MyPage** (applicant dossier portal) | patent | [`mijnoctrooi.mypage.rvo.nl`](https://mijnoctrooi.mypage.rvo.nl/) | personal | applicant-side only | 🔴 (not a search surface) |
| **Online Filing eOLF** | patent | [`efiling.mijnoctrooi.rvo.nl`](https://efiling.mijnoctrooi.rvo.nl/) | personal | filing forms | 🔴 (not a search surface) |
| **BOIP register / search** (Benelux TM + design) | trademark / design | [`boip.int/en/search`](https://www.boip.int/en/search) | none, **but Google reCAPTCHA gates `robots.txt` and the site root** | HTML | 🔴 (captcha-gated; no developer page; no `/api`) |

Material details for the most consequential surfaces:

- **BPP eRegister About page** ([primary source](https://mijnoctrooi.rvo.nl/fo-eregister-view/about/home.action), text verbatim 2026-05-18): *"The NL Patent register provides a **daily feed of selected bibliographical data on European patents in Netherlands to the Federated Register Service of the European Patent Office**."* This is the architectural fact that drives the strategy — NL's structured data already reaches programmatic consumers through EPO indirection.
- **eRegister structured outputs (UI-side only).** Client JavaScript at [`/fo-eregister-view/resources/scripts/exportToCSV.js`](https://mijnoctrooi.rvo.nl/fo-eregister-view/resources/scripts/exportToCSV.js) hard-codes `maxExportResults = 1000` for the CSV export endpoint (`/fo-eregister-view/download/exportCSV`) and exposes a per-document XML download at `/fo-eregister-view/download/downloadFileXML` that requires an opaque `docId` from a prior HTML search. The "RSS" button is a saved-search subscription, not a general feed.
- **All `/api`, `/rest`, `/swagger-ui.html`, `/v3/api-docs` probes return 404** on both `/fo-eregister-view/` and `/bpp-portal/` (probed 2026-05-18). No developer page anywhere on the RVO subdomains.
- **data.overheid.nl entry is metadata-only.** The JSON-LD `distribution` `contentUrl` points back at the Struts2 search UI; `dateModified: 2020-03-27`; there is no bulk download behind the dataset link. License is **CC-BY 4.0**.
- **BOIP gates its site behind reCAPTCHA.** `boip.int/robots.txt` and `boip.int/sitemap.xml` both return a captcha challenge HTML page. There is no developer portal at `/en/developers`, no `/en/open-data`, and no BOIP entry on the WIPO catalog. BOIP's TM and design records reach the public through EUIPN TMview / DesignView via the EUIPN Common Tools Integration back-office bridge — i.e. through EUIPO infrastructure, not a BOIP-operated API.

## §4 Fees

**Policy: link only.** Reproducing fee amounts is not our job.

RVO/Octrooicentrum publishes a fee schedule (in EUR) for NL patents
(filing, search, examination, grant, renewals), NL SPCs (filing,
renewal, paediatric extension), and miscellaneous services (file
inspection, certified copies, priority documents). BOIP publishes its
own fee schedule (also in EUR) for Benelux trademark and design
filings and renewals.

- **NL patent fee schedule:** [Octrooi aanvragen → Tarieven](https://www.rvo.nl/onderwerpen/octrooien-ofwel-patenten/aanvragen) (linked from [English RVO patent office page](https://english.rvo.nl/topics/patents-intellectual-property-rights/about-patent-office))
- **Statutory basis (NL patents):** [Rijksoctrooiwet 1995](https://wetten.overheid.nl/BWBR0007118) on `wetten.overheid.nl`
- **BOIP fee schedule:** [BOIP entrepreneurs portal](https://www.boip.int/en/entrepreneurs/intellectual-property) (per-right pages link to current fee tables)
- **Statutory basis (Benelux TM/design):** [Benelux Convention on Intellectual Property](https://www.boip.int/en/about-operations) (BCIP, registered TMs and designs)

## §5 Connector strategy

### What we cover today

- **NL patent biblio + family + legal events** — transitively via
  [`patent_client_agents.epo_ops`](../regional/epo.md) (country code `NL`).
  Particularly strong because RVO **explicitly feeds a daily delta** of
  NL bibliographic data to the EPO's Federated Register Service.
- **EUTMs designating NL and Community designs (RCD/REUD)** —
  transitively via the planned EUIPO connector.
- **Madrid IRs / Hague IRs designating BX** — via planned WIPO
  Madrid / Hague connectors.
- **UPC-routed disputes touching NL** — via shipped `upc_decisions`
  connector. NL is a UPC contracting state, UP system live 2023-06-01.

### What we should add

**Nothing in the form of a direct RVO or BOIP connector.** The rating
is 🔴 **Red — `red_no_api`** for both surfaces — there is no
programmatic surface to proxy, BYOK, or contract against. Connector
status: **skipped**.

If we want richer NL coverage beyond what EPO OPS / EUIPO / WIPO
already provide, the realistic avenues are to monitor RVO/BOIP for a
developer-programme announcement and to stand up a separate NL
substantive-law layer via `wetten.overheid.nl` (out of scope for this
synopsis — *Rijksoctrooiwet 1995* is the patent statute; the BCIP
governs Benelux TM/design).

### What we should NOT add

- **eRegister Struts2 scrape.** Same anti-pattern as AT see.ip — server-rendered HTML, 1k-row CSV cap, per-document XML only with opaque `docId` derivation, no documented contract. Strategic memory: do not re-evaluate.
- **`data.overheid.nl` "octrooiregister" bulk download.** Doesn't exist; the dataset entry is metadata pointing at the live Struts2 UI. `dateModified: 2020-03-27`.
- **Octrooi-informatie Portal gazette PDF mirror.** Weekly PDFs only, Dutch primarily, unstructured.
- **BOIP scrape.** reCAPTCHA-gated on `robots.txt`; no API; BOIP records flow to TMview/DesignView via EUIPN CTI — route through the planned EUIPO connector when it lands.

### Next steps

1. Watch [WIPO IP API Catalog](https://apicatalog.wipo.int/) for any RVO or BOIP entries — the canonical signal an IP office has shipped a public API.
2. Watch the BPP portal news feed at [`mijnoctrooi.rvo.nl/bpp-portal/en/news-page`](https://mijnoctrooi.rvo.nl/bpp-portal/en/news-page) for a developer-programme announcement (none as of 2026-05-18).
3. When the EUIPO connector lands, confirm Benelux TM / design records surface via TMview / DesignView at the expected fidelity; document any BOIP-specific fields that don't make it through CTI.
4. Re-evaluate when any of those signals fires. Until then, route NL patent queries through EPO OPS and document the NL-national-only patent / SPC / topography / file-history gap as a known limitation.

## §6 Open questions

- **Bilateral "Data Delivery" path.** Did RVO ever publish a private licensable interface (analogous to IPI's signed-ToU API in Switzerland or the JPO BYOK pattern)? Institutional pages are silent; worth a direct enquiry to `octrooien@rvo.nl` before final closure.
- **NL→FRS feed completeness.** The eRegister About page says RVO sends "selected bibliographical data on European patents in Netherlands" daily to FRS. Does that include NL national-only patents (not EP), NL SPCs, NL topographies — or just EP-NL? Probe needed: pull a known NL-national patent (e.g. NL `1015875`, the worked example on the WIPO INSPIRE PDF) through EPO OPS and confirm coverage.
- **BOIP CTI fidelity in TMview / DesignView.** When EUIPO connector lands, audit what BOIP fields make the CTI round-trip vs. drop in transit. Class headings, Benelux-only renewal events, and legal-status nuance are the typical losses on CTI bridges.
- **BPP cross-leg coverage.** BPP runs three legs (NL, BE, LU); all three look identical in behaviour. Worth confirming whether the BE leg ([`bpp.economie.fgov.be/fo-eregister-view/`](https://bpp.economie.fgov.be/fo-eregister-view/)) and the LU leg ([`patent.public.lu/bpp-portal/`](https://patent.public.lu/bpp-portal/)) ever ship divergent endpoints — a "common API" announcement covering BX would be the leading indicator.
- **NL legal-status fidelity vs. INPADOC.** Per WIPO INSPIRE, legal status like "lapsed for non-payment of annual fee" is canonical from the NL register. Does INPADOC ingest the *event code + reason*, or only the lapse-date? Empirical probe needed.

## §7 References

Primary sources only — `rvo.nl`, `mijnoctrooi.rvo.nl`,
`octrooicentrum.nl`, `data.overheid.nl`, `wetten.overheid.nl`,
`boip.int`, `apicatalog.wipo.int`, `inspire.wipo.int`, `euipn.org`.

**Service overviews:**
- [About the Netherlands Patent Office (EN)](https://english.rvo.nl/topics/patents-intellectual-property-rights/about-patent-office)
- [BPP Portal home (EN)](https://mijnoctrooi.rvo.nl/bpp-portal/en)
- [Netherlands Patent Register — BPP eRegister](https://mijnoctrooi.rvo.nl/fo-eregister-view/?locale=en)
- [eRegister About page (FRS daily-feed statement)](https://mijnoctrooi.rvo.nl/fo-eregister-view/about/home.action)
- [eRegister Help page (RSS-subscription, wildcards, stop-word list)](https://mijnoctrooi.rvo.nl/fo-eregister-view/help/home.action)
- [Octrooi-informatie Portal (NL patent bulletins)](https://www.rvo.nl/octrooiportal)
- [BOIP entrepreneurs portal (EN)](https://www.boip.int/en)
- [BOIP search](https://www.boip.int/en/search)

**Substantive rights:**
- [Rijksoctrooiwet 1995](https://wetten.overheid.nl/BWBR0007118) — Dutch Patent Act 1995
- [Benelux Convention on Intellectual Property — BOIP about operations](https://www.boip.int/en/about-operations)
- [WIPO INSPIRE Netherlands jurisdiction PDF](https://inspire.wipo.int/system/files/juri/nl.pdf)

**Open data + portal entries:**
- [data.overheid.nl — Octrooiregister Nederland dataset](https://data.overheid.nl/dataset/octrooiregister-nederland-01) — CC-BY 4.0
- [RVO open data overview](https://www.rvo.nl/onderwerpen/open-data)

**Cross-office context:**
- [WIPO IP API Catalog (canonical inventory)](https://apicatalog.wipo.int/) — probed 2026-05-18; 0 NL/BX entries across 179 office APIs
- [EUIPN Common Tools Integration (CTI)](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI) — TMview / DesignView back-office bridge for BOIP records
- [EUIPN TMview](https://www.euipn.org/en/tools/TMview) — surfaces Benelux trademark records
- [Benelux Patent Platform — BE leg](https://bpp.economie.fgov.be/fo-eregister-view/) — sibling eRegister at the FPS Economy Belgium
- [Benelux Patent Platform — LU leg](https://patent.public.lu/bpp-portal/) — sibling at the Luxembourg Office of IP

**Detail surveys + waves:**
- [`waves/2026-05-18-secondary-nationals-wave/nl-rvo.md`](../waves/2026-05-18-secondary-nationals-wave/nl-rvo.md) — 2026-05-18 grounded API discovery

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-18 | Initial synopsis; rating **`red_no_api`**. Findings: (a) the BPP eRegister at [`mijnoctrooi.rvo.nl/fo-eregister-view/`](https://mijnoctrooi.rvo.nl/fo-eregister-view/) is a Struts2 server-rendered application whose only structured outputs are saved-search RSS subscriptions, per-document XML downloads, and a 1,000-row capped CSV export — no documented public API; (b) the eRegister About page is explicit that **NL feeds a daily bibliographic delta to the EPO's Federated Register Service**, so EPO OPS / EP Register is the canonical programmatic indirection; (c) RVO and BOIP have **zero entries** in the [WIPO IP API Catalog](https://apicatalog.wipo.int/) (179 office APIs across 10 organisations, all non-NL/BX); (d) the [data.overheid.nl `octrooiregister-nederland-01` dataset](https://data.overheid.nl/dataset/octrooiregister-nederland-01) is metadata-only with `contentUrl` pointing back at the same Struts2 UI and `dateModified: 2020-03-27`; (e) BOIP gates its site behind a Google reCAPTCHA on `robots.txt`, has no developer page, and routes its TM/design records to the public through EUIPN TMview / DesignView via the [Common Tools Integration](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI) back-office bridge — not a BOIP-operated API. Strategic memory: NL is reachable transitively via EPO OPS (with daily-feed freshness from the NL→FRS pipeline), EUIPO (EUTMs / RCDs), WIPO Madrid / Hague (IR designations to BX), and the shipped UPC connector (UP system live 2023-06-01). Genuine national-only gaps — NL national patents that never went EP, NL SPCs at register fidelity, NL semiconductor topographies, NL file history, Benelux-only TMs and designs at BOIP-register fidelity — have no programmatic path. | [waves/2026-05-18-secondary-nationals-wave/nl-rvo.md](../waves/2026-05-18-secondary-nationals-wave/nl-rvo.md) |
