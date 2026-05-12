# TMEP (Trademark Manual of Examining Procedure)

Full-text search and section retrieval for the TMEP, the primary reference for trademark examination procedure at the USPTO. Backed by the same MPEP-style RDMS search/content API USPTO ships for the patent manual.

## Source

| | |
|---|---|
| Module | `patent_client_agents.tmep` |
| Client | `TmepClient` |
| Base URL | `https://tmep.uspto.gov` |
| Auth | None |
| Rate limits | Not published |
| Status | Active |

## Library API

```python
from patent_client_agents.tmep import TmepClient, SearchInput, search, get_section

# Client-style
async with TmepClient() as client:
    results = await client.search("likelihood of confusion")
    section = await client.get_section("1207.01(a)")

# Convenience functions
results = await search(SearchInput(query="2(d) refusal"))
section = await get_section("1207")
```

### Methods

| Method | Returns | Description |
|---|---|---|
| `search(query, version="current", syntax="adj", per_page=10, page=1)` | `TmepSearchResponse` | Full-text search with relevance ranking |
| `get_section(section, version="current", highlight_query=...)` | `TmepSection` | Get section by number (e.g. "1207", "1207.01(a)") or href |
| `resolve_section_href(section_number, version="current")` | `str \| None` | Resolve a section number to its internal href |
| `list_versions()` | `list[TmepVersion]` | List available TMEP versions |

Section numbers are automatically resolved to internal hrefs. Accepts formats like "1207", "1207.01", "1207.01(a)".

## MCP Tools

| Tool | Description |
|---|---|
| `search_tmep` | Search the TMEP by keyword |
| `get_tmep_section` | Get a specific TMEP section by number or href |
