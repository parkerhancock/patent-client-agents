# UKIPO Manual of Patent Practice (MoPP) corpus access

October 22, 2026. The TypeScript library reads the UK Intellectual Property
Office's Manual of Patent Practice from an offline SQLite/FTS5 snapshot of the
gov.uk guidance pages, through the same verified-artifact lifecycle as
[MPEP](mpep.md) and [TMEP](tmep.md). The MoPP corpus has the shared outline
schema (`meta`, `sections`, an external-content `sections_fts` over section
number, title and text, and a `compression_dict` for dictionary-compressed
HTML), so the client is a thin layer over the shared `OutlineCorpus` reader in
[`corpus/outline.ts`](../packages/client/src/corpus/outline.ts). One row is one
gov.uk page: a Patents Act 1977 section, or an appendix such as the glossary.
No API key is needed. HTTP access uses a separate `ukipo:read` scope.

| Library client | MCP tools | Status resource | Path variable |
| --- | --- | --- | --- |
| `MoppClient` | `search_mopp`, `get_mopp_section` | `mopp://corpus/status` | `MOPP_CORPUS_PATH` |

The tool names and Python parameters match (`query`, `limit` 1-100 default 25,
`offset`, `syntax`, `sort`, `full` for search; `section` as a string or list
for get). The path variable and the default file name
(`~/.cache/patent_client_agents/mopp.db`) match the Python connector and the
deploy image (`MOPP_CORPUS_PATH=/app/corpora/mopp.db`). `MOPP_CORPUS_SHA256`
pins the decoded SQLite bytes and `MOPP_CORPUS_FILE_SHA256` the distributed
file. In the curated facade, `search_legal_reference` and `get_legal_reference`
with `corpus='ukipo_mopp'` route to the same reader, as the Python facade routes
them to `search_mopp` and `get_mopp_section`. Explicit `version` values other
than `current` are refused, as for TMEP.

## Behavior

Search quotes every term (`adj`/`exact` as one phrase, `and`, `or`), so FTS
operators in user text are searched as words. Results rank by BM25 with the
href as tie-breaker. `sort='outline'` orders by the stored section-number text
(`102A` before `4`, unnumbered pages first), as Python does. Hits carry the
section number, `path` (`["4A"]`; MoPP has no chapters), the FTS5 snippet and a
`result_url` on gov.uk.

`get_mopp_section` accepts:

- a section number, in either case (`1`, `4A`, `4a`, `102A`);
- a paragraph citation (`1.07`, `14.99(a)`), which returns the section's page,
  since the corpus stores one page per section and paragraphs live in its body;
- a gov.uk slug, with or without section 4A's leading dash
  (`section-14-the-application`, `-section-4a-methods-of-treatment-or-diagnosis`);
- a gov.uk path or URL, with any query or fragment dropped
  (`https://www.gov.uk/guidance/manual-of-patent-practice-mopp/section-14-the-application#ref14-01`).

`search_mopp` returns Python's lean stub by default (section number, title
without the number, snippet capped at 400 characters, href) and the full hit
with `full=true`, plus an optional `cursor` bound to the query and the artifact
identity. `get_mopp_section` keeps input order; a single missing string
reference is an error, as in Python, and missing entries of a list go to
`not_found` with Python's "Fetched X of Y" summary. As for TMEP, items carry
plaintext inline up to a 32,000-character budget across the response and
deliver longer text through the download store (most MoPP sections are longer:
section 1 is 133,767 characters, section 14 is 228,599); `format='html'`
delivers the section HTML as an artifact. Items carry `content_sha256` (of the
HTML) and the corpus metadata. Provenance has `cache_hit: true`, the snapshot
date as `retrieved_at` and `corpus_synced_at` (UTC midnight), and
`corpus_version`.

## Snapshot and freshness

The deployed corpus meta records `schema_version` 1, `snapshot_date`
2026-05-14 and the gov.uk index as `source`, with no `source_version` or
`section_count`. gov.uk publishes no MoPP revision label, so, as in Python's
`get_corpus_status` (`snapshot_label="snapshot-{}"`), `corpus_version` is
`snapshot-2026-05-14` and `corpus_synced_at` is 2026-05-14T00:00:00Z. The
corpus holds 192 pages, 183 of them with a stored section number. The deployed
manifest's `section_count` of 0 reflects the missing meta key, not the rows.
UKIPO revises MoPP several times a year (the corpus's own "changes" page is
headed April 2026); availability does not establish that the text is current.

## Artifact source, packaging and verification

The runtime never fetches or rebuilds the corpus. The deploy image pulls
corpora from `gs://patentclient-mcp-corpora/manifest.json` into
`/app/corpora/mopp.db`. This port used that manifest's `ukipo_mopp` entry
unchanged: `gs://patentclient-mcp-corpora/ukipo_mopp/2026-05-14/mopp.db`, built
2026-05-21T13:56:57Z, 5,525,504 bytes, SHA-256
`6bed606494c91eb80b71c3fd38bd232df040351e8f3c2dfa880623ac2702e8bf` (a read-only
download; the local `~/.cache/patent_client_agents/mopp.db` is a different
build). It is a WAL-mode file, so it was prepared with the generic MPEP
preparation script (backup into DELETE journal mode with metadata and
integrity checks) and packaged. From `typescript/`:

