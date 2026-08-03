# Connector spec — Swiss Federal Institute of Intellectual Property (CH/IPI)

**Source synopsis:** [`../national/ch-ipi.md`](../national/ch-ipi.md)
**Source detail survey:** [`../waves/2026-05-18-secondary-nationals-wave/ch-ipi.md`](../waves/2026-05-18-secondary-nationals-wave/ch-ipi.md)
**Authoring date:** 2026-08-03
**Implementation status:** Shipped beta on 2026-08-03; schema-tested, live account validation pending.
**Rating basis:** The IPI datadelivery API permits private use with individual credentials after signed Terms of Use. It uses OpenID Connect password-grant authentication and XML POST requests. Shared project credentials remain out of scope.

## §1 Scope and package layout

Build the supported live datadelivery API surface for Swiss patents,
trademarks, supplementary protection certificates, and their publication
records. Do not add designs because the API has no `DesignSearch` action. Do
not ingest the semiannual patent CSV or scrape Swissreg.

**Package name:** `patent_client_agents.ipi_swissreg`

**Canonical templates:** use `patent_client_agents.jpo` for two-credential
environment gating and `patent_client_agents.dpma_register` for namespace-aware
XML parsing. Follow the IPI public XSDs for request construction and fixtures.

**Files:**

- `src/patent_client_agents/ipi_swissreg/{__init__,api,client,models,resources}.py`
- `src/patent_client_agents/ipi_swissreg/py.typed`
- `src/patent_client_agents/mcp/tools/ipi_swissreg.py`
- `tests/ipi_swissreg/` with schema-derived XML fixtures and contract tests

## §2 Authentication and limits

Use `IPI_DATA_USERNAME` and `IPI_DATA_PASSWORD`. Optional
`IPI_DATA_TOTP_TOKEN` supports accounts that require a caller-supplied current
TOTP code. Explicit constructor values take precedence over environment values.

Obtain tokens from
`https://idp.ipi.ch/auth/realms/egov/protocol/openid-connect/token` with
`client_id=datadelivery-api-client` and `grant_type=password`. Reuse the access
token until shortly before expiry. The client may refresh with the returned
refresh token. Never log credentials, TOTP codes, tokens, or authorization
headers.

Send authenticated XML POST requests to
`https://www.swissreg.ch/public/api/v1`. Honor HTTP 429 and `Retry-After` as a
rate-limit error. The service permits 12 concurrent requests and 2 GiB of
response data in a rolling 24-hour window. Fetch fan-out uses at most five
concurrent requests and accepts at most 50 identifiers.

Every tool is environment-gated on the username and password. Keep the
connector off the shared hosted demo. The usage resource must state the signed
Terms of Use requirement and the schema-tested, live-unverified status.

## §3 XML and model contract

Construct `ApiRequest` documents with the published IPI namespaces:

- core: `urn:ige:schema:xsd:datadeliverycore-1.0.0`
- common: `urn:ige:schema:xsd:datadeliverycommon-1.0.0`
- action-specific `datadelivery-{type}-1.0.0` namespace

Initial searches contain one typed `Action`, `Representation`, `Page`, and
`Query`. Free-text search uses common `Any`. Identifier fetches use the
action-specific number field. Continuation calls contain only the returned
`Continuation name="NextPage"` action. Do not invent offset pagination.

Parse `TotalItemCount`, `ItemCountOffset`, and `ItemCount` from `Meta`. Preserve
the opaque next-page continuation as `next_cursor`. Reject failed `Result`
elements and error logs as `ApiError`. Parsing must tolerate namespaces and
preserve unknown Swiss ST.96 extensions in `raw`.

Add these Pydantic models:

- `IpiPatentRecord`
- `IpiTrademarkRecord`
- `IpiSpcRecord`
- `IpiPublicationRecord`
- `IpiSearchMeta`

Lean projections keep identifiers, title or product, status, primary dates,
owner, and primary classification. `full=True` includes normalized raw XML.

## §4 MCP tool surface

All tools are read-only and return `ListEnvelope`. Fetch tools accept one
identifier or a list capped at 50.

| Tool | Upstream action | Main input |
|---|---|---|
| `search_ipi_patents` | `PatentSearch` | `query`, `limit=25`, `cursor=None` |
| `get_ipi_patent` | `PatentSearch` | `patent_number` |
| `search_ipi_patent_publications` | `PatentPublicationSearch` | `query`, `limit=25`, `cursor=None` |
| `search_ipi_trademarks` | `TrademarkSearch` | `query`, `limit=25`, `cursor=None` |
| `get_ipi_trademark` | `TrademarkSearch` | `trademark_number` |
| `search_ipi_spcs` | `SPCSearch` | `query`, `limit=25`, `cursor=None` |
| `get_ipi_spc` | `SPCSearch` | `spc_number` |
| `search_ipi_spc_publications` | `SPCPublicationSearch` | `query`, `limit=25`, `cursor=None` |

Provenance must identify the IPI datadelivery endpoint and state that the
connector is schema-tested but not validated with a live account. Patent tools
identify EPO OPS as the preferred substitute for ordinary CH patent
bibliography. IPI remains the authoritative source for Swiss SPCs and
national-only trademarks.

## §5 Manifest and tracking

Add beta `registered_ip` rows for `CH/IPI/Patents`, `CH/IPI/Trademarks`, and
`CH/IPI/SPCs`. Use `rest_api`, `oauth2_password`, both required environment
variables, `patent_client_agents.ipi_swissreg`, and `mcp_proxy`. Patent notes
must mention the CH and LI unified patent territory. All rows must disclose the
schema-tested, live-unverified status.

Mount `ipi_swissreg_mcp`, update the full configured tool count, add its
tool-source mapping, and mark CH/IPI shipped beta in `research/STATE.yaml` only
after the connector gate passes.

## §6 Test and verification plan

Use XML fixtures derived from the public IPI XSDs and documentation. Do not use
real credentials or authenticated cassettes.

Required checks:

- explicit credentials override environment values
- missing credentials identify the official registration page
- token requests use the documented grant, client ID, and optional TOTP
- access tokens are reused and never appear in logs or fixtures
- request XML uses exact namespaces, action types, page sizes, and query fields
- all five action response shapes parse with metadata and continuation cursors
- failed result XML, malformed XML, authentication failures, and HTTP 429 map to domain errors
- identifier fan-out, lean and full projections, envelopes, and provenance work
- eight tools require both credentials
- manifests, counts, tracking, and changelog remain synchronized

Run `scripts/verify_connector.py ipi_swissreg --jurisdiction "Swiss Federal Institute of Intellectual Property"`, followed by coverage, tool-count, MCP-contract, lint, type, and focused test checks.

## §7 Deferred items

- Live account validation remains pending a signed IPI data-delivery account.
- Do not add automatic TOTP generation or store TOTP secrets in v1.
- Defer ZIP bundles, images, documents, and secondary resource endpoints.
- Defer Swiss designs because the datadelivery API does not expose them.

## §8 Primary references

- [IPI data delivery](https://www.ige.ch/en/services/digital-resources/ip-data/data-delivery-api)
- [IPI datadelivery API documentation](https://www.swissreg.ch/public/apidocs/)
- [Single-page API documentation](https://www.swissreg.ch/public/apidocs/singlehtml/index.html)
- [IPI XML catalog](https://schema.ige.ch/xml/catalog.xml)
- [`CONNECTOR_STANDARDS.md`](../../CONNECTOR_STANDARDS.md)
