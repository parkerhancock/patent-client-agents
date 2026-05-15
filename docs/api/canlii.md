# CanLII

Read-only access to the [CanLII REST API](https://github.com/canlii/API_documentation/blob/master/EN.md) — Canadian courts, tribunals, statutes, and regulations. The IP-relevant slice covers the Federal Court, Federal Court of Appeal, Supreme Court of Canada, Trade-marks Opposition Board (TMOB), the Commissioner of Patents — Patent Appeal Board, plus the Patent Act / Trademarks Act / Industrial Design Act / Copyright Act with point-in-time entry-into-force markers.

## Auth

Free API key by request via the [CanLII feedback form](https://www.canlii.org/en/feedback/feedback.html). Set `CANLII_API_KEY` in your environment.

## Quick Start

```python
from patent_client_agents.canlii import (
    BrowseCasesInput,
    CanLIIClient,
    GetCaseInput,
    GetLegislationInput,
    SubjectMatter,
    browse_cases,
    get_case,
    get_legislation,
)

async with CanLIIClient() as client:
    # 20 most recent TMOB decisions
    cases = await client.browse_cases(database_id="tmob-comc", result_count=20)

    # Detailed view of a single case
    dunsmuir = await client.get_case(database_id="csc-scc", case_id="2008scc9")

    # Patent Act — point-in-time consolidated
    act = await client.get_legislation(database_id="cas", legislation_id="rsc-1985-c-p-4")
```

## Functions

| Function | Description |
|---|---|
| `list_case_databases()` | All courts / tribunals |
| `browse_cases(database_id, ...)` | Paginated list with date filters |
| `get_case(database_id, case_id)` | Full case metadata |
| `get_cited_cases(database_id, case_id)` | Citator: cases this one cites |
| `get_citing_cases(database_id, case_id)` | Citator: cases that cite this one |
| `get_cited_legislations(database_id, case_id)` | Citator: legislation cited |
| `list_legislation_databases()` | Statute / regulation databases |
| `browse_legislation(database_id)` | List statutes within a database |
| `get_legislation(database_id, legislation_id)` | Metadata with start / end dates |

## Common Databases

| `database_id` | Coverage |
|---|---|
| `csc-scc` | Supreme Court of Canada |
| `fca` | Federal Court of Appeal |
| `fct` | Federal Court (patent / TM infringement) |
| `tmob-comc` | Trade-marks Opposition Board |
| `cab-cab` | Commissioner of Patents — Patent Appeal Board |
| `cas` | Federal statutes (Patent Act lives here as `rsc-1985-c-p-4`) |
| `car` | Federal regulations |

## Limits and ToS

- HTTPS only
- `result_count` capped at 10,000
- 10 MB response cap (surfaces as `ApiError(413)`)
- High-volume scraping discouraged; keys revocable
- Citator endpoints are English-only

## MCP Tool Surface

MCP tools register only when `CANLII_API_KEY` is set in the server's environment (matches the JPO env-gating pattern — tools are absent from `tool/list` on deployments that don't carry the key). Nine tools mirror the library functions:
`list_canlii_case_databases`, `search_canlii_cases`, `get_canlii_case`, `get_canlii_cited_cases`, `get_canlii_citing_cases`, `get_canlii_cited_legislations`, `list_canlii_legislation_databases`, `search_canlii_legislation`, `get_canlii_legislation`.