```sh
mkdir -p .data/ukipo_mopp/gcs
gcloud storage cp gs://patentclient-mcp-corpora/ukipo_mopp/2026-05-14/mopp.db .data/ukipo_mopp/gcs/mopp.db
uv run --frozen --no-sync python scripts/prepare-mpep-corpus.py \
  --input .data/ukipo_mopp/gcs/mopp.db --output .data/ukipo_mopp/mopp.db \
  --sha256 6bed606494c91eb80b71c3fd38bd232df040351e8f3c2dfa880623ac2702e8bf
bun scripts/compress-corpus.ts --input .data/ukipo_mopp/mopp.db --output .data/ukipo_mopp/mopp.db.zst
bun run verify:ukipo-mopp --file .data/ukipo_mopp/mopp.db.zst
```

The preparation script's "MPEP" error wording is cosmetic for this corpus.

| Rows | Prepared bytes | Zstandard bytes | Decoded SHA-256 | File SHA-256 |
| --- | --- | --- | --- | --- |
| 192 | 5,525,504 | 2,560,203 | `4bd204a2873034ecfc4078513dc81bdebf9c75c54330e46a1587486e9af4ddac` | `d48e10116b928c76677137799da7dd9eadbd80a3643e5c82c2f21af61c3ea785` |

On October 22, 2026 the verifier configured the packaged file and both pins,
then checked the library against values Python's `MoppClient`
(patent-client-agents 0.30.0, the deployed version) returned for the same
snapshot: the href, decoded HTML hash and text length of sections 1, 4A, 14 and
the glossary, and the top five hits for "inventive step", "methods of
treatment", "industrial application" and "sufficiency". All match. It then
resolved the references Python misses (below) and exercised the default full
and curated MCP servers (`search_mopp`, a four-reference `get_mopp_section`
with one missing reference, an HTML artifact whose bytes match Python's hash,
and the facade's `search_legal_reference` and `get_legal_reference` for
`ukipo_mopp`). The live facade script's two `ukipo_mopp` probes also passed.
The artifacts stay under ignored `.data/` and were not deployed.

## Python bugs fixed here

Each was reproduced against the deployed snapshot with Python's `MoppClient`.

- The MCP summary and single-section `source_url` strip the leading dash from
  section 4A's slug. gov.uk serves the page only at
  `/guidance/manual-of-patent-practice-mopp/-section-4a-methods-of-treatment-or-diagnosis`;
  the dashless URL returns 404. TypeScript links the stored slug, as Python's
  own `result_url` already does.
- Lettered section numbers are matched case-sensitively against the stored
  upper-case value, so `4a` and `102a` are not found. TypeScript upper-cases
  the number.
- The builder's slug pattern needs `section-`, so the page
  `sections-11-effect-of-transfer-of-application-under-s-8-or-10` was stored
  without a section number and `11` is not found. TypeScript reads the number
  from the slug when none is stored, for lookups and hits.
- The tool description and usage notes offer paragraph citations (`1.07`), but
  each row is a whole section page, so they are never found. TypeScript returns
  the section's page.
- A gov.uk URL with a fragment or query (`...#ref14-01`) is not normalized and
  is not found.
- `get_usage_resource()` reads `patent_client_agents.mopp.docs`, a package that
  does not exist, and raises `ModuleNotFoundError`. The usage resource is not
  ported; `mopp://corpus/status` describes the installed snapshot instead.

## Other Python differences

- Python's search hits carry no snippet, and its lean stub copies the title into
  `snippet`. TypeScript hits carry the FTS5 snippet with `<mark>` highlights.
- Python's section result has no `section_number`; TypeScript returns it.
- The text cap, HTML artifacts, `cursor`, `format`, the version refusal and the
  `ukipo:read` scope are described above.

## Tests

The [fixture](../tests/fixtures/ukipo-mopp/README.md) holds six real rows
copied from the deployed snapshot, including dictionary-compressed HTML, the
dash-prefixed 4A slug and the unnumbered `sections-11-...` page.
[Library tests](../tests/ukipo-mopp-client.test.ts) cover status, search syntax
and operator quoting, paging and outline order, every reference form above,
not-found and version errors, the section-size limit, Zstandard bytes, pins,
WAL rejection and the environment variables. [MCP tests](../tests/ukipo-mopp-mcp.test.ts)
cover both tools, cursors, `not_found`, text and HTML artifacts, the status
resource, the curated facade routing and the `ukipo:read` scope on the
authenticated HTTP listener. The Node smoke run reads the fixture as bytes.
All run offline.
