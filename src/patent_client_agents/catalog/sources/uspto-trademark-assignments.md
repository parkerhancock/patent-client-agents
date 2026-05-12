# USPTO Trademark Assignments

Trademark ownership-transfer records from the USPTO Assignment Center. Supports searches by assignee, assignor, serial number, registration number, and reel/frame. Returns `TrademarkAssignmentRecord` objects carrying assignors, assignees, conveyance metadata, and the list of affected `TrademarkProperty` rows for each recordation.

## Source

| | |
|---|---|
| Module | `patent_client_agents.uspto_trademark_assignments` |
| Client | `TrademarkAssignmentClient` |
| Base URL | `https://assignmentcenter.uspto.gov` |
| Auth | None |
| Rate limits | Not published |
| Status | Active |

## Library API

```python
from patent_client_agents.uspto_trademark_assignments import TrademarkAssignmentClient

async with TrademarkAssignmentClient() as client:
    records = await client.search_by_assignee("Apple Inc", limit=100)
    for r in records:
        print(f"{r.reel_frame}: {r.assignors} -> {r.assignees}")

    history = await client.search_by_serial("97123456")
```

### Methods

| Method | Description |
|---|---|
| `search(criteria, start_row=1, limit=100)` | General search; accepts a list of `{property, searchBy}` dicts |
| `search_by_assignee(name, start_row, limit)` | Company/person acquiring rights |
| `search_by_assignor(name, start_row, limit)` | Company/person transferring rights |
| `search_by_serial(serial_number, start_row, limit)` | Chain of title for a serial |
| `search_by_registration(registration_number, start_row, limit)` | Chain of title for a registration |
| `search_by_reel_frame(reel_frame, start_row, limit)` | Direct recordation lookup (e.g. `9006/0093`) |
| `search_all(by, query)` | Paginated full-result iterator across all rows |

Pagination: pass `start_row` and `limit` (max 1000 per request) for manual pagination. `search_all` follows the next-row cursor automatically.

## Result shape

```python
class TrademarkAssignmentRecord(BaseModel):
    reel_number: int
    frame_number: str
    reel_frame: str                       # computed property "<reel>/<frame>"
    assignor_execution_date: str | None
    correspondent_name: str | None
    domestic_representative: str | None
    assignors: list[Assignor]
    assignees: list[str]
    number_of_properties: int
    properties: list[TrademarkProperty]   # serial/registration, mark, dates
```

## MCP Tools

| Tool | Description |
|---|---|
| `search_trademark_assignments` | Search by `assignee`, `assignor`, `serial_number`, `registration_number`, or `reel_frame` (axis chosen via the `by` parameter) |
