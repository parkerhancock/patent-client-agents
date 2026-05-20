# MPEP (Manual of Patent Examining Procedure)

Full-text search and section retrieval for the MPEP, the primary
reference for patent examination procedure at the USPTO.

## Source

| | |
|---|---|
| Module | `patent_client_agents.mpep` |
| Client | `MpepClient` |
| Base URL | `https://mpep.uspto.gov` (build-time snapshot source; no runtime HTTP) |
| Backend | Local SQLite/FTS5 corpus (no runtime HTTP) |
| Snapshot source | Scraped from `https://mpep.uspto.gov/RDMS/MPEP/content` |
| Auth | None |
| Rate limits | None at runtime; corpus builder uses ordinary USPTO website requests |
| Status | Active |

## Backend: local SQLite/FTS5 corpus

The runtime does not call USPTO. `MpepClient` reads from a SQLite
database produced by the `patent-client-agents-build-mpep-corpus`
console script. The wheel ships the builder; the corpus is materialized
separately, either into `~/.cache/patent_client_agents/mpep.db` (default)
or any path pointed to by the `MPEP_CORPUS_PATH` env var.

```bash
patent-client-agents-build-mpep-corpus \
    --output ~/.cache/patent_client_agents/mpep.db
```

A fresh build is ~4 minutes and produces ~3,000 sections across all 29
MPEP chapters in ~50MB. USPTO's eMPEP `/search` endpoint has been
intermittently broken since 2026-05-13, which is the immediate
motivation for the corpus design; the longer-term motivation is that
section text and search are deterministic functions of a published
revision — there's no reason to round-trip USPTO on every read.

## Library API

```python
from patent_client_agents.mpep import MpepClient

async with MpepClient() as client:
    results = await client.search("obviousness")
    section = await client.get_section("2106")
```

| Method | Returns | Description |
|--------|---------|-------------|
| `search(query, version="current", syntax="adj", per_page=10, page=1)` | `MpepSearchResponse` | FTS5-backed full-text search |
| `get_section(section, version="current", highlight_query=...)` | `MpepSection` | Get section by number (e.g. "2106", "2106.04(a)") or href |
| `resolve_section_href(section_number, version="current")` | `str \| None` | Resolve a section number to its internal href |
| `list_versions()` | `list[MpepVersion]` | Single-entry list reflecting the loaded snapshot |

Section numbers are resolved via the corpus' `section_number` index.
Accepts formats like "2106", "2106.04", "2106.04(a)", "706.03(a)(1)".

If the corpus is missing, the first call raises `CorpusUnavailable`
(from `patent_client_agents.mpep.corpus`) with the build command in the
message — there is no silent fallback to live HTTP.

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_mpep` | Search the MPEP by keyword |
| `get_mpep_section` | Get a specific MPEP section by number or href |
