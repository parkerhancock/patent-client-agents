# TMEP corpus access

October 21, 2026. The TypeScript library reads the USPTO Trademark Manual of
Examining Procedure (TMEP) from an offline SQLite/FTS5 snapshot, through the
same verified-artifact lifecycle as [MPEP](mpep.md). The TMEP corpus has the
MPEP's outline schema (`meta`, `sections`, an external-content `sections_fts`
over section number, title and text, and a `compression_dict` for
dictionary-compressed HTML), so the client is a thin layer over the shared
`OutlineCorpus` reader in [`corpus/outline.ts`](../packages/client/src/corpus/outline.ts).
No API key is needed. HTTP access uses the `uspto:read` scope, as MPEP does.

| Library client | MCP tools | Status resource | Path variable |
| --- | --- | --- | --- |
| `TmepClient` | `search_tmep`, `get_tmep_section` | `tmep://corpus/status` | `TMEP_CORPUS_PATH` |

The tool names and Python parameters match (`query`, `limit` 1-100 default 25,
`offset`, `syntax`, `sort`, `full` for search; `section` as a string or list
for get). The path variable and the default file name
(`~/.cache/patent_client_agents/tmep.db`) match the Python connector.
`TMEP_CORPUS_SHA256` pins the decoded SQLite bytes and
`TMEP_CORPUS_FILE_SHA256` the distributed file. In the curated facade,
`search_legal_reference` and `get_legal_reference` with `corpus='uspto_tmep'`
route to the same reader, as the Python facade routes them to `search_tmep` and
`get_tmep_section`. Explicit `version` values other than `current` are refused
there, as in Python.

## Why a separate client rather than a shared one

`MpepClient` carries MPEP-only behavior: a dated release check, release
selection by `version`, the `[R-...]` section revision and release-tagged
result URLs. `TmepClient` reuses the shared reader (artifact pins, Zstandard,
WAL rejection, schema and FTS validation, dictionary decoding, FTS quoting and
timestamp parsing) and adds only the TMEP status, URLs and section lookup.
MPEP code and tests are unchanged.

## Behavior

Search quotes every term (`adj`/`exact` as one phrase, `and`, `or`), so FTS
operators in user text are searched as words, as in Python. Results rank by
BM25 with the href as tie-breaker. `sort='outline'` orders by the stored
section-number text, so `904` sorts after `1401.02(a)`; Python orders the same
way. Section references are section numbers (`1207.01(a)`, matched by Python's
pattern) or stored hrefs, with or without `.html` (`TMEP-1200d1e8145.html`,
`ch1300_d2266f_1dcc2_11c`).

`search_tmep` returns Python's lean stub by default (section number, title
without the number, snippet capped at 400 characters, href) and the full hit
with `full=true`. It also takes an optional `cursor`, bound to the query and
the artifact identity, as `search_mpep` does. `get_tmep_section` keeps input
order. A single missing string reference is an error, as in Python; missing
entries of a list go to `not_found` with Python's "Fetched X of Y" summary.
Unlike Python, which returns HTML and text inline, items carry plaintext inline
up to a 32,000-character budget across the response and deliver longer text as
an artifact through the download store; `format='html'` delivers the section
HTML as an artifact. Items carry `content_sha256` (of the HTML), `chapter` and
the corpus metadata. Provenance has `cache_hit: true`, the snapshot date as
`retrieved_at` and `corpus_synced_at` (UTC midnight) and `corpus_version`.

The status resource reports availability, `corpus_version`, schema version,
section count, snapshot date, both hashes and compression. No release check
exists for TMEP; availability does not establish that the edition is current.

## Snapshot and freshness

The deployed corpus meta records `schema_version` 1, `snapshot_date`
2026-05-13, `section_count` 1751 and `source_version` `current`. As in Python's
`get_corpus_status`, `current` is a moving label, so `corpus_version` is
`unknown` and `corpus_synced_at` is 2026-05-13T00:00:00Z. The library accepts
only `version='current'`; Python accepts any value and echoes it back, but only
one snapshot is installed.

