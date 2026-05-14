# MoPP Usage

The MoPP client reads from a **local SQLite/FTS5 snapshot** of the
UKIPO Manual of Patent Practice — it does not call gov.uk at runtime.
Section retrieval and full-text search both go through the local
corpus.

## First-time setup

The wheel ships the builder, not the corpus. Build the snapshot once
into the default cache path:

```bash
patent-client-agents-build-mopp-corpus \
    --output ~/.cache/patent_client_agents/mopp.db
```

The crawl takes ~2 minutes against gov.uk (192 pages × 0.5 s polite
pause) and yields ~190 sections (PA 1977 + appendices + glossary,
~9 MB SQLite). UKIPO refreshes MoPP quarterly; re-run on the same
cadence.

For cloud deploys, build the corpus into the container image and set
`MOPP_CORPUS_PATH` in the runtime env to point at it; the file does
not have to live in `~/.cache`.

## Search

* `MoppClient.search(query, syntax="adj", sort="relevance",
  per_page=10, page=1)` runs a FTS5 MATCH query.
* `syntax="adj"` (default) and `syntax="exact"` quote the query as a
  phrase. `syntax="and"` is FTS5's space-separated default —
  matching documents that contain *all* tokens anywhere.
  `syntax="or"` joins tokens with `OR`.
* `sort="relevance"` orders by FTS5 BM25 rank; `sort="outline"` orders
  by `section_number` ascending.
* `per_page` ≤ 100; `page` is 1-based; the response sets `has_more`
  when more rows remain.

## Section retrieval

* `MoppClient.get_section(section)` accepts either a PA 1977 section
  number (`"1"`, `"14"`, `"4A"`, `"100"`, `"1.07"`) or a gov.uk slug
  (`"section-14-the-application"`,
  `"glossary-of-terms-and-abbreviations-used-in-this-manual"`,
  or the full path `/guidance/manual-of-patent-practice-mopp/...`).
* The returned `MoppSection.html` is the cleaned outerHTML of the
  page's `<main>` element with form/sidebar/feedback widgets stripped.
  `.text` is the same content with whitespace collapsed.

## Versions

`MoppClient.list_versions()` returns a single-entry list reflecting
the loaded snapshot (`label = "current (snapshot YYYY-MM-DD)"`,
`value = "current"`, `current = True`). The corpus is a point-in-time
freeze; passing a non-`"current"` version is a no-op.

## Cache-miss behavior

If neither `MOPP_CORPUS_PATH` nor `~/.cache/patent_client_agents/mopp.db`
exists, the first call raises
`patent_client_agents.ukipo_mopp.corpus.CorpusUnavailable` with the
build command in the message — no silent fallback to live HTTP.
