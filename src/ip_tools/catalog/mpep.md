# MPEP (Manual of Patent Examining Procedure)

Full-text search and section retrieval for the MPEP, the primary reference for patent examination procedure at the USPTO.

## Source

| | |
|---|---|
| Module | `ip_tools.mpep` |
| Client | `MpepClient` |
| Base URL | `https://mpep.uspto.gov` |
| Auth | None |
| Rate limits | Not published |
| Status | Active |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/RDMS/MPEP/search` | Full-text search with relevance ranking |
| GET | `/RDMS/MPEP/content` | Get section content by href |
| GET | `/RDMS/MPEP/result` | Get section with search term highlighting |
| GET | `/RDMS/MPEP/current` | List available MPEP versions |

## Library API

```python
from ip_tools.mpep import MpepClient

async with MpepClient() as client:
    results = await client.search("obviousness")
    section = await client.get_section("2106")
```

| Method | Returns | Description |
|--------|---------|-------------|
| `search(query, version="current", syntax="adj", per_page=10, page=1)` | `MpepSearchResponse` | Full-text search with relevance ranking |
| `get_section(section, version="current", highlight_query=)` | `MpepSection` | Get section by number (e.g. "2106", "2106.04(a)") or href |
| `resolve_section_href(section_number, version="current")` | `str \| None` | Resolve a section number to its internal href |
| `list_versions()` | `list[MpepVersion]` | List available MPEP versions |

Section numbers are automatically resolved to internal hrefs. Accepts formats like "2106", "2106.04", "2106.04(a)".

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_mpep` | Search the MPEP by keyword |
| `get_mpep_section` | Get a specific MPEP section by number or href |
