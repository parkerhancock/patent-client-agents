# AR/INPI — wave file (2026-05-18 secondary nationals wave)

Grounded API discovery for **INPI Argentina** (Instituto Nacional de la
Propiedad Industrial — `inpi.gob.ar`, NOT to be confused with INPI
Brazil at `gov.br/inpi` or INPI France at `inpi.fr`). Verified against
the repo's zero-infra-proxy constraint on 2026-05-18.

Rights covered: patents of invention, utility models (modelos de
utilidad — under Ley 24.481 alongside patents), trademarks
(Ley 22.362), industrial models and designs (Decreto-Ley 6.673/63),
technology-transfer contracts (Ley 22.426). No software / IC-topography
register at INPI (those route through DNDA — the copyright office —
under separate statutes).

---

## 1. Endpoint

INPI Argentina exposes **no public REST/JSON register API** for the
live patent, trademark, or design registers. The programmatic surfaces
discovered:

- **`portaltramites.inpi.gob.ar/marcasconsultas/busqueda`** — the live
  trademark register search UI. ASP.NET MVC server-rendered HTML form
  ([`/MarcasConsultas/Grilla`](https://portaltramites.inpi.gob.ar/MarcasConsultas/Busqueda)
  POST handler) returning HTML table results. Three forms on the page:
  *búsqueda puntual* (by Acta/Registro number), *búsqueda avanzada*
  (denomination + class + applicant + date range), *búsqueda de
  renovaciones*. Hidden form input `tipob` (0/1/2) discriminates.
- **`portaltramites.inpi.gob.ar/PatenteConsultas/BusquedaParametros`** —
  the live patent register search UI. Same ASP.NET MVC pattern;
  POST to [`/PatenteConsultas/Grilla`](https://portaltramites.inpi.gob.ar/PatenteConsultas/BusquedaParametros)
  with hidden `tipob` values `BUSQUEDA_PARAMETRO_PUNTUAL` /
  `BUSQUEDA_PARAMETRO_AVANZADA`. HTML hits, no JSON.
- **`portaltramites.inpi.gob.ar/ModelosConsultas/BusquedaParametros`** —
  industrial models and designs register; same shape as the patent
  search.
- **`ws.inpi.gob.ar/wsinpi.asmx`** — a SOAP/ASMX web service exists with
  publicly-fetchable [WSDL](https://ws.inpi.gob.ar/wsinpi.asmx?WSDL).
  **It is a filer-portal endpoint, NOT a register read API.** Nine
  operations:
  - `Ingresar_MarcasNuevas`, `Ingresar_MarcaRenovacion`,
    `Ingresar_ModeloNuevo`, `Ingresar_ModeloRenovacion`,
    `Ingresar_PatenteInvecionNueva`, `Ingresar_PatenteUtilidadNueva`
    — submit new filings.
  - `ConsultaDenominacion(Denominacion)` — TM-name search returning
    `PaginadoBusquedaAvanzada { total, estado, rows[GrillaMarcas{ Acta,
    Titulares, Fecha_Ingreso, Clase, Denominacion, Tipo_Marca,
    Numero_Resolucion, Estado }] }`.
  - `ConsultaCuitOTitular(cuit, titular)` — owner search returning the
    same `PaginadoBusquedaAvanzada` envelope.
  - `ConsultaNotificaciones(fechaInicial, fechafinal, expediente,
    direccion, tipoNotificacion, datosUsuario:Usuario)` — **your own**
    notifications inbox; gated by `datosUsuario` (CUIT-bound).
  - WSDL targetNamespace is `http://tempuri.org/` (auto-generated, no
    explicit semantics).
- **`datos.inpi.gob.ar`** — public stats portal
  ([Home](https://datos.inpi.gob.ar/Home/EstadisticasINPI),
  [Patentes](https://datos.inpi.gob.ar/Home/Patentes)). .NET Kestrel
  application serving server-side-rendered ECharts dashboards. No AJAX
  layer behind the charts; no documented JSON endpoint; no record-level
  data. Aggregate counts only (monthly / annual filings and
  resolutions).
- **`portaltramites.inpi.gob.ar/Home/SolicitudWS`** — the human-facing
  *landing page* explaining the SOAP filer service above, with PDF
  guides and credential-issuance contact
  (`soporteinformatica@inpi.gob.ar`).
- **`portaltramites.inpi.gob.ar/Uploads/Boletines/{NNNN}_3_.pdf`** — the
  weekly Boletín de Marcas / Boletín de Patentes (e.g. RPI 5991 was
  2026-02-11). PDF only; no XML/JSON publication.
- **`datos.gob.ar`** — Argentina's open-data CKAN portal at
  [datos.gob.ar](https://datos.gob.ar/). Probed via CKAN action
  [`/api/3/action/package_search?q=INPI`](https://datos.gob.ar/api/3/action/package_search?q=INPI&rows=20)
  on 2026-05-18; **`count: 0`** — zero datasets published by INPI on the
  national open-data portal. The Decreto 117/16 + Ley 27.275 framework
  technically obliges INPI to publish, but the office has not done so.

The trademark and patent search UIs are the live register for humans;
nothing in between. There is **no equivalent to ES OEPM's INVENES /
CEO documented SOAP services, no equivalent to BR INPI's RPI weekly
XML bulk feed, and no equivalent to the EPO OPS / USPTO ODP query
API stack**.

## 2. Auth

- **`portaltramites.inpi.gob.ar` search UIs (`marcasconsultas`,
  `PatenteConsultas`, `ModelosConsultas`)**: anonymous browse for the
  hit list page; **client-side CAPTCHA** enforced via
  `Captcha/jquery.motionCaptcha.0.2.js` (a draw-a-shape gesture
  captcha) before showing detail. ASP.NET session cookie
  (`cookiesession1`) plus AntiForgery cookie
  (`.AspNetCore.Antiforgery.*`).
- **`ws.inpi.gob.ar/wsinpi.asmx`**: per-applicant **CUIT-bound** user
  account; credentials issued by emailing
  `soporteinformatica@inpi.gob.ar` with CUIT, business name, email,
  phone. Production and homologation (`wstesting.inpi.gob.ar`)
  environments are separate; user must register against the same CUIT
  in both. **The credential is bound to the natural / legal person it
  belongs to** — this is a CUIT-anchored BYOK shape and is not designed
  for shared-key / hosted-proxy use.
- **`datos.inpi.gob.ar`**: anonymous, no auth.
- **`portaltramites.inpi.gob.ar` boletines PDF directory**: anonymous,
  no auth.

Foreign-developer accessibility: the CAPTCHA-gated search UIs work
from anywhere (no geofencing observed empirically), but Spanish-only
and CAPTCHA-bound. Credential issuance for the SOAP webservice
empirically requires a CUIT (Argentine tax ID); foreign filers
typically operate via an Argentine local agent who holds the
credentials. No primary source documents a foreign-developer pathway.

## 3. Query language

- **`portaltramites.inpi.gob.ar` search UIs**: HTML form fields per
  modality. No documented URL parameter grammar; URLs are MVC POSTs
  with hidden `tipob` discriminators. No documented SolR / Lucene
  syntax. CAPTCHA throttles automated form submission.
- **`ws.inpi.gob.ar/wsinpi.asmx` `ConsultaDenominacion`**: takes a
  single `Denominacion` string; returns paginated TM hits. The query
  surface is **single-field, single-modality (TMs only)**, with no
  Boolean / wildcard / class-filter / date-range grammar exposed in
  the WSDL.
- **`ws.inpi.gob.ar/wsinpi.asmx` `ConsultaCuitOTitular`**: takes
  `(cuit, titular)`; returns paginated TM hits owned by that owner.
  Again, **TMs only** in the response shape (`ArrayOfGrillaMarcas`);
  no patent / design overlay.
- **`ws.inpi.gob.ar/wsinpi.asmx` `ConsultaNotificaciones`**: takes a
  date range + a personal `Usuario` block (the credentialed user's own
  expedientes); returns notifications. **Auth-gated to the filer's
  own portfolio** — not a public register read.
- **`datos.inpi.gob.ar`**: dashboard UI; no query language.
- No SolR, no Lucene, no GraphQL, no SPARQL, no CQL, no OData.

## 4. Pagination

- **Search UIs**: HTML pagination through hit list; no documented page
  size cap; session-state-dependent.
- **`ConsultaDenominacion` / `ConsultaCuitOTitular`**: response wraps
  `total` (int) + `rows` (`ArrayOfGrillaMarcas`) but the WSDL does NOT
  expose a `page` / `pageSize` / `offset` parameter on the request
  side — the entire result set comes back in one call. No primary
  source documents the server-side cap; empirically untested as
  credentials are required.
- **Boletines PDF**: pagination N/A — one PDF per weekly issue.

## 5. Response shape

- **Search UIs**: HTML tables. No JSON.
- **`ConsultaDenominacion`** SOAP response (per
  [WSDL](https://ws.inpi.gob.ar/wsinpi.asmx?WSDL)):

  ```
  PaginadoBusquedaAvanzada
    total: int
    estado: string
    rows: ArrayOfGrillaMarcas[
      GrillaMarcas {
        Acta: long
        Titulares: string
        Fecha_Ingreso: dateTime
        Clase: int
        Denominacion: string
        Tipo_Marca: string
        Numero_Resolucion: string
        Estado: string
      }
    ]
  ```

  Thin biblio: Acta (file number), holder string, Nice class, mark
  type, resolution number, status. No images, no goods/services list,
  no procedural history, no opposition log.
- **`ConsultaCuitOTitular`** SOAP response: same `PaginadoBusquedaAvanzada`
  envelope — TMs only, owner-filtered.
- **`ConsultaNotificaciones`** SOAP response: `ArrayOfNotificaciones_Archivos`
  envelope — your own filer-mailbox items.
- **Boletines PDF**: dispatch-coded acts published as printable
  bulletin pages; no machine-readable companion.

No primary source publishes sample JSON of a register hit because
**there is no public JSON register surface to sample**.

## 6. Coverage scope

- **`portaltramites.inpi.gob.ar` search UIs**: live registers — current
  filings + historical backfile. INPI is the sole authoritative
  registrar for AR patents (post-1864), AR utility models, AR
  trademarks, AR industrial models and designs, and AR
  technology-transfer contracts. Backfile depth not documented on the
  public-facing UI; the CAPTCHA blocks empirical probing.
- **`ConsultaDenominacion` / `ConsultaCuitOTitular`**: TMs only.
  Returns Acta + biblio fields. Coverage depth not documented.
- **Boletines PDF**: weekly publication; numbering ~5990s as of
  February 2026.
- **TMview / DesignView (cross-office)**: AR INPI joined TMview in
  November 2017 with [~2.5M trademarks](https://www.tmdn.org/network/-/argentina-and-moldova-join-tmview?inheritRedirect=true)
  and DesignView with ~86k industrial designs. This is the cleanest
  bridge for cross-office AR trademark and design data — same shape as
  ES OEPM's CTI bridge.
- **EPO INPADOC**: AR national-route patents flow through INPADOC at
  biblio + family fidelity where the corresponding application has
  reached publication and INPI feeds the data to EPO (CPC adoption
  agreement signed 2018 — see [EU IP Helpdesk note](https://intellectual-property-helpdesk.ec.europa.eu/news-events/news/latin-america-watch-out-inpi-argentina-about-start-using-cpc-2019-01-25_en)).
  AR utility models and AR-only filings without EP / PCT counterparts
  are partial-to-absent.

## 7. Rate limits / quotas

- **Search UIs**: undocumented; CAPTCHA is the enforcement mechanism
  rather than published throttles.
- **`ws.inpi.gob.ar/wsinpi.asmx`**: not documented on the public web.
  Per-credential limits may be in the per-applicant `documentacion y
  ejemplos en C#` packet ([landing](https://portaltramites.inpi.gob.ar/Home/SolicitudWS)).
- **`datos.inpi.gob.ar`**: undocumented; static dashboards.
- **Boletines PDF**: static HTTP downloads, no published throttle.
- **`datos.gob.ar` CKAN**: standard public CKAN — no INPI datasets
  exposed (zero hits as of 2026-05-18 — see §1).

## 8. Terms of service

- **`portaltramites.inpi.gob.ar`**: ASP.NET MVC application running
  under IIS 8.5 (`Microsoft-IIS/8.5` server header), with
  `Content-Security-Policy: upgrade-insecure-requests`,
  `Strict-Transport-Security: max-age=31536000;includeSubDomains;preload`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`,
  `Permissions-Policy: camera=(), geolocation=(), microphone=()`. The
  motionCaptcha gesture-captcha is the operative anti-automation signal
  — no published "Términos de Uso" page for the search UIs found beyond
  this implicit posture.
- **`ws.inpi.gob.ar`**: terms are negotiated as part of the credential
  issuance via `soporteinformatica@inpi.gob.ar`. No public ToS page
  found.
- **AR open data policy**:
  [Ley 27.275 (Acceso a la Información Pública)](https://servicios.infoleg.gob.ar/infolegInternet/anexos/265000-269999/265949/norma.htm)
  + [Decreto 117/16](https://www.argentina.gob.ar/normativa/nacional/decreto-117-2016-257755)
  obligate national executive bodies to publish open data, but **INPI
  has not published register data on `datos.gob.ar`** as of 2026-05-18
  (CKAN search `q=INPI` returns 0 datasets — see §1). Only aggregate
  statistics on `datos.inpi.gob.ar` satisfy the office's open-data
  posture today.
- **Public records as such**: industrial-property files are public
  records under Ley 24.481 (patents), Ley 22.362 (TMs), and
  Decreto-Ley 6.673/63 (designs). Reuse of register data carries no
  proprietary restriction — the *delivery channel* is the gating factor,
  and that channel is CAPTCHA-gated HTML.

## 9. Operational notes

- **Language**: Spanish-only across `portaltramites.inpi.gob.ar`,
  `datos.inpi.gob.ar`, `ws.inpi.gob.ar`, and the substantive sections
  of `argentina.gob.ar/inpi`. EN summary pages exist (e.g. EU IP
  Helpdesk content) but no EN regulatory or technical documentation
  from INPI itself.
- **PCT status (critical recent change)**: Argentina is **not currently
  a PCT contracting state** as of 2026-05-18. Under the
  [US-Argentina Reciprocal Trade and Investment Agreement (ARTI),
  signed 2026-02-05](https://www.palacio.com.ar/en/2026/02/09/argentina-united-statements-agreement-arti-impact-on-patent-prosecution-in-argentina/),
  Argentina committed to submit PCT accession to Congress no later than
  **2026-04-30**. The deadline has passed as of this wave; no primary
  source confirms or denies on-time submission. *This is the most
  important watch item for AR INPI coverage going forward — once
  Argentina joins PCT, AR national-phase applications become reachable
  via WIPO PATENTSCOPE.* (Original-prompt note "AR is NOT a PCT
  contracting state for filings originating elsewhere (it acceded in
  2018 but watch for current status)" is inaccurate — Argentina has
  never joined PCT; the 2018 reference is to CPC, the EPO/USPTO
  Cooperative Patent Classification, adopted 2018 per the
  [EU IP Helpdesk note](https://intellectual-property-helpdesk.ec.europa.eu/news-events/news/latin-america-watch-out-inpi-argentina-about-start-using-cpc-2019-01-25_en).)
- **TMview / DesignView coverage**: AR INPI joined both networks
  2017-11-20, contributing ~2.5M TMs + ~86k designs. Going through
  EUIPN tooling is the cleanest cross-office bridge for AR
  trademarks and designs.
- **Geofencing**: none observed; all probed URLs serve from inside
  Argentina but accept requests from outside.
- **Downtime**: `portaltramites.inpi.gob.ar` historically experiences
  AFIP-authentication outages (AFIP is the AR tax authority that hosts
  the SSO flow). No published SLA.
- **Server stack**: ASP.NET MVC on IIS 8.5 (search UIs + filing
  portal), Kestrel/.NET (datos.inpi.gob.ar stats portal), classical
  ASMX SOAP (ws.inpi.gob.ar). All Microsoft. ASMX is end-of-life as
  a Microsoft technology but remains in production at INPI.
- **Fee restructuring (2026)**: INPI Resolución 75/2026 (effective
  2026-04-01, UMAPI indexation effective 2026-05-01) created the
  *Unidad de Medida de Aranceles de Propiedad Industrial* (UMAPI) —
  initial value ARS 360, updated monthly by INDEC's CPI ([HYA IP
  summary](https://www.hyaip.com/es/espacio/incremento-tasas-propiedad-industrial-argentina/)).
  Fee amounts are now expressed in UMAPI units and resolve to ARS at
  monthly cadence. This makes fee mirroring **even more wrong** than
  the default position; link-only is mandatory.

## 10. Verdict

**Verdict: 🔴 red_no_api** for the live register.

INPI Argentina exposes **no public REST/JSON register API** for
patents, trademarks, or designs. The three live register search UIs
at `portaltramites.inpi.gob.ar` (`marcasconsultas`, `PatenteConsultas`,
`ModelosConsultas`) are ASP.NET MVC HTML + a motionCaptcha
draw-a-shape gesture captcha — non-proxyable by repo policy. The SOAP
service at `ws.inpi.gob.ar/wsinpi.asmx` is a **filer portal** (six
`Ingresar_*` operations submit new filings; three `Consulta*`
operations expose narrow read views — TM-name search, TM-owner search,
and your own filer-mailbox notifications). Even the `Consulta`
operations are CUIT-bound and would require BYOK with strong
CUIT-anchoring that the public access form does not contemplate
sharing across multiple end users.

The stats portal at `datos.inpi.gob.ar` is dashboard-only (no record
fidelity). The national open-data portal `datos.gob.ar` lists **zero
INPI datasets** as of 2026-05-18.

The single bridge that *does* yield record-level AR coverage is
**TMview / DesignView** (since 2017-11-20) for trademarks and
industrial designs, accessed transitively via the planned EUIPN
connector. For patents, **EPO INPADOC** covers AR national-route
patents at biblio + family fidelity where they have corresponding EP
publications or PCT entries.

**No connector to build at AR INPI itself.** Sibling pattern to
BR/INPI (also red_no_api on the live register) and several other
Latin American offices that publish neither REST nor cleanly licensed
bulk feeds.

---

## Drift vs. STATE.yaml

STATE.yaml has `rating: tbd` for AR INPI as of the prompt date. This
wave resolves to `red_no_api`. Per-surface ratings (synopsis §3):

| Surface | Rating |
|---|---|
| `portaltramites.inpi.gob.ar/marcasconsultas` (TM register UI) | 🔴 |
| `portaltramites.inpi.gob.ar/PatenteConsultas` (patent register UI) | 🔴 |
| `portaltramites.inpi.gob.ar/ModelosConsultas` (design register UI) | 🔴 |
| `ws.inpi.gob.ar/wsinpi.asmx` (filer SOAP, narrow `Consulta*` reads) | 🔴 |
| `datos.inpi.gob.ar` (stats dashboard) | 🔴 |
| `datos.gob.ar` (national CKAN, 0 INPI datasets) | 🔴 |
| TMview/DesignView bridge (transitive via EUIPN, since 2017) | informational — covered via EUIPN |
| EPO INPADOC bridge (transitive via EPO OPS, partial) | informational — covered via EPO OPS |

## Recommended STATE.yaml resolution

- `rating: red_no_api` (was `tbd`)
- `rating_basis: no public register REST API; live UIs HTML + motionCaptcha; ws.inpi.gob.ar is filer-portal SOAP with three narrow Consulta operations bound to CUIT credentials; datos.inpi.gob.ar is dashboard-only; datos.gob.ar lists 0 INPI datasets; AR pre-PCT (2026 commitment in motion)`
- `connector_status: none`
- `next_action: monitor PCT accession (post-2026-04-30 deadline) — once Argentina joins PCT, WIPO PATENTSCOPE will reach AR national-phase applications; also monitor any future register-API announcement from INPI as part of the Ley 27.275 + Decreto 117/16 open-data obligations`

## Sources (primary)

- INPI portal (ES): [argentina.gob.ar/inpi](https://www.argentina.gob.ar/inpi)
- INPI legacy portal: [inpi.gob.ar](http://www.inpi.gob.ar/)
- Portal de Trámites: [portaltramites.inpi.gob.ar](https://portaltramites.inpi.gob.ar/)
- TM register UI: [portaltramites.inpi.gob.ar/marcasconsultas/busqueda](https://portaltramites.inpi.gob.ar/marcasconsultas/busqueda)
- Patent register UI: [portaltramites.inpi.gob.ar/PatenteConsultas/BusquedaParametros](https://portaltramites.inpi.gob.ar/PatenteConsultas/BusquedaParametros)
- Design register UI: [portaltramites.inpi.gob.ar/ModelosConsultas/BusquedaParametros](https://portaltramites.inpi.gob.ar/ModelosConsultas/BusquedaParametros)
- Filing portal landing: [portaltramites.inpi.gob.ar/Home/SolicitudWS](https://portaltramites.inpi.gob.ar/Home/SolicitudWS)
- Filer SOAP WSDL: [ws.inpi.gob.ar/wsinpi.asmx?WSDL](https://ws.inpi.gob.ar/wsinpi.asmx?WSDL)
- Stats portal: [datos.inpi.gob.ar](https://datos.inpi.gob.ar/Home/EstadisticasINPI) · [Patentes](https://datos.inpi.gob.ar/Home/Patentes)
- INPI fees: [portaltramites.inpi.gob.ar/InfoPortal/Aranceles](https://portaltramites.inpi.gob.ar/InfoPortal/Aranceles) · [Aranceles INPI](https://www.argentina.gob.ar/inpi/aranceles-inpi)
- Fees PDF: [portaltramites.inpi.gob.ar/Documentos/Aranceles_Anexo.pdf](https://portaltramites.inpi.gob.ar/Documentos/Aranceles_Anexo.pdf)
- Open-data page: [argentina.gob.ar/inpi/transparencia-activa/portales-de-datos-abiertos](https://www.argentina.gob.ar/inpi/transparencia-activa/portales-de-datos-abiertos)
- Bases de datos de libre acceso: [argentina.gob.ar/inpi/informacion-tecnologica/bases-de-datos-de-libre-acceso](https://www.argentina.gob.ar/inpi/informacion-tecnologica/bases-de-datos-de-libre-acceso)
- National open-data portal: [datos.gob.ar](https://datos.gob.ar/) · [CKAN search q=INPI](https://datos.gob.ar/api/3/action/package_search?q=INPI&rows=20)
- Ley 24.481 (patentes): [servicios.infoleg.gob.ar/infolegInternet/anexos/35000-39999/35001/texact.htm](https://servicios.infoleg.gob.ar/infolegInternet/anexos/35000-39999/35001/texact.htm)
- Ley 22.362 (marcas): [argentina.gob.ar/normativa/nacional/ley-22362-18803/actualizacion](https://www.argentina.gob.ar/normativa/nacional/ley-22362-18803/actualizacion)
- Ley 22.426 (transferencia de tecnología): [servicios.infoleg.gob.ar/infolegInternet/anexos/15000-19999/18804/norma.htm](https://servicios.infoleg.gob.ar/infolegInternet/anexos/15000-19999/18804/norma.htm)
- Ley 27.275 (acceso a información pública): [servicios.infoleg.gob.ar/infolegInternet/anexos/265000-269999/265949/norma.htm](https://servicios.infoleg.gob.ar/infolegInternet/anexos/265000-269999/265949/norma.htm)
- Decreto 117/16 (datos abiertos): [argentina.gob.ar/normativa/nacional/decreto-117-2016-257755](https://www.argentina.gob.ar/normativa/nacional/decreto-117-2016-257755)
- US-Argentina ARTI (PCT commitment): [palacio.com.ar/en/2026/02/09/argentina-united-statements-agreement-arti-impact-on-patent-prosecution-in-argentina/](https://www.palacio.com.ar/en/2026/02/09/argentina-united-statements-agreement-arti-impact-on-patent-prosecution-in-argentina/)
- INPI joins TMview / DesignView (2017-11-20): [tmdn.org/network/-/argentina-and-moldova-join-tmview](https://www.tmdn.org/network/-/argentina-and-moldova-join-tmview?inheritRedirect=true)
- INPI adopts CPC (2018): [intellectual-property-helpdesk.ec.europa.eu/news-events/news/latin-america-watch-out-inpi-argentina-about-start-using-cpc-2019-01-25_en](https://intellectual-property-helpdesk.ec.europa.eu/news-events/news/latin-america-watch-out-inpi-argentina-about-start-using-cpc-2019-01-25_en)
- WIPO API Catalog: [apicatalog.wipo.int](https://apicatalog.wipo.int/) (probed 2026-05-18; AR INPI not listed)
- WIPO Lex Argentina profile: [wipo.int/wipolex/en/legislation/profile/AR](https://www.wipo.int/wipolex/en/legislation/profile/AR)
