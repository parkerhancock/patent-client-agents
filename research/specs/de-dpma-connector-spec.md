# Connector spec — DPMA Germany (DE/DPMA)

**Source synopsis:** [`../national/de-dpma.md`](../national/de-dpma.md)
**Source detail survey:** [`../connectors/dpma.md`](../connectors/dpma.md)
**Source contract review:** [`../waves/2026-05-18-priority-2-synopses/dpma-byok-rating.md`](../waves/2026-05-18-priority-2-synopses/dpma-byok-rating.md)
**Authoring date:** 2026-08-03
**Roadmap rating basis:** DPMAconnectPlus supports a contracting party's own REST client with HTTP Basic credentials and a registered static IP. The project classifies this as `yellow_byok` and excludes it from the shared hosted demo.

## §1 Scope and package layout

Build the interactive DPMAregister surface only. It covers German patents,
utility models, national trademarks, and national designs. Do not wrap the
public web interfaces, optional paid data packages, or backfiles in v1.

**Package name:** `patent_client_agents.dpma_register`

**Canonical templates:** copy the package and MCP structure from
`patent_client_agents.kipo_kipris` for XML parsing and environment-gated tools.
Use `patent_client_agents.jpo` as the two-credential configuration precedent.

**Files:**

- `src/patent_client_agents/dpma_register/{__init__,api,client,models,resources}.py`
- `src/patent_client_agents/dpma_register/py.typed`
- `src/patent_client_agents/mcp/tools/dpma_register.py`
- `tests/dpma_register/` with XML fixtures and focused contract tests

Mount `dpma_register_mcp` from `patent_client_agents.mcp`. Export
`DpmaRegisterClient`, record models, and module-level helpers from the package.

## §2 Auth and deployment controls

**Environment variables:** `DPMA_CONNECTPLUS_USERNAME` and
`DPMA_CONNECTPLUS_PASSWORD`.

`DpmaRegisterClient` resolves explicit constructor values before environment
values. It sends them with `httpx.BasicAuth` only to an HTTPS base URL. It must
never log credentials or the `Authorization` header.

Every MCP tool uses `conditional_tool(..., requires_env=[...])`. The connector
must remain absent from the shared hosted server, even if that deployment later
receives unrelated DPMA credentials.

The usage resource must distinguish these sourced contract terms from project
policy:

- The DPMA contract requires access from the recipient's registered,
  non-dynamic IP and requires the recipient to prevent unauthorized access.
- Contract §3 limits use to the purpose selected by the recipient. It contains
  stated exceptions for uses under §3(1)(b) through (d).
- The library does not expand the recipient's approved purpose. Each deployer
  must obtain its own account and confirm its own use with DPMA.
- The project's conservative control is local or private BYOK deployment only.
  Shared project credentials and the public hosted demo are out of scope.

Use `account_required` in `coverage/sources.yaml`. The manifest vocabulary has
no HTTP Basic value; explain the Basic-auth transport in each row's `notes`.

## §3 Client and model contract

Base URL: `https://dpmaconnect.dpma.de/dpmaws/rest-services/`.

Service paths:

- `DPMAregisterPatService` for patents and utility models
- `DPMAregisterMarkeService` for national trademarks
- `DPMAregisterGsmService` for national designs

Each service supports `version`, `search/<expert-query>`, and
`getRegisterInfo/<number>`. Search returns XML hit lists. Detail responses use
DPMA extensions to WIPO ST.36, ST.66, and ST.86 respectively.

Add `PatentUtilityRecord`, `TrademarkRecord`, and `DesignRecord` Pydantic
models. Parsing must tolerate XML namespaces and unknown extension fields.
Lean projections keep stable identifiers, title or mark text, status, primary
dates, owner, and primary classification. `full=True` includes the complete
normalized record, event history, image or document references, and preserved
extension fields.

Production searches return at most 1,000 hits; test accounts return at most
100. The v1 API does not invent pagination. Set `next_cursor=None`. Report the
upstream cap in the summary when a result reaches the account limit.

## §4 MCP tool surface

All tools are read-only and return `ListEnvelope`, including single-record
fetches. Fetch tools accept a string or list of strings and use bounded
concurrency with a list cap of 50.

