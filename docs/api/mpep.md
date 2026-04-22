# MPEP

Access the Manual of Patent Examining Procedure (MPEP) for searching and retrieving patent examination guidance.

## Quick Start

```python
from ip_tools.mpep import MpepClient

async with MpepClient() as client:
    # Search MPEP
    results = await client.search("obviousness")

    # Get specific section
    section = await client.get_section("2141")

    # List available versions
    versions = await client.list_versions()
```

## Functions

| Function | Description |
|----------|-------------|
| `search()` | Search MPEP content |
| `get_section()` | Get a specific MPEP section |
| `list_versions()` | List available MPEP versions |

## Common Sections

| Section | Topic |
|---------|-------|
| 2100 | Patentability |
| 2106 | Patent Subject Matter Eligibility |
| 2111 | Claim Interpretation |
| 2141 | Obviousness |
| 2163 | Written Description |
| 2164 | Enablement |
| 2173 | Definiteness |

## Usage Pattern

```python
from ip_tools.mpep import (
    MpepClient,
    search,
    get_section,
)

# Context manager (recommended)
async with MpepClient() as client:
    results = await client.search("Alice test")

# One-shot convenience functions
results = await search(query="obviousness prima facie")
section = await get_section(section_id="2141.02")
```
