# TMEP (Trademark Manual of Examining Procedure)

Full-text search and section retrieval for the TMEP, the primary
reference for trademark examination procedure at the USPTO. Same
SQLite/FTS5 corpus pattern as the MPEP module.

## Source

| | |
|---|---|
| Module | `patent_client_agents.tmep` |
| Client | `TmepClient` |
| Base URL | `https://tmep.uspto.gov` (build-time snapshot source; no runtime HTTP) |
| Backend | Local SQLite/FTS5 corpus (no runtime HTTP) |
| Snapshot source | Scraped from `https://tmep.uspto.gov/RDMS/TMEP/content` |
| Auth | None |
| Rate limits | None at runtime; corpus builder uses ordinary USPTO website requests |
| Status | Active |

## Backend: local SQLite/FTS5 corpus

The runtime does not call USPTO. `TmepClient` reads from a SQLite
database produced by the `patent-client-agents-build-tmep-corpus`
console script. The wheel ships the builder; the corpus is materialized
separately, either into `~/.cache/patent_client_agents/tmep.db` (default)
or any path pointed to by the `TMEP_CORPUS_PATH` env var.

```bash
patent-client-agents-build-tmep-corpus \
    --output ~/.cache/patent_client_agents/tmep.db
```

A fresh build is ~2 minutes and produces ~1,750 sections across all 19
TMEP chapters in ~16MB. USPTO's eTMEP `/search` endpoint has been
intermittently broken since 2026-05-13; `/content` and `/current`
remain healthy, which is what the builder uses.

## Library API

```python
from patent_client_agents.tmep import TmepClient

async with TmepClient() as client:
    results = await client.search("likelihood of confusion")
    section = await client.get_section("1207.01(a)")
```

| Method | Returns | Description |
|---|---|---|
| `search(query, version="current", syntax="adj", per_page=10, page=1)` | `TmepSearchResponse` | FTS5-backed full-text search |
| `get_section(section, version="current", highlight_query=...)` | `TmepSection` | Get section by number (e.g. "1207", "1207.01(a)") or href |
| `resolve_section_href(section_number, version="current")` | `str \| None` | Resolve a section number to its internal href |
| `list_versions()` | `list[TmepVersion]` | Single-entry list reflecting the loaded snapshot |

Section numbers are resolved via the corpus' `section_number` index.
Accepts formats like "1207", "1207.01", "1207.01(a)".

If the corpus is missing, the first call raises `CorpusUnavailable`
(from `patent_client_agents.tmep.corpus`) with the build command in the
message — there is no silent fallback to live HTTP.

## MCP Tools

| Tool | Description |
|---|---|
| `search_tmep` | Search the TMEP by keyword |
| `get_tmep_section` | Get a specific TMEP section by number or href |
