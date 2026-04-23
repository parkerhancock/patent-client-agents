# Google Patents

Search and retrieve patent documents from Google Patents.

## Quick Start

```python
from patent_client_agents.google_patents import GooglePatentsClient

async with GooglePatentsClient() as client:
    # Search for patents
    results = await client.search("machine learning drug discovery", limit=20)

    # Get full patent details
    patent = await client.get_patent("US10000000B2")
    print(patent.title)
    print(patent.abstract)
```

## Client Methods

| Method | Description |
|--------|-------------|
| `search()` | Search for patents by keyword |
| `get_patent()` | Get full patent details by publication number |
| `get_claims()` | Get just the claims section |
| `get_figures()` | Get figure images and descriptions |

## Convenience Functions

| Function | Description |
|----------|-------------|
| `search()` | Search patents (one-shot) |
| `fetch()` | Fetch patent details (one-shot) |
| `fetch_figures()` | Fetch figures (one-shot) |
| `fetch_pdf()` | Download patent as PDF |

## Models

| Model | Description |
|-------|-------------|
| `PatentData` | Full patent document with all fields |
| `GooglePatentsSearchResponse` | Search results container |
| `GooglePatentsSearchResult` | Individual search result |
| `FigureEntry` | Figure with image data |

## Usage Pattern

```python
from patent_client_agents.google_patents import (
    GooglePatentsClient,
    search,
    fetch,
)

# Context manager (recommended for multiple requests)
async with GooglePatentsClient() as client:
    results = await client.search("AI robotics", limit=10)
    patent = await client.get_patent("US10000000B2")

# One-shot convenience functions
results = await search(query="machine learning", limit=10)
patent = await fetch(patent_number="US10000000B2")
```

## Caching

Enable HTTP caching for repeated requests:

```python
async with GooglePatentsClient(use_cache=True) as client:
    # First request hits the network
    patent1 = await client.get_patent("US10000000B2")

    # Second request uses cache
    patent2 = await client.get_patent("US10000000B2")
```
