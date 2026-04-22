"""USPTO Assignment Center API client.

Provides programmatic access to USPTO patent assignment records via the
Assignment Center's undocumented JSON API. Supports searching by assignee,
assignor, patent number, application number, and other criteria.

Example:
    from ip_tools.uspto_assignments import AssignmentCenterClient

    async with AssignmentCenterClient() as client:
        # Search by assignee name
        records = await client.search_by_assignee("Apple Inc", limit=100)
        for record in records:
            print(f"{record.reel_frame}: {record.assignees}")
            for prop in record.properties:
                print(f"  - {prop.patent_number or prop.application_number}")

        # Search by assignor name
        records = await client.search_by_assignor("Samsung", limit=50)

        # Get all assignments for a company (handles pagination)
        all_records = await client.search_all(assignee_name="Microsoft")
"""

from .client import AssignmentCenterClient
from .models import (
    AssignmentRecord,
    AssignmentSearchResponse,
    Assignor,
    Property,
    SearchCriterion,
)

__all__ = [
    "AssignmentCenterClient",
    "AssignmentRecord",
    "AssignmentSearchResponse",
    "Assignor",
    "Property",
    "SearchCriterion",
]
