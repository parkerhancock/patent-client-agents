# Oficina Española de Patentes y Marcas (ES/OEPM) — national

**Layer:** national
**Jurisdiction:** ES (WIPO ST.3: ES)
**Issuing body:** Oficina Española de Patentes y Marcas (Spanish Patent and Trade Mark Office, OEPM)
**Rights administered:** patent, utility_model (*modelo de utilidad*), trademark, trade name (*nombre comercial*), industrial design (*diseño industrial*), supplementary protection certificate (SPC), semiconductor topography; Latipat coordination for 18 Latin American offices
**Working languages:** Spanish (primary); English (institutional pages + EN versions of Sede electrónica + Opendata documentation); the BOPI gazette is Spanish-only
**Connector status:** **planned (yellow — BYOK)**
**Last verified:** 2026-05-18
**Manifest entry:** not yet listed (planned)

**Detail surveys:**
- [`waves/2026-05-18-secondary-nationals-wave/es-oepm.md`](../waves/2026-05-18-secondary-nationals-wave/es-oepm.md) — 2026-05-18 grounded API discovery

**Higher layers covering this office transitively:**
- **EPO INPADOC / OPS** (via [`regional/epo.md`](../regional/epo.md)) — ES-validated EP patents at biblio/family/legal-events fidelity; Spain feeds bibliographic data and legal status to the EPO Federated Register Service per [Lexology Federated European Patent Register overview](https://www.lexology.com/library/detail.aspx?g=81e0bad2-50fd-4dbf-82cb-a69c70c0d7de). Spain is an EPC contracting state.
- **EUIPO** (via planned `regional/euipo.md`) — EUTMs designating ES, Community designs (RCDs / REUDs). ES-national-only TMs and designs flow into [TMview / DesignView via the EUIPN Common Tools Integration (CTI)](https://www.tmdn.org/network/-/common-tools-integration-implemented-in-spain) back-office bridge — Spain implemented CTI in cooperation with EUIPO.
- **WIPO Madrid Monitor / Hague Express** — Madrid IRs designating ES / Hague IRs designating ES.
- **UPC — N/A.** Spain is one of three EU Member States (with Poland and Croatia) that did NOT sign the UPC Agreement and is not part of the UPC system, per [Baker McKenzie EMEA UPC long-arm (2026-02)](https://www.bakermckenzie.com/en/insight/publications/2026/02/emea-upcs-long-arm-jurisdiction) and the [Kluwer Patent Blog notice on Spain's continued non-participation](https://legalblogs.wolterskluwer.com/patent-blog/despite-the-defeat-at-the-cjeu-spain-will-not-join-the-unitary-patent-system/). ES patents never route through the `upc_decisions` connector — they stay national/EPO only, with disputes in the Tribunales de lo Mercantil de Madrid and Barcelona.
- **Latipat-Espacenet** — Spain coordinates the Latipat cooperation among 18 Latin American offices + EPO; Latin American patent data flows through [lp.espacenet.com](https://lp.espacenet.com/?locale=en_LP) and is reachable via EPO OPS.

---

## §1 Mission

OEPM is Spain's national IP office — the sole authoritative registrar
for ES national patents, ES utility models (*modelo de utilidad*), ES
trademarks and trade names, ES industrial designs, and Spanish
supplementary protection certificates. It also operates the
**Boletín Oficial de la Propiedad Industrial (BOPI)** gazette and
coordinates the **Latipat** project, the Spanish/Portuguese-language
patent backfile for 18 Latin American offices + EPO ([Proyecto Latipat](https://www.oepm.es/en/sobre-OEPM/nosotros/cooperacion-regiones-y-organizaciones-internacionales/con-la-organizacion-mundial-de-la-propiedad-intelectual-OMPI/proyecto-LATIPAT/)).

Because Spain is an EPC contracting state and an EU member, most
"Spanish patents" of commercial scale are EP-route (covered by EPO
OPS) and most "Spanish trademarks" of scale are EUTMs (covered by
EUIPO). **Crucially, Spain is the major EU non-UPC holdout** — ES
patent disputes never route through the UPC connector. OEPM's
genuine value-add for agents is the **ES-national-only slice**: ES
national-route patents, ES utility models (no novelty examination at
filing — distinct right), ES national-only TMs and designs, the
expediente (file history) at register fidelity, ES SPCs, and the BOPI
gazette in Spanish-language XML.

## §2 What's unique here

- **ES national-route patents** — filed directly at OEPM, not via EP. Spanish-language full text.
- **ES utility models (*modelo de utilidad*)** — distinct national right (10-year term, novelty examined only on opposition request) per [OEPM utility model page (EN)](https://www.oepm.es/en/invenciones/Presentar-una-solicitud/solicitar-un-modelo-de-utilidad/); sometimes in INPADOC but not at full fidelity.
- **ES national-only trademarks** — filed at OEPM, not via Madrid IR or EUTM. Surfaces in TMview via CTI but full register events (oppositions, renewals, transfers) live at OEPM.
- **ES national-only designs** — filed at OEPM, not via Hague or RCD. Same CTI / DesignView story.
- **Live ES file history / expediente** — accessible through CEO (Consulta de Expedientes OEPM), the successor to legacy SITADEX (sunset for distinctive signs 2017-05-30 per [SITADEX-to-CEO migration notice](https://oepm.es/es/detalle-noticia/La-aplicacion-de-Consulta-de-Situacion-de-Expedientes-SITADEX-seguira-actualizando-los-relativos-a-Signos-Distintivos-hasta-el-30-de-mayo-de-2017/)); covers bibliographic data, processing actions, assignments, licenses, and documents per [CEO Sede page (EN)](https://sede.oepm.gob.es/eSede/datos/en/servicios-web/ceo/).
- **ES SPCs** — Spanish supplementary protection certificate register status.
- **BOPI gazette** — daily official gazette with [updated 2024 XSD for Tomo 2 (Invenciones)](https://www.oepm.es/es/detalle-noticia/Actualizacion-del-esquema-XSD-del-Boletin-Oficial-de-la-Propiedad-Industrial-Tomo-2-Invenciones-para-descarga-en-formato-XML/); historical archive 1886-1997 hosted by UAM at [`historico.oepm.es/bopi.php`](http://historico.oepm.es/bopi.php).
- **Pre-EPO ES patent backfile (1826 onward)** — INVENES holds bibliographic data since 1826 and ~1.5M full-text documents from the 1940s onward; the historical archive 1878-1940 ships as a [datos.gob.es dataset](https://datos.gob.es/en/catalogo/ea0038829-archivo-historico-base-de-datos-de-solicitudes-de-patentes-1878-1940-de-la-oficina-espanola-de-patentes-y-marcas-oepm).
- **Latipat coordination** — 18 Latin American patent offices + EPO cooperate through OEPM's leadership; data surfaces via Espacenet-Latipat.

## §3 Programmatic surfaces

### OEPM Web Services catalogue (the documented programmatic path)

| Field | Value |
|---|---|
| Endpoint | Five SOAP/XML services advertised at [`sede.oepm.gob.es/eSede/datos/es/servicios-web/`](https://sede.oepm.gob.es/eSede/datos/es/servicios-web/) — INVENES + Diseños, CEO, CLINMAR, Localizador de marcas, BOPI-LOPD-protected |
| Auth | **free username + password issued via [Formulario de acceso a servicios web](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/acceso-a-servicios-web/)** — per-applicant; no OAuth, no shared-key option contemplated on the public form |
| Format | SOAP/XML; per-service WSDL + PDF technical manual distributed to credentialed users (not on public web) |
| Rate limit | not published on public web; may be specified in per-service registered-user PDFs |
| ToS posture | [Aviso legal Opendata OEPM](https://sede.oepm.gob.es/eSede/datos/es/aviso-legal/) at the Opendata layer permits commercial + non-commercial reuse with attribution; SOAP-service-specific licence not separately published on public web |
| Rating (zero-infra proxy) | 🟡 **Yellow — BYOK** |
| Primary source | [Servicios web de la OEPM landing (ES)](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/) |

This is the canonical machine-to-machine path — OEPM's own page reads
"Los Servicios Web (SW) son una tecnología, 'máquina-máquina', que
utiliza un conjunto de protocolos y estándares que sirven para el
intercambio de datos entre aplicaciones." Per-service detail:

- **INVENES + Diseños** ([landing EN](https://www.oepm.es/en/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/INVENES-Y-DISENOS/)) — patent/utility-model search across ES + Latipat + ES national designs.
- **CEO** ([landing EN](https://www.oepm.es/en/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/CEO/)) — file history / expediente status across all modalities; the SITADEX successor.
- **CLINMAR** ([landing EN](https://www.oepm.es/en/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/CLINMAR/)) — Nice classification harmonised database (cooperation with EUIPO; redirects to EUIPO TMclass for ongoing use).
- **Localizador de marcas** ([Sede ES](https://sede.oepm.gob.es/eSede/datos/es/servicios-web/localizador-de-marcas/)) — fielded TM/distinctive-sign search.
- **Datos protegidos LOPD** ([form](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/lopd/)) — personal-data-bearing BOPI / Opendata feeds, separate consent track.

What pushes this to yellow rather than green: per-applicant credentials,
WSDL behind registration wall, hosted-proxy posture not addressed by
the public access form.

### OEPM Opendata bulk catalogues

| Field | Value |
|---|---|
| Endpoint | [`sede.oepm.gob.es/eSede/datos/`](https://sede.oepm.gob.es/eSede/datos/es/) (master) + per-catalogue download URLs |
| Auth | **none** for main inventions/marks/designs catalogues; free **LOPD form** for personal-data-bearing distributions |
| Format | XML — **WIPO ST.36** (inventions, since 2019-01-01; pre-2019 proprietary), **WIPO ST.66** (TMs), **WIPO ST.86** (designs, [XSD updated 2024](https://www.oepm.es/en/sobre-OEPM/noticias-y-eventos/noticias/noticiap/Update-of-the-XSD-schemas-of-the-OEPM-Opendata-portal-for-XML-format-download-of-data-from-the-Industrial-Designs-Data-Catalog-bibliographic-data-and-images/)) |
| ToS posture | [Aviso legal](https://sede.oepm.gob.es/eSede/datos/es/aviso-legal/) — **commercial + non-commercial reuse permitted** with attribution ("Origen de los datos: Oficina Española de Patentes y Marcas"); statutory basis [Ley 37/2007](https://www.boe.es/buscar/act.php?id=BOE-A-2007-19814) transposing [EU Open Data Directive 2019/1024](https://eur-lex.europa.eu/eli/dir/2019/1024) |
| Rating (zero-infra proxy) | 🔴 Red against zero-infra — bulk only — but **clean license posture** informs the credentialed SOAP path |
| Primary source | [OpenData Project EN](https://sede.oepm.gob.es/eSede/datos/en/) · [Catálogo invenciones EN](https://sede.oepm.gob.es/eSede/datos/en/catalogo/datos.html?a=1&catalogo=invenciones) · [Catálogo marcas ES](https://sede.oepm.gob.es/eSede/datos/es/catalogo/datos.html?catalogo=marcas) |

Daily / monthly / yearly publication cadence per the inventions
catalogue page. The license posture is the most informative governance
signal — Spain's transposition of the EU Open Data Directive applies
**by default** to OEPM's public data, with attribution and
no-distortion as the only material constraints. Bulk ingestion is out
of scope for the zero-infra constraint, but the redistribution
permission is the legal scaffolding that makes a hosted-proxy posture
plausible if shared-key access is later negotiated through the
acceso-a-servicios-web form.

### BOPI gazette download

| Field | Value |
|---|---|
| Endpoint | [`sede.oepm.gob.es/bopiweb/descargaPublicaciones/`](https://sede.oepm.gob.es/bopiweb/descargaPublicaciones/formBusqueda.action) (Struts2 `.action`) |
| Auth | XML/HTML downloads available to registered users; PDF unrestricted |
| Format | PDF (unrestricted), XML/HTML (registered) — proprietary XSD with [updated Tomo 2 schema 2024](https://www.oepm.es/es/detalle-noticia/Actualizacion-del-esquema-XSD-del-Boletin-Oficial-de-la-Propiedad-Industrial-Tomo-2-Invenciones-para-descarga-en-formato-XML/) |
| Rating | 🔴 Red — Struts2 server-rendered UI for the queryable layer; not a programmatic surface for arbitrary queries |
| Primary source | [BOPI page (EN)](https://sede.oepm.gob.es/eSede/en/consultas/boletin-oficial-de-la-propiedad-industrial/) |

Same Struts2 pattern as NL/RVO's eRegister and AT/ÖPA's pre-see.ip
register — not a programmatic surface. The BOPI is reachable
indirectly through the Opendata catalogues (bulk) or the CEO SOAP
service (file-level).

### Web search UIs (informational only)

| Surface | URL | Rating | Notes |
|---|---|---|---|
| **INVENES** web UI | [`consultas2.oepm.es/InvenesWeb/`](https://consultas2.oepm.es/InvenesWeb/faces/busquedaInternet.jsp) | 🔴 | JSF; UI on top of the INVENES SOAP backend — not a separate API |
| **CEO** web UI | [`consultas2.oepm.es/ceo/`](https://consultas2.oepm.es/ceo/) | 🔴 | Web frontend of the CEO SOAP service |
| **Localizador de Marcas** web UI | [`consultas2.oepm.es/LocalizadorWeb/`](https://consultas2.oepm.es/LocalizadorWeb/) | 🔴 | Web frontend of the Localizador SOAP service |
| **BOPI Histórico** (1886-1997) | [`historico.oepm.es/bopi.php`](http://historico.oepm.es/bopi.php) | 🔴 | PHP UI on UAM hosting; historical only |
| **Latipat-Espacenet** | [`lp.espacenet.com`](https://lp.espacenet.com/?locale=en_LP) | informational — covered via EPO OPS |

Unlike SE/PRV's `search.prv.se` SPA on undocumented JSON, the OEPM
search UIs are classical JSF/Struts2 server-rendered pages — the SOAP
web services are the intentional programmatic path, not a
reverse-engineered JSON layer behind the UI.

### WIPO IP API Catalog

| Field | Value |
|---|---|
| Endpoint | [`apicatalog.wipo.int`](https://apicatalog.wipo.int/) |
| Result | **0 OEPM entries** as of 2026-05-18 (179 total across DPMA, EPO, EUIPO, IP Australia, JPO, MOIP Korea, QAZ, UPRP, USPTO, WIPO) |
| Rating | informational — confirms the SOAP services are undocumented from the canonical-inventory standpoint |

## §4 Fees

**Policy: link only.**

OEPM publishes fee schedules (in EUR) covering patent and utility
model filing, search, examination, grant, opposition, renewal, and
SPC fees; trademark filing per class and renewals (multi-class
schedule); industrial design filing per design and renewals;
miscellaneous services (file inspection, certified copies, priority
documents, BOPI publication of acts). Statutory basis is the **Ley
24/2015, de 24 de julio, de Patentes** (Patents Act 2015), the **Ley
17/2001, de 7 de diciembre, de Marcas** (Trademarks Act), and the
**Ley 20/2003, de 7 de julio, de Protección Jurídica del Diseño
Industrial** (Industrial Designs Act), each with implementing fee
schedules updated annually via the *Ley de Presupuestos Generales del
Estado* (national budget law).

- **Official patent fee schedule:** [OEPM patent fees (Tasas, Pagos y reintegros — Invenciones, ES)](https://www.oepm.es/es/invenciones/Presentar-una-solicitud/tasas-pagos-y-reintegros/)
- **Official trademark fee schedule:** [OEPM trademark fees (Marcas y nombres comerciales — ES)](https://www.oepm.es/es/marcas-y-nombres-comerciales/presentar-una-solicitud/)
- **Statutory basis (patents):** [Ley 24/2015, de Patentes — BOE](https://www.boe.es/buscar/act.php?id=BOE-A-2015-8328)
- **Statutory basis (trademarks):** [Ley 17/2001, de Marcas — BOE](https://www.boe.es/buscar/act.php?id=BOE-A-2001-23093)
- **Statutory basis (designs):** [Ley 20/2003, de Protección Jurídica del Diseño Industrial — BOE](https://www.boe.es/buscar/act.php?id=BOE-A-2003-13615)
- **Live BOPI fee publication track:** [BOPI viewer](https://sede.oepm.gob.es/bopiweb/descargaPublicaciones/formBusqueda.action) — fee-schedule updates published as administrative acts

Notable discount programmes *(name + eligibility — no amounts or dates)*:

- **Reducciones para emprendedores e investigadores** — fee reductions for individuals, SMEs, universities, and public research organisations under [Ley 24/2015 art. 186](https://www.boe.es/buscar/act.php?id=BOE-A-2015-8328).
- **SME Fund (EUIPO Ideas Powered for Business)** — partial reimbursement of national TM and design fees, administered jointly with EUIPO for ES applicants.

## §5 Connector strategy

### What we cover today

- **ES-validated EP patents at biblio / family / legal-events fidelity** — transitively via [`patent_client_agents.epo_ops`](../regional/epo.md) (country code `ES`).
- **EUTMs designating ES and Community designs (RCD / REUD)** — transitively via the planned EUIPO connector.
- **ES national TMs and designs (TMview / DesignView)** — transitively via [CTI](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI) through the planned EUIPO connector.
- **Madrid IRs / Hague IRs designating ES** — via planned WIPO Madrid / Hague connectors.
- **Latipat patents** — transitively via EPO OPS through the Espacenet-Latipat interface.
- **NOT covered: UPC.** Spain is not in the UPC system. ES patent disputes route through national civil courts only (out of scope for this connector layer).

### What we should add (planned — yellow, BYOK)

- **`patent_client_agents.oepm`** — JPO-shaped BYOK SOAP client. Per-user credentials obtained via the [acceso-a-servicios-web form](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/acceso-a-servicios-web/). One client class per right modality:
  - `OepmInvencionesClient` (INVENES + Diseños) — ES national patents, utility models, designs, Latipat.
  - `OepmCeoClient` — file history across all modalities (the SITADEX successor).
  - `OepmLocalizadorClient` — TM / distinctive sign search.
  - `OepmClinmarClient` — Nice classification (low priority; EUIPO TMclass covers same).

**Closes the ES-national-only patent + utility-model + TM + design + expediente + SPC gaps.**
Estimated 1-2 weeks build once credentials are issued — SOAP via
`zeep` if WSDLs ship to credentialed users, otherwise hand-rolled
`lxml` clients. Response models derive from WIPO ST.36 / ST.66 / ST.86
schemas (same standards as DPMA, EUIPO RCD bulk, and INPI designs).

### What we should NOT add

- **HTML scrape of `consultas2.oepm.es` UIs.** The SOAP services are the documented programmatic path. JSF / Struts2 UIs are anti-pattern.
- **HTML scrape of `sede.oepm.gob.es/bopiweb/`.** Same anti-pattern.
- **Bulk ingestion of `sede.oepm.gob.es/eSede/datos/` Opendata catalogues.** Violates the zero-infra constraint — these are weekly/monthly ZIP/XML drops. The license is permissive but bulk ingestion is out of scope.
- **HTML scrape of `historico.oepm.es/bopi.php`.** Historical-only PHP UI; not a connector target.
- **Wrapping a third-party commercial proxy** (e.g. [Iberinform's "API consulta OEPM"](https://www.iberinform.es/en/productos/apis)). Adds a paid intermediary without the upstream guarantees.

### Next steps

1. **Submit the [acceso-a-servicios-web form](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/acceso-a-servicios-web/)** identifying the project. In the same submission, request clarification on:
   - whether **shared-technical-account use** is permitted under the access conditions (would unlock hosted-proxy posture, similar to EPO OPS);
   - whether the per-service **WSDLs and technical PDFs** can be referenced in published documentation;
   - whether any **rate limits** or per-call quotas apply.
2. **If shared-key permitted:** rerate to 🟢 green-restricted (similar to EPO OPS shape — shared key with attribution); build a hosted proxy.
3. **If shared-key not permitted (likely):** treat as yellow_byok, build the per-user BYOK pattern uniformly with JPO and (planned) INPI BYOK paths.
4. **Independent of credentials:** confirm ES utility model coverage depth in EPO INPADOC empirically — if INPADOC carries ES UMs at full fidelity, the priority of the INVENES SOAP client drops.

## §6 Open questions

- **Shared-key vs. per-user policy.** Direct enquiry to OEPM (`opendata@oepm.es` / [Sede contact](https://sede.oepm.gob.es/eSede/datos/es/contacto/)) needed. The acceso-a-servicios-web form is per-applicant; whether a project applicant can request a shared technical account is unstated.
- **WSDL public availability.** Are the WSDL files downloadable post-registration from a known URL, or do they ship as PDF attachments to the credential-issue email?
- **Rate limits.** Not on public web. Per-service registered-user PDFs likely state — empirical probe after registration.
- **Aviso legal applicability to credentialed SOAP services.** The Aviso legal is hosted on the Opendata section; whether the same redistribution permission applies to the credentialed SOAP layer is the gating legal question for any hosted-proxy posture.
- **CEO vs. legacy SITADEX completeness.** Per [news article](https://oepm.es/es/detalle-noticia/La-aplicacion-de-Consulta-de-Situacion-de-Expedientes-SITADEX-seguira-actualizando-los-relativos-a-Signos-Distintivos-hasta-el-30-de-mayo-de-2017/), SITADEX was sunset 2017-05-30 for distinctive signs. The [datos.gob.es SITADEX dataset entry](https://datos.gob.es/en/catalogo/ea0038829-sitadex-base-de-datos-de-la-situacion-juridica-de-expedientes-de-la-oficina-espanola-de-patentes-y-marcas-oepm) is still indexed — confirm it points to CEO data or is dormant.
- **ES utility model coverage in INPADOC.** Empirical probe needed — if INPADOC carries ES UMs at full fidelity, BYOK priority drops.
- **DesignView fidelity vs. INVENES Diseños.** Does INVENES surface ES-only fields that DesignView via CTI drops in transit (Locarno classes, sequence in multi-design filings, expediente events)?
- **Latipat-via-INVENES fidelity vs. Latipat-via-Espacenet.** The Latipat cooperation runs through OEPM; INVENES may carry per-national fields that the EPO ingestion strips.

## §7 References

Primary sources only — `oepm.es`, `sede.oepm.gob.es`,
`consultas2.oepm.es`, `datos.gob.es`, `boe.es` (statutes),
`apicatalog.wipo.int`, EUIPN.

**Service overviews:**
- [OEPM portal home (EN)](https://www.oepm.es/en/)
- [Sede electrónica OEPM (ES)](https://sede.oepm.gob.es/)
- [Servicios web de la OEPM (ES)](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/)
- [Servicios web (SW) — Sede](https://sede.oepm.gob.es/eSede/datos/es/servicios-web/)
- [Formulario de acceso a servicios web](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/acceso-a-servicios-web/)
- [INVENES & DESIGNS SW (EN)](https://www.oepm.es/en/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/INVENES-Y-DISENOS/)
- [SW Invenes and Designs — Sede (EN)](https://sede.oepm.gob.es/eSede/datos/en/servicios-web/invenes-y-disenos/)
- [CEO web service (EN)](https://www.oepm.es/en/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/CEO/)
- [CEO — Sede (EN)](https://sede.oepm.gob.es/eSede/datos/en/servicios-web/ceo/)
- [CLINMAR web service (EN)](https://www.oepm.es/en/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/CLINMAR/)
- [Localizador de marcas — Sede](https://sede.oepm.gob.es/eSede/datos/es/servicios-web/localizador-de-marcas/)
- [LOPD form — protected BOPI / Opendata](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/lopd/)

**Open data + licenses:**
- [OpenData Project — Sede (EN)](https://sede.oepm.gob.es/eSede/datos/en/)
- [Aviso legal Opendata OEPM (ES)](https://sede.oepm.gob.es/eSede/datos/es/aviso-legal/)
- [Data formats — WIPO ST.36/ST.66/ST.86 (EN)](https://sede.oepm.gob.es/eSede/datos/en/especificacion-de-datos/formato-de-los-datos/)
- [Catálogo OpenData OEPM (datos.gob.es)](https://datos.gob.es/es/catalogo/ea0038829-catalogo-opendata-de-la-oficina-espanola-de-patentes-y-marcas-oepm)
- [BOPI dataset on datos.gob.es](https://datos.gob.es/en/catalogo/ea0038829-bopi-boletin-oficial-de-la-propiedad-industrial)
- [SITADEX dataset on datos.gob.es](https://datos.gob.es/en/catalogo/ea0038829-sitadex-base-de-datos-de-la-situacion-juridica-de-expedientes-de-la-oficina-espanola-de-patentes-y-marcas-oepm)
- [Historical archive 1878-1940 dataset](https://datos.gob.es/en/catalogo/ea0038829-archivo-historico-base-de-datos-de-solicitudes-de-patentes-1878-1940-de-la-oficina-espanola-de-patentes-y-marcas-oepm)
- [Archivo histórico 1930-1966 patentes concedidas BOPI](https://datos.gob.es/en/catalogo/ea0038829-archivo-historico-base-de-datos-de-patentes-concedidas-y-publicadas-en-el-bopi-1930-1966-de-la-oficina-espanola-de-patentes-y-marcas-oepm)
- [Industrial designs XSD update notice 2024](https://www.oepm.es/en/sobre-OEPM/noticias-y-eventos/noticias/noticiap/Update-of-the-XSD-schemas-of-the-OEPM-Opendata-portal-for-XML-format-download-of-data-from-the-Industrial-Designs-Data-Catalog-bibliographic-data-and-images/)

**BOPI:**
- [BOPI: Spanish Official Industrial Property Gazette (EN)](https://sede.oepm.gob.es/eSede/en/consultas/boletin-oficial-de-la-propiedad-industrial/)
- [BOPI descarga publicaciones (Struts2 UI)](https://sede.oepm.gob.es/bopiweb/descargaPublicaciones/formBusqueda.action)
- [BOPI Histórico 1886-1997 (UAM)](http://historico.oepm.es/bopi.php)
- [BOPI Tomo 2 XSD update notice](https://www.oepm.es/es/detalle-noticia/Actualizacion-del-esquema-XSD-del-Boletin-Oficial-de-la-Propiedad-Industrial-Tomo-2-Invenciones-para-descarga-en-formato-XML/)

**Substantive law (Spanish statutes via BOE):**
- [Ley 24/2015, de Patentes — BOE](https://www.boe.es/buscar/act.php?id=BOE-A-2015-8328)
- [Ley 17/2001, de Marcas — BOE](https://www.boe.es/buscar/act.php?id=BOE-A-2001-23093)
- [Ley 20/2003, de Protección Jurídica del Diseño Industrial — BOE](https://www.boe.es/buscar/act.php?id=BOE-A-2003-13615)
- [Ley 37/2007, sobre reutilización de la información del sector público — BOE](https://www.boe.es/buscar/act.php?id=BOE-A-2007-19814) (transposes [EU Directive 2019/1024](https://eur-lex.europa.eu/eli/dir/2019/1024))

**Cross-office context:**
- [WIPO IP API Catalog](https://apicatalog.wipo.int/) — probed 2026-05-18; 0 OEPM entries
- [PCT Applicant's Guide — Spain](https://pctlegal.wipo.int/eGuide/view-doc.xhtml?doc-code=ES&doc-lang=en)
- [Latipat-Espacenet interface](https://lp.espacenet.com/?locale=en_LP) — coordinated by OEPM
- [Proyecto LATIPAT](https://www.oepm.es/en/sobre-OEPM/nosotros/cooperacion-regiones-y-organizaciones-internacionales/con-la-organizacion-mundial-de-la-propiedad-intelectual-OMPI/proyecto-LATIPAT/)
- [Common Tools Integration implemented in Spain (TMDN news)](https://www.tmdn.org/network/-/common-tools-integration-implemented-in-spain) — ES national TMs and designs into TMview / DesignView via [CTI](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI)
- [Federated European Patent Register overview — Lexology](https://www.lexology.com/library/detail.aspx?g=81e0bad2-50fd-4dbf-82cb-a69c70c0d7de) — Spain provides FRS deep-linking

**UPC non-participation:**
- [Despite the defeat at the CJEU, Spain will not join the Unitary Patent system — Kluwer Patent Blog](https://legalblogs.wolterskluwer.com/patent-blog/despite-the-defeat-at-the-cjeu-spain-will-not-join-the-unitary-patent-system/)
- [Baker McKenzie EMEA UPC long-arm (2026-02)](https://www.bakermckenzie.com/en/insight/publications/2026/02/emea-upcs-long-arm-jurisdiction) — restates Spain / Poland / Croatia non-participation as of February 2026

**Detail surveys + waves:**
- [`waves/2026-05-18-secondary-nationals-wave/es-oepm.md`](../waves/2026-05-18-secondary-nationals-wave/es-oepm.md) — 2026-05-18 grounded API discovery

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-18 | Initial synopsis; rating **`yellow_byok`**. Findings: (a) OEPM publishes a documented catalogue of five free SOAP/XML web services (INVENES + Diseños, CEO, CLINMAR, Localizador de marcas, BOPI-LOPD-protected) at [`sede.oepm.gob.es/eSede/datos/es/servicios-web/`](https://sede.oepm.gob.es/eSede/datos/es/servicios-web/), all gated by a per-applicant [acceso-a-servicios-web](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/acceso-a-servicios-web/) form issuing free username/password credentials — JPO-shaped BYOK pattern; (b) parallel Opendata bulk distributions ship in **WIPO ST.36 (since 2019-01-01), ST.66, and ST.86** under a permissive [Aviso legal](https://sede.oepm.gob.es/eSede/datos/es/aviso-legal/) explicitly authorising commercial and non-commercial reuse with attribution, under the statutory cover of [Ley 37/2007](https://www.boe.es/buscar/act.php?id=BOE-A-2007-19814) transposing [EU Directive 2019/1024](https://eur-lex.europa.eu/eli/dir/2019/1024); (c) Spain is **NOT in the UPC system** per [Baker McKenzie 2026-02](https://www.bakermckenzie.com/en/insight/publications/2026/02/emea-upcs-long-arm-jurisdiction) — ES patent disputes route through national courts (`Tribunales de lo Mercantil de Madrid / Barcelona`) only; (d) ES national TMs and designs flow into TMview / DesignView through the EUIPN [CTI](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI) back-office bridge — the SOAP path adds full register-event fidelity beyond CTI's bibliographic slice; (e) [WIPO IP API Catalog](https://apicatalog.wipo.int/) returns 0 OEPM entries — services are undocumented from the canonical-inventory standpoint; (f) the OEPM web search UIs at `consultas2.oepm.es` are classical JSF/Struts2 server-rendered pages — unlike SE/PRV's SPA-on-undocumented-JSON pattern, the documented SOAP services are the intended programmatic path, not a reverse-engineerable JSON layer. Connector status: **planned (yellow — BYOK)**; queue `patent_client_agents.oepm` as a JPO-shaped client once credentials issued. Highest-priority gap closure: ES utility models, ES-national-only TMs / designs, and CEO file-history fidelity. | [waves/2026-05-18-secondary-nationals-wave/es-oepm.md](../waves/2026-05-18-secondary-nationals-wave/es-oepm.md) |
