# Patent Assignments

Single unified search over the USPTO Assignment Center.

## Why one tool

The Assignment Center exposes a single search endpoint that handles every
indexed axis (assignee, assignor, correspondent, application, patent,
publication, reel/frame, PCT, international registration). The response
shape is identical across axes. The tool surface mirrors that — one
method, one MCP tool, one response model.

## MCP tool

```
search_patent_assignments(
    query: str,
    by: Literal["assignee", "assignor", "correspondent",
                "application_number", "patent_number", "publication_number",
                "reel_frame", "international_registration_number", "pct_number"],
    exact: bool = False,
    executed_after: str | None = None,   # YYYY-MM-DD
    executed_before: str | None = None,  # YYYY-MM-DD
    conveyance: str | None = None,       # contains-match
    offset: int = 0,
    limit: int | None = None,
) -> dict
```

Returns `{records, total, truncated, [warning]}`. Each record carries
reel/frame, conveyance type, conveyance code, assignors (with execution
dates), assignees, correspondent, and affected properties (applications
and patents).

When USPTO's ~10,000-record cap is hit, `truncated` is `True` and a
human-readable `warning` is included so agents can prompt for narrower
queries.

## Python API

```python
from datetime import date
from patent_client_agents.uspto_assignments import AssignmentCenterClient

async with AssignmentCenterClient() as client:
    result = await client.search(
        query="Anthropic PBC",
        by="assignee",
        executed_between=(date(2024, 1, 1), date(2024, 12, 31)),
        limit=100,
    )
    for record in result:
        ...
    if result.truncated:
        ...
```

The library and MCP tool have the same shape; the wrapper just translates
date strings and surfaces the truncation warning.

## Related

- `get_patent_assignment(application_number)` — **different source**. Uses
  USPTO ODP (embedded assignment data on the application record), not
  Assignment Center (raw recordation records). Both answer "who owns this
  patent?" but return different shapes; they are deliberately kept
  separate.
