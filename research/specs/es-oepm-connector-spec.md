# Connector spec — Oficina Española de Patentes y Marcas (ES/OEPM)

**Source synopsis:** [`../national/es-oepm.md`](../national/es-oepm.md)
**Source detail survey:** [`../waves/2026-05-18-secondary-nationals-wave/es-oepm.md`](../waves/2026-05-18-secondary-nationals-wave/es-oepm.md)
**Authoring date:** 2026-08-03
**Implementation status:** Beta implementation complete; public-WSDL tested, live account validation pending.
**Rating basis:** OEPM provides its CEO machine service free of charge after registration. The public WSDL documents one exact-file operation with credentials in the request object. Shared project credentials remain out of scope.

## §1 Scope and package layout

Build only the publicly documented CEO file-detail operation. It covers
distinctive signs (`M`, `N`, `R`, `H`), inventions (`P`, `U`, `E`, `W`, `C`,
`T`, `F`, `L`), and designs (`D`, `I`, `G`, `DT`, `DI`, `DS`). Do not imply
that CEO supports free-text search. Do not ingest OEPM OpenData or BOPI bulk
files.

**Package name:** `patent_client_agents.oepm_spain`

**Files:**

- `src/patent_client_agents/oepm_spain/{__init__,api,client,models,resources}.py`
- `src/patent_client_agents/oepm_spain/py.typed`
- `src/patent_client_agents/mcp/tools/oepm_spain.py`
- `tests/oepm_spain/` with WSDL-derived SOAP fixtures and contract tests

## §2 Authentication and endpoint

Use `OEPM_CEO_USERNAME` and `OEPM_CEO_PASSWORD`. Explicit constructor values
take precedence over environment values. Every MCP tool requires both
variables. OEPM accepts access applications through its free web-services
form.

Post SOAP 1.1 XML to:

`https://consultas2.oepm.es/ceo/WSDetalleExpedienteOEPM`

The WSDL is public at the same URL with `?wsdl`. It declares an HTTP endpoint,
but the identical contract is available over HTTPS. The connector must use
HTTPS. The WSDL declares document/literal SOAP and an empty `SOAPAction`.

Authentication is part of `DetalleExpedienteOEPMRequest`, not HTTP Basic
authentication. The request contains `numExpediente`, `usuario`, and `pass`.
Never log or preserve the outgoing SOAP body because it contains credentials.
Disable response caching.

OEPM does not publish a rate limit. Map HTTP 429 and `Retry-After` to a domain
rate-limit error. Fetch fan-out accepts at most 50 identifiers and uses at most
five concurrent requests.

## §3 WSDL and model contract

The WSDL target namespace is:

`http://detalleExpOEPM.ws.ceo.oepm.es/`

It exposes one operation, `detalleExpedienteOEPM`. The response contains
`resultado`, `datosBibliograficos`, public processing acts, licence data,
payments, assignments, annotations, and oppositions. The result-state table is:

| State | Meaning | Connector mapping |
|---|---|---|
| `0` | successful response | parse record |
| `-1` | service error | `ApiError` |
| `-2` | invalid file number | `ApiError` |
| `-3` | file not found | `NotFoundError` |
| `-4` | invalid username or password | `AuthenticationError` |
| `-5` | file is not public | `ApiError` |

Add permissive Pydantic models:

- `OepmPatentRecord`
- `OepmTrademarkRecord`
- `OepmDesignRecord`
- `OepmProceedingAct`

Normalize the main identifier, modality, status, owner, applicant,
representative, dates, title or denomination, classifications, and public
processing acts. Preserve the complete normalized response under `raw`.
Unknown future WSDL fields must not break parsing.

## §4 MCP tool surface

All tools are read-only and return `ListEnvelope`. Each accepts one exact file
number or a list capped at 50.

| Tool | Accepted modalities | Upstream operation |
|---|---|---|
| `get_oepm_patent` | `P`, `U`, `E`, `W`, `C`, `T`, `F`, `L` | `detalleExpedienteOEPM` |
| `get_oepm_trademark` | `M`, `N`, `R`, `H` | `detalleExpedienteOEPM` |
| `get_oepm_design` | `D`, `I`, `G`, `DT`, `DI`, `DS` | `detalleExpedienteOEPM` |

The connector omits search because the CEO WSDL has no search operation. The
separate INVENES, design, and trademark-locator services require separate
contracts and should not be inferred from CEO. OEPM OpenData is bulk-only and
stays outside the MCP surface.

Provenance must identify the CEO endpoint and state that the connector is
tested against the public WSDL with synthetic fixtures but remains live
unverified.

## §5 Test and verification plan

Use synthetic SOAP/XML fixtures derived from the embedded WSDL schemas. Do not
use real credentials or authenticated cassettes.

Required checks:

- explicit credentials override environment values
- missing credentials identify the official registration page
- request XML uses SOAP 1.1, the exact operation namespace, empty SOAP action,
  and documented unqualified request fields
- patent, trademark, and design responses parse their documented subtypes
- result states, SOAP faults, malformed XML, HTTP authentication failures, and
  HTTP 429 map to domain errors
- modality validation prevents a typed tool from returning a different right
- list fan-out, lean and full projections, envelopes, and provenance work
- all three tools require both credentials

Run focused tests, Ruff, and ty. Run the repository connector gate after the
shared manifests and MCP mount are added.

## §6 Deferred items

- Live account validation remains pending an OEPM web-services account.
- Defer INVENES patent search, the trademark locator, CLINMAR, and protected
  BOPI data until each current public contract is independently verified.
- Keep OpenData and BOPI bulk ingestion outside this zero-infrastructure
  connector.
- Do not expose filing or C2O submission services through this read-only
  package.

## §7 Primary references

- [OEPM web services](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/)
- [CEO service specification PDF](https://www.oepm.es/export/sites/portal/comun/documentos_relacionados/varios_todas_modalidades/Servicio_web_CEO_Especificacion_Servicios.pdf)
- [Public CEO WSDL](https://consultas2.oepm.es/ceo/WSDetalleExpedienteOEPM?wsdl)
- [`CONNECTOR_STANDARDS.md`](../../CONNECTOR_STANDARDS.md)
