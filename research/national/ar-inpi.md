# INPI Argentina (AR) — national

**Layer:** national
**Jurisdiction:** AR (WIPO ST.3: AR)
**Issuing body:** Instituto Nacional de la Propiedad Industrial — INPI
(`inpi.gob.ar`)
**Naming collision note:** Three different national IP offices share
the acronym **INPI** — Argentina (this synopsis, `inpi.gob.ar`),
[Brazil](./br-inpi.md) (`gov.br/inpi`), and
[France](./fr-inpi.md) (`inpi.fr`). They are unrelated; the only thing
they share is the Latinate name. Always disambiguate by country.
**Rights administered:** patent, utility model (*modelo de utilidad* —
under Ley 24.481 alongside patents, not a separate filing track),
trademark, industrial models and designs (*modelos y diseños
industriales*), technology-transfer contracts (*transferencia de
tecnología*). Software and IC-topography are out of scope — software
copyright registers at DNDA under separate statutes.
**Working languages:** Spanish (primary, near-exclusive). English
summary pages exist on partner sites (EU IP Helpdesk, WIPO) but no EN
regulatory or technical documentation from INPI itself.
**Connector status:** **none** — rated red against the zero-infra-proxy
constraint; no live register API exists.
**Last verified:** 2026-05-18
**Manifest entry:** *not yet listed* — `AR/INPI/*` not added to
`coverage/sources.yaml`.

**Detail surveys:**
- [`waves/2026-05-18-secondary-nationals-wave/ar-inpi.md`](../waves/2026-05-18-secondary-nationals-wave/ar-inpi.md) — 2026-05-18 grounded API discovery; locks in the red rating.

