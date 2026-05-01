# USPTO Assignments

Access patent ownership transfer history via the USPTO Assignment Center.
No API key required.

## Quick Start

```python
from patent_client_agents.uspto_assignments import AssignmentCenterClient

async with AssignmentCenterClient() as client:
    # By assignee company
    records = await client.search_by_assignee("[Company Name]")
    for r in records:
        print(f"{r.reel_frame}: {r.assignor_name} -> {r.assignee_name}")

    # By specific patent
    history = await client.search_by_patent("10123456")

    # By application number
    app_records = await client.search_by_application("16123456")
```

## Configuration

No credentials required. Rate limit is unpublished — the client's
hishel cache + `default_retryer` handle transient throttling.

## Client

`AssignmentCenterClient` inherits from `law_tools_core.BaseAsyncClient`.

## Functions

| Function | Description |
|---|---|
| `search(**kwargs)` | General search by any field |
| `search_by_assignee(name)` | Company/person acquiring rights |
| `search_by_assignor(name)` | Company/person transferring rights |
| `search_by_patent(patent_number)` | Chain of title for a patent |
| `search_by_application(application_number)` | Chain of title for an app |
| `search_by_reel_frame(reel_frame)` | Direct record lookup (e.g. `52614/446`) |
| `search_all(**kwargs)` | Paginated full-result iterator |

## Result shape

```python
class AssignmentRecord(BaseModel):
    reel_frame: str
    recording_date: date | None
    conveyance_type: str
    assignor_name: str
    assignee_name: str
    assignee_address: str | None
    properties: list[AssignmentProperty]  # patents/applications transferred
```

## Usage patterns

```python
from patent_client_agents.uspto_assignments import AssignmentCenterClient

async with AssignmentCenterClient() as client:
    # Paginate for large result sets
    all_records = await client.search_all(assignee_name="[Company Name]")
    print(f"found {len(all_records)} assignments")
```

## Error handling

Inherits typed exceptions from `law_tools_core`:
`NotFoundError`, `ApiError`. No auth errors (public endpoint).