| Tool | Inputs | Result |
|---|---|---|
| `search_dpma_patents` | `expert_query: str`, `right_type: patent \| utility_model \| both`, `limit=25`, `full=False` | Patent and utility-model register hits |
| `get_dpma_patent` | `application_number: str \| list[str]`, `full=False` | Patent or utility-model register records |
| `search_dpma_trademarks` | `expert_query: str`, `limit=25`, `full=False` | National trademark register hits |
| `get_dpma_trademark` | `application_number: str \| list[str]`, `full=False` | National trademark register records |
| `search_dpma_designs` | `expert_query: str`, `limit=25`, `full=False` | National design register hits |
| `get_dpma_design` | `design_number: str \| list[str]`, `full=False` | National design register records |

Search tools pass the official DPMA expert-query syntax through unchanged after
basic non-empty and length validation. The usage resource links the separate
field guides for patents, trademarks, and designs.

Every tool names its search or fetch sibling. Patent tools also identify EPO
OPS as the preferred source for ordinary DE patent bibliography and families.
DPMA remains the authoritative source for German utility models and national
trademark and design records.

Provenance uses the exact called DPMAconnectPlus URL and the matching source
name from the manifest. Cache metadata must reflect the original upstream
fetch time.

## §5 Manifest entries

Add three beta `registered_ip` rows at integration:

| ID | Rights | Data types |
|---|---|---|
| `DE/DPMA/Patents` | `[patent]` | `[bibliographic, classification, legal_status]` |
| `DE/DPMA/Trademarks` | `[trademark]` | `[bibliographic, classification, legal_status]` |
| `DE/DPMA/Designs` | `[design]` | `[bibliographic, classification, legal_status]` |

Use `rest_api`, `account_required`, both auth environment variables,
`patent_client_agents.dpma_register`, `mcp_proxy`, and `beta`. The patents
row name and notes must state that the service also covers utility models,
because `utility_model` is not in the manifest rights vocabulary.

## §6 Test and verification plan

Use namespace-bearing XML fixtures for all three search and detail schemas.
Do not use real credentials in fixtures or cassettes.

Required checks:

- explicit credentials take precedence over environment values
- missing credentials raise `ConfigurationError` with the DPMA signup link
- only HTTPS is accepted outside injected test transports
- Basic auth is present on requests and absent from logs and saved fixtures
- all three hit-list and detail schemas parse, including unknown extensions
- malformed XML and upstream XML error payloads become `ApiError`
- search caps, lean projections, list fan-out, and envelope provenance work
- six tools are absent without both variables and present with both variables
- manifest, tool-source mapping, documentation counts, and changelog are updated

Do not add a live-test flag or record authenticated cassettes. CI is fixture-only
until a contributor with a DPMAconnectPlus account can validate from its
registered IP. State this limit in the package, tools, provenance, manifest,
README, changelog, and usage resource. Invite community testing and sanitized
response samples that contain no credentials, personal data, or confidential
records.

Run `scripts/verify_connector.py dpma_register --jurisdiction "DPMA Germany"`
before integration, followed by the coverage, tool-count, lint, type, and
focused test gates.

## §7 Deferred and unresolved items

- Defer weekly frontfiles, backfiles, and register-extract ZIP endpoints. Their
  access and costs depend on the recipient's selected contract options.
- Defer patent PDFs and trademark or design images until authenticated binary
  responses can be tested through the shared download registry.
- Confirm whether DPMA now accepts signed electronic contract copies. The
  current official page still instructs users to send two originally signed
  copies by post.
- Do not claim live compatibility. Public documents define the schemas and
  operations but do not prove current account behavior. Community support from
  an account holder is welcome for live testing and sanitized schema samples.
- Treat the 2020 contract PDF as the current linked German form. The English
  page, updated 2026-07-27, states that updated documents are forthcoming.

## §8 Primary references

- [DPMAconnectPlus overview](https://www.dpma.de/english/search/data_supply_services/dpmaconnect/index.html)
- [DPMAconnectPlus interface description](https://www.dpma.de/docs/recherche/dienste/schnittstellenbeschreibungdpmaconnectplus.pdf)
- [DPMAconnectPlus standard contract and Annex 1](https://www.dpma.de/docs/recherche/dienste/standardvertrag_dpmaconnectplus.pdf)
- [`CONNECTOR_STANDARDS.md`](../../CONNECTOR_STANDARDS.md) §§3, 5, 6, and 7