**Higher layers covering this office transitively:**
- **EPO INPADOC** (via [`regional/epo.md`](../regional/epo.md)) — AR
  patent biblio + family when an EP / future-PCT counterpart exists;
  AR-national-only filings and utility models are partial-to-absent.
  AR adopted CPC in 2018 ([EU IP Helpdesk note](https://intellectual-property-helpdesk.ec.europa.eu/news-events/news/latin-america-watch-out-inpi-argentina-about-start-using-cpc-2019-01-25_en)),
  which improved INPADOC classification fidelity.
- **WIPO PATENTSCOPE** — covers PCT applications, but **Argentina is
  not yet a PCT contracting state** as of 2026-05-18. PATENTSCOPE
  coverage is currently nil for AR national-route filings.
- **TMview / DesignView (EUIPN)** — AR INPI joined TMview and
  DesignView on 2017-11-20, contributing **~2.5 million trademarks and
  ~86,000 industrial designs** ([TMDN announcement](https://www.tmdn.org/network/-/argentina-and-moldova-join-tmview?inheritRedirect=true)).
  Same back-office bridge pattern as ES OEPM's CTI implementation.
- **WIPO Madrid** — Argentina is **not** a Madrid Protocol contracting
  party; no Madrid IRs designate AR. All AR trademarks are
  national-route via INPI.
- **WIPO Hague** — Argentina is **not** a Hague contracting party; AR
  industrial designs are INPI-exclusive.
- **Latipat-Espacenet** — Argentina is one of 18 Latin American
  offices in the Latipat cooperation coordinated by ES OEPM; AR
  patents flow through Espacenet-Latipat at biblio fidelity.

---

## §1 Mission

INPI is Argentina's national IP office under the Ministerio de Economía
([argentina.gob.ar/inpi](https://www.argentina.gob.ar/inpi)) and the
only authoritative registrar for AR-national patents, utility models,
trademarks, industrial designs and models, and technology-transfer
contracts. Argentina is the second-largest IP economy in Latin America
behind Brazil and a major regional anchor. Critically, Argentina has
**never joined the PCT or the Madrid Protocol** — every AR patent and
every AR trademark of any vintage is a national-route INPI filing.
That isolation makes INPI the single point of authority for the entire
AR registered-IP universe and the only meaningful read surface for any
question of AR-specific rights. The 2026-02 US-Argentina Reciprocal
Trade and Investment Agreement (ARTI) committed Argentina to submit
PCT accession to Congress by 2026-04-30 ([Palacio IP analysis](https://www.palacio.com.ar/en/2026/02/09/argentina-united-statements-agreement-arti-impact-on-patent-prosecution-in-argentina/));
that deadline is the one watchword that could reshape this synopsis.

## §2 What's unique here

- **AR-national patents (incl. utility models)** — all AR patents are
  INPI-national; no PCT national-phase entries exist because AR is
  pre-PCT. Some flow into INPADOC where they have EP counterparts, but
  the AR-only slice is INPI-exclusive.
- **AR-national trademarks** — all AR TMs are INPI-national; no Madrid
  IRs designate AR. Bridge through TMview surfaces ~2.5M biblio records
  at TMview's documented fidelity (1-class, single-image, status).
- **AR-national industrial designs and models** — INPI-exclusive at the
  register level (AR not Hague contracting); TMview's sibling
  [DesignView](https://www.tmdn.org/tmdsview-web/welcome) surfaces ~86k
  designs at DesignView's bibliographic fidelity.
- **Technology-transfer contracts under Ley 22.426** — INPI registers
  and approves cross-border technology-transfer contracts (royalty-flow
  tax treatment depends on this register). INPI-only; no analogue at
  any higher layer.
- **AR procedural register details** — file-history / dispatch acts /
  oppositions / annuity status live on `portaltramites.inpi.gob.ar`
  under the CAPTCHA, not in INPADOC or DesignView.
- **UMAPI fee unit** — Resolución 75/2026 created the *Unidad de
  Medida de Aranceles de Propiedad Industrial*, monthly-CPI-indexed
  starting 2026-05-01 ([HYA IP summary](https://www.hyaip.com/es/espacio/incremento-tasas-propiedad-industrial-argentina/)).
  No other AR office uses this unit; it is INPI-specific and a
  hard-stop reason for the "fees: link only" policy.

## §3 Programmatic surfaces

### TM / patent / design register search UIs

| Field | Value |
|---|---|
| Endpoint | [`portaltramites.inpi.gob.ar/marcasconsultas/busqueda`](https://portaltramites.inpi.gob.ar/marcasconsultas/busqueda) (TMs), [`portaltramites.inpi.gob.ar/PatenteConsultas/BusquedaParametros`](https://portaltramites.inpi.gob.ar/PatenteConsultas/BusquedaParametros) (patents), [`portaltramites.inpi.gob.ar/ModelosConsultas/BusquedaParametros`](https://portaltramites.inpi.gob.ar/ModelosConsultas/BusquedaParametros) (designs) |
| Auth | Anonymous browse; **motionCaptcha gesture-captcha** for detail (`Captcha/jquery.motionCaptcha.0.2.js`) |
| Format | ASP.NET MVC HTML (Server: `Microsoft-IIS/8.5`) |
| Rate limit | Undocumented; CAPTCHA is the throttle |
| ToS posture | No published Términos de Uso page beyond the implicit CAPTCHA-enforced anti-automation posture |
| Rating | 🔴 Red — HTML + CAPTCHA |
| Primary source | [Portal de Trámites landing](https://portaltramites.inpi.gob.ar/) |

Live registers are HTML-only and gesture-CAPTCHA-gated. Three forms per
modality (puntual / avanzada / renovaciones); each POSTs to a
`*Consultas/Grilla` MVC handler that renders an HTML hit table. No JSON
or XML response.

### `ws.inpi.gob.ar/wsinpi.asmx` — filer-portal SOAP

| Field | Value |
|---|---|
| Endpoint | [`ws.inpi.gob.ar/wsinpi.asmx`](https://ws.inpi.gob.ar/wsinpi.asmx) ([WSDL](https://ws.inpi.gob.ar/wsinpi.asmx?WSDL)); testing env at `wstesting.inpi.gob.ar/wsinpi.asmx` |
| Auth | Per-applicant **CUIT-bound** username/password; credentials issued by emailing `soporteinformatica@inpi.gob.ar` |
| Format | SOAP/ASMX (Microsoft auto-generated, `targetNamespace="http://tempuri.org/"`) |
| Scope | Six `Ingresar_*` operations submit new filings; three `Consulta*` operations expose narrow reads — TM-name search, TM-owner search, and your own filer-mailbox |
| Rating | 🔴 Red — filer portal, not a public register API; the three `Consulta` operations are TM-only and CUIT-bound |
| Primary source | [Solicitud WS landing](https://portaltramites.inpi.gob.ar/Home/SolicitudWS) |

The WSDL fetches publicly but the operations are designed for
**outbound filer traffic** (`Ingresar_MarcasNuevas`,
`Ingresar_PatenteInvecionNueva`, etc.). The `ConsultaDenominacion` and
`ConsultaCuitOTitular` reads return only thin TM biblio (`Acta,
Titulares, Fecha_Ingreso, Clase, Denominacion, Tipo_Marca,
Numero_Resolucion, Estado`) with no Boolean / wildcard / class-filter
query grammar. Same posture as BR INPI's
`meu.inpi.gov.br/pag/swagger/index.html` — listed so future-us doesn't
mistake it for the missing register API.

### `datos.inpi.gob.ar` — public stats dashboards

| Field | Value |
|---|---|
| Endpoint | [`datos.inpi.gob.ar`](https://datos.inpi.gob.ar/Home/EstadisticasINPI) · [Patentes](https://datos.inpi.gob.ar/Home/Patentes) |
| Auth | None |
| Format | Server-rendered HTML with ECharts charts (`.NET Kestrel`) |
| Scope | Aggregate counts of filings and resolutions per modality, monthly + annual |
| Rating | 🔴 Red — dashboard only; no record-level data, no AJAX/JSON layer |
| Primary source | [Estadísticas page](https://datos.inpi.gob.ar/Home/EstadisticasINPI) |

Stats only — useful for trend reporting, not for register lookups.

### `datos.gob.ar` — national open-data CKAN

| Field | Value |
|---|---|
| Endpoint | [`datos.gob.ar/api/3/action/package_search?q=INPI`](https://datos.gob.ar/api/3/action/package_search?q=INPI&rows=20) |
| Auth | None |
| Result | **`count: 0`** — zero INPI datasets published on the national CKAN portal as of 2026-05-18 |
| Rating | 🔴 Red — INPI has not exposed register data despite Ley 27.275 + Decreto 117/16 obligations |
| Primary source | [datos.gob.ar](https://datos.gob.ar/) |

Argentina runs the standard CKAN open-data portal; INPI has not yet
populated it.

### Boletines (weekly bulletin) PDFs

| Field | Value |
|---|---|
| Endpoint | [`portaltramites.inpi.gob.ar/Uploads/Boletines/{NNNN}_3_.pdf`](https://portaltramites.inpi.gob.ar/Uploads/Boletines/) — numbering ~5990s (e.g. RPI 5991 = 2026-02-11) |
| Format | PDF (no XML / JSON companion) |
| Rating | 🔴 Red — bulk PDF, not a query API |
| Primary source | Linked from [Boletines page](https://www.argentina.gob.ar/inpi) |

Weekly publication; no machine-readable companion (unlike BR INPI's
RPI ZIP+XML).

### WIPO IP API Catalog

| Field | Value |
|---|---|
| Endpoint | [`apicatalog.wipo.int`](https://apicatalog.wipo.int/) |
| Result | **0 AR INPI entries** as of 2026-05-18 |
| Rating | informational — confirms INPI has not published any developer API to the canonical inventory |

## §4 Fees

**Policy: link only.** INPI publishes a fee schedule (in Argentine
pesos, ARS) covering patents (filing, search, examination, grant,
opposition, renewal/annuity), utility models, trademarks (filing,
renewal, opposition — per Nice class), industrial designs and models
(filing, renewal), technology-transfer contracts, and miscellaneous
services (priority documents, certified copies, file inspection).

**Critical structural change effective 2026**: Resolución 75/2026
(published 2026-03-18, effective 2026-04-01; UMAPI indexation effective
2026-05-01) restructured the entire schedule and introduced the
**UMAPI** unit (*Unidad de Medida de Aranceles de Propiedad
Industrial*). All fees are expressed in UMAPIs and convert to ARS at
monthly cadence based on INDEC's Consumer Price Index. Initial UMAPI
value: ARS 360 (2026-04). This automatic indexation makes any
mirrored fee amount stale within a month and is a hard reason for
strict link-only policy.

- **Official fee schedule (current):** [Aranceles INPI](https://portaltramites.inpi.gob.ar/InfoPortal/Aranceles)
- **Fee anexo PDF:** [Aranceles_Anexo.pdf](https://portaltramites.inpi.gob.ar/Documentos/Aranceles_Anexo.pdf)
- **Fee policy page:** [argentina.gob.ar/inpi/aranceles-inpi](https://www.argentina.gob.ar/inpi/aranceles-inpi)
- **Statutory bases:** [Ley 24.481 (patents)](https://servicios.infoleg.gob.ar/infolegInternet/anexos/35000-39999/35001/texact.htm) · [Ley 22.362 (TMs)](https://www.argentina.gob.ar/normativa/nacional/ley-22362-18803/actualizacion) · [Decreto-Ley 6.673/63 (designs)](https://www.argentina.gob.ar/normativa/nacional/decreto-ley-6673-1963-65216) · [Ley 22.426 (technology transfer)](https://servicios.infoleg.gob.ar/infolegInternet/anexos/15000-19999/18804/norma.htm)
- **Recent rate adjustments:** see weekly Boletines under [portaltramites.inpi.gob.ar/Uploads/Boletines/](https://portaltramites.inpi.gob.ar/Uploads/Boletines/)

Notable discount programmes *(name + one-line eligibility — no
amounts, no dates)*:

- **PyME / persona humana / universidades públicas** — fee reductions
  on patent annuities for SMEs, natural persons, and public
  universities under the Resolución 75/2026 schedule.

## §5 Connector strategy

### What we cover today

- Nothing direct on AR INPI.
- AR patent biblio + family transitively via
  [`patent_client_agents.epo_ops`](../regional/epo.md) (INPADOC), where
  the AR application has an EP / future-PCT counterpart. AR adopted
  CPC in 2018, improving classification fidelity in INPADOC.
- AR trademark and design biblio transitively via the planned EUIPN
  TMview / DesignView connector (since 2017-11-20 contribution).
- AR Latipat patents transitively via Espacenet-Latipat (covered through
  EPO OPS).

### What we should NOT add

- **CAPTCHA-bound scraping of `portaltramites.inpi.gob.ar`.** HTML +
  motionCaptcha + ToS-implicit anti-automation. No.
- **`ws.inpi.gob.ar/wsinpi.asmx` as a register API.** It is a filer
  portal. The three `Consulta*` operations are TM-only and CUIT-bound
  (each credential is anchored to one CUIT/applicant). Even as BYOK,
  the surface is too narrow (TM only, no Boolean grammar, no
  patent/design read) to be load-bearing.
- **Boletines PDF scraping.** Bulk weekly PDFs with no machine
  companion. Building OCR + dispatch-code extraction would be
  off-spec for the zero-infra constraint.
- **`datos.inpi.gob.ar` scraping.** Dashboard-only; no record fidelity
  even if scraped.

### What we *could* still add (separate decision)

- **`AR/IP/Statute` — static-law module.** Argentine industrial-property
  law is consolidated across four anchor statutes:
  - [Ley 24.481 (patents + utility models)](https://servicios.infoleg.gob.ar/infolegInternet/anexos/35000-39999/35001/texact.htm)
  - [Ley 22.362 (trademarks)](https://www.argentina.gob.ar/normativa/nacional/ley-22362-18803/actualizacion)
  - [Decreto-Ley 6.673/63 (designs)](https://www.argentina.gob.ar/normativa/nacional/decreto-ley-6673-1963-65216)
  - [Ley 22.426 (technology transfer)](https://servicios.infoleg.gob.ar/infolegInternet/anexos/15000-19999/18804/norma.htm)

  Same SQLite/FTS5 pattern already shipped for `ipo_in_statutes`,
  `dpma_statutes`, `legifrance_ip`, `tw_trade_secrets`. ES corpus
  from Infoleg + optional EN translations from
  [WIPO Lex AR](https://www.wipo.int/wipolex/en/legislation/profile/AR).
  Queue separately from any live-register decision.

### Next steps

1. Resolve STATE.yaml: `rating: red_no_api`,
   `connector_status: none`, `next_action: monitor`.
2. **Watch: PCT accession.** The 2026-04-30 congressional submission
   deadline passed before this synopsis date; track whether Argentina
   actually submitted and whether ratification follows. Once the PCT
   accession deposit lands at WIPO, AR national-phase patent
   applications become reachable via WIPO PATENTSCOPE and the
   AR-isolation calculus shifts substantially.
2. **Watch: register-API publication under Ley 27.275 / Decreto 117/16.**
   No current INPI dataset on [datos.gob.ar](https://datos.gob.ar/);
   open-data obligations technically apply. Any future
   `datos.gob.ar/organization/inpi` listing or
   `datos.inpi.gob.ar/api/*` endpoint would unblock at least
   bibliographic coverage.
3. **File a separate BACKLOG entry for `AR/IP/Statute`** static-law
   module — Infoleg corpus, WIPO Lex AR cross-reference.

## §6 Open questions

- **Does `wsinpi.asmx` ever externalise a true public register read?**
  No primary source confirms or denies. It is the only signal that INPI
  runs a modern API stack internally for filing; whether any of the
  read operations get broadened (Boolean grammar; patent/design overlay;
  shared-key posture) is the live unblock question.
- **PCT post-deadline status.** Did Argentina submit accession to
  Congress by 2026-04-30 under the ARTI commitment? Is ratification on
  track? No primary source as of synopsis date.
- **TMview / DesignView fidelity gap vs. live INPI register.** TMview
  carries the biblio slice; does the AR slice include opposition events,
  renewals after 2017, and assignment changes? Empirical probe via
  [tmdn.org](https://www.tmdn.org/tmview/welcome) needed against a
  cluster of known AR registrations.
- **CUIT requirement for foreign developers on `wsinpi.asmx`.** The
  `soporteinformatica@inpi.gob.ar` form expects a CUIT; no
  primary-source path documents a foreign-developer alternative. In
  practice, foreign filers route through an Argentine local agent who
  holds the CUIT.
- **UMAPI indexation transparency.** Resolución 75/2026 specifies INDEC
  CPI updates, but the official monthly UMAPI-to-ARS conversion
  publication channel (Boletín? `aranceles-inpi` page?) is not
  explicitly stated — relevant for any caller that needs to surface
  current cost figures.

## §7 References

Primary sources only — `argentina.gob.ar/inpi`, `inpi.gob.ar`,
`portaltramites.inpi.gob.ar`, `ws.inpi.gob.ar`, `datos.inpi.gob.ar`,
`infoleg.gob.ar`, WIPO.

**INPI service entry points:**
- [INPI portal (ES)](https://www.argentina.gob.ar/inpi) · [INPI legacy portal](http://www.inpi.gob.ar/)
- [Portal de Trámites](https://portaltramites.inpi.gob.ar/) · [TM register UI](https://portaltramites.inpi.gob.ar/marcasconsultas/busqueda) · [Patent register UI](https://portaltramites.inpi.gob.ar/PatenteConsultas/BusquedaParametros) · [Design register UI](https://portaltramites.inpi.gob.ar/ModelosConsultas/BusquedaParametros)
- [Bases de datos de libre acceso](https://www.argentina.gob.ar/inpi/informacion-tecnologica/bases-de-datos-de-libre-acceso) · [Información tecnológica](https://www.argentina.gob.ar/inpi/informacion-tecnologica)
- [Trámites de Marcas](https://www.argentina.gob.ar/inpi/marcas/tramites-de-marcas) · [Seguí tu trámite](https://www.argentina.gob.ar/inpi/marcas/seguir-el-tramite)

**Filer-portal SOAP service (NOT a register API):**
- [`ws.inpi.gob.ar/wsinpi.asmx`](https://ws.inpi.gob.ar/wsinpi.asmx) · [WSDL](https://ws.inpi.gob.ar/wsinpi.asmx?WSDL) · [Solicitud WS landing](https://portaltramites.inpi.gob.ar/Home/SolicitudWS) · testing env `wstesting.inpi.gob.ar/wsinpi.asmx`

**Stats portal + open data:**
- [datos.inpi.gob.ar](https://datos.inpi.gob.ar/Home/EstadisticasINPI) · [Patentes dashboard](https://datos.inpi.gob.ar/Home/Patentes)
- [INPI open-data page](https://www.argentina.gob.ar/inpi/transparencia-activa/portales-de-datos-abiertos)
- [National CKAN datos.gob.ar](https://datos.gob.ar/) · [CKAN search q=INPI](https://datos.gob.ar/api/3/action/package_search?q=INPI&rows=20) (zero hits, 2026-05-18)

**Statutes (substantive law):**
- [Ley 24.481 — Patentes de Invención y Modelos de Utilidad](https://servicios.infoleg.gob.ar/infolegInternet/anexos/35000-39999/35001/texact.htm)
- [Ley 22.362 — Marcas y Designaciones](https://www.argentina.gob.ar/normativa/nacional/ley-22362-18803/actualizacion)
- [Decreto-Ley 6.673/63 — Modelos y Diseños Industriales](https://www.argentina.gob.ar/normativa/nacional/decreto-ley-6673-1963-65216)
- [Ley 22.426 — Transferencia de Tecnología](https://servicios.infoleg.gob.ar/infolegInternet/anexos/15000-19999/18804/norma.htm)
- [Ley 27.275 — Acceso a la Información Pública](https://servicios.infoleg.gob.ar/infolegInternet/anexos/265000-269999/265949/norma.htm)
- [Decreto 117/16 — Datos abiertos](https://www.argentina.gob.ar/normativa/nacional/decreto-117-2016-257755)
- [WIPO Lex Argentina profile](https://www.wipo.int/wipolex/en/legislation/profile/AR)

**Fees:**
- [Aranceles INPI](https://portaltramites.inpi.gob.ar/InfoPortal/Aranceles) · [Aranceles INPI page](https://www.argentina.gob.ar/inpi/aranceles-inpi) · [Aranceles_Anexo.pdf](https://portaltramites.inpi.gob.ar/Documentos/Aranceles_Anexo.pdf)

**Cross-office context:**
- [TMview AR launch (2017-11-20)](https://www.tmdn.org/network/-/argentina-and-moldova-join-tmview?inheritRedirect=true) · [tmview](https://www.tmdn.org/tmview/welcome) · [DesignView](https://www.tmdn.org/tmdsview-web/welcome)
- [INPI adopts CPC (2018)](https://intellectual-property-helpdesk.ec.europa.eu/news-events/news/latin-america-watch-out-inpi-argentina-about-start-using-cpc-2019-01-25_en)
- [US-Argentina ARTI / PCT commitment](https://www.palacio.com.ar/en/2026/02/09/argentina-united-statements-agreement-arti-impact-on-patent-prosecution-in-argentina/) · [Argentina-US trade agreement IP reform context](https://intellectual-property-helpdesk.ec.europa.eu/news-events/news/argentina-us-trade-agreement-paves-way-significant-ip-reform-2026-03-16_en)
- [Latipat-Espacenet](https://lp.espacenet.com/?locale=en_LP)
- [WIPO API Catalog](https://apicatalog.wipo.int/) (probed 2026-05-18; AR INPI not listed)

**Wave file:**
- [`waves/2026-05-18-secondary-nationals-wave/ar-inpi.md`](../waves/2026-05-18-secondary-nationals-wave/ar-inpi.md)

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-18 | Initial synopsis. Rated 🔴 red_no_api against the zero-infra-proxy constraint. Findings: (a) all three live register search UIs at `portaltramites.inpi.gob.ar` (TMs, patents, designs) are ASP.NET MVC HTML + a [motionCaptcha gesture captcha](https://portaltramites.inpi.gob.ar/marcasconsultas/busqueda) — no JSON layer; (b) the SOAP service at [`ws.inpi.gob.ar/wsinpi.asmx`](https://ws.inpi.gob.ar/wsinpi.asmx?WSDL) is a **filer portal**, not a register API — six `Ingresar_*` ops submit new filings, three `Consulta*` ops expose narrow TM-only reads and a CUIT-bound notifications inbox; (c) `datos.inpi.gob.ar` is dashboard-only (.NET Kestrel + ECharts, no AJAX layer); (d) `datos.gob.ar` returns **zero INPI datasets** on CKAN `q=INPI` despite Ley 27.275 + Decreto 117/16 obligations; (e) AR is **not yet a PCT contracting state**; the 2026-02-05 [US-Argentina ARTI](https://www.palacio.com.ar/en/2026/02/09/argentina-united-statements-agreement-arti-impact-on-patent-prosecution-in-argentina/) committed Argentina to submit PCT accession to Congress by 2026-04-30 — primary watch item; (f) AR joined [TMview / DesignView on 2017-11-20](https://www.tmdn.org/network/-/argentina-and-moldova-join-tmview?inheritRedirect=true) with ~2.5M TMs + ~86k designs — the cleanest cross-office bridge for AR registered IP; (g) Resolución 75/2026 introduced the [UMAPI fee unit](https://www.hyaip.com/es/espacio/incremento-tasas-propiedad-industrial-argentina/) (effective 2026-04-01, monthly CPI-indexed from 2026-05-01) — mandatory link-only fee policy; (h) WIPO IP API Catalog has 0 AR INPI entries. Connector status: **none**. Highest-value follow-ups: `AR/IP/Statute` static-law module (Infoleg + WIPO Lex AR) and PCT accession monitoring. Correction vs. original prompt: prompt stated "AR is NOT a PCT contracting state for filings originating elsewhere (it acceded in 2018 but watch for current status)" — the 2018 reference is to **CPC** (Cooperative Patent Classification, adopted by INPI in 2018 per [EU IP Helpdesk](https://intellectual-property-helpdesk.ec.europa.eu/news-events/news/latin-america-watch-out-inpi-argentina-about-start-using-cpc-2019-01-25_en)), not PCT; Argentina has never joined PCT. | [waves/2026-05-18-secondary-nationals-wave/ar-inpi.md](../waves/2026-05-18-secondary-nationals-wave/ar-inpi.md) |
