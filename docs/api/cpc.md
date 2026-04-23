# CPC Classification

Access the Cooperative Patent Classification (CPC) system for looking up and searching patent classifications.

## Quick Start

```python
from patent_client_agents.cpc import retrieve_cpc, search_cpc

# Look up a classification
cpc = await retrieve_cpc(symbol="G06N3/08")

# Search classifications
results = await search_cpc(query="machine learning")
```

## Functions

| Function | Description |
|----------|-------------|
| `retrieve_cpc()` | Look up a CPC classification by symbol |
| `search_cpc()` | Search classifications by keyword |
| `map_classification()` | Map between classification systems |
| `fetch_media()` | Get media/images for a classification |
| `fetch_biblio_cpci()` | Get bibliographic CPC info |

## CPC Hierarchy

The CPC system is hierarchical:

- **Section** (e.g., G = Physics)
- **Class** (e.g., G06 = Computing)
- **Subclass** (e.g., G06N = Computer systems based on specific computational models)
- **Group** (e.g., G06N3 = Computer systems based on biological models)
- **Subgroup** (e.g., G06N3/08 = Learning methods)

## Usage Pattern

```python
from patent_client_agents.cpc import retrieve_cpc, search_cpc

# Get classification details
cpc = await retrieve_cpc(symbol="H01L21/00")
print(cpc.title)
print(cpc.definition)

# Search for related classifications
results = await search_cpc(query="semiconductor manufacturing")
for result in results.classifications:
    print(f"{result.symbol}: {result.title}")
```
