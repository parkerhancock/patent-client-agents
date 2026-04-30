# USPTO Patent Assignments

Patent ownership transfer records from the USPTO Assignment Center. Covers assignments, security interests, licenses, and other recorded conveyances.

## Source

| | |
|---|---|
| Module | `patent_client_agents.uspto_assignments` |
| Client | `AssignmentCenterClient` |
| Base URL | `https://assignmentcenter.uspto.gov` |
| Auth | None |
| Rate limits | Not published |
| Status | Active |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ipas/search/api/v2/public/search/patent` | Reverse-engineered from the Assignment Center web UI. Accepts a `searchCriteria` array body and returns flat recordations with conveyance populated for every search axis. |

## Library API

```python
from datetime import date
from patent_client_agents.uspto_assignments import AssignmentCenterClient

async with AssignmentCenterClient() as client:
    result = await client.search(query="Apple Inc", by="assignee")
    for record in result:
        print(record.reel_frame, record.conveyance, record.assignees)
    if result.truncated:
        print(f"Capped at {len(result)} of {result.total}+ — narrow query")

    # Date-filtered, paginated, conveyance-narrowed
    result = await client.search(
        query="Google",
        by="assignee",
        executed_between=(date(2024, 1, 1), date(2024, 12, 31)),
        conveyance="SECURITY",
        offset=0,
        limit=100,
    )
```

### `search(*, query, by, exact=False, executed_between=None, conveyance=None, offset=0, limit=None) -> SearchResults`

| Param | Type | Description |
|---|---|---|
| `query` | `str` | Value to search for |
| `by` | `Literal[...]` | Search axis: `assignee`, `assignor`, `correspondent`, `application_number`, `patent_number`, `publication_number`, `reel_frame`, `international_registration_number`, `pct_number` |
| `exact` | `bool` | Exact-match (`True`) vs contains (`False`, default). Ignored for number axes |
| `executed_between` | `tuple[date, date] \| None` | Narrow by assignor execution-date range. Only date filter USPTO honors |
| `conveyance` | `str \| None` | Contains-match against conveyance text (e.g. `"SECURITY"`) |
| `offset` | `int` | Records to skip from the start |
| `limit` | `int \| None` | Max records to return (None fetches all matching) |

`SearchResults` is list-like (`for r in result`, `len(result)`, `result[0]`) with three additional attributes:

| Attr | Description |
|---|---|
| `records` | `list[AssignmentRecord]` |
| `total` | USPTO's stated total before slicing |
| `truncated` | `True` iff USPTO's ~10k cap was hit; more data exists |

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_patent_assignments(query, by, exact?, executed_after?, executed_before?, conveyance?, offset?, limit?)` | Unified patent-assignment search across every axis. Returns `{records, total, truncated, [warning]}`; `warning` is set when USPTO caps the result set. |
