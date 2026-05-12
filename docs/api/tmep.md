# TMEP

Access the Trademark Manual of Examining Procedure (TMEP) for searching
and retrieving trademark examination guidance.

## Quick Start

```python
from patent_client_agents.tmep import TmepClient

async with TmepClient() as client:
    # Search the TMEP
    results = await client.search("likelihood of confusion")

    # Get a specific section
    section = await client.get_section("1207.01(a)")

    # List available versions
    versions = await client.list_versions()
```

## Functions

| Function | Description |
|---|---|
| `search()` | Full-text search across the TMEP |
| `get_section()` | Get a specific TMEP section by number or href |
| `list_versions()` | List available TMEP editions |

## Common Sections

| Section | Topic |
|---|---|
| 1202 | Use of subject matter as a trademark |
| 1207 | Refusal on the basis of likelihood of confusion (§ 2(d)) |
| 1209 | Refusal on basis of descriptiveness |
| 1212 | Acquired distinctiveness (§ 2(f)) |
| 1213 | Disclaimers |
| 1402 | Identification and classification of goods/services |
| 1715 | Letter of protest |
| 904 | Specimens |

## Usage Pattern

```python
from patent_client_agents.tmep import (
    TmepClient,
    SearchInput,
    search,
    get_section,
)

# Context manager (recommended)
async with TmepClient() as client:
    results = await client.search("disclaimer")

# One-shot convenience functions
results = await search(SearchInput(query="2(d) refusal"))
section = await get_section("1207.01(a)")
```

## Configuration

No credentials required. Rate limit is unpublished — the client's
`hishel` cache + `default_retryer` handle transient throttling.
