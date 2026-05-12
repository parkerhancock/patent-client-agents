# USPTO Trademark Assignments

Access trademark ownership-transfer history via the USPTO Assignment
Center. No API key required.

## Quick Start

```python
from patent_client_agents.uspto_trademark_assignments import TrademarkAssignmentClient

async with TrademarkAssignmentClient() as client:
    # By assignee company
    records = await client.search_by_assignee("Apple Inc")
    for r in records:
        print(f"{r.reel_frame}: {r.assignors} -> {r.assignees}")

    # By assignor (party transferring rights)
    records = await client.search_by_assignor("Samsung", limit=50)

    # By specific serial number
    history = await client.search_by_serial("97123456")

    # By registration number
    history = await client.search_by_registration("5123456")

    # Direct recordation lookup
    record = await client.search_by_reel_frame("9006/0093")
```

## Configuration

No credentials required. Rate limit is unpublished — the client's
hishel cache + `default_retryer` handle transient throttling.

## Client

`TrademarkAssignmentClient` inherits from `law_tools_core.BaseAsyncClient`.

## Functions

| Function | Description |
|---|---|
| `search(criteria, start_row=1, limit=100)` | General search; takes `[{property, searchBy}, ...]` criterion list |
| `search_by_assignee(name)` | Company/person acquiring rights |
| `search_by_assignor(name)` | Company/person transferring rights |
| `search_by_serial(serial_number)` | Chain of title for a serial |
| `search_by_registration(registration_number)` | Chain of title for a registration |
| `search_by_reel_frame(reel_frame)` | Direct recordation lookup (e.g. `9006/0093`) |
| `search_all(by, query)` | Paginated full-result iterator |

## Result shape

```python
class TrademarkAssignmentRecord(BaseModel):
    reel_number: int
    frame_number: str
    reel_frame: str                       # computed "<reel>/<frame>"
    assignor_execution_date: str | None
    correspondent_name: str | None
    domestic_representative: str | None
    assignors: list[Assignor]             # name + execution_date
    assignees: list[str]
    number_of_properties: int
    properties: list[TrademarkProperty]   # serial/registration, mark, dates
```

## Usage patterns

```python
from patent_client_agents.uspto_trademark_assignments import TrademarkAssignmentClient

async with TrademarkAssignmentClient() as client:
    # Paginate for large result sets
    all_records = await client.search_all(by="assignee", query="Apple Inc")
    print(f"found {len(all_records)} assignments")
```

## Error handling

Inherits typed exceptions from `law_tools_core`:
`NotFoundError`, `ApiError`. No auth errors (public endpoint).