## Artifact source, packaging and verification

The runtime never fetches or rebuilds the corpus. The deploy image pulls
corpora from `gs://patentclient-mcp-corpora/manifest.json` into
`/app/corpora/tmep.db`. This port used that manifest's TMEP entry unchanged:
`gs://patentclient-mcp-corpora/tmep/2026-05-13/tmep.db`, built
2026-05-21T13:56:52Z, 8,417,280 bytes, SHA-256
`df85277ae9dab5557d2eab9ebfd87a993ec493a8b1b273beade0ad9e68d7c2f6` (a read-only
download; the local `~/.cache/patent_client_agents/tmep.db` has the same hash).
It is a WAL-mode file, so it was prepared with the generic MPEP preparation
script (backup into DELETE journal mode with metadata and integrity checks)
and packaged. From `typescript/`:

```sh
mkdir -p .data/tmep/gcs
gcloud storage cp gs://patentclient-mcp-corpora/tmep/2026-05-13/tmep.db .data/tmep/gcs/tmep.db
uv run --frozen --no-sync python scripts/prepare-mpep-corpus.py \
  --input .data/tmep/gcs/tmep.db --output .data/tmep/tmep.db \
  --sha256 df85277ae9dab5557d2eab9ebfd87a993ec493a8b1b273beade0ad9e68d7c2f6
bun scripts/compress-corpus.ts --input .data/tmep/tmep.db --output .data/tmep/tmep.db.zst
bun run verify:tmep --file .data/tmep/tmep.db.zst
```

The preparation script's "MPEP" error wording is cosmetic for this corpus.

| Rows | Prepared bytes | Zstandard bytes | Decoded SHA-256 | File SHA-256 |
| --- | --- | --- | --- | --- |
| 1,751 | 8,417,280 | 3,316,287 | `2d678fdf821fb94dd7aec66c738a91bc9cbffee2adb2a4e438abf48d8cd52aa8` | `398814bd370d146e5fbe9c8471564d4c828faea6b2ff359f559780be39ac780a` |

On October 21, 2026 the verifier configured the packaged file and both pins,
then exercised the library (status, search, an href lookup, section 1207.01)
and the default full and curated MCP servers (`search_tmep`, a four-reference
`get_tmep_section` with one missing reference, an HTML artifact whose bytes
match the library's hash, and the facade's `search_legal_reference` and
`get_legal_reference` for `uspto_tmep`). Section 1207.01's decoded HTML hashes
to `1c95abbac653a701f39d2412986ebaddcb5713321514cc8705213a345ce1a7ae` and its
text is 12,227 characters in both the TypeScript and the Python readers, and
the two return the same top hits for "likelihood of confusion" and "acquired
distinctiveness". The artifacts stay under ignored `.data/` and were not
deployed.

## Python differences

- Python's outline search hits carry no snippet (the shared hit model has
  `title`, `href`, `path` and `result_url` only), so `search_tmep`'s lean stub
  always returns an empty `snippet` and `full=true` rows have none. The
  TypeScript hits carry the FTS5 snippet with `<mark>` highlights, and full
  rows also carry `section_number`.
- Python's `get_tmep_section` sets `section_number` only when the caller passed
  a number; an href lookup returns `null`. TypeScript returns the stored
  section number either way.
- The text cap, HTML artifacts, `cursor`, `format` and the version refusal are
  described above.

## Tests

The [fixture](../tests/fixtures/tmep/README.md) holds seven real rows copied
from the deployed snapshot, including dictionary-compressed HTML.
[Library tests](../tests/tmep-client.test.ts) cover status, search syntax and
operator quoting, paging and outline order, number and href lookups, not-found
and version errors, the section-size limit, Zstandard bytes, pins, WAL
rejection and the environment variables. [MCP tests](../tests/tmep-mcp.test.ts)
cover both tools, cursors, `not_found`, text and HTML artifacts, the status
resource, the curated facade routing and the `uspto:read` scope on the
authenticated HTTP listener. The Node smoke run reads the fixture as bytes.
All run offline.
