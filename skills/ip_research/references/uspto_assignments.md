# USPTO Assignments

Patent assignment and ownership data via USPTO Assignment Search API.

## Client

```python
from ip_tools.uspto_assignments import UsptoAssignmentsClient
```

No API key required.

## Methods

### assignments_for_patent(patent_number) -> list[AssignmentRecord]

Get assignments by patent number.

```python
async with UsptoAssignmentsClient() as client:
    assignments = await client.assignments_for_patent("10123456")

    for a in assignments:
        a.reel_frame           # "12345/0678"
        a.conveyance_text      # "ASSIGNMENT OF ASSIGNORS INTEREST"
        a.recorded_date
        a.execution_date

        for assignor in a.assignors:
            assignor.name
            assignor.execution_date

        for assignee in a.assignees:
            assignee.name
            assignee.address
            assignee.city
            assignee.state
            assignee.country
```

### assignments_for_application(application_number) -> list[AssignmentRecord]

Get assignments by application number.

```python
assignments = await client.assignments_for_application("16123456")
```

### assignments_for_assignee(assignee_name) -> list[AssignmentRecord]

Search assignments by assignee name.

```python
assignments = await client.assignments_for_assignee("Google LLC")
```

## AssignmentRecord Fields

| Field | Type | Description |
|-------|------|-------------|
| `reel_frame` | str | Reel/frame number |
| `conveyance_text` | str | Type of conveyance |
| `recorded_date` | date | USPTO recording date |
| `execution_date` | date | Execution date |
| `assignors` | list[AssignmentParty] | Previous owners |
| `assignees` | list[AssignmentParty] | New owners |
| `patent_numbers` | list[str] | Related patents |
| `application_numbers` | list[str] | Related applications |

## Conveyance Types

Common conveyance types:
- `ASSIGNMENT OF ASSIGNORS INTEREST` - Standard assignment
- `SECURITY AGREEMENT` - Security interest
- `RELEASE BY SECURED PARTY` - Release of security
- `MERGER` - Corporate merger
- `CHANGE OF NAME` - Name change
- `LICENSE` - License grant
