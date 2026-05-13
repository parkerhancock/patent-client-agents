# TMEP Usage

The TMEP client reads from a **local SQLite/FTS5 snapshot** of the TMEP
— it does not call USPTO at runtime. USPTO's eTMEP `/search` endpoint
has been intermittently broken since 2026-05-13 and is not part of the
library's request path. Section retrieval and full-text search both go
through the local corpus.

## First-time setup

The wheel ships the builder, not the corpus. Build the snapshot once
into the default cache path:

```bash
patent-client-agents-build-tmep-corpus \
    --output ~/.cache/patent_client_agents/tmep.db
```

The crawl takes ~2 minutes against live USPTO and yields ~1,750
sections across all 19 TMEP chapters (~16MB SQLite). Re-run
periodically to pick up USPTO revisions.

For cloud deploys, build the corpus into the container image and set
`TMEP_CORPUS_PATH` in the runtime env to point at it; the file does not
have to live in `~/.cache`.

## Search

* `TmepClient.search(query, syntax="adj", sort="relevance",
  per_page=10, page=1)` runs a FTS5 MATCH query.
* `syntax="adj"` (default) and `syntax="exact"` quote the query as a
  phrase. `syntax="and"` is FTS5's space-separated default. `syntax="or"`
  joins tokens with `OR`.
* `sort="relevance"` orders by FTS5 BM25 rank; `sort="outline"` orders
  by `section_number` ascending.
* `per_page` ≤ 100; `page` is 1-based; the response sets `has_more`
  when more rows remain.
* `include_index`, `include_notes`, and `snippet` are accepted for API
  parity but no longer affect the query — all body text is indexed
  together in the corpus.

## Section retrieval

* `TmepClient.get_section(section)` accepts either a section number
  (`"1207"`, `"1207.01(a)"`, `"904.03(i)"`) or an internal href
  (`"TMEP-1200d1e8145.html"`, `"ch1200_d24d81_22612_ee.html"`). Section
  numbers are resolved via the `section_number` index.
* The returned `TmepSection.html` is the cleaned outerHTML of the
  smallest section-id-bearing block that contains the heading. `.text`
  is the same content with whitespace collapsed.
* `highlight_query` is accepted for API parity but no longer fetches a
  separate highlighted view — search results already carry FTS5
  `<mark>`-wrapped snippets.

## Versions

`TmepClient.list_versions()` returns a single-entry list reflecting the
loaded snapshot (`label = "current (snapshot YYYY-MM-DD)"`,
`value = "current"`, `current = True`). The corpus is a point-in-time
freeze; passing a non-`"current"` version is a no-op.

## Cache-miss behavior

If neither `TMEP_CORPUS_PATH` nor `~/.cache/patent_client_agents/tmep.db`
exists, the first call raises
`patent_client_agents.tmep.corpus.CorpusUnavailable` with the build
command in the message — no silent fallback to live HTTP.
