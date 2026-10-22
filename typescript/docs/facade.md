# Curated facade toolset

October 21, 2026. `createServer({ toolset: "curated" })`, or `PCA_TOOLSET=curated`,
serves the public tool surface of the Python `patent-client-facade`: the tools
both deployments actually expose (`search_patents`, `get_patent`, `get_uspto`,
`search_uspto`, `get_file_history`, `get_epo` and the rest). The default
`"full"` toolset is unchanged. Over HTTP the curated tools need the
`tools:read` scope.

Usage over the 30 days to October 21: 89% of the deployments' patent-tool
calls (16,840 of 18,825) went to tools whose connectors are all ported, and
another 10% to tools that are partly ported.

## Contract

The deployed Python facade's tool list, exported with `USITC_EDIS_TOKEN` unset,
is archived at [`tests/fixtures/facade/python-facade-tools.json`](../tests/fixtures/facade/python-facade-tools.json).
[A contract test](../tests/facade-contract.test.ts) requires every Python tool
to be served or listed as unported, and every served tool to keep the Python
parameter names, required parameters and routing enums. Defaults stay
optional: the facade publishes input-mode JSON schemas, since FastMCP's
output-mode schemas mark defaulted parameters as required.

## What is served

| Tools | Status |
| --- | --- |
| `search_patents`, `get_patent`, `resolve_patent_number`, `patent_client_status` | Served. KR routes (KIPRIS) are not ported. |
| `search_uspto`, `get_uspto`, `get_file_history`, `search_office_actions`, `search_patent_assignments` | Served |
| `get_epo`, `search_epo` | Served; need EPO OPS credentials |
| `search_trademarks`, `get_trademark`, `search_trademark_assignments` | Served; TSDR views need `USPTO_TSDR_API_KEY` |
| `classify_cpc` | Served; needs EPO OPS credentials. USCLS mapping is rejected (OPS maps CPC, IPC and ECLA). |
| `get_fees` | Served for EPO and the Unitary Patent; other offices report not yet ported |
| `search_litigation`, `get_litigation`, `list_ptab_children` | PTAB served; CAFC and UPC not ported; USITC tools stay off as in the EDIS-less Python build |
| `search_legal_reference`, `get_legal_reference` | MPEP and the five EPO corpora served; TMEP, DPMA, UKIPO MOPP, India and Taiwan not ported |
| `search_bulk_data`, `download_document` | ODP bulk data, patent PDFs and PTAB documents served; CAFC, USITC and IP Australia not ported |
| `copyright`, `get_upc_section`, `search_upc_statutes`, `search_upc_decisions`, `search_wipo_lex_legislation`, `get_wipo_lex_legislation`, `search_cafc_patent_opinions` | Not registered; listed by `patent_client_status` |

Sub-modes without a TypeScript connector fail with "… is not yet available on
the TypeScript server"; credential-gated families say which variable to set.
`patent_client_status` returns `unported_tools` and `unported_modes`.

## Differences from the Python facade

Inputs match. Outputs keep the §5.9 envelope keys and, where the TypeScript
data allows, the Python lean-stub field names (PTAB stubs and trademark
assignment stubs match exactly). Item contents come from the TypeScript
clients, so full records are not byte-compatible. Notable changes:

- Every tool returns an envelope; Python returned raw values for `get_patent`
  claims, family and figures, `patent_client_status` and `search_bulk_data`.
- Downloads are single artifacts (one PDF, or a ZIP with a manifest) instead
  of per-document resource links. Bulk-data product listings omit download
  URLs, as Python does without its signing proxy, which is not ported.
- US `get_patent` citations resolve the number to its application first;
  Python passed the patent number's digits as an application number.
- The EPO claims fallback splits the English claim block into numbered claims
  instead of one claim per language.
- The patent PDF cascade tries Patent Public Search only for US numbers, then
  EPO OPS.
- Family is the ODP family graph; TSDR views and full trademark records use the
  TypeScript client shapes (TSDR is camelCase).
- Searches without a cursor parameter in the Python schema return
  `next_cursor: null` with `more_available`.

Each module documents its own deviations inline:
[patents](../packages/mcp/src/facade/patents.ts),
[USPTO](../packages/mcp/src/facade/uspto.ts),
[EPO](../packages/mcp/src/facade/epo.ts),
[trademarks](../packages/mcp/src/facade/trademarks.ts),
[reference](../packages/mcp/src/facade/reference.ts),
[litigation](../packages/mcp/src/facade/litigation.ts),
[legal reference](../packages/mcp/src/facade/legal-reference.ts),
[documents](../packages/mcp/src/facade/documents.ts).

## Verification

37 facade tests across [patents and USPTO](../tests/facade-patents-uspto.test.ts),
[EPO, trademarks and reference](../tests/facade-epo-tm-ref.test.ts) and
[litigation, legal reference and documents](../tests/facade-lit-ref-docs.test.ts)
check routing, cascades, list handling, validation and gaps against synthetic
upstreams and the real corpus fixtures, plus the contract test. The curated
toolset has not been run against live offices or deployed.
