# CanLII

Read-only access to the [CanLII REST API](https://github.com/canlii/API_documentation/blob/master/EN.md), covering Canadian courts, tribunals, statutes, and regulations.

## IP-relevant databases

Court / tribunal databases (scope: Canadian IP layer):

| `database_id` | Coverage | Scope |
|---|---|---|
| `tmob-comc` | Trade-marks Opposition Board / Commission des oppositions des marques de commerce | Pure-IP tribunal |
| `cab-cab` | Commissioner of Patents — Patent Appeal Board decisions | Pure-IP tribunal |
| `fct` | Federal Court | General — IP-filtered |
| `fca` | Federal Court of Appeal | General — IP-filtered |
| `csc-scc` | Supreme Court of Canada | General — IP-filtered |
| `cas` | Federal statutes (consolidated) | Statutes |
| `car` | Federal regulations | Regulations |

The MCP tool `search_canlii_ip_cases` rolls all five court / tribunal
databases up in one call, applying an IP-rights keyword filter
(`patent` / `trademark` / `copyright` / `design`, EN + FR) to the
general-court rows.

## Canadian IP statutes

All four canonical Canadian IP Acts live in the federal-statutes
database (`cas`):

| Right | `legislation_id` | Statute |
|---|---|---|
| Patent | `rsc-1985-c-p-4` | Patent Act, R.S.C. 1985, c. P-4 |
| Trademark | `rsc-1985-c-t-13` | Trademarks Act, R.S.C. 1985, c. T-13 |
| Industrial Design | `rsc-1985-c-i-9` | Industrial Design Act, R.S.C. 1985, c. I-9 |
| Copyright | `rsc-1985-c-c-42` | Copyright Act, R.S.C. 1985, c. C-42 |

`list_canlii_ip_statutes` returns this catalog directly; pass any
`legislation_id` to `get_canlii_legislation` for point-in-time
metadata.

## Authentication

Free API key via the [CanLII feedback form](https://www.canlii.org/en/feedback/feedback.html).
Set `CANLII_API_KEY` in the environment.

## Limits

- HTTPS only
- Max `result_count` = 10,000 per browse
- 10 MB response cap (surfaces as `TOO_LONG` envelope → `ApiError(413)`)

## Quick example

```python
from patent_client_agents.canlii import (
    BrowseCasesInput,
    browse_cases,
    get_case,
    GetCaseInput,
)

# Last 20 TMOB decisions
cases = await browse_cases(BrowseCasesInput(database_id="tmob-comc", result_count=20))

# Detailed view of a Federal Court IP case
case = await get_case(
    GetCaseInput(database_id="fct", case_id="2024fc12345")
)
```

## Cross-jurisdiction notes

CanLII surfaces both English and French content via the `language` parameter
(except the citator, which is English-only). Point-in-time legislation
queries use `start_date` / `end_date` on the legislation metadata, which
reflect the entry-into-force and repeal dates respectively.
