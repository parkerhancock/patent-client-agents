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
| `search_patents`, `get_patent`, `resolve_patent_number`, `patent_client_status` | Served. KR routes need `KIPO_KIPRIS_API_KEY`; without it they report how to enable them. |
| `search_uspto`, `get_uspto`, `get_file_history`, `search_office_actions`, `search_patent_assignments` | Served |
| `get_epo`, `search_epo` | Served; need EPO OPS credentials |
| `search_trademarks`, `get_trademark`, `search_trademark_assignments` | Served; TSDR views need `USPTO_TSDR_API_KEY` |
| `classify_cpc` | Served; needs EPO OPS credentials. USCLS mapping is rejected (OPS maps CPC, IPC and ECLA). |
| `get_fees` | Served for the EPO, the Unitary Patent and the USPTO (patent, trademark, design); other offices report not yet ported |
| `search_litigation`, `get_litigation`, `list_ptab_children`, `search_cafc_patent_opinions` | PTAB and CAFC served; UPC decisions not ported (the site now sits behind a Cloudflare challenge); USITC appears only with `USITC_EDIS_TOKEN`, matching the Python EDIS-enabled build (checked by a second contract fixture) |
| `search_legal_reference`, `get_legal_reference` | MPEP, TMEP, UKIPO MoPP, DPMA, the Taiwan Trade Secrets Act and the five EPO corpora served; India not ported. See [DPMA statutes](dpma-statutes.md). For `tw_trade_secrets` an omitted `syntax` means all terms, as the description says; Python sent phrase. See [Taiwan Trade Secrets Act](tw-trade-secrets.md) |
| `search_bulk_data`, `download_document` | ODP bulk data, patent PDFs, PTAB documents and CAFC opinions served; USITC attachments with `USITC_EDIS_TOKEN`; IP Australia not ported |
| `search_upc_statutes`, `get_upc_section` | Served from the UPC statutes corpus. See [UPC statutes](upc-statutes.md) |
| `search_wipo_lex_legislation`, `get_wipo_lex_legislation` | Served. See [WIPO Lex](wipo-lex.md) |
| `copyright` | Served. See [copyright](copyright.md) |
| `search_upc_decisions` | Not registered; listed by `patent_client_status` |

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
- CAFC appeal numbers work with four-digit years (`2024-1945`); Python passed
  them to the court's index unchanged, where only `24-1945` matches.
  `download_document(source='cafc')` also takes the opinion's PDF URL as
  `identifier`, since the facade has no `document_url` parameter.
- `search_legal_reference` has no schema default for `syntax`. Omitted, it
  is `adj` for the manuals and `and` for `dpma`, as its description says;
  Python's facade defaults it to `adj` and so phrase-matches DPMA searches.
- WIPO Lex, Copyright Office, UPC and DPMA statutes outputs correct several Python
  bugs (inverted `include_historical`, empty post-1978 copyright titles and
  claimants, unquoted FTS operators, among others); each connector doc lists
  them. Long UPC instrument texts arrive as text artifacts past 32,000
  characters, not inline.
- CAFC `more_available` comes from the index's filtered count, and the
  `search_litigation` summary reports source rows inspected out of that count.

Each module documents its own deviations inline:
[patents](../packages/mcp/src/facade/patents.ts),
[USPTO](../packages/mcp/src/facade/uspto.ts),
[EPO](../packages/mcp/src/facade/epo.ts),
[trademarks](../packages/mcp/src/facade/trademarks.ts),
[reference](../packages/mcp/src/facade/reference.ts),
[litigation](../packages/mcp/src/facade/litigation.ts),
[legal reference](../packages/mcp/src/facade/legal-reference.ts),
[documents](../packages/mcp/src/facade/documents.ts).

## Live check

On October 21, 2026, [`scripts/live-facade.ts`](../scripts/live-facade.ts)
(`bun run verify:facade-live <report.json>`) called every served tool and mode
against the live offices: 81 calls in the first run, with the deployed ODP, TSDR and EPO OPS
keys and Trademark Search WAF session read from Secret Manager into the process
environment only, the fresh MPEP artifact and the prepared EPO corpora.
Every call behaved as expected after one fix:

- **Fixed:** ODP answers HTTP 404 for a trial's decisions while the trial is
  pending. `list_ptab_children` and `download_document(source='ptab_trial')`
  failed for every pending IPR. The PTAB client now reads that 404 as an empty
  list ([regression test](../tests/ptab-children.test.ts)); a pending trial's
  download reports that no decisions match, and a decided trial
  (IPR2020-00019) returns its 105 documents and a 42 KB decision.

Confirmed live, among others: the claims cascade (ODP for a granted US patent,
Patent Public Search for a pre-grant publication, EPO OPS for EP1000000B1), all
eleven `get_epo` views including the registered Unitary Patent EP4108782,
Trademark Search through the deployed WAF session, all four TSDR views, EPO
fee lookups, PTAB search across all five record types, office-action text by
document identifier, file-history item (25 KB) and NOA bundle (780 KB), and
patent PDFs for US (618 KB) and EP (558 KB). Unported modes returned their
not-yet-available messages. A later run on October 21 added CAFC: free-text
and patent-only search, patent opinions for September 2026 (61 rows), and
opinion PDFs by four-digit appeal number (127 KB) and by a harvested appeal
(112 KB). A third run added the UPC statutes (search and the fee table, read
from the May 14 snapshot), WIPO Lex (Canadian patent laws, then the Patent
Act with its attachments) and the Copyright Office (233 hits for "Steamboat
Willie", then one record by id). On October 22, TMEP search and section 1207.01, the USPTO patent
schedule (412 fees, effective January 19, 2025) and a small-entity year-4
maintenance fee lookup passed live, and KR search reported that
`KIPO_KIPRIS_API_KEY` is not configured. The full toolset's public USITC tools
also answered live (HTS search, the IDS investigation feed).
Later on October 22, `search_legal_reference` and `get_legal_reference` for
`ukipo_mopp` ("inventive step", section 4A) passed against the packaged
May 14 MoPP snapshot, and DPMA search (`Unterlassung` in PatG) and `§ 139 PatG`
passed against the packaged DPMA statutes artifact; that corpus is local, so
the run checks wiring, not an upstream. The Taiwan Trade Secrets Act search and Article 13-1 also passed; that
text is bundled, so no network call is involved.

Not facade defects, but visible in the run:

- `search_legal_reference(corpus='epc', query='novelty')` returns no hits,
  because the crawled EPC text runs heading words into numbers. The builder
  fix is on `fix/epo-legal-heading-whitespace`; the corpora have not been
  rebuilt with it.
- `get_epo(view='register_biblio')` summarizes with the first register title,
  which is the German one for EP1000000. The data includes all three.
- Trademark Search owner names can carry runs of spaces from the source.

## Verification

37 facade tests across [patents and USPTO](../tests/facade-patents-uspto.test.ts),
[EPO, trademarks and reference](../tests/facade-epo-tm-ref.test.ts) and
[litigation, legal reference and documents](../tests/facade-lit-ref-docs.test.ts)
check routing, cascades, list handling, validation and gaps against synthetic
upstreams and the real corpus fixtures, plus the contract test. The curated
toolset is not deployed.
