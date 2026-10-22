# DPMA statutes corpus access

October 22, 2026. The TypeScript library reads the DPMA statutes corpus: sections
of the six German IP Acts (Patentgesetz, Markengesetz, Gebrauchsmustergesetz,
Designgesetz, Urheberrechtsgesetz and Geschäftsgeheimnisgesetz) in one offline
SQLite/FTS5 snapshot, read through the same verified-artifact lifecycle as the
[UPC statutes](upc-statutes.md). No API key is needed. The MCP adapter uses a
separate `dpma:read` scope for HTTP access.

| Library client | MCP tools | Status resource | Path variable |
| --- | --- | --- | --- |
| `DpmaStatutesClient` | `search_dpma_statutes`, `get_dpma_section` | `dpma-statutes://corpus/status` | `DPMA_STATUTES_CORPUS_PATH` |

Tool names and parameters (`query`, `statute`, `limit`, `offset`, `syntax`,
`sort`, `full` for search; `citation` as a string or list of up to 50 for get),
the path variable and the default file name
(`~/.cache/patent_client_agents/dpma_statutes.db`) match the Python connector.
`DPMA_STATUTES_CORPUS_SHA256` pins the decoded SQLite bytes and
`DPMA_STATUTES_CORPUS_FILE_SHA256` the distributed file. The DPMA register
connector (DPMAconnectPlus) is a separate Python module and is not ported.

The curated facade routes `search_legal_reference` and `get_legal_reference`
with `corpus='dpma'` to the same code, as the Python facade forwards to
`search_dpma_statutes` and `get_dpma_section`. The `statute` filter is passed
only for `dpma` and ignored for the other corpora. `get_legal_reference` takes
the identifier as one citation and returns the get tool's envelope, including
`not_found`.

## The corpus is a 12-section seed

There is no fuller DPMA corpus anywhere. The Python builder does not crawl
gesetze-im-internet.de; it loads the `seed.jsonl` bundled with the package,
which holds 12 sections (PatG §§ 1, 3, 139; MarkenG §§ 14, 32; GebrMG §§ 1, 11;
DesignG § 1; UrhG §§ 1, 97; GeschGehG §§ 1, 2), each cut to its first paragraph
or sentence. The deploy image does not build it or set
`DPMA_STATUTES_CORPUS_PATH`, and `gs://patentclient-mcp-corpora/` has no DPMA
object, so the deployed Python server answers every DPMA call with "corpus not
found" (checked on October 22 through the hosted `search_legal_reference`).
Python has no runtime fallback to the seed; neither does this port. A real
corpus needs a builder for the official texts, which is out of scope here.

## Schema and behavior

Each row of `sections` is one § of one Act (`statute`, `section`, `title`,
`text`), indexed by the external-content FTS5 table `sections_fts` over all
four columns with the `porter unicode61` tokenizer. The reader checks meta
`schema_version` 1, the columns and the FTS5 definition, and rejects WAL files,
as the shared `openCorpusSnapshot` does for every corpus.

