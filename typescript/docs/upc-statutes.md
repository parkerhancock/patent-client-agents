# UPC statutes corpus access

October 21, 2026. The TypeScript library reads the Unified Patent Court
statutes corpus: the Agreement on a Unified Patent Court (UPCA, which includes
the Statute as Annex I), the consolidated Rules of Procedure and the
consolidated Table of Court Fees, each in English, French and German. It is an
offline SQLite/FTS5 snapshot read through the same verified-artifact lifecycle
as [MPEP](mpep.md) and the [EPO legal corpora](epo-legal.md). No API key is
needed. The MCP adapter uses a separate `upc:read` scope for HTTP access.

| Library client | MCP tools | Status resource | Path variable |
| --- | --- | --- | --- |
| `UpcStatutesClient` | `search_upc_statutes`, `get_upc_section`, `list_upc_instruments` | `upc-statutes://corpus/status` | `UPC_STATUTES_CORPUS_PATH` |

Tool names, parameters (`query`, `instrument`, `language`, `per_page`, `page`
for search; `instrument` as a key or list, `language` for get), the path
variable and the default file name (`~/.cache/patent_client_agents/upc_statutes.db`)
match the Python connector. `UPC_STATUTES_CORPUS_SHA256` pins the decoded
SQLite bytes and `UPC_STATUTES_CORPUS_FILE_SHA256` the distributed file. The
UPC decisions tools in the same Python module are a separate port.

The curated facade serves `search_upc_statutes` and `get_upc_section`
verbatim, as the Python facade re-exposes them. `search_legal_reference` and
`get_legal_reference` have no UPC corpus value in Python, so nothing routes
there.

## Schema and behavior

The corpus is not an outline corpus. It stores one row per (instrument,
language) in an `instruments` table with the full extracted text, indexed by
`instruments_fts` (short name, title, text). There are no per-Article or
per-Rule sections, so `get_upc_section` returns whole instruments, and search
returns ranked snippets with `<mark>` highlights that locate the provision.

The artifact lifecycle (file and decoded pins, whole-file Zstandard, WAL
rejection, read-only in-memory SQLite) is the shared `openCorpusSnapshot` in
[`corpus/outline.ts`](../packages/client/src/corpus/outline.ts); this port
split it out of `OutlineCorpus` so a reader with a different schema can reuse
it. The UPC reader adds its own schema check (meta `schema_version` 1, the
`instruments` columns, an external-content FTS5 table over them).

Instrument keys are `upca`, `rop`, `fees` and `coc`, with Python's aliases
(`statute`, `annex i`, `agreement`, `rules of procedure`, `court fees`, `code
of conduct` and others), matched case-insensitively. Search defaults to English
and all-terms matching; the library also takes `language: null` for every
language, `syntax` (`and`, `or`, `adj`, `exact`) and `sort` (`relevance` or
`instrument`), which the MCP tool does not expose, as in Python. Ties in BM25
rank fall back to row order so pages are stable.

`get_upc_section` keeps input order, lists missing keys in `not_found`, and
returns an empty item list with a "not found" summary for a single missing key,
as Python does. Unlike Python, which returns every text inline (the German RoP
is 359,385 characters), texts beyond a 32,000-character inline budget are
delivered as text artifacts through the download store, as the EPO legal tools
do. Items carry `content_sha256` and `corpus_version`.

## Snapshot and freshness

The consolidated PDFs carry no version label, so the Python builder records
only `snapshot_date`. Following Python's `get_corpus_status`, the client
reports `corpus_version` as `snapshot <date>` and `corpus_synced_at` as that
date at UTC midnight. A missing or malformed date gives `unknown` and `null`.
`source_version` is null on every row of the deployed snapshot even though
the fees table text records amendments in force from 1 January 2026. No
release or currency check exists in this port.

## Artifact source, packaging and verification

The runtime never fetches or rebuilds the corpus. The Python builder
(`patent-client-agents-build-upc-statutes-corpus`) cannot run from Cloud Build
because unifiedpatentcourt.org's Cloudflare blocks those addresses, so the
deploy image copies a pre-built file committed in the deploy repository
(`patent-client-agents-deploy/corpora/upc_statutes.db`, built May 14, 2026,
SHA-256 `6eaef0e48d0ef896b20f79f6cf0367a4ebad575f988391a7fe1727c7df96fce6`).
This port uses that file unchanged. It is a WAL-mode database, so it is
prepared (backup into DELETE journal mode, metadata and integrity checked) with
the generic MPEP preparation script and then packaged. From `typescript/`:

```sh
mkdir -p .data/upc
uv run --frozen --no-sync python scripts/prepare-mpep-corpus.py \
  --input ../../patent-client-agents-deploy/corpora/upc_statutes.db \
  --output .data/upc/upc_statutes.db
bun scripts/compress-corpus.ts \
  --input .data/upc/upc_statutes.db \
  --output .data/upc/upc_statutes.db.zst
bun run verify:upc-statutes --file .data/upc/upc_statutes.db.zst
```

The preparation script's output says `source_version: unknown` and its error
messages say "MPEP"; both are cosmetic for this corpus.

On October 21, 2026 this sequence ran against the deploy repository's file.
The verifier configured the packaged file and both pins, then exercised the
library and the default full and curated MCP servers (search, a German RoP
fetch, and a four-key `get_upc_section` with one missing key).

| Rows | Prepared bytes | Zstandard bytes | Decoded SHA-256 | File SHA-256 |
| --- | --- | --- | --- | --- |
| 9 (UPCA, RoP, Fees × en/fr/de) | 1,986,560 | 652,442 | `2d1fd1e1aadefe3fd6122cd3488acab80ddd14304eecb3efd5c6ea204fbac0b9` | `8f8477f68912ba8fb42704cdac10cd55797794b968de55778cdea90e91dca50d` |

The decoded German RoP text hashes to the same SHA-256 as the Python reader's
(`78d621d26c52eaa24b0904337760b31ef728a7c711ad73ebef0f07300bb41287`). The
artifacts stay under ignored `.data/` and were not deployed.

## Python differences and source-data limits

- Python leaves bare words unquoted in FTS5 queries, so `OR`, `AND`, `NEAR`
  and `NOT` run as operators (`opt-out OR zzz` matches) or fail (`NOT` alone
  raises an FTS5 syntax error). The TypeScript reader quotes every term, so
  caller input is always text.
- The tool descriptions and models name a Code of Conduct (`coc`), but the
  deployed snapshot has no CoC rows; `coc` is reported as not found.
- Stored source URLs for the RoP and fees PDFs contain spaces. The client
  percent-encodes them and reports only `https://www.unifiedpatentcourt.org`
  URLs; anything else falls back to the legal-documents page.
- The text is plain PDF extraction with page furniture ("3 | Page") and runs of
  blank lines. The port does not rewrite stored text.

## Tests

The [fixture](../tests/fixtures/upc-statutes/README.md) holds four real rows
(UPCA in English and the fees table in three languages).
[Library tests](../tests/upc-statutes-client.test.ts) cover status, search,
language and instrument filters, aliases, paging and sort order, FTS operator
quoting, full-text hashes, the text-size limit, Zstandard bytes, missing, WAL,
schema and pin failures, metadata gaps, untrusted URLs and the environment
variables. [MCP tests](../tests/upc-statutes-mcp.test.ts) cover the three
tools, `not_found`, text artifacts, the status resource, the curated facade
against the Python contract and the `upc:read` scope on the authenticated
HTTP listener. Node and browser smoke runs read the fixture as bytes. All run
offline.
