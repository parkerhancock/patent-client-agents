# OEPM Spain (ES) — Patents, Trademarks, Designs API Discovery

**Date:** 2026-05-18
**Scope:** Determine whether the **Oficina Española de Patentes y
Marcas** (OEPM, the Spanish Patent and Trade Mark Office) exposes a
public, queryable REST/JSON/XML API that we can proxy at runtime, with
zero infrastructure on our side. Bulk dumps and HTML-only surfaces
would be a **red** verdict; per-user BYOK is **yellow**;
undocumented-but-unauthenticated stable JSON is **green**. Because
Spain is the major EU holdout that did NOT ratify the UPC Agreement
([Kluwer Patent Blog 2015](https://legalblogs.wolterskluwer.com/patent-blog/despite-the-defeat-at-the-cjeu-spain-will-not-join-the-unitary-patent-system/),
restated 2026-02 in [Baker McKenzie EMEA UPC long-arm](https://www.bakermckenzie.com/en/insight/publications/2026/02/emea-upcs-long-arm-jurisdiction):
"Spain, Poland and Croatia have not signed the agreement and are not
part of the UPC system"), ES patents never route through the UPC
connector — they stay national or EPO-validated, period.

**TL;DR — Verdict: 🟡 yellow_byok.** OEPM publishes a documented
catalogue of **five free SOAP/XML web services** at
[`sede.oepm.gob.es/eSede/datos/es/servicios-web/`](https://sede.oepm.gob.es/eSede/datos/es/servicios-web/)
covering the four IP rights agents actually care about (patents +
utility models, designs, trademarks/distinctive signs, classifications).
Every service is **free**, **machine-to-machine by design** (the
OEPM page reads: *"Los Servicios Web (SW) son una tecnología,
'máquina-máquina', que utiliza un conjunto de protocolos y estándares
que sirven para el intercambio de datos entre aplicaciones"*), and
**gated by a registration form** at
[`oepm.es/.../acceso-a-servicios-web/`](https://www.oepm.es/en/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/acceso-a-servicios-web/)
that issues a username/password. There is also a separate Opendata
bulk download program at [`sede.oepm.gob.es/eSede/datos/`](https://sede.oepm.gob.es/eSede/datos/es/)
shipping XML in WIPO ST.36 (since 2019-01-01), ST.66, and ST.86
formats with a published [Aviso legal](https://sede.oepm.gob.es/eSede/datos/es/aviso-legal/)
that explicitly permits commercial and non-commercial reuse provided
the source is cited ("Origin of the data: Oficina Española de Patentes
y Marcas"). What OEPM does **NOT** publish: a documented REST/JSON
surface; an OpenAPI/Swagger spec; an OAuth2 stack; an entry in the
[WIPO IP API Catalog](https://apicatalog.wipo.int/) (probed 2026-05-18
— OEPM is absent from the 179-entry inventory). The shape is
recognisably **JPO-like** — free per-user credentials, machine-to-
machine designation, no shared-key option. Not a hosted-proxy
candidate; a clean **BYOK** candidate.

**Material distinguishers vs. the wave so far:**
- **vs. SE/PRV (green undocumented):** OEPM has *documentation* (manuals, WSDL specs, access form, Aviso legal permitting redistribution) but *requires registration*. PRV had no docs but no auth either. OEPM is more like a JPO BYOK shape; PRV is more like a Google Patents zero-auth shape.
- **vs. AT/ÖPA (red, personal-use Impressum):** OEPM has the opposite legal posture — explicit redistribution permission *with* attribution, applying [Ley 37/2007](https://www.boe.es/buscar/act.php?id=BOE-A-2007-19814) (PSI Directive transposition) which is permissive by default. ÖPA's Impressum forbids commercial use without written consent; OEPM's Aviso legal grants it.
- **vs. NL/RVO (red no API):** OEPM has documented SOAP services with WSDLs and a developer access form; NL has nothing beyond Struts2 HTML.
- **vs. FR/INPI (yellow_byok via api-gateway.inpi.fr):** Conceptually similar — both require a free per-user account, both have documented technical APIs. INPI is REST/JSON with session tokens and explicit quotas (10 req/min, 10k/day); OEPM is older SOAP/XML with no published rate limits but a stricter registration form requiring an `acceso-a-servicios-web` application.

---

## 1. Endpoint inventory

### 1.1 OEPM web-service catalogue ([`sede.oepm.gob.es/eSede/datos/es/servicios-web/`](https://sede.oepm.gob.es/eSede/datos/es/servicios-web/))

Five services published. Each has its own landing page on the OEPM
informational portal (`oepm.es`) and a sister page on the Sede
electrónica (`sede.oepm.gob.es`).

| # | Service | Right(s) | Landing (oepm.es) | Sede page |
|---|---|---|---|---|
| 1 | **INVENES + Diseños** (patents/utility models/Latipat + national designs) | patent, utility model, design | [INVENES & DESIGNS SW (EN)](https://www.oepm.es/en/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/INVENES-Y-DISENOS/) | [SW Invenes and Designs (EN)](https://sede.oepm.gob.es/eSede/datos/en/servicios-web/invenes-y-disenos/) |
| 2 | **CEO** (Consulta de Expedientes — file/dossier status) | patent, utility model, TM, design (all modalities) | [CEO web service (EN)](https://www.oepm.es/en/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/CEO/) | [CEO (EN)](https://sede.oepm.gob.es/eSede/datos/en/servicios-web/ceo/) |
| 3 | **CLINMAR** (Nice classification harmonized DB) | trademark classification metadata | [CLINMAR web service (EN)](https://www.oepm.es/en/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/CLINMAR/) | [SW Clinmar (EN)](https://sede.oepm.gob.es/eSede/datos/en/servicios-web/clinmar/) |
| 4 | **Localizador de marcas** (TM locator / fielded search) | trademark, distinctive signs | n/a (Sede-only) | [Localizador de marcas (ES)](https://sede.oepm.gob.es/eSede/datos/es/servicios-web/localizador-de-marcas/) |
| 5 | **Datos protegidos BOPI + Opendata** (LOPD access form for protected BOPI feeds) | TM/design BOPI XML | [LOPD access form](https://www.oepm.es/en/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/lopd/) | [Formulario datos protegidos](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/lopd/) |

All five share a single access path:

> *"Para acceder a los servicios web es necesario cumplimentar el formulario que la OEPM dispone al efecto, en el que se solicita acceso y se proporcionan unas credenciales (usuario y contraseña)."*

— [Servicios web de la OEPM](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/) (ES landing page). The form itself is [Formulario de acceso a servicios web](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/acceso-a-servicios-web/).

### 1.2 Opendata bulk distributions ([`sede.oepm.gob.es/eSede/datos/`](https://sede.oepm.gob.es/eSede/datos/es/))

Free, unauthenticated, downloadable bulk publications in WIPO standard XML:

| Catalogue | Format | Standard | URL |
|---|---|---|---|
| Inventions (patents + utility models + EP-ES + PCT-ES) | XML/SGML/PDF | **WIPO ST.36** (since 2019-01-01); pre-2019 = proprietary XML | [Catálogo invenciones (EN)](https://sede.oepm.gob.es/eSede/datos/en/catalogo/datos.html?catalogo=invenciones) |
| Trademarks & trade names | XML | **WIPO ST.66** | [Catálogo marcas (ES)](https://sede.oepm.gob.es/eSede/datos/es/catalogo/datos.html?catalogo=marcas) |
| Industrial designs | XML | **WIPO ST.86** | [Update XSD designs — news 2024](https://www.oepm.es/en/sobre-OEPM/noticias-y-eventos/noticias/noticiap/Update-of-the-XSD-schemas-of-the-OEPM-Opendata-portal-for-XML-format-download-of-data-from-the-Industrial-Designs-Data-Catalog-bibliographic-data-and-images/) |
| BOPI (Boletín Oficial de la Propiedad Industrial) | XML/HTML/PDF | proprietary XSD (updated 2024 Tomo 2) | [BOPI Descarga](https://sede.oepm.gob.es/bopiweb/descargaPublicaciones/formBusqueda.action) · [BOPI dataset on datos.gob.es](https://datos.gob.es/en/catalogo/ea0038829-bopi-boletin-oficial-de-la-propiedad-industrial) · [XSD update notice](https://www.oepm.es/es/detalle-noticia/Actualizacion-del-esquema-XSD-del-Boletin-Oficial-de-la-Propiedad-Industrial-Tomo-2-Invenciones-para-descarga-en-formato-XML/) |
| Historical archive (1878-1940 applications, 1930-1966 grants) | tabular | n/a — historical only | [Archivo histórico solicitudes](https://datos.gob.es/en/catalogo/ea0038829-archivo-historico-base-de-datos-de-solicitudes-de-patentes-1878-1940-de-la-oficina-espanola-de-patentes-y-marcas-oepm) |
| SITADEX (legal status of expedientes) — CEO replacement | tabular dataset entry | n/a | [SITADEX dataset](https://datos.gob.es/en/catalogo/ea0038829-sitadex-base-de-datos-de-la-situacion-juridica-de-expedientes-de-la-oficina-espanola-de-patentes-y-marcas-oepm) |

Two layers of access:

- **Free without registration:** main inventions/marks/designs catalogues
  in WIPO-standard XML at the publication frequency (daily/monthly/yearly).
- **Free with registration (LOPD):** "protected BOPI and Opendata" feeds
  via the [LOPD access form](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/lopd/)
  — applicant-personal-data carrying distributions.

### 1.3 Web UI surfaces (the human-facing search apps)

| Surface | Right(s) | URL | API behind it |
|---|---|---|---|
| **INVENES** (web UI for the SOAP service above) | patent, utility model, design | [`consultas2.oepm.es/InvenesWeb/`](https://consultas2.oepm.es/InvenesWeb/faces/busquedaInternet.jsp) | JSF (`*.jsp`/`*.xhtml`); UI on top of the same backend, not a separate API |
| **CEO** | all modalities | [`consultas2.oepm.es/ceo/`](https://consultas2.oepm.es/ceo/) | Web frontend of the CEO SOAP service |
| **Localizador de Marcas** | trademark | [`consultas2.oepm.es/LocalizadorWeb/`](https://consultas2.oepm.es/LocalizadorWeb/) | Web frontend of the Localizador SOAP service |
| **BOPI viewer** | all | [`sede.oepm.gob.es/bopiweb/`](https://sede.oepm.gob.es/bopiweb/descargaPublicaciones/formBusqueda.action) (Struts2 `.action`) | Same Struts2 stack as NL/RVO; not a programmatic surface |
| **BOPI Histórico** (1886-1997) | all | [`historico.oepm.es/bopi.php`](http://historico.oepm.es/bopi.php) (UAM-hosted) | PHP; historical only |
| **Latipat-Espacenet** | patent (ES + 18 LATAM countries) | [`lp.espacenet.com`](https://lp.espacenet.com/?locale=en_LP) | Routes through EPO; covered via EPO OPS |

**Important:** the `consultas2.oepm.es` UIs are **not** the SPA-on-JSON
pattern we found at SE/PRV. They're classical JSF/Struts2 server-
rendered pages — the SOAP web services are the documented, intended
programmatic path, not a reverse-engineered JSON layer behind the UI.

## 2. Auth model

Per the access-form page and the per-service landing pages, the model is:

1. Applicant submits the **Formulario de acceso a servicios web** ([oepm.es](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/acceso-a-servicios-web/)) identifying organization, intended use, and contact.
2. OEPM issues a **username + password** pair.
3. Credentials are presented to each SOAP service per call (the per-service technical docs are PDFs distributed alongside the WSDLs to credentialed users — not on the public web).

**No OAuth2.** No JWT. No bearer tokens. No "client_id / client_secret"
language anywhere on the public pages. The wording "credenciales
(usuario y contraseña)" is consistent across every service page and
the access-form page.

**No published quotas.** The public pages do not list throughput,
daily caps, payload size limits, or query-result caps. (Compare INPI:
10 req/min, 10k/day, 10 GB/day, 10k-result cap, offset ≤ 500.) We
won't know until we register and exercise.

**No "no-obstruction" clause observed** in the [Aviso legal](https://sede.oepm.gob.es/eSede/datos/es/aviso-legal/)
text (cf. INPI's CGU "anti-obstruction" clause that effectively
prohibits saturating a shared key). The Aviso legal is permissive:
attribution-required, no-distortion, no-implied-endorsement, but
explicitly permitting **commercial and non-commercial reuse**:

> *"Estas condiciones generales permiten la reutilización de los documentos sometidos a ellas para fines comerciales y no comerciales. Se entiende por reutilización… la copia, difusión, modificación, adaptación, extracción, reordenación y combinación de la información."*

— [Aviso legal Opendata OEPM](https://sede.oepm.gob.es/eSede/datos/es/aviso-legal/) (verbatim 2026-05-18).

That's a **clean redistribution posture** at the Opendata layer.
Whether the same posture extends to the SOAP services with a shared
technical account is the question that would need a written
confirmation from OEPM before any hosted-proxy posture — the access
form requests identification of intended use, suggesting the issued
credential is **per-applicant**, not transferable.

## 3. Format

Per [Data formats](https://sede.oepm.gob.es/eSede/datos/en/especificacion-de-datos/formato-de-los-datos/)
and the per-catalogue pages:

- **Inventions catalogue:** XML in **WIPO ST.36** since 2019-01-01; pre-2019 proprietary XML. Annual stock + monthly + daily increments.
- **Trademarks/distinctive signs:** XML in **WIPO ST.66**.
- **Industrial designs:** XML in **WIPO ST.86**, with XSD schema updated [in news 2024](https://www.oepm.es/en/sobre-OEPM/noticias-y-eventos/noticias/noticiap/Update-of-the-XSD-schemas-of-the-OEPM-Opendata-portal-for-XML-format-download-of-data-from-the-Industrial-Designs-Data-Catalog-bibliographic-data-and-images/).
- **BOPI:** XML/HTML/PDF; proprietary XSD with [Tomo 2 (Invenciones) schema updated 2024](https://www.oepm.es/es/detalle-noticia/Actualizacion-del-esquema-XSD-del-Boletin-Oficial-de-la-Propiedad-Industrial-Tomo-2-Invenciones-para-descarga-en-formato-XML/).

For the SOAP services, format is SOAP/XML (the public pages reference
WSDL specifications without publishing the WSDLs themselves — they
ship to registered users alongside the technical PDF manual).

This is technically the strongest WIPO-standards posture in this
wave — ST.36, ST.66, and ST.86 are exactly the formats EUIPO bulk
publishes for its TMs and RCDs. INPI publishes ST.86 v1.0 for designs.
DPMA publishes ST.36 for patents. OEPM matches all three.

## 4. Rate limit

**Unknown, undocumented.** The Servicios Web catalogue pages are
silent on rate limits. The per-service PDFs (not on public web) may
state limits; we won't know until we register.

The Opendata bulk distributions presumably have a download-frequency
expectation rather than a per-call rate limit — the publication
cadence is daily/monthly/yearly per the [Catálogo invenciones page](https://sede.oepm.gob.es/eSede/datos/en/catalogo/datos.html?catalogo=invenciones).

## 5. ToS

The [Aviso legal Opendata OEPM](https://sede.oepm.gob.es/eSede/datos/es/aviso-legal/)
covers the Opendata catalogues. Verbatim 2026-05-18 (English summary):

- Users use datasets **under their own account and risk**, solely
  responsible vis-à-vis third parties for damages from use.
- OEPM not responsible for use that reusers make of its information.
- OEPM does not guarantee continuity in availability (content or form).
- Source must be cited: **"Origen de los datos: Oficina Española de Patentes y Marcas"** and last-update date if originally included.
- **Prohibited to suggest** OEPM participates in, sponsors, or supports the reuse.
- **Reuse for commercial and non-commercial purposes is permitted.**
  Reuse expressly includes "copying, dissemination, modification,
  adaptation, extraction, reordering, and combination of the information."
- The meaning of the information must not be distorted.
- Personal-data carrying documents require explicit consent and are
  routed through the LOPD form, not the open catalogues.

Statutory basis: **[Ley 37/2007](https://www.boe.es/buscar/act.php?id=BOE-A-2007-19814)
sobre reutilización de la información del sector público** —
Spain's transposition of [EU Directive 2019/1024](https://eur-lex.europa.eu/eli/dir/2019/1024)
(Open Data Directive). Amended in application of Directive 2019/1024
in 2021 to align with the EU Open Data Directive defaults.

The Web Services per-service pages refer back to this Aviso legal as
the governing document. Whether the *credentialed* SOAP services
inherit the same redistribution permission, or whether the
"acceso-a-servicios-web" form contemplates an additional applicant-
specific licence, is **not stated on the public pages** — this is
the gating question for any hosted-proxy posture.

## 6. Verdict and shape

🟡 **yellow_byok.** Documented, intentional, machine-to-machine SOAP
services, free per-applicant credentials, no published quotas, no
shared-key option contemplated in the public access form. The Aviso
legal at the Opendata layer is permissive for redistribution, but the
SOAP-service-specific licence is not separately published — and the
per-applicant nature of the access form suggests OEPM intends
identified-user accountability rather than open shared-key proxying.
Closest sibling: **FR/INPI** (yellow_byok, also a free-credential
shape, with a published REST API instead of SOAP, and a more
articulated quota policy).

What pushes this to yellow rather than green:

- Credentials must be obtained per-applicant; not zero-auth.
- WSDLs and technical PDFs are not on the public web — they ship to
  credentialed users only. Cannot pre-validate request shapes from
  bibliographic-reading alone.
- Hosted proxy with a shared technical account is conceivable under
  the Aviso legal *redistribution* permission, but the access form
  is per-applicant — would need written confirmation from OEPM.

What pushes this off red:

- Documented, supported web services (not reverse-engineered).
- WIPO ST.36 / ST.66 / ST.86 format compliance.
- Aviso legal explicitly permits commercial reuse.
- Per the [datos.gob.es OEPM publisher catalogue](https://datos.gob.es/en/catalogo?publisher_display_name=Oficina+Espa%C3%B1ola+de+Patentes+y+Marcas),
  OEPM is one of the most-active OGD publishers in Spain (multiple
  inventions / marks / historical-archive datasets).

## 7. Coverage already in place

Spain coverage transitively, **before any OEPM-specific connector:**

| Right | Higher layer | Notes |
|---|---|---|
| **Patents (EP-validated in ES)** | [EPO OPS / INPADOC](https://www.epo.org/searching-for-patents/data/web-services/ops.html) | Spain is an EPC contracting state; EP-route patents validated in ES are well-covered at biblio/family/legal-events fidelity. |
| **Patents (national ES route)** | EPO INPADOC (partial) | Per [Federated European Patent Register overview (Lexology)](https://www.lexology.com/library/detail.aspx?g=81e0bad2-50fd-4dbf-82cb-a69c70c0d7de), Spain is among 34 EPC member states providing FRS deep-linking; OEPM-Sitadex provides "legal status of patents, utility models, trademarks and designs with effects in Spain, from their publication date" — i.e. ES feeds bibliographic data to EPO FRS. ES-national-only patents that never went EP are the gap. |
| **EUTMs designating ES** | [EUIPO](https://www.euipo.europa.eu/en/trade-marks/before-applying/availability) | EU trademarks; covered by planned EUIPO connector. |
| **Community designs (RCDs / REUDs) designating ES** | EUIPO | Same. |
| **ES national TMs (via TMview)** | [EUIPN TMview](https://www.tmdn.org/network/-/common-tools-integration-implemented-in-spain) | Spain implemented [CTI (Common Tools Integration)](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI) — ES national TMs and designs flow into TMview / DesignView via CTI back-office bridge. |
| **ES national designs (via DesignView)** | EUIPO DesignView | Same CTI route. |
| **Madrid IRs designating ES** | WIPO Madrid Monitor | International registrations designating Spain. |
| **Hague IRs designating ES** | WIPO Hague Express | International design registrations. |
| **UPC** | **N/A — Spain is NOT in the UPC.** | Per [Baker McKenzie EMEA UPC long-arm (2026-02)](https://www.bakermckenzie.com/en/insight/publications/2026/02/emea-upcs-long-arm-jurisdiction): "Spain, Poland and Croatia have not signed the agreement and are not part of the UPC system." Spanish challenge to the UP system was dismissed by the CJEU but Spain has not changed position. ES patent disputes stay in national civil courts (Tribunales de lo Mercantil de Madrid / Barcelona). |

## 8. Genuine OEPM-only gaps that the BYOK SOAP path could fill

| Gap | Service | Right | Notes |
|---|---|---|---|
| **ES-national-only patents** (filed direct at OEPM, not EP) | INVENES SOAP | patent | Low volume relative to EP route, but not in INPADOC at full fidelity. Spanish-language full text. |
| **ES utility models ("modelo de utilidad")** | INVENES SOAP | utility model | Distinct ES right, 10-year term, no novelty examination at filing (search done on request). Per [OEPM utility model page (EN)](https://www.oepm.es/en/invenciones/Presentar-una-solicitud/solicitar-un-modelo-de-utilidad/). Sometimes in INPADOC but often not at full fidelity. |
| **ES-national-only TMs** | Localizador de marcas SOAP | trademark | Surfaces in TMview via CTI, but full register fidelity (events, oppositions, renewals) is OEPM-side. |
| **ES-national-only designs** | INVENES + Diseños SOAP | design | Same logic — DesignView via CTI surfaces bibliographic data; OEPM register has the full event detail. |
| **ES file history / expediente** | CEO SOAP | all modalities | "Bibliographic data, processing actions, assignments and licenses of files, as well as searchable documents associated with the file" — per [Sede CEO page (EN)](https://sede.oepm.gob.es/eSede/datos/en/servicios-web/ceo/). This is the genuine OEPM-only fidelity for file history. |
| **ES SPCs** | INVENES/CEO | patent | ES SPC register status; tracked at OEPM. |
| **Pre-1997 BOPI archive** | UAM historical viewer | all | [historico.oepm.es/bopi.php](http://historico.oepm.es/bopi.php) — niche but real. |
| **Latipat** (18 LATAM patent offices) | INVENES SOAP / [lp.espacenet.com](https://lp.espacenet.com/?locale=en_LP) | patent | Covered via EPO OPS through the Espacenet-Latipat interface; OEPM coordinates the cooperation. |

## 9. WIPO API Catalog probe

[`https://apicatalog.wipo.int/`](https://apicatalog.wipo.int/) — probed
2026-05-18. **OEPM does not appear** in the published inventory.
Confirms the SOAP services are unindexed from the canonical-inventory
standpoint. This aligns with the pattern across the secondary-
nationals wave: SE/PRV (0 entries), NL/RVO (0 entries), AT/ÖPA (0
entries), ES/OEPM (0 entries). The catalog reports 179 entries across
DPMA, EPO, EUIPO, IP Australia, JPO, MOIP Korea, QAZ, UPRP, USPTO,
WIPO as of 2026-05-18.

## 10. Recommendation

**Connector status: planned (yellow, BYOK).** Queue
`patent_client_agents.oepm` as a JPO-shaped BYOK connector:

1. **Submit the [acceso-a-servicios-web](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/acceso-a-servicios-web/) form** identifying the project. Ask in the same submission whether (a) shared-technical-account use is permitted under the access conditions, (b) whether the per-service WSDLs and technical PDFs can be published as part of the project documentation, (c) whether any rate limits apply.
2. **If shared-key is permitted:** treat as 🟢 green-restricted (similar to EPO OPS — shared key with attribution). Build a hosted proxy.
3. **If shared-key is *not* permitted (the expected outcome based on the per-applicant access form):** treat as yellow_byok — single-tenant BYOK, OEPM credentials per end-user, same shape as the JPO and INPI patterns.
4. **Independent of credentialed path:** the Opendata catalogues are permissively licensed and could be ingested in a separate workstream if the bulk-ingestion constraint relaxes. Current zero-infra constraint keeps them out of scope.

The closest precedent in the existing codebase is `patent_client_agents.jpo`
(JPO BYOK with username/password). The connector shape would mirror
that: per-call basic-auth in env-var-supplied credentials, SOAP/XML
parsing (most likely via `zeep` or `lxml` if no WSDL is published), one
client class per right modality (`OepmInvencionesClient`,
`OepmDisenosClient`, `OepmCeoClient`, `OepmLocalizadorClient`,
`OepmClinmarClient`).

Estimated 1-2 weeks once credentials are issued — including SOAP
client construction, WIPO ST.36/66/86 response model derivation, and
cassette recording. Faster if the WSDLs are sharable (zeep auto-codegens
from WSDL).

## 11. Open questions

- **Shared-key vs. per-user policy.** Direct enquiry to the OEPM access-form contact (`opendata@oepm.es` / [contact page](https://sede.oepm.gob.es/eSede/datos/es/contacto/)) needed.
- **WSDL public availability.** Are the WSDL files distributed only to credentialed users or downloadable from a known URL after registration? Public web is silent.
- **CEO vs. SITADEX transition completeness.** Per [news article](https://oepm.es/es/detalle-noticia/La-aplicacion-de-Consulta-de-Situacion-de-Expedientes-SITADEX-seguira-actualizando-los-relativos-a-Signos-Distintivos-hasta-el-30-de-mayo-de-2017/), SITADEX was sunset 2017-05-30 for distinctive signs; CEO is the canonical successor. Whether the [datos.gob.es SITADEX dataset entry](https://datos.gob.es/en/catalogo/ea0038829-sitadex-base-de-datos-de-la-situacion-juridica-de-expedientes-de-la-oficina-espanola-de-patentes-y-marcas-oepm) (still indexed) points to current CEO data or is dormant needs confirmation.
- **Rate limits.** Not on public pages — registered-user PDF likely states. Empirical probe after registration.
- **Coverage depth of INVENES "Diseños" vs. DesignView via CTI.** Spain ships ES designs to DesignView via [CTI](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI); does INVENES surface ES-only fields that DesignView drops in transit?
- **Latipat scope.** Does OEPM credentialed access expose Latipat (Iberoamerican patents) at fidelity beyond what Espacenet-Latipat surfaces? Per [Latipat project page](https://www.oepm.es/en/sobre-OEPM/nosotros/cooperacion-regiones-y-organizaciones-internacionales/con-la-organizacion-mundial-de-la-propiedad-intelectual-OMPI/proyecto-LATIPAT/), 19 IberoAmerican offices cooperate; the SOAP path may carry more national-event detail than EPO ingestion does.
- **Iberinform-style commercial proxy.** [Iberinform](https://www.iberinform.es/en/productos/apis) lists "API consulta Oficina Española de Patentes y Marcas" among its commercial APIs — suggesting at least one third-party proxy exists. Treat as evidence that BYOK is the standard pattern, not evidence we should adopt their wrapper.

## 12. References — primary sources only

**OEPM web services (catalogue + per-service):**
- [Servicios web de la OEPM (ES landing)](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/)
- [Servicios web (SW) — Sede](https://sede.oepm.gob.es/eSede/datos/es/servicios-web/)
- [Formulario de acceso a servicios web](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/acceso-a-servicios-web/)
- [INVENES & DESIGNS SW (EN)](https://www.oepm.es/en/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/INVENES-Y-DISENOS/)
- [SW Invenes and Designs — Sede (EN)](https://sede.oepm.gob.es/eSede/datos/en/servicios-web/invenes-y-disenos/)
- [CEO web service (EN)](https://www.oepm.es/en/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/CEO/)
- [CEO — Sede (EN)](https://sede.oepm.gob.es/eSede/datos/en/servicios-web/ceo/)
- [CLINMAR web service (EN)](https://www.oepm.es/en/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/CLINMAR/)
- [SW Clinmar — Sede (EN)](https://sede.oepm.gob.es/eSede/datos/en/servicios-web/clinmar/)
- [Localizador de marcas — Sede (ES)](https://sede.oepm.gob.es/eSede/datos/es/servicios-web/localizador-de-marcas/)
- [LOPD form — protected BOPI / Opendata](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/lopd/)

**Opendata:**
- [OpenData Project — Sede (EN)](https://sede.oepm.gob.es/eSede/datos/en/)
- [Catálogo de datos — Sede](https://sede.oepm.gob.es/eSede/datos/es/catalogo/datos.html)
- [Catálogo invenciones (EN)](https://sede.oepm.gob.es/eSede/datos/en/catalogo/datos.html?a=1&catalogo=invenciones)
- [Catálogo marcas y nombres comerciales (ES)](https://sede.oepm.gob.es/eSede/datos/es/catalogo/datos.html?catalogo=marcas)
- [Data formats (EN)](https://sede.oepm.gob.es/eSede/datos/en/especificacion-de-datos/formato-de-los-datos/)
- [Aviso legal Opendata OEPM (ES)](https://sede.oepm.gob.es/eSede/datos/es/aviso-legal/)
- [Update of XSD schemas for industrial designs (2024 news)](https://www.oepm.es/en/sobre-OEPM/noticias-y-eventos/noticias/noticiap/Update-of-the-XSD-schemas-of-the-OEPM-Opendata-portal-for-XML-format-download-of-data-from-the-Industrial-Designs-Data-Catalog-bibliographic-data-and-images/)
- [Update of BOPI Tomo 2 (Invenciones) XSD (news)](https://www.oepm.es/es/detalle-noticia/Actualizacion-del-esquema-XSD-del-Boletin-Oficial-de-la-Propiedad-Industrial-Tomo-2-Invenciones-para-descarga-en-formato-XML/)

**BOPI gazette:**
- [BOPI: Spanish Official Industrial Property Gazette (EN)](https://sede.oepm.gob.es/eSede/en/consultas/boletin-oficial-de-la-propiedad-industrial/)
- [BOPI descarga publicaciones](https://sede.oepm.gob.es/bopiweb/descargaPublicaciones/formBusqueda.action)
- [BOPI suscripción tomos](https://consultas2.oepm.es/bopiweb/suscribirse/formSuscribirse.action)
- [BOPI: Boletín Oficial de la Propiedad Industrial — datos.gob.es dataset](https://datos.gob.es/en/catalogo/ea0038829-bopi-boletin-oficial-de-la-propiedad-industrial)
- [BOPI Histórico 1886-1997 — UAM](http://historico.oepm.es/bopi.php)

**datos.gob.es entries (publisher = OEPM):**
- [OEPM publisher catalogue at datos.gob.es](https://datos.gob.es/en/catalogo?publisher_display_name=Oficina+Espa%C3%B1ola+de+Patentes+y+Marcas)
- [Catálogo OpenData de la OEPM (master entry)](https://datos.gob.es/es/catalogo/ea0038829-catalogo-opendata-de-la-oficina-espanola-de-patentes-y-marcas-oepm)
- [Archivo histórico 1878-1940 — solicitudes](https://datos.gob.es/en/catalogo/ea0038829-archivo-historico-base-de-datos-de-solicitudes-de-patentes-1878-1940-de-la-oficina-espanola-de-patentes-y-marcas-oepm)
- [Archivo histórico 1930-1966 — patentes concedidas BOPI](https://datos.gob.es/en/catalogo/ea0038829-archivo-historico-base-de-datos-de-patentes-concedidas-y-publicadas-en-el-bopi-1930-1966-de-la-oficina-espanola-de-patentes-y-marcas-oepm)
- [SITADEX dataset entry](https://datos.gob.es/en/catalogo/ea0038829-sitadex-base-de-datos-de-la-situacion-juridica-de-expedientes-de-la-oficina-espanola-de-patentes-y-marcas-oepm)
- [CLINMAR dataset](https://datos.gob.es/en/catalogo/ea0038829-clinmar)
- [SERVICIO WEB INVENES dataset](https://datos.gob.es/en/catalogo/ea0038829-servicio-web-invenes)

**Substantive law:**
- [Ley 37/2007, de 16 de noviembre, sobre reutilización de la información del sector público — BOE](https://www.boe.es/buscar/act.php?id=BOE-A-2007-19814)
- [EU Open Data Directive (EU) 2019/1024](https://eur-lex.europa.eu/eli/dir/2019/1024)

**Cross-office context:**
- [WIPO IP API Catalog](https://apicatalog.wipo.int/) — probed 2026-05-18; 0 OEPM entries
- [Latipat-Espacenet (EN)](https://lp.espacenet.com/?locale=en_LP)
- [Common Tools Integration implemented in Spain (TMDN news)](https://www.tmdn.org/network/-/common-tools-integration-implemented-in-spain)
- [EUIPN Common Tools Integration (CTI)](https://www.euipn.org/bg/tools/Common-Tools-Integration-CTI)
- [Federated European Patent Register overview — Lexology](https://www.lexology.com/library/detail.aspx?g=81e0bad2-50fd-4dbf-82cb-a69c70c0d7de)
- [PCT Legal — Spain (WIPO eGuide)](https://pctlegal.wipo.int/eGuide/view-doc.xhtml?doc-code=ES&doc-lang=en)

**UPC non-participation:**
- [Baker McKenzie EMEA UPC long-arm (2026-02)](https://www.bakermckenzie.com/en/insight/publications/2026/02/emea-upcs-long-arm-jurisdiction)
- [Despite the defeat at the CJEU, Spain will not join the Unitary Patent system — Kluwer Patent Blog](https://legalblogs.wolterskluwer.com/patent-blog/despite-the-defeat-at-the-cjeu-spain-will-not-join-the-unitary-patent-system/)

---

**Verdict line:** 🟡 yellow_byok. Documented free SOAP web services
with WSDLs, free per-applicant credentials, no shared-key on the
public access form, but permissive Aviso legal at the Opendata layer
(Ley 37/2007 transposing EU Directive 2019/1024) explicitly allowing
commercial and non-commercial reuse with attribution. Connector
status: planned, JPO-shaped, queue for BYOK build once credentials
issued via the [acceso-a-servicios-web form](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/acceso-a-servicios-web/).