Act names resolve through Python's alias table (`PatG`, `Patentgesetz`, `Patent
Act`, `Trade Mark Act`, `Geschäftsgeheimnisgesetz`, `Copyright Act` and the
rest, case-insensitively); unknown names pass through and find nothing.
`get_dpma_section` parses `§ 139 PatG`, `Section 14 MarkenG`, `Sec. 14 of the
Trade Mark Act`, `S. 139 PatG` and bare `139`. A bare number found in one Act
resolves; one found in several fails with the list of Acts (`AMBIGUOUS_SECTION`).
A single missing citation fails the call; in a list, missing citations go to
`not_found` while parse and ambiguity errors fail the call, as in Python.

Search defaults to all-terms matching and BM25 order, returns lean stubs
(statute, section, title, a 400-character snippet with `<mark>` highlights) or,
with `full`, the hit with its rank. Status reports `corpus_version` as
`source_version` when the build recorded one, otherwise `snapshot-<date>`
(Python's form, with a hyphen), and `corpus_synced_at` as that date at UTC
midnight; a missing or malformed date gives `unknown` and `null`. Section text
beyond a 32,000-character inline budget would be delivered as a text artifact,
as the other corpus tools do; no seed section comes close.

## Python differences

Python is being retired, so these are fixed here rather than there.

- Python leaves bare words unquoted in FTS5 queries, so `OR`, `AND`, `NEAR`
  and `NOT` run as operators (`Unterlassung OR Marke` in the default `and`
  mode matches either word) or fail (`NOT` alone raises an FTS5 syntax error).
  The TypeScript reader quotes every term.
- `sort='outline'` ordered sections as text, so § 139 came before § 3. Sections
  now sort numerically within each Act. BM25 ties fall back to row order so
  pages are stable.
- The citation parser rejected German subdivisions (`§ 139 Abs. 1 PatG`,
  `§ 2 Nr. 1 GeschGehG`) and Act citations without a `§` (`139 PatG`). Both now
  resolve to the whole section. Letter suffixes are lowercased (`16A` → `16a`)
  to match gesetze-im-internet.de numbering.
- Python's facade passes its own `syntax` default (`adj`) to the DPMA search,
  so an omitted `syntax` phrase-matched although the parameter text says
  statutes default to `and`. The TypeScript facade leaves `syntax` without a
  schema default and applies `and` for `dpma`, `adj` for the manuals.

## Artifact source, packaging and verification

The runtime never fetches or rebuilds the corpus. From `typescript/`, with the
Python project's environment (the builder only reads the bundled seed):

```sh
mkdir -p .data/dpma_statutes
uv run --project .. --frozen --no-sync patent-client-agents-build-dpma-statutes-corpus \
  --output "$TMPDIR/dpma_statutes.db"
uv run --project .. --frozen --no-sync python scripts/prepare-mpep-corpus.py \
  --input "$TMPDIR/dpma_statutes.db" --output .data/dpma_statutes/dpma_statutes.db
bun scripts/compress-corpus.ts \
  --input .data/dpma_statutes/dpma_statutes.db \
  --output .data/dpma_statutes/dpma_statutes.db.zst
bun run verify:dpma-statutes --file .data/dpma_statutes/dpma_statutes.db.zst
```

The builder writes a WAL-mode database, so the preparation step is required.
Its output says `source_version: unknown` and its errors say "MPEP"; both are
cosmetic here. A rebuild on another day changes `snapshot_date` and so the
hashes.

On October 22, 2026 this sequence ran over the seed (SHA-256
`2a84f3ce8c62056f140193dcbdc73e1bfe16efef364fa8aca62570c727d496dd`). The
verifier configured the packaged file and both pins, then exercised the
library and the default full and curated MCP servers.

| Sections | Built (WAL) SHA-256 | Prepared bytes | Decoded SHA-256 | Zstandard bytes | File SHA-256 |
| --- | --- | --- | --- | --- | --- |
| 12 | `6f8fc6029d883baa830d55b52990470241c7cd45779db71a9252dc861f6b8849` | 53,248 | `6256d69d7d32325a05c3c8e30c619ed66b61043a4b7879927b700307dcec3b98` | 5,266 | `c5605037b18975e157e2476504a33b8e38d30abf2eb10b07b0e9f8df232b6121` |

A one-off comparison ran the Python `DpmaStatutesClient` and the TypeScript
client on the same prepared file: seven searches (all four syntaxes, Act
filters, outline sort) returned the same hits in the same order with identical
snippets, and seven citations returned identical sections. BM25 ranks differ
only in the last floating-point digit (SQLite builds differ). The outline
search compared has no § 3/§ 139 pair, so the sort fix is not visible there.
The live facade probe (`dpma search`, `dpma section`) passed against the
packaged file. The artifacts stay under ignored `.data/` and were not deployed.

## Tests

The [fixture](../tests/fixtures/dpma-statutes/README.md) is the whole prepared
build. [Library tests](../tests/dpma-statutes-client.test.ts) cover citation
parsing, status, sections, ambiguity and not-found errors, search syntax, Act
filters and aliases, numeric outline order, paging, FTS operator quoting,
Zstandard bytes, pins, the environment variables, WAL, schema and metadata
gaps. [MCP tests](../tests/dpma-statutes-mcp.test.ts) cover both tools against
the Python summaries and shapes, `not_found`, the status resource, the curated
facade routing (statute filter, default syntax, get envelope) and the
`dpma:read` scope on the authenticated HTTP listener. Node and browser smoke
runs read the fixture as bytes. All run offline.
