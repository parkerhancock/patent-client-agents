# USPTO Assignments

Patent assignment and ownership data via the USPTO Assignment Center.

## Client

```python
from patent_client_agents.uspto_assignments import AssignmentCenterClient
```

No API key required.

## Methods

All search methods return `list[AssignmentRecord]`.

### search_by_patent(patent_number, *, limit=100)

```python
async with AssignmentCenterClient() as client:
    records = await client.search_by_patent("10123456")
```

### search_by_application(application_number, *, limit=100)

```python
records = await client.search_by_application("16123456")
```

### search_by_assignee(assignee_name, *, start_row=1, limit=100)

```python
records = await client.search_by_assignee("Google LLC")
```

### search_by_assignor(assignor_name, *, start_row=1, limit=100)

```python
records = await client.search_by_assignor("Jane Doe")
```

### search_by_reel_frame(reel_frame, *, limit=100)

```python
records = await client.search_by_reel_frame("12345/0678")
```

### search_all(criteria, *, start_row=1, limit=1000) and search(...)

Advanced paginated / multi-criteria searches. See docstrings on
`AssignmentCenterClient` for the filter schema.

## AssignmentRecord Fields

Each record exposes:

| Field | Type | Description |
|-------|------|-------------|
| `reel_frame` | str | Reel/frame number |
| `conveyance_text` | str | Type of conveyance |
| `recorded_date` | date | USPTO recording date |
| `execution_date` | date \| None | Execution date |
| `assignors` | list[`Assignor`] | Previous owners |
| `assignees` | list[`Assignor`] | New owners (shared model) |
| `properties` | list[`Property`] | Patents/applications affected |

`Property` exposes `patent_number`, `application_number`, `filing_date`,
`publication_number`, `invention_title`, etc.

## Conveyance Types

Common values in `conveyance_text`:

- `ASSIGNMENT OF ASSIGNORS INTEREST` — standard assignment
- `SECURITY AGREEMENT` / `RELEASE BY SECURED PARTY` — security interests
- `MERGER` / `CHANGE OF NAME` — corporate changes
- `LICENSE` — license grants
