# USPTO Patent Assignments

Patent ownership transfer records from the USPTO Assignment Center. Covers assignments, security interests, licenses, and other recorded conveyances.

## Source

| | |
|---|---|
| Module | `ip_tools.uspto_assignments` |
| Client | `AssignmentCenterClient` |
| Base URL | `https://assignmentcenter.uspto.gov` |
| Auth | None |
| Rate limits | Not published |
| Status | Active |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ipas/search/api/v2/public/patent/exportPublicPatentData` | Search patent assignment records |

## Library API

```python
from ip_tools.uspto_assignments import AssignmentCenterClient

async with AssignmentCenterClient() as client:
    records = await client.search_by_assignee("Apple Inc")
    records = await client.search_by_patent("10000000")
```

| Method | Returns | Description |
|--------|---------|-------------|
| `search_by_assignee(assignee_name, start_row=1, limit=100)` | `list[AssignmentRecord]` | Search by assignee (receiving party) |
| `search_by_assignor(assignor_name, start_row=1, limit=100)` | `list[AssignmentRecord]` | Search by assignor (transferring party) |
| `search_by_patent(patent_number, limit=100)` | `list[AssignmentRecord]` | Search by patent number |
| `search_by_application(application_number, limit=100)` | `list[AssignmentRecord]` | Search by application number |
| `search_by_reel_frame(reel_frame)` | `list[AssignmentRecord]` | Search by reel/frame (e.g. "52614/446") |
| `search(assignee_name=, assignor_name=, patent_number=, ...)` | `list[AssignmentRecord]` | Multi-criteria search |
| `search_all(assignee_name=, assignor_name=, batch_size=1000, max_results=)` | `list[AssignmentRecord]` | Auto-paginated search |

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_patent_assignments_by_assignee` | Search by assignee name |
| `search_patent_assignments_by_assignor` | Search by assignor name |
| `search_patent_assignments_by_patent` | Get assignment chain of title for a patent |
| `search_patent_assignments_by_application` | Get assignments by application number |
| `search_patent_assignments_by_reel_frame` | Search by recording reel/frame |
| `search_all_patent_assignments` | Paginated search through all matching assignments |
| `search_patent_assignments` | General assignment search by assignee name |
