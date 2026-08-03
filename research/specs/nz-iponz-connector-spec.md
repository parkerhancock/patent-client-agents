# Connector spec — Intellectual Property Office of New Zealand (NZ/IPONZ)

**Source synopsis:** [`../national/nz-iponz.md`](../national/nz-iponz.md)
**Source detail survey:** [`../waves/2026-05-18-secondary-nationals-wave/nz-iponz.md`](../waves/2026-05-18-secondary-nationals-wave/nz-iponz.md)
**Authoring date:** 2026-08-03
**Implementation status:** Shipped beta on 2026-08-03; public-contract tested, live subscription validation pending.
**Rating basis:** Each caller supplies an MBIE API subscription key obtained with a RealMe-backed IPONZ account. The connector remains off the shared hosted demo.

## §1 Scope and package layout

Implement the public read-only IPONZ v5 operations for patent, trade mark, and
design details and date-range change lists. Do not expose renewal, application,
correspondence, or document operations. Some of those operations incur fees or
change official records.

**Package name:** `patent_client_agents.iponz_new_zealand`

**Files:**

- `src/patent_client_agents/iponz_new_zealand/{__init__,api,client,models,resources}.py`
- `src/patent_client_agents/iponz_new_zealand/py.typed`
- `src/patent_client_agents/mcp/tools/iponz_new_zealand.py`
- `tests/iponz_new_zealand/` with XSD-valid synthetic XML fixtures

## §2 Official contract and authentication

The public OpenAPI 3.0.1 definition identifies version v5 and these base URLs:

- production: `https://api.business.govt.nz/gateway/intellectual-property-office-nz/v5`
- sandbox: `https://api.business.govt.nz/sandbox/intellectual-property-office-nz/v5`

Use `IPONZ_SUBSCRIPTION_KEY` in the `Ocp-Apim-Subscription-Key` header. The
OpenAPI definition also permits `subscription-key` as a query parameter, but
the connector must not put credentials in URLs. `IPONZ_ENV` accepts
`production` or `sandbox`; production is the default. A caller may supply an
optional current bearer token through `IPONZ_ACCESS_TOKEN`. The connector does
not obtain or persist OAuth credentials.

Honor HTTP 401 and 403 as authentication errors, HTTP 404 as not found, and
HTTP 429 with `Retry-After` as a rate-limit error. Fetch fan-out accepts at most
50 identifiers and uses at most five concurrent requests.

## §3 XML and model contract

IPONZ publishes separate response XSD bundles for patents, trade marks, and
designs. Parse XML by local element name so namespace prefixes may vary. Reject
`TransactionError` bodies even when the HTTP response is 200. Preserve the
normalized response subtree in `raw` for forward compatibility.

Add these Pydantic models:

- `IponzPatentRecord`
- `IponzTrademarkRecord`
- `IponzDesignRecord`
- `IponzRegisterSummary`

Date-range paths use `YYYYMMDD-YYYYMMDD`. The start date cannot precede
2010-01-01, the end cannot precede the start, and the period must be shorter
than one year. IPONZ does not document pagination for these XML list
operations. Tools may trim a response to the caller's limit, set
`more_available`, and tell the caller to split the date range. They must not
invent a cursor.

## §4 MCP tool surface

All tools are read-only and return `ListEnvelope`. Detail tools accept one
identifier or a list capped at 50.

| Tool | Upstream operation | Main input |
|---|---|---|
| `get_iponz_patent` | `GET /patent/{patent-number}` | `patent_number` |
| `list_iponz_patents_updated` | `GET /patents/updated/{date-range}` | `start`, `end`, `limit=100` |
| `get_iponz_trademark` | `GET /trademarks/{trademark-number}` | `trademark_number` |
| `list_iponz_trademarks_updated` | `GET /trademarks/updated/{date-range}` | `start`, `end`, `limit=100` |
| `get_iponz_design` | `GET /design/{design-number}` | `design_number` |
| `list_iponz_designs_updated` | `GET /designs/updated/{date-range}` | `start`, `end`, `limit=100` |
| `list_iponz_designs_registered` | `GET /designs/registered/{date-range}` | `start`, `end`, `limit=100` |

Provenance must identify IPONZ and state that the connector is tested against
public contracts but not a live subscription.

## §5 Test and verification plan

Use synthetic fixtures that validate against the official IPONZ XSDs. Do not
use real credentials or authenticated cassettes.

Required checks:

- production and sandbox paths match the public OpenAPI definition
- the subscription key stays in the request header
- optional bearer tokens are caller supplied
- all three detail schemas and all date-range list shapes parse
- date-range and identifier validation reject invalid input
- transaction errors, malformed XML, authentication failures, not-found
  responses, and rate limits map to domain errors
- lean and full projections, fan-out, envelopes, and provenance work
- all seven tools require `IPONZ_SUBSCRIPTION_KEY`

Run the focused tests, Ruff, and ty. The shared connector gate, manifests,
mount, counts, and documentation are integration work outside this package.

## §6 Deferred items

- Live sandbox and production validation remain pending an approved subscription.
- Defer `POST /trademarksearch` until a live sandbox test confirms its SOAP error and result behavior.
- Defer document downloads because they return unbounded Base64 payloads with a 120-second service timeout.
- Defer renewals, fee checks, applications, and correspondence because they are outside the read-only register scope.
- PVR and geographical indications remain uncovered because the v5 API does not expose them.

## §7 Primary references

- [IPONZ API overview](https://www.iponz.govt.nz/about-iponz/iponz-api/)
- [MBIE IPONZ API portal](https://portal.api.business.govt.nz/api/iponz)
- [MBIE API getting started](https://portal.api.business.govt.nz/getting-started)
- [IPONZ patent information XSD bundle](https://portal.api.business.govt.nz/content/Patent-Information%20schema%20v1_50.zip)
- [IPONZ trade mark information XSD bundle](https://portal.api.business.govt.nz/content/TradeMark-Information%20schema%20v3_01.zip)
- [IPONZ design information XSD bundle](https://portal.api.business.govt.nz/content/Design-Information%20schema%20v1_08.zip)
- [`CONNECTOR_STANDARDS.md`](../../CONNECTOR_STANDARDS.md)
